import streamlit as st
import urllib.request
import urllib.error
import json

def enviar_email(destinatario, assunto, corpo_html):
    try:
        api_key = st.secrets["SENDGRID_API_KEY"]
        remetente = st.secrets["REMETENTE_EMAIL"]
        nome_remetente = st.secrets["REMETENTE_NOME"]

        dados = {
            "personalizations": [{"to": [{"email": destinatario}]}],
            "from": {"email": remetente, "name": nome_remetente},
            "subject": assunto,
            "content": [{"type": "text/html", "value": corpo_html}]
        }

        req = urllib.request.Request(
            "https://api.sendgrid.com/v3/mail/send",
            data=json.dumps(dados).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            method="POST"
        )
        urllib.request.urlopen(req)
        return True
    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}")
        return False

def email_novo_chamado(email_contabilidade, protocolo, setor, tipo, prioridade, parceiro, numero_nota, solicitante):
    assunto = f"ROC — Novo Chamado {protocolo}"
    corpo = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#f9f9f9;padding:20px;border-radius:12px;">
        <div style="background:#041747;padding:20px;border-radius:8px 8px 0 0;text-align:center;">
            <h1 style="color:#FAC318;font-size:24px;margin:0;letter-spacing:4px;">ROC</h1>
            <p style="color:rgba(255,255,255,0.7);font-size:12px;margin:4px 0 0;">Registro de Ocorrências Contábeis — Grupo LLE</p>
        </div>
        <div style="background:white;padding:24px;border-radius:0 0 8px 8px;border:1px solid #e8e8e8;">
            <h2 style="color:#041747;font-size:18px;margin:0 0 16px;">📋 Novo chamado aberto</h2>
            <table style="width:100%;border-collapse:collapse;">
                <tr><td style="padding:8px;background:#f5f7fa;font-weight:600;color:#041747;width:40%;border-radius:4px;">Protocolo</td><td style="padding:8px;color:#333;">{protocolo}</td></tr>
                <tr><td style="padding:8px;font-weight:600;color:#041747;">Setor</td><td style="padding:8px;color:#333;">{setor}</td></tr>
                <tr><td style="padding:8px;background:#f5f7fa;font-weight:600;color:#041747;">Solicitante</td><td style="padding:8px;color:#333;">{solicitante}</td></tr>
                <tr><td style="padding:8px;font-weight:600;color:#041747;">Tipo</td><td style="padding:8px;color:#333;">{tipo}</td></tr>
                <tr><td style="padding:8px;background:#f5f7fa;font-weight:600;color:#041747;">Parceiro</td><td style="padding:8px;color:#333;">{parceiro}</td></tr>
                <tr><td style="padding:8px;font-weight:600;color:#041747;">Número NF</td><td style="padding:8px;color:#333;">{numero_nota}</td></tr>
                <tr><td style="padding:8px;background:#f5f7fa;font-weight:600;color:#041747;">Prioridade</td><td style="padding:8px;color:{"#ef4444" if prioridade == "Urgente" else "#22c55e"};font-weight:600;">{prioridade}</td></tr>
            </table>
            <div style="margin-top:20px;padding:12px;background:#FFF8E7;border-left:4px solid #FAC318;border-radius:4px;">
                <p style="margin:0;font-size:13px;color:#666;">Acesse o ROC para visualizar e responder este chamado.</p>
            </div>
        </div>
        <p style="text-align:center;font-size:11px;color:#999;margin-top:12px;">ROC © 2026 · Grupo LLE</p>
    </div>
    """
    return enviar_email(email_contabilidade, assunto, corpo)

def email_atualizacao_chamado(email_setor, protocolo, novo_status, mensagem=None):
    cores_status = {"Aberto": "#ef4444", "Em andamento": "#f59e0b", "Resolvido": "#22c55e", "Cancelado": "#6b7280"}
    cor = cores_status.get(novo_status, "#041747")
    assunto = f"ROC — Chamado {protocolo} atualizado"
    msg_html = f"""
        <div style="margin-top:16px;padding:12px;background:#f5f7fa;border-radius:6px;">
            <p style="margin:0;font-size:13px;font-weight:600;color:#041747;">💬 Mensagem da Contabilidade:</p>
            <p style="margin:8px 0 0;font-size:13px;color:#333;">{mensagem}</p>
        </div>
    """ if mensagem else ""

    corpo = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#f9f9f9;padding:20px;border-radius:12px;">
        <div style="background:#041747;padding:20px;border-radius:8px 8px 0 0;text-align:center;">
            <h1 style="color:#FAC318;font-size:24px;margin:0;letter-spacing:4px;">ROC</h1>
            <p style="color:rgba(255,255,255,0.7);font-size:12px;margin:4px 0 0;">Registro de Ocorrências Contábeis — Grupo LLE</p>
        </div>
        <div style="background:white;padding:24px;border-radius:0 0 8px 8px;border:1px solid #e8e8e8;">
            <h2 style="color:#041747;font-size:18px;margin:0 0 16px;">🔔 Atualização do seu chamado</h2>
            <table style="width:100%;border-collapse:collapse;">
                <tr><td style="padding:8px;background:#f5f7fa;font-weight:600;color:#041747;width:40%;">Protocolo</td><td style="padding:8px;color:#333;">{protocolo}</td></tr>
                <tr><td style="padding:8px;font-weight:600;color:#041747;">Novo Status</td><td style="padding:8px;color:{cor};font-weight:700;">{novo_status}</td></tr>
            </table>
            {msg_html}
            <div style="margin-top:20px;padding:12px;background:#FFF8E7;border-left:4px solid #FAC318;border-radius:4px;">
                <p style="margin:0;font-size:13px;color:#666;">Acesse o ROC para acompanhar seu chamado.</p>
            </div>
        </div>
        <p style="text-align:center;font-size:11px;color:#999;margin-top:12px;">ROC © 2026 · Grupo LLE</p>
    </div>
    """
    return enviar_email(email_setor, assunto, corpo)

def email_nova_mensagem(email_destinatario, protocolo, autor, mensagem):
    assunto = f"ROC — Nova mensagem no chamado {protocolo}"
    corpo = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#f9f9f9;padding:20px;border-radius:12px;">
        <div style="background:#041747;padding:20px;border-radius:8px 8px 0 0;text-align:center;">
            <h1 style="color:#FAC318;font-size:24px;margin:0;letter-spacing:4px;">ROC</h1>
            <p style="color:rgba(255,255,255,0.7);font-size:12px;margin:4px 0 0;">Registro de Ocorrências Contábeis — Grupo LLE</p>
        </div>
        <div style="background:white;padding:24px;border-radius:0 0 8px 8px;border:1px solid #e8e8e8;">
            <h2 style="color:#041747;font-size:18px;margin:0 0 16px;">💬 Nova mensagem no chamado</h2>
            <table style="width:100%;border-collapse:collapse;">
                <tr><td style="padding:8px;background:#f5f7fa;font-weight:600;color:#041747;width:40%;">Protocolo</td><td style="padding:8px;color:#333;">{protocolo}</td></tr>
                <tr><td style="padding:8px;font-weight:600;color:#041747;">De</td><td style="padding:8px;color:#333;">{autor}</td></tr>
            </table>
            <div style="margin-top:16px;padding:16px;background:#F0F4FF;border-radius:8px;border-left:4px solid #041747;">
                <p style="margin:0;font-size:14px;color:#041747;">{mensagem}</p>
            </div>
            <div style="margin-top:20px;padding:12px;background:#FFF8E7;border-left:4px solid #FAC318;border-radius:4px;">
                <p style="margin:0;font-size:13px;color:#666;">Acesse o ROC para responder esta mensagem.</p>
            </div>
        </div>
        <p style="text-align:center;font-size:11px;color:#999;margin-top:12px;">ROC © 2026 · Grupo LLE</p>
    </div>
    """
    return enviar_email(email_destinatario, assunto, corpo)
