import streamlit as st
import urllib.request
import json
import base64
import mimetypes
from datetime import datetime
from zoneinfo import ZoneInfo
from database.connection import run_query

BRASILIA = ZoneInfo("America/Sao_Paulo")

def get_url_base():
    try:
        return st.secrets.get("APP_URL", "https://registro-de-ocorr-ncia---system.streamlit.app")
    except:
        return "https://registro-de-ocorr-ncia---system.streamlit.app"

def registrar_notificacao(protocolo, destinatario, assunto, tipo, sucesso):
    try:
        run_query("""INSERT INTO notificacoes (protocolo, destinatario, assunto, tipo, enviado_em, sucesso)
            VALUES (%s, %s, %s, %s, %s, %s)""",
            (protocolo, destinatario, assunto, tipo,
             datetime.now(BRASILIA).strftime("%Y-%m-%d %H:%M:%S"), 1 if sucesso else 0))
    except:
        pass

def enviar_email(destinatario, assunto, corpo_html, protocolo=None, tipo="geral", anexos=None):
    """anexos: lista de tuplas (nome_arquivo, conteudo_bytes)."""
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

        if anexos:
            lista_anexos = []
            for nome_arquivo, conteudo in anexos:
                if not conteudo:
                    continue
                mime, _ = mimetypes.guess_type(nome_arquivo)
                lista_anexos.append({
                    "content": base64.b64encode(conteudo).decode("utf-8"),
                    "filename": nome_arquivo,
                    "type": mime or "application/octet-stream",
                    "disposition": "attachment"
                })
            if lista_anexos:
                dados["attachments"] = lista_anexos

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
        registrar_notificacao(protocolo, destinatario, assunto, tipo, True)
        return True
    except Exception as e:
        registrar_notificacao(protocolo, destinatario, assunto, tipo, False)
        return False

def botao_chamado(protocolo):
    url = f"{get_url_base()}/?protocolo={protocolo}"
    return f"""
    <div style="text-align:center;margin-top:20px;">
        <a href="{url}" style="background:#041747;color:white;padding:12px 28px;
        border-radius:8px;text-decoration:none;font-family:Arial,sans-serif;
        font-size:14px;font-weight:600;display:inline-block;">
        🔗 Abrir Chamado {protocolo}
        </a>
    </div>
    """

def cabecalho_email():
    return """
    <div style="background:#041747;padding:20px;border-radius:8px 8px 0 0;text-align:center;">
        <h1 style="color:#FAC318;font-size:24px;margin:0;letter-spacing:4px;">ROC</h1>
        <p style="color:rgba(255,255,255,0.7);font-size:12px;margin:4px 0 0;">
        Registro de Ocorrências Contábeis — Grupo LLE</p>
    </div>
    """

def rodape_email():
    return """
    <p style="text-align:center;font-size:11px;color:#999;margin-top:12px;">
    ROC © 2026 · Grupo LLE · Este é um e-mail automático, não responda diretamente.</p>
    """

def tabela_row(label, valor, alt=False):
    bg = "#f5f7fa" if alt else "white"
    return f"""<tr>
        <td style="padding:8px;background:{bg};font-weight:600;color:#041747;width:40%;border-radius:4px;">{label}</td>
        <td style="padding:8px;background:{bg};color:#333;">{valor}</td>
    </tr>"""

def email_novo_chamado(email_contabilidade, protocolo, setor, tipo, prioridade, parceiro, numero_nota, solicitante, anexos=None, nu_financeiro="", nu_nota=""):
    assunto = f"ROC — Novo Chamado {protocolo}"
    cor_prio = "#ef4444" if prioridade == "Urgente" else "#22c55e"
    linha_nu_fin = tabela_row("Nº Único Financeiro", nu_financeiro) if nu_financeiro else ""
    linha_nu_nota = tabela_row("Nº Único da Nota", nu_nota, True) if nu_nota else ""
    corpo = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#f9f9f9;padding:20px;border-radius:12px;">
        {cabecalho_email()}
        <div style="background:white;padding:24px;border-radius:0 0 8px 8px;border:1px solid #e8e8e8;">
            <h2 style="color:#041747;font-size:18px;margin:0 0 16px;">📋 Novo chamado aberto</h2>
            <table style="width:100%;border-collapse:collapse;">
                {tabela_row("Protocolo", protocolo, True)}
                {tabela_row("Setor", setor)}
                {tabela_row("Solicitante", solicitante, True)}
                {tabela_row("Tipo", tipo)}
                {tabela_row("Parceiro", parceiro, True)}
                {tabela_row("Número NF", numero_nota)}
                {linha_nu_fin}
                {linha_nu_nota}
                {tabela_row("Prioridade", f'<span style="color:{cor_prio};font-weight:700;">{prioridade}</span>', True)}
            </table>
            {botao_chamado(protocolo)}
        </div>
        {rodape_email()}
    </div>
    """
    return enviar_email(email_contabilidade, assunto, corpo, protocolo, "novo_chamado", anexos=anexos)

def email_atualizacao_chamado(email_setor, protocolo, novo_status, setor=""):
    cores = {"Aberto":"#ef4444","Em andamento":"#f59e0b","Resolvido":"#22c55e","Cancelado":"#6b7280"}
    cor = cores.get(novo_status, "#041747")
    assunto = f"ROC — Chamado {protocolo} atualizado para {novo_status}"
    corpo = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#f9f9f9;padding:20px;border-radius:12px;">
        {cabecalho_email()}
        <div style="background:white;padding:24px;border-radius:0 0 8px 8px;border:1px solid #e8e8e8;">
            <h2 style="color:#041747;font-size:18px;margin:0 0 16px;">🔔 Chamado atualizado</h2>
            <table style="width:100%;border-collapse:collapse;">
                {tabela_row("Protocolo", protocolo, True)}
                {tabela_row("Novo Status", f'<span style="color:{cor};font-weight:700;">{novo_status}</span>')}
                {tabela_row("Data", datetime.now(BRASILIA).strftime("%d/%m/%Y às %H:%M"), True)}
            </table>
            {botao_chamado(protocolo)}
        </div>
        {rodape_email()}
    </div>
    """
    return enviar_email(email_setor, assunto, corpo, protocolo, "atualizacao_status")

def email_conclusao_chamado(email_contabilidade, email_setor, protocolo, tipo, data_conclusao):
    assunto = f"ROC — Chamado {protocolo} concluído"
    corpo = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#f9f9f9;padding:20px;border-radius:12px;">
        {cabecalho_email()}
        <div style="background:white;padding:24px;border-radius:0 0 8px 8px;border:1px solid #e8e8e8;">
            <h2 style="color:#22c55e;font-size:18px;margin:0 0 16px;">✅ Chamado concluído</h2>
            <table style="width:100%;border-collapse:collapse;">
                {tabela_row("Protocolo", protocolo, True)}
                {tabela_row("Tipo", tipo)}
                {tabela_row("Status Final", '<span style="color:#22c55e;font-weight:700;">Resolvido</span>', True)}
                {tabela_row("Data de Conclusão", data_conclusao)}
            </table>
            {botao_chamado(protocolo)}
        </div>
        {rodape_email()}
    </div>
    """
    sucesso = True
    if email_contabilidade:
        sucesso = enviar_email(email_contabilidade, assunto, corpo, protocolo, "conclusao")
    if email_setor:
        sucesso = enviar_email(email_setor, assunto, corpo, protocolo, "conclusao")
    return sucesso

def email_nova_mensagem(email_destinatario, protocolo, autor, mensagem):
    assunto = f"ROC — Nova mensagem no chamado {protocolo}"
    corpo = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#f9f9f9;padding:20px;border-radius:12px;">
        {cabecalho_email()}
        <div style="background:white;padding:24px;border-radius:0 0 8px 8px;border:1px solid #e8e8e8;">
            <h2 style="color:#041747;font-size:18px;margin:0 0 16px;">💬 Nova mensagem no chamado</h2>
            <table style="width:100%;border-collapse:collapse;">
                {tabela_row("Protocolo", protocolo, True)}
                {tabela_row("De", autor)}
                {tabela_row("Data", datetime.now(BRASILIA).strftime("%d/%m/%Y às %H:%M"), True)}
            </table>
            <div style="margin-top:16px;padding:16px;background:#F0F4FF;border-radius:8px;border-left:4px solid #041747;">
                <p style="margin:0;font-size:14px;color:#041747;font-style:italic;">"{mensagem}"</p>
            </div>
            {botao_chamado(protocolo)}
        </div>
        {rodape_email()}
    </div>
    """
    return enviar_email(email_destinatario, assunto, corpo, protocolo, "nova_mensagem")

def email_setor_em_copia(email_setor, protocolo, setor, aberto_por=""):
    assunto = f"ROC — Você foi incluído no chamado {protocolo}"
    info_aberto = tabela_row("Aberto por", aberto_por, True) if aberto_por else ""
    corpo = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#f9f9f9;padding:20px;border-radius:12px;">
        {cabecalho_email()}
        <div style="background:white;padding:24px;border-radius:0 0 8px 8px;border:1px solid #e8e8e8;">
            <h2 style="color:#041747;font-size:18px;margin:0 0 8px;">👥 Você está em cópia neste chamado</h2>
            <p style="color:#555;font-size:14px;margin:0 0 16px;">
            O setor <strong>{setor}</strong> foi incluído como acompanhante do chamado abaixo.
            Você pode visualizar todos os detalhes e responder pelo chat interno.</p>
            <table style="width:100%;border-collapse:collapse;">
                {tabela_row("Protocolo", protocolo)}
                {info_aberto}
            </table>
            {botao_chamado(protocolo)}
        </div>
        {rodape_email()}
    </div>
    """
    return enviar_email(email_setor, assunto, corpo, protocolo, "copia_chamado")
