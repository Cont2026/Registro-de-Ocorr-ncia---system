"""
Alerta de SLA (tempo sem resposta) — ROC / Grupo LLE
Roda 1x/dia (via GitHub Actions). Para cada chamado ABERTO ou EM ANDAMENTO,
calcula quantas HORAS ÚTEIS (ignorando fim de semana e feriados) se passaram
desde a última atividade (última mensagem do chat ou, se não houver, a abertura).

Regras:
  - Pré-aviso ao atingir 18h úteis sem resposta.
  - Alerta de atraso ao atingir 24h úteis sem resposta.
  - Cada nível é avisado só 1 vez por período de espera. Qualquer mensagem nova
    "zera" o relógio (muda a base de atividade) e libera novos avisos.
  - Avisa o SETOR responsável E a CONTABILIDADE.
Controle de duplicidade: tabela notificacoes (não precisa de tabela nova).
"""
import os
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import psycopg2
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

BRASILIA = ZoneInfo("America/Sao_Paulo")

DB_HOST = os.environ["DB_HOST"]
DB_NAME = os.environ["DB_NAME"]
DB_USER = os.environ["DB_USER"]
DB_PASSWORD = os.environ["DB_PASSWORD"]
DB_PORT = os.environ.get("DB_PORT", "5432")
SENDGRID_API_KEY = os.environ["SENDGRID_API_KEY"]
REMETENTE_EMAIL = os.environ.get("REMETENTE_EMAIL", "contabilidade@grupolle.com.br")
REMETENTE_NOME = os.environ.get("REMETENTE_NOME", "ROC - Registro de Ocorrencias Contabeis")
APP_URL = os.environ.get("APP_URL", "https://registro-de-ocorrencias-system-iaw5pyzvhkchnum6kseate.streamlit.app")

# Parâmetros do SLA (em horas úteis)
HORAS_PREAVISO = 18
HORAS_ESTOURO = 24

# Feriados nacionais 2026 (datas em que o relógio NÃO conta).
# Você pode adicionar feriados municipais/estaduais no mesmo formato (AAAA, MM, DD).
FERIADOS = {
    datetime(2026, 1, 1).date(),    # Confraternização
    datetime(2026, 2, 16).date(),   # Carnaval (segunda)
    datetime(2026, 2, 17).date(),   # Carnaval (terça)
    datetime(2026, 4, 3).date(),    # Sexta-feira Santa
    datetime(2026, 4, 21).date(),   # Tiradentes
    datetime(2026, 5, 1).date(),    # Dia do Trabalho
    datetime(2026, 6, 4).date(),    # Corpus Christi
    datetime(2026, 9, 7).date(),    # Independência
    datetime(2026, 10, 12).date(),  # Nossa Senhora Aparecida
    datetime(2026, 11, 2).date(),   # Finados
    datetime(2026, 11, 15).date(),  # Proclamação da República
    datetime(2026, 12, 25).date(),  # Natal
}

def conectar():
    return psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER,
                            password=DB_PASSWORD, port=DB_PORT, sslmode="require")

def parse_dt(valor):
    if valor is None:
        return None
    if isinstance(valor, datetime):
        d = valor
    else:
        d = None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                d = datetime.strptime(str(valor).strip(), fmt)
                break
            except:
                continue
        if d is None:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=BRASILIA)
    return d

def horas_uteis(inicio, fim, cap=48):
    """Horas decorridas entre 'inicio' e 'fim' ignorando sábados, domingos e feriados.
    Para de contar ao atingir 'cap' (não precisamos saber além disso)."""
    if inicio is None or fim <= inicio:
        return 0.0
    total = 0.0
    cur = inicio
    while cur < fim and total < cap:
        prox = min(cur + timedelta(hours=1), fim)
        if cur.weekday() < 5 and cur.date() not in FERIADOS:
            total += (prox - cur).total_seconds() / 3600.0
        cur = prox
    return total

def ultima_atividade(conn, protocolo, aberto_em):
    with conn.cursor() as cur:
        cur.execute("SELECT MAX(enviado_em) FROM mensagens WHERE chamado_protocolo=%s", (protocolo,))
        r = cur.fetchone()
    base = parse_dt(aberto_em)
    msg = parse_dt(r[0]) if r and r[0] else None
    if msg and (base is None or msg > base):
        return msg
    return base

def email_setor(conn, setor):
    with conn.cursor() as cur:
        cur.execute("""SELECT email FROM usuarios
            WHERE (setor_nome=%s OR nome=%s) AND perfil='setor' AND ativo=1
              AND email IS NOT NULL AND email <> '' LIMIT 1""", (setor, setor))
        r = cur.fetchone()
    return r[0] if r else None

def email_contabilidade(conn):
    with conn.cursor() as cur:
        cur.execute("""SELECT email FROM usuarios WHERE perfil='contabilidade' AND ativo=1
            AND email IS NOT NULL AND email <> '' ORDER BY id LIMIT 1""")
        r = cur.fetchone()
    return r[0] if r else None

def ja_enviado(conn, chave, destinatario):
    with conn.cursor() as cur:
        cur.execute("""SELECT COUNT(*) FROM notificacoes
            WHERE protocolo=%s AND destinatario=%s AND sucesso=true""", (chave, destinatario))
        return cur.fetchone()[0] > 0

def registrar(conn, chave, destinatario, assunto, sucesso):
    with conn.cursor() as cur:
        cur.execute("""INSERT INTO notificacoes (protocolo, destinatario, assunto, tipo, enviado_em, sucesso)
            VALUES (%s,%s,%s,%s,%s,%s)""",
            (chave, destinatario, assunto, "alerta_sla",
             datetime.now(BRASILIA).strftime("%Y-%m-%d %H:%M:%S"), sucesso))
    conn.commit()

def montar_email(protocolo, setor, horas, nivel):
    estourado = nivel == "estourado"
    cor = "#EF4444" if estourado else "#FAC318"
    titulo = "🛑 Chamado cancelado por falta de resposta (24h)" if estourado else "⏳ Chamado se aproximando do prazo"
    frase = (f"Este chamado está há <strong style='color:{cor};'>{int(horas)}h úteis sem resposta</strong>, "
             f"ultrapassou o prazo de {HORAS_ESTOURO}h e foi <strong style='color:{cor};'>CANCELADO automaticamente</strong>." if estourado
             else f"Este chamado está há <strong style='color:{cor};'>{int(horas)}h úteis sem resposta</strong>. "
                  f"O prazo é de {HORAS_ESTOURO}h úteis.")
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#f9f9f9;padding:20px;border-radius:12px;">
        <div style="background:#041747;padding:20px;border-radius:8px 8px 0 0;text-align:center;">
            <h1 style="color:#FAC318;font-size:24px;margin:0;letter-spacing:4px;">ROC</h1>
            <p style="color:rgba(255,255,255,0.7);font-size:12px;margin:4px 0 0;">
            Registro de Ocorrencias Contabeis — Grupo LLE</p>
        </div>
        <div style="background:white;padding:24px;border-radius:0 0 8px 8px;border:1px solid #e8e8e8;">
            <h2 style="color:{cor};font-size:18px;margin:0 0 8px;">{titulo}</h2>
            <p style="color:#333;font-size:14px;margin:0 0 16px;">{frase}</p>
            <table style="width:100%;border-collapse:collapse;">
                <tr><td style="padding:8px;background:#f5f7fa;font-weight:600;color:#041747;width:40%;">Protocolo</td><td style="padding:8px;color:#333;">{protocolo}</td></tr>
                <tr><td style="padding:8px;font-weight:600;color:#041747;">Setor responsável</td><td style="padding:8px;color:#333;">{setor}</td></tr>
                <tr><td style="padding:8px;background:#f5f7fa;font-weight:600;color:#041747;">Tempo sem resposta</td><td style="padding:8px;color:{cor};font-weight:700;">{int(horas)}h úteis</td></tr>
            </table>
            <p style="color:#555;font-size:13px;margin:16px 0;">
            Por favor, acesse o ROC e responda/atualize este chamado o quanto antes.</p>
            <div style="text-align:center;margin-top:20px;">
                <a href="{APP_URL}" style="background:#041747;color:white;padding:12px 28px;
                border-radius:8px;text-decoration:none;font-size:14px;font-weight:600;display:inline-block;">
                🔗 Acessar o ROC</a>
            </div>
        </div>
        <p style="text-align:center;font-size:11px;color:#999;margin-top:12px;">
        ROC 2026 · Grupo LLE · Mensagem automática, não responder.</p>
    </div>
    """

def enviar_email(destinatario, assunto, corpo_html):
    message = Mail(from_email=(REMETENTE_EMAIL, REMETENTE_NOME),
                   to_emails=destinatario, subject=assunto, html_content=corpo_html)
    sg = SendGridAPIClient(SENDGRID_API_KEY)
    resp = sg.send(message)
    return resp.status_code in (200, 201, 202)

def main():
    agora = datetime.now(BRASILIA)
    print(f"[ROC-SLA] Verificando chamados em {agora.strftime('%d/%m/%Y %H:%M')} (Brasília)")
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT protocolo, setor, aberto_em FROM chamados
                WHERE status IN ('Aberto','Em andamento')""")
            chamados = cur.fetchall()

        cont_email = email_contabilidade(conn)
        total = 0

        for protocolo, setor, aberto_em in chamados:
            ult = ultima_atividade(conn, protocolo, aberto_em)
            if ult is None:
                continue
            horas = horas_uteis(ult, agora)

            if horas >= HORAS_ESTOURO:
                nivel = "estourado"
            elif horas >= HORAS_PREAVISO:
                nivel = "pre"
            else:
                continue

            # base = momento da última atividade -> some quando há nova mensagem (zera o relógio)
            base = ult.strftime("%Y%m%d%H%M")
            chave = f"SLA-{protocolo}-{nivel}-{base}"
            assunto = (f"ROC — Chamado {protocolo} sem resposta há {int(horas)}h"
                       if nivel == "estourado" else
                       f"ROC — Chamado {protocolo} se aproximando do prazo")
            corpo = montar_email(protocolo, setor, horas, nivel)

            destinatarios = []
            es = email_setor(conn, setor)
            if es:
                destinatarios.append(es)
            if cont_email and cont_email not in destinatarios:
                destinatarios.append(cont_email)

            for dest in destinatarios:
                if ja_enviado(conn, chave, dest):
                    continue
                try:
                    ok = enviar_email(dest, assunto, corpo)
                except Exception as e:
                    ok = False
                    print(f"   ERRO ao enviar {protocolo} para {dest}: {e}")
                registrar(conn, chave, dest, assunto, ok)
                if ok:
                    total += 1
                    print(f"   [{nivel}] {protocolo} ({int(horas)}h) -> {dest}")

            # Ao estourar 24h úteis: status muda automaticamente para Cancelado.
            if nivel == "estourado":
                try:
                    with conn.cursor() as cur:
                        cur.execute("""UPDATE chamados SET status='Cancelado',
                            atendente=COALESCE(NULLIF(atendente,''), 'Cancelado automaticamente (SLA 24h)')
                            WHERE protocolo=%s AND status IN ('Aberto','Em andamento')""", (protocolo,))
                    conn.commit()
                    print(f"   -> {protocolo} CANCELADO automaticamente (SLA 24h)")
                except Exception as e:
                    print(f"   ERRO ao cancelar {protocolo}: {e}")

        print(f"[ROC-SLA] Concluído. E-mails enviados: {total}")
    finally:
        conn.close()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[ROC-SLA] FALHA GERAL: {e}")
        sys.exit(1)
