import streamlit as st
import smtplib
import ssl
from email.message import EmailMessage
from datetime import datetime
from zoneinfo import ZoneInfo
from database.connection import run_query

BRASILIA = ZoneInfo("America/Sao_Paulo")

# Controla a cópia (BCC) para a Contabilidade: 1 por assunto dentro de uma mesma ação,
# evitando várias cópias quando um protocolo tem vários setores marcados.
_bcc_recente = {}

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

@st.cache_data(ttl=300)
def _email_contabilidade():
    """E-mail da Contabilidade, para receber cópia (BCC) de todas as notificações."""
    try:
        r = run_query("SELECT email FROM usuarios WHERE perfil='contabilidade' AND ativo=1 AND email IS NOT NULL AND email<>'' ORDER BY id LIMIT 1", fetch=True)
        return r[0][0] if r and r[0] and r[0][0] else None
    except:
        return None

def _config_smtp():
    """Dados do servidor de envio, lidos das Secrets.

    O envio é feito por SMTP (protocolo padrão de e-mail), e não pela API de um
    serviço específico. Assim o sistema funciona com Brevo, Mailjet, Resend ou o
    próprio Microsoft 365 da empresa — para trocar de serviço basta mudar estas
    Secrets, sem alterar uma linha de código.

    Secrets necessárias:
        SMTP_HOST      ex.: smtp-relay.brevo.com
        SMTP_PORT      587 (com STARTTLS) ou 465 (SSL direto)
        SMTP_USER      o login que o serviço fornece
        SMTP_PASSWORD  a chave/senha SMTP que o serviço fornece
    """
    host = str(st.secrets["SMTP_HOST"]).strip()
    porta = int(str(st.secrets.get("SMTP_PORT", 587)).strip() or 587)
    usuario = str(st.secrets["SMTP_USER"]).strip()
    senha = str(st.secrets["SMTP_PASSWORD"]).strip()
    return host, porta, usuario, senha

def _texto_alternativo(assunto):
    """Versão em texto puro do e-mail. Alguns filtros de spam penalizam mensagens
    que só têm HTML, então vai sempre uma versão simples junto."""
    return (f"{assunto}\n\n"
            f"Este é um aviso automático do ROC — Registro de Ocorrências Contábeis.\n"
            f"Acesse o sistema para ver os detalhes: {get_url_base()}\n\n"
            f"Grupo LLE · mensagem automática, não responda diretamente.")

def enviar_email(destinatario, assunto, corpo_html, protocolo=None, tipo="geral", anexos=None, copiar_contabilidade=True):
    """destinatario: pode ser um e-mail (str) OU uma lista de e-mails.
    Quando é lista, o 1º vira 'Para' e os demais entram em CC — assim sai
    UM e-mail só (em vez de um por pessoa), economizando cota de envio.
    anexos: lista de tuplas (nome_arquivo, conteudo_bytes).
    copiar_contabilidade: quando False, NÃO coloca a Contabilidade em BCC
    (usado no e-mail de 'você está em cópia', que é redundante para ela)."""
    dest_unicos = []
    try:
        host, porta, usuario, senha = _config_smtp()
        remetente = str(st.secrets["REMETENTE_EMAIL"]).strip()
        nome_remetente = str(st.secrets["REMETENTE_NOME"]).strip()

        # Normaliza a entrada: aceita str ou lista, remove vazios e duplicados.
        if isinstance(destinatario, (list, tuple, set)):
            bruto = list(destinatario)
        else:
            bruto = [destinatario]
        vistos = set()
        for e in bruto:
            el = str(e or "").strip()
            if el and el.lower() not in vistos:
                vistos.add(el.lower())
                dest_unicos.append(el)
        if not dest_unicos:
            return False

        # 1º destinatário = "Para"; os demais = CC (1 e-mail só para todos).
        para = [dest_unicos[0]]
        cc = dest_unicos[1:]
        bcc = []

        # Contabilidade recebe cópia (BCC) de todas as notificações automaticamente,
        # mas apenas 1 vez por assunto (evita várias cópias quando há vários setores),
        # e não duplica quando a contabilidade já está entre os destinatários (To/CC).
        # Quando copiar_contabilidade=False, esse BCC é suprimido.
        if copiar_contabilidade:
            email_cont = _email_contabilidade()
            if email_cont and email_cont.strip().lower() not in vistos:
                agora = datetime.now(BRASILIA).timestamp()
                chave = (assunto or "").strip().lower()
                ultimo = _bcc_recente.get(chave, 0)
                if agora - ultimo > 60:  # mesma "rodada" de envios: só a 1ª cópia
                    bcc.append(email_cont.strip())
                    _bcc_recente[chave] = agora
                    for k in [k for k, v in _bcc_recente.items() if agora - v > 600]:
                        _bcc_recente.pop(k, None)

        # Os anexos NÃO são enviados por e-mail (evita recusa por tamanho e mantém
        # os e-mails leves). O arquivo continua salvo no sistema; o e-mail apenas
        # avisa para acessar o chamado e baixar lá, quando houver anexo.
        if anexos and any(c for (_n, c) in anexos if c):
            aviso = ("<div style=\"max-width:600px;margin:8px auto 0;padding:12px 16px;"
                     "background:#F0F4FF;border:1px solid #b9c7f0;border-radius:8px;"
                     "font-family:Arial,sans-serif;font-size:13px;color:#041747;\">"
                     "📎 <strong>Este chamado possui anexo(s).</strong> "
                     "Acesse o chamado no sistema para visualizar e baixar o(s) arquivo(s).</div>")
            corpo_html = corpo_html + aviso

        msg = EmailMessage()
        msg["Subject"] = assunto
        msg["From"] = f"{nome_remetente} <{remetente}>"
        msg["To"] = ", ".join(para)
        if cc:
            msg["Cc"] = ", ".join(cc)
        # O BCC NÃO entra no cabeçalho (senão deixaria de ser oculto): ele vai
        # apenas na lista de entrega passada ao servidor.
        msg.set_content(_texto_alternativo(assunto))
        msg.add_alternative(corpo_html, subtype="html")

        todos = para + cc + bcc
        contexto = ssl.create_default_context()
        if porta == 465:
            with smtplib.SMTP_SSL(host, porta, timeout=30, context=contexto) as s:
                s.login(usuario, senha)
                s.send_message(msg, from_addr=remetente, to_addrs=todos)
        else:
            with smtplib.SMTP(host, porta, timeout=30) as s:
                s.ehlo()
                s.starttls(context=contexto)
                s.ehlo()
                s.login(usuario, senha)
                s.send_message(msg, from_addr=remetente, to_addrs=todos)

        registrar_notificacao(protocolo, ", ".join(dest_unicos), assunto, tipo, True)
        return True

    except smtplib.SMTPAuthenticationError as e:
        # Login/senha SMTP recusados — normalmente Secret errada ou chave revogada.
        motivo = f"[ERRO SMTP autenticacao] {str(e)[:400]}"
        log_dest = ", ".join(dest_unicos) if dest_unicos else str(destinatario)
        registrar_notificacao(protocolo, log_dest, f"{assunto} {motivo}", tipo, False)
        return False
    except smtplib.SMTPRecipientsRefused as e:
        # O servidor recusou os destinatários (endereço inválido, por exemplo).
        motivo = f"[ERRO SMTP destinatarios] {str(e)[:400]}"
        log_dest = ", ".join(dest_unicos) if dest_unicos else str(destinatario)
        registrar_notificacao(protocolo, log_dest, f"{assunto} {motivo}", tipo, False)
        return False
    except smtplib.SMTPException as e:
        # Outra falha do servidor de e-mail (cota, remetente não verificado, etc.).
        motivo = f"[ERRO SMTP {type(e).__name__}] {str(e)[:400]}"
        log_dest = ", ".join(dest_unicos) if dest_unicos else str(destinatario)
        registrar_notificacao(protocolo, log_dest, f"{assunto} {motivo}", tipo, False)
        return False
    except Exception as e:
        # Falha fora do envio (rede, Secret ausente, etc.).
        motivo = f"[ERRO {type(e).__name__}] {str(e)[:400]}"
        log_dest = ", ".join(dest_unicos) if dest_unicos else str(destinatario)
        registrar_notificacao(protocolo, log_dest, f"{assunto} {motivo}", tipo, False)
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

def bloco_mensagem(mensagem, titulo="💬 Mensagem enviada junto com a atualização"):
    """Caixa com o texto da mensagem, usada quando a atualização de status vem
    acompanhada de uma mensagem no chat — assim sai 1 e-mail só, com as duas
    informações, em vez de dois e-mails quase simultâneos."""
    txt = (mensagem or "").strip()
    if not txt:
        return ""
    return f"""
            <div style="margin-top:16px;padding:16px;background:#F0F4FF;border-radius:8px;border-left:4px solid #041747;">
                <p style="margin:0 0 6px;font-size:12px;font-weight:700;color:#041747;">{titulo}</p>
                <p style="margin:0;font-size:14px;color:#041747;font-style:italic;">"{txt}"</p>
            </div>
    """

def email_novo_chamado(email_contabilidade, protocolo, setor, tipo, prioridade, parceiro, numero_nota, solicitante, anexos=None, nu_financeiro="", nu_nota="", atrasos=""):
    assunto = f"ROC — Novo Chamado {protocolo}"
    cor_prio = "#ef4444" if prioridade == "Urgente" else "#22c55e"
    # Linhas que só aparecem quando têm conteúdo (ex.: INFORMAR ENTREGÁVEIS não tem parceiro/NF).
    linha_parceiro = tabela_row("Parceiro", parceiro, True) if (parceiro or "").strip() else ""
    linha_numero_nf = tabela_row("Número NF", numero_nota) if (numero_nota or "").strip() else ""
    linha_nu_fin = tabela_row("Nº Único Financeiro", nu_financeiro) if nu_financeiro else ""
    linha_nu_nota = tabela_row("Nº Único da Nota", nu_nota, True) if nu_nota else ""
    linha_atrasos = tabela_row("Atrasos de entregáveis", atrasos) if atrasos else ""
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
                {linha_parceiro}
                {linha_numero_nf}
                {linha_nu_fin}
                {linha_nu_nota}
                {linha_atrasos}
                {tabela_row("Prioridade", f'<span style="color:{cor_prio};font-weight:700;">{prioridade}</span>', True)}
            </table>
            {botao_chamado(protocolo)}
        </div>
        {rodape_email()}
    </div>
    """
    return enviar_email(email_contabilidade, assunto, corpo, protocolo, "novo_chamado", anexos=anexos)

def email_atualizacao_chamado(email_setor, protocolo, novo_status, setor="", atendente="", mensagem=""):
    """Avisa a mudança de status. Quando 'mensagem' vem preenchida, o texto do chat
    entra no MESMO e-mail — evitando dois disparos para as mesmas pessoas."""
    cores = {"Aberto":"#ef4444","Em andamento":"#f59e0b","Pendente":"#fb923c",
             "Resolvido":"#22c55e","Cancelado":"#6b7280"}
    cor = cores.get(novo_status, "#041747")
    assunto = f"ROC — Chamado {protocolo} atualizado para {novo_status}"
    linha_atend = tabela_row("Atualizado por", atendente) if atendente else ""
    caixa_msg = bloco_mensagem(mensagem)
    corpo = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#f9f9f9;padding:20px;border-radius:12px;">
        {cabecalho_email()}
        <div style="background:white;padding:24px;border-radius:0 0 8px 8px;border:1px solid #e8e8e8;">
            <h2 style="color:#041747;font-size:18px;margin:0 0 16px;">🔔 Chamado atualizado</h2>
            <table style="width:100%;border-collapse:collapse;">
                {tabela_row("Protocolo", protocolo, True)}
                {tabela_row("Novo Status", f'<span style="color:{cor};font-weight:700;">{novo_status}</span>')}
                {linha_atend}
                {tabela_row("Data", datetime.now(BRASILIA).strftime("%d/%m/%Y às %H:%M"), True)}
            </table>
            {caixa_msg}
            {botao_chamado(protocolo)}
        </div>
        {rodape_email()}
    </div>
    """
    return enviar_email(email_setor, assunto, corpo, protocolo, "atualizacao_status")

def email_conclusao_chamado(email_contabilidade, email_setor, protocolo, tipo, data_conclusao, atendente="", mensagem=""):
    """Avisa a conclusão. Quando 'mensagem' vem preenchida, o texto do chat entra
    no MESMO e-mail — evitando dois disparos para as mesmas pessoas."""
    assunto = f"ROC — Chamado {protocolo} concluído"
    linha_atend = tabela_row("Concluído por", atendente, True) if atendente else ""
    caixa_msg = bloco_mensagem(mensagem, "💬 Mensagem enviada junto com a conclusão")
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
                {linha_atend}
            </table>
            {caixa_msg}
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
    # A Contabilidade recebe cópia (BCC) de tudo e enxerga quem está em cópia direto
    # no card do chamado, então este e-mail de "você está em cópia" é redundante para ela:
    # não é enviado a ela diretamente nem em BCC.
    email_cont = _email_contabilidade()
    if email_cont and email_cont.strip().lower() == (email_setor or "").strip().lower():
        return True

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
    return enviar_email(email_setor, assunto, corpo, protocolo, "copia_chamado", copiar_contabilidade=False)

def email_troca_setor(email_novo, email_antigo, protocolo, setor_novo, setor_antigo):
    """Envia UM único e-mail avisando a transferência, com o novo setor e o antigo
    juntos (1º no 'Para', o outro em CC; a Contabilidade entra no BCC automático).
    Texto neutro, que serve para todos os destinatários."""
    destinos = []
    for e in (email_novo, email_antigo):
        el = (e or "").strip()
        if el and el.lower() not in [d.lower() for d in destinos]:
            destinos.append(el)
    if not destinos:
        return True

    assunto = f"ROC — Chamado {protocolo} transferido de setor"
    corpo = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#f9f9f9;padding:20px;border-radius:12px;">
        {cabecalho_email()}
        <div style="background:white;padding:24px;border-radius:0 0 8px 8px;border:1px solid #e8e8e8;">
            <h2 style="color:#041747;font-size:18px;margin:0 0 8px;">🔄 Chamado transferido de setor</h2>
            <p style="color:#555;font-size:14px;margin:0 0 16px;">
            Este chamado foi <strong>transferido do setor {setor_antigo} para o setor {setor_novo}</strong>,
            que passa a ser o responsável por dar andamento.</p>
            <table style="width:100%;border-collapse:collapse;">
                {tabela_row("Protocolo", protocolo, True)}
                {tabela_row("Setor anterior", setor_antigo)}
                {tabela_row("Novo setor responsável", setor_novo, True)}
                {tabela_row("Data da transferência", datetime.now(BRASILIA).strftime("%d/%m/%Y às %H:%M"))}
            </table>
            {botao_chamado(protocolo)}
        </div>
        {rodape_email()}
    </div>
    """
    return enviar_email(destinos, assunto, corpo, protocolo, "troca_setor")
