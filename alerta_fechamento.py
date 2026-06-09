"""
Alerta de Fechamento Parcial — ROC / Grupo LLE
Roda diariamente (via GitHub Actions). Para cada Fechamento Parcial cadastrado,
envia e-mail aos setores quando a data for HOJE ou AMANHÃ (no fuso de Brasília).
Não reenvia o que já foi enviado com sucesso (controle pela tabela notificacoes).
"""
import os
import sys
from datetime import datetime, date
from zoneinfo import ZoneInfo

import psycopg2
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

BRASILIA = ZoneInfo("America/Sao_Paulo")

# --- Configuração via variáveis de ambiente (GitHub Secrets) ---
DB_HOST = os.environ["DB_HOST"]
DB_NAME = os.environ["DB_NAME"]
DB_USER = os.environ["DB_USER"]
DB_PASSWORD = os.environ["DB_PASSWORD"]
DB_PORT = os.environ.get("DB_PORT", "5432")
SENDGRID_API_KEY = os.environ["SENDGRID_API_KEY"]
REMETENTE_EMAIL = os.environ.get("REMETENTE_EMAIL", "contabilidade@grupolle.com.br")
REMETENTE_NOME = os.environ.get("REMETENTE_NOME", "ROC - Registro de Ocorrencias Contabeis")
APP_URL = os.environ.get("APP_URL", "https://registro-de-ocorr-ncia---system.streamlit.app")

TIPOS_PARCIAIS = (
    "Fechamento Parcial 1",
    "Fechamento Parcial 2",
    "Fechamento Parcial 3",
    "Fechamento Parcial 4",
    "Fechamento Consolidado Corporativo",  # nome antigo = Parcial 4
)

def label_tipo(tipo):
    if tipo == "Fechamento Consolidado Corporativo":
        return "Fechamento Parcial 4"
    return tipo

def conectar():
    return psycopg2.connect(
        host=DB_HOST, dbname=DB_NAME, user=DB_USER,
        password=DB_PASSWORD, port=DB_PORT, sslmode="require"
    )

def buscar_fechamentos(conn):
    placeholders = ",".join(["%s"] * len(TIPOS_PARCIAIS))
    sql = f"""
        SELECT f.id, f.tipo, f.data_fechamento, f.hora_fechamento, c.mes_ano
        FROM fechamentos f
        JOIN competencias c ON c.id = f.competencia_id
        WHERE f.data_fechamento IS NOT NULL
          AND f.tipo IN ({placeholders})
    """
    with conn.cursor() as cur:
        cur.execute(sql, TIPOS_PARCIAIS)
        return cur.fetchall()

def buscar_setores(conn):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT email, setor_nome FROM usuarios
            WHERE perfil='setor' AND ativo=1 AND email IS NOT NULL AND email <> ''
        """)
        return cur.fetchall()

def ja_enviado(conn, chave, destinatario):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) FROM notificacoes
            WHERE protocolo=%s AND destinatario=%s AND sucesso=true
        """, (chave, destinatario))
        return cur.fetchone()[0] > 0

def registrar_notificacao(conn, chave, destinatario, assunto, sucesso):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO notificacoes (protocolo, destinatario, assunto, tipo, enviado_em, sucesso)
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (chave, destinatario, assunto, "alerta_fechamento",
              datetime.now(BRASILIA).strftime("%Y-%m-%d %H:%M:%S"), sucesso))
    conn.commit()

def montar_email(tipo_nome, mes_ano, data_fech, hora_fech, quando_txt):
    hora_str = f" às {hora_fech}" if hora_fech else ""
    cor_destaque = "#FAC318" if quando_txt == "amanhã" else "#EF4444"
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#f9f9f9;padding:20px;border-radius:12px;">
        <div style="background:#041747;padding:20px;border-radius:8px 8px 0 0;text-align:center;">
            <h1 style="color:#FAC318;font-size:24px;margin:0;letter-spacing:4px;">ROC</h1>
            <p style="color:rgba(255,255,255,0.7);font-size:12px;margin:4px 0 0;">
            Registro de Ocorrencias Contabeis — Grupo LLE</p>
        </div>
        <div style="background:white;padding:24px;border-radius:0 0 8px 8px;border:1px solid #e8e8e8;">
            <h2 style="color:#041747;font-size:18px;margin:0 0 8px;">📅 Lembrete de Fechamento</h2>
            <p style="color:#333;font-size:14px;margin:0 0 16px;">
            O <strong>{tipo_nome}</strong> da competência <strong>{mes_ano}</strong> é
            <strong style="color:{cor_destaque};">{quando_txt}</strong>.</p>
            <table style="width:100%;border-collapse:collapse;">
                <tr><td style="padding:8px;background:#f5f7fa;font-weight:600;color:#041747;width:40%;">Tipo</td><td style="padding:8px;color:#333;">{tipo_nome}</td></tr>
                <tr><td style="padding:8px;font-weight:600;color:#041747;">Competência</td><td style="padding:8px;color:#333;">{mes_ano}</td></tr>
                <tr><td style="padding:8px;background:#f5f7fa;font-weight:600;color:#041747;">Data</td><td style="padding:8px;color:#333;">{data_fech.strftime('%d/%m/%Y')}{hora_str}</td></tr>
            </table>
            <p style="color:#555;font-size:13px;margin:16px 0;">
            Por favor, garanta que todas as solicitações do seu setor sejam registradas no ROC
            antes do prazo de fechamento.</p>
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
    message = Mail(
        from_email=(REMETENTE_EMAIL, REMETENTE_NOME),
        to_emails=destinatario,
        subject=assunto,
        html_content=corpo_html,
    )
    sg = SendGridAPIClient(SENDGRID_API_KEY)
    resp = sg.send(message)
    return resp.status_code in (200, 201, 202)

def main():
    hoje = datetime.now(BRASILIA).date()
    print(f"[ROC] Verificando fechamentos para {hoje.strftime('%d/%m/%Y')} (Brasília)")

    conn = conectar()
    try:
        fechamentos = buscar_fechamentos(conn)
        setores = buscar_setores(conn)

        if not setores:
            print("[ROC] Nenhum setor ativo com e-mail. Nada a enviar.")
            return

        total_enviados = 0
        for fid, tipo, data_fech, hora_fech, mes_ano in fechamentos:
            if isinstance(data_fech, datetime):
                data_fech = data_fech.date()

            dias = (data_fech - hoje).days
            if dias == 0:
                quando_txt, sufixo = "hoje", "D0"
            elif dias == 1:
                quando_txt, sufixo = "amanhã", "D1"
            else:
                continue

            tipo_nome = label_tipo(tipo)
            chave = f"FECHAMENTO-{fid}-{sufixo}"
            assunto = f"ROC — {tipo_nome} de {mes_ano} é {quando_txt}"
            corpo = montar_email(tipo_nome, mes_ano, data_fech, hora_fech, quando_txt)

            print(f"[ROC] {tipo_nome} ({mes_ano}) em {data_fech.strftime('%d/%m/%Y')} — {quando_txt}")
            for email_setor, setor_nome in setores:
                if ja_enviado(conn, chave, email_setor):
                    print(f"        já enviado para {email_setor}, pulando.")
                    continue
                try:
                    ok = enviar_email(email_setor, assunto, corpo)
                except Exception as e:
                    ok = False
                    print(f"        ERRO ao enviar para {email_setor}: {e}")
                registrar_notificacao(conn, chave, email_setor, assunto, ok)
                if ok:
                    total_enviados += 1
                    print(f"        enviado para {email_setor} ({setor_nome})")

        print(f"[ROC] Concluído. Total de e-mails enviados: {total_enviados}")
    finally:
        conn.close()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[ROC] FALHA GERAL: {e}")
        sys.exit(1)
