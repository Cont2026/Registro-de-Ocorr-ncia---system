"""
Alerta de Fechamento (importação contábil) — ROC / Grupo LLE
Roda 1x/dia às 12h (via GitHub Actions). Avisa, 1 DIA ÚTIL ANTES, que haverá
um fechamento/importação, informando a parcial, o período (data a data) e a
data da importação.

Regras:
  - Verifica se o PRÓXIMO DIA ÚTIL (pulando fim de semana e feriados) é a data
    de alguma das 4 parciais/importações (tabela 'fechamentos').
  - Parciais 1, 2 e 3: aviso normal de fechamento parcial.
  - Parcial 4: é o FECHAMENTO do mês (Consolidação) — aviso destacado.
  - Avisa TODOS os setores + a CONTABILIDADE (1 e-mail só, com todos em cópia).
  - Cada alerta é enviado só 1 vez (dedup via tabela notificacoes).
Controle de duplicidade: tabela notificacoes (não precisa de tabela nova).
"""
import os
import sys
from datetime import datetime, timedelta, date
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

# Nomes das parciais (o 4º pode vir com o nome antigo "Consolidado Corporativo").
PARCIAL_4_ANTIGO = "Fechamento Consolidado Corporativo"

# Feriados nacionais 2026 (dias que NÃO contam como dia útil).
FERIADOS = {
    date(2026, 1, 1), date(2026, 2, 16), date(2026, 2, 17), date(2026, 4, 3),
    date(2026, 4, 21), date(2026, 5, 1), date(2026, 6, 4), date(2026, 9, 7),
    date(2026, 10, 12), date(2026, 11, 2), date(2026, 11, 15), date(2026, 12, 25),
}

def conectar():
    return psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER,
                            password=DB_PASSWORD, port=DB_PORT, sslmode="require")

def eh_dia_util(d):
    return d.weekday() < 5 and d not in FERIADOS

def proximo_dia_util(a_partir_de):
    """Retorna o próximo dia útil DEPOIS de 'a_partir_de'."""
    d = a_partir_de + timedelta(days=1)
    while not eh_dia_util(d):
        d += timedelta(days=1)
    return d

def to_date(valor):
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(str(valor).strip(), fmt).date()
        except:
            continue
    return None

def fmt(d):
    return d.strftime("%d/%m/%Y") if d else "—"

def normaliza_tipo(t):
    return "Fechamento Parcial 4" if t == PARCIAL_4_ANTIGO else t

def emails_todos_setores(conn):
    with conn.cursor() as cur:
        cur.execute("""SELECT email FROM usuarios
            WHERE perfil='setor' AND ativo=1 AND email IS NOT NULL AND email <> ''""")
        return [r[0] for r in cur.fetchall()]

def email_contabilidade(conn):
    with conn.cursor() as cur:
        cur.execute("""SELECT email FROM usuarios WHERE perfil='contabilidade' AND ativo=1
            AND email IS NOT NULL AND email <> '' ORDER BY id LIMIT 1""")
        r = cur.fetchone()
    return r[0] if r else None

def ja_enviado(conn, chave, destinatario):
    with conn.cursor() as cur:
        cur.execute("""SELECT COUNT(*) FROM notificacoes
            WHERE protocolo=%s AND destinatario=%s AND sucesso=1""", (chave, destinatario))
        return cur.fetchone()[0] > 0

def registrar(conn, chave, destinatario, assunto, sucesso):
    with conn.cursor() as cur:
        cur.execute("""INSERT INTO notificacoes (protocolo, destinatario, assunto, tipo, enviado_em, sucesso)
            VALUES (%s,%s,%s,%s,%s,%s)""",
            (chave, destinatario, assunto, "alerta_fechamento",
             datetime.now(BRASILIA).strftime("%Y-%m-%d %H:%M:%S"), 1 if sucesso else 0))
    conn.commit()

def montar_email(titulo, nome_evento, data_evento, periodo_ini, periodo_fim, eh_final):
    cor = "#EF4444" if eh_final else "#041747"
    destaque = "🔒 FECHAMENTO DO MÊS" if eh_final else "📅 Fechamento Parcial"
    intro = ("Esta é a <strong>última importação (fechamento) da competência</strong>. "
             "Fiquem atentos ao prazo." if eh_final else
             "Este é um <strong>fechamento parcial</strong> da competência.")
    linha_periodo = ""
    if periodo_ini or periodo_fim:
        linha_periodo = f"""<tr><td style="padding:8px;background:#f5f7fa;font-weight:600;color:#041747;width:45%;">Período a importar</td>
            <td style="padding:8px;color:#333;">{fmt(periodo_ini)} → {fmt(periodo_fim)}</td></tr>"""
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#f9f9f9;padding:20px;border-radius:12px;">
        <div style="background:#041747;padding:20px;border-radius:8px 8px 0 0;text-align:center;">
            <h1 style="color:#FAC318;font-size:24px;margin:0;letter-spacing:4px;">ROC</h1>
            <p style="color:rgba(255,255,255,0.7);font-size:12px;margin:4px 0 0;">
            Registro de Ocorrencias Contabeis — Grupo LLE</p>
        </div>
        <div style="background:white;padding:24px;border-radius:0 0 8px 8px;border:1px solid #e8e8e8;">
            <h2 style="color:{cor};font-size:18px;margin:0 0 8px;">{destaque}</h2>
            <p style="color:#333;font-size:14px;margin:0 0 4px;">{intro}</p>
            <p style="color:#333;font-size:14px;margin:0 0 16px;">
            <strong>Amanhã ({fmt(data_evento)})</strong> haverá o <strong>{nome_evento}</strong>.
            Providenciem as pendências do período antes da importação.</p>
            <table style="width:100%;border-collapse:collapse;">
                <tr><td style="padding:8px;background:#f5f7fa;font-weight:600;color:#041747;width:45%;">Evento</td>
                    <td style="padding:8px;color:#333;">{nome_evento}</td></tr>
                <tr><td style="padding:8px;font-weight:600;color:#041747;">Data da importação</td>
                    <td style="padding:8px;color:{cor};font-weight:700;">{fmt(data_evento)}</td></tr>
                {linha_periodo}
            </table>
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

def enviar_email(destinatarios, assunto, corpo_html):
    """destinatarios: lista. 1º vai no 'to', os demais em CC (1 e-mail só)."""
    dest = [d for d in destinatarios if d]
    if not dest:
        return False
    message = Mail(from_email=(REMETENTE_EMAIL, REMETENTE_NOME),
                   to_emails=dest[0], subject=assunto, html_content=corpo_html)
    if len(dest) > 1:
        for cc in dest[1:]:
            try:
                message.add_cc(cc)
            except:
                pass
    sg = SendGridAPIClient(SENDGRID_API_KEY)
    resp = sg.send(message)
    return resp.status_code in (200, 201, 202)

def coletar_eventos_do_dia(conn, alvo):
    """Retorna a lista de eventos de fechamento cuja data de importação é 'alvo'.
    Cada evento: (nome_evento, data, periodo_ini, periodo_fim, eh_final, chave_dedup)."""
    eventos = []

    with conn.cursor() as cur:
        cur.execute("""SELECT tipo, data_fechamento, periodo_inicio, periodo_fim
            FROM fechamentos WHERE data_fechamento IS NOT NULL""")
        linhas = cur.fetchall()
    for tipo, dfech, pini, pfim in linhas:
        d = to_date(dfech)
        if d != alvo:
            continue
        tipo_norm = normaliza_tipo(tipo)
        eh_final = (tipo_norm == "Fechamento Parcial 4")
        nome = "Fechamento Parcial 4 (Consolidação)" if eh_final else tipo_norm
        chave = f"FECH-{d.strftime('%Y%m%d')}-{tipo_norm.replace(' ', '')}"
        eventos.append((nome, d, to_date(pini), to_date(pfim), eh_final, chave))

    return eventos

def main():
    agora = datetime.now(BRASILIA)
    hoje = agora.date()
    alvo = proximo_dia_util(hoje)  # o "amanhã útil" que queremos avisar
    print(f"[ROC-FECH] Verificando em {agora.strftime('%d/%m/%Y %H:%M')} (Brasília). "
          f"Próximo dia útil: {fmt(alvo)}")

    conn = conectar()
    try:
        eventos = coletar_eventos_do_dia(conn, alvo)
        if not eventos:
            print("[ROC-FECH] Nenhum fechamento no próximo dia útil. Nada a enviar.")
            return

        # Destinatários: todos os setores + contabilidade (1 e-mail só, com CC).
        destinatarios = emails_todos_setores(conn)
        cont = email_contabilidade(conn)
        if cont and cont not in destinatarios:
            destinatarios.append(cont)
        if not destinatarios:
            print("[ROC-FECH] Nenhum destinatário ativo encontrado.")
            return

        total = 0
        vistos_chave = set()
        for nome, d, pini, pfim, eh_final, chave in eventos:
            if chave in vistos_chave:
                continue
            vistos_chave.add(chave)

            assunto = f"ROC — Amanhã: {nome} ({fmt(d)})"
            corpo = montar_email(assunto, nome, d, pini, pfim, eh_final)

            ref = destinatarios[0]
            if ja_enviado(conn, chave, ref):
                print(f"   (já enviado) {chave}")
                continue
            try:
                ok = enviar_email(destinatarios, assunto, corpo)
            except Exception as e:
                ok = False
                print(f"   ERRO ao enviar {chave}: {e}")
            for dest in destinatarios:
                registrar(conn, chave, dest, assunto, ok)
            if ok:
                total += 1
                print(f"   [enviado] {nome} ({fmt(d)}) -> {len(destinatarios)} destinatários")

        print(f"[ROC-FECH] Concluído. Alertas enviados: {total}")
    finally:
        conn.close()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[ROC-FECH] FALHA GERAL: {e}")
        sys.exit(1)
