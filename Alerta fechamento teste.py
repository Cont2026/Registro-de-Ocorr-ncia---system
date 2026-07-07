"""
TESTE do Alerta de Fechamento — ROC / Grupo LLE
Versão de teste que envia o alerta APENAS para a CONTABILIDADE, usando uma
parcial REAL do calendário (a próxima com data futura). NÃO grava dedup, então
pode ser rodado quantas vezes quiser. Serve para validar o visual do e-mail.

Como rodar: GitHub Actions -> "TESTE Alerta de Fechamento ROC" -> Run workflow.
Depois de validado, pode ignorar/remover este arquivo e o workflow de teste.
"""
import os
import sys
from datetime import datetime, date

import psycopg2
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

BRASILIA_TZ = "America/Sao_Paulo"
from zoneinfo import ZoneInfo
BRASILIA = ZoneInfo(BRASILIA_TZ)

DB_HOST = os.environ["DB_HOST"]
DB_NAME = os.environ["DB_NAME"]
DB_USER = os.environ["DB_USER"]
DB_PASSWORD = os.environ["DB_PASSWORD"]
DB_PORT = os.environ.get("DB_PORT", "5432")
SENDGRID_API_KEY = os.environ["SENDGRID_API_KEY"]
REMETENTE_EMAIL = os.environ.get("REMETENTE_EMAIL", "contabilidade@grupolle.com.br")
REMETENTE_NOME = os.environ.get("REMETENTE_NOME", "ROC - Registro de Ocorrencias Contabeis")
APP_URL = os.environ.get("APP_URL", "https://registro-de-ocorrencias-system-iaw5pyzvhkchnum6kseate.streamlit.app")

PARCIAL_4_ANTIGO = "Fechamento Consolidado Corporativo"

def conectar():
    return psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER,
                            password=DB_PASSWORD, port=DB_PORT, sslmode="require")

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

def email_contabilidade(conn):
    with conn.cursor() as cur:
        cur.execute("""SELECT email FROM usuarios WHERE perfil='contabilidade' AND ativo=1
            AND email IS NOT NULL AND email <> '' ORDER BY id LIMIT 1""")
        r = cur.fetchone()
    return r[0] if r else None

def montar_email(nome_evento, data_evento, periodo_ini, periodo_fim, eh_final):
    cor = "#EF4444" if eh_final else "#041747"
    destaque = "🔒 FECHAMENTO DO MÊS" if eh_final else "📅 Fechamento Parcial"
    intro = ("Esta é a <strong>última importação (fechamento) da competência</strong>. "
             "Fiquem atentos ao prazo." if eh_final else
             "Este é um <strong>fechamento parcial</strong> da competência.")
    linha_periodo = ""
    if periodo_ini or periodo_fim:
        linha_periodo = f"""<tr><td style="padding:8px;background:#f5f7fa;font-weight:600;color:#041747;width:45%;">Período a importar</td>
            <td style="padding:8px;color:#333;">{fmt(periodo_ini)} → {fmt(periodo_fim)}</td></tr>"""
    aviso_teste = ("<div style='background:#FFF4E5;border:1px solid #F0B86E;border-radius:8px;"
                   "padding:10px 14px;margin-bottom:12px;color:#8a5a00;font-size:13px;text-align:center;'>"
                   "⚙️ <strong>E-MAIL DE TESTE</strong> — enviado apenas para a contabilidade.</div>")
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#f9f9f9;padding:20px;border-radius:12px;">
        <div style="background:#041747;padding:20px;border-radius:8px 8px 0 0;text-align:center;">
            <h1 style="color:#FAC318;font-size:24px;margin:0;letter-spacing:4px;">ROC</h1>
            <p style="color:rgba(255,255,255,0.7);font-size:12px;margin:4px 0 0;">
            Registro de Ocorrencias Contabeis — Grupo LLE</p>
        </div>
        <div style="background:white;padding:24px;border-radius:0 0 8px 8px;border:1px solid #e8e8e8;">
            {aviso_teste}
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
        ROC 2026 · Grupo LLE · Mensagem automática de TESTE, não responder.</p>
    </div>
    """

def enviar_email(destinatario, assunto, corpo_html):
    message = Mail(from_email=(REMETENTE_EMAIL, REMETENTE_NOME),
                   to_emails=destinatario, subject=assunto, html_content=corpo_html)
    sg = SendGridAPIClient(SENDGRID_API_KEY)
    resp = sg.send(message)
    return resp.status_code in (200, 201, 202)

def escolher_parciais_teste(conn):
    """Pega DUAS parciais reais do calendário para o teste:
    uma parcial normal (1, 2 ou 3) e a parcial 4 (fechamento), preferindo datas
    futuras. Assim a contabilidade vê os dois modelos de e-mail."""
    with conn.cursor() as cur:
        cur.execute("""SELECT tipo, data_fechamento, periodo_inicio, periodo_fim
            FROM fechamentos WHERE data_fechamento IS NOT NULL
            ORDER BY data_fechamento""")
        linhas = cur.fetchall()

    hoje = datetime.now(BRASILIA).date()
    normal = None   # primeira parcial 1/2/3 futura (ou qualquer uma)
    final = None    # primeira parcial 4 futura (ou qualquer uma)
    for tipo, dfech, pini, pfim in linhas:
        d = to_date(dfech)
        tn = normaliza_tipo(tipo)
        eh_final = (tn == "Fechamento Parcial 4")
        registro = (tn, d, to_date(pini), to_date(pfim), eh_final)
        if eh_final:
            if final is None or (d and d >= hoje and (final[1] is None or final[1] < hoje)):
                final = registro
        else:
            if normal is None or (d and d >= hoje and (normal[1] is None or normal[1] < hoje)):
                normal = registro
    escolhidos = []
    if normal:
        escolhidos.append(normal)
    if final:
        escolhidos.append(final)
    return escolhidos

def main():
    print("[ROC-FECH-TESTE] Enviando alerta(s) de teste APENAS para a contabilidade.")
    conn = conectar()
    try:
        cont = email_contabilidade(conn)
        if not cont:
            print("[ROC-FECH-TESTE] E-mail da contabilidade não encontrado.")
            return

        parciais = escolher_parciais_teste(conn)
        if not parciais:
            print("[ROC-FECH-TESTE] Nenhuma parcial cadastrada no calendário para testar.")
            return

        total = 0
        for tn, d, pini, pfim, eh_final in parciais:
            nome = "Fechamento Parcial 4 (Consolidação)" if eh_final else tn
            assunto = f"[TESTE] ROC — Amanhã: {nome} ({fmt(d)})"
            corpo = montar_email(nome, d, pini, pfim, eh_final)
            try:
                ok = enviar_email(cont, assunto, corpo)
            except Exception as e:
                ok = False
                print(f"   ERRO ao enviar teste ({nome}): {e}")
            if ok:
                total += 1
                print(f"   [teste enviado] {nome} ({fmt(d)}) -> {cont}")

        print(f"[ROC-FECH-TESTE] Concluído. E-mails de teste enviados: {total} (para {cont})")
    finally:
        conn.close()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[ROC-FECH-TESTE] FALHA GERAL: {e}")
        sys.exit(1)
