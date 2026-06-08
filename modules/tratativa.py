import streamlit as st
from database.connection import run_query
from datetime import datetime
from zoneinfo import ZoneInfo
from modules.email_service import enviar_email

BRASILIA = ZoneInfo("America/Sao_Paulo")

def get_url_base():
    try:
        return st.secrets.get("APP_URL", "https://registro-de-ocorr-ncia---system.streamlit.app")
    except:
        return "https://registro-de-ocorr-ncia---system.streamlit.app"

def buscar_setores():
    rows = run_query(
        "SELECT nome, email, setor_nome FROM usuarios WHERE perfil='setor' AND ativo=1 ORDER BY nome",
        fetch=True)
    return rows if rows else []

def email_solicitacao_tratativa(email_setor, setor_nome, empresa, tipo, parceiro, numero_nota, tipo_nota, valor, observacao, criado_por):
    url = get_url_base()
    assunto = "ROC — Solicitacao de Tratativa - Origem Contabilidade"
    corpo = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#f9f9f9;padding:20px;border-radius:12px;">
        <div style="background:#041747;padding:20px;border-radius:8px 8px 0 0;text-align:center;">
            <h1 style="color:#FAC318;font-size:24px;margin:0;letter-spacing:4px;">ROC</h1>
            <p style="color:rgba(255,255,255,0.7);font-size:12px;margin:4px 0 0;">
            Registro de Ocorrencias Contabeis — Grupo LLE</p>
        </div>
        <div style="background:white;padding:24px;border-radius:0 0 8px 8px;border:1px solid #e8e8e8;">
            <h2 style="color:#041747;font-size:18px;margin:0 0 8px;">📋 Solicitacao de Tratativa</h2>
            <p style="color:#666;font-size:13px;margin:0 0 20px;">
            A Contabilidade identificou uma inconsistencia e solicita que seu setor abra um ROC
            com as informacoes abaixo.</p>

            <table style="width:100%;border-collapse:collapse;">
                <tr><td style="padding:8px;background:#f5f7fa;font-weight:600;color:#041747;width:40%;">Setor Responsavel</td><td style="padding:8px;color:#333;">{setor_nome}</td></tr>
                <tr><td style="padding:8px;font-weight:600;color:#041747;">Empresa</td><td style="padding:8px;color:#333;">{empresa or "—"}</td></tr>
                <tr><td style="padding:8px;background:#f5f7fa;font-weight:600;color:#041747;">Tipo de Inconsistencia</td><td style="padding:8px;color:#333;">{tipo or "—"}</td></tr>
                <tr><td style="padding:8px;font-weight:600;color:#041747;">Tipo de Movimentacao</td><td style="padding:8px;color:#333;">{tipo_nota or "—"}</td></tr>
                <tr><td style="padding:8px;background:#f5f7fa;font-weight:600;color:#041747;">Nome do Parceiro</td><td style="padding:8px;color:#333;">{parceiro or "—"}</td></tr>
                <tr><td style="padding:8px;font-weight:600;color:#041747;">Numero da Nota</td><td style="padding:8px;color:#333;">{numero_nota or "—"}</td></tr>
                <tr><td style="padding:8px;background:#f5f7fa;font-weight:600;color:#041747;">Valor</td><td style="padding:8px;color:#333;">{valor or "—"}</td></tr>
            </table>

            {"<div style='margin-top:16px;padding:14px;background:#FFF8E7;border-left:4px solid #FAC318;border-radius:4px;'><p style='font-size:13px;font-weight:600;color:#041747;margin:0 0 6px;'>Observacao da Contabilidade:</p><p style='font-size:13px;color:#333;margin:0;'>" + observacao + "</p></div>" if observacao else ""}

            <div style="margin-top:24px;padding:16px;background:#EFF6FF;border-radius:8px;border:1px solid #BFDBFE;">
                <p style="font-size:13px;color:#041747;font-weight:600;margin:0 0 8px;">📌 Instrucoes:</p>
                <p style="font-size:13px;color:#555;margin:0 0 12px;">
                Clique no botao abaixo para acessar o ROC e abrir o chamado com as informacoes acima.</p>
                <div style="text-align:center;">
                    <a href="{url}" style="background:#041747;color:white;padding:12px 28px;
                    border-radius:8px;text-decoration:none;font-family:Arial,sans-serif;
                    font-size:14px;font-weight:600;display:inline-block;">
                    🔗 Abrir ROC e registrar chamado
                    </a>
                </div>
            </div>
        </div>
        <p style="text-align:center;font-size:11px;color:#999;margin-top:12px;">
        ROC 2026 · Grupo LLE · Solicitacao enviada por: {criado_por}</p>
    </div>
    """
    return enviar_email(email_setor, assunto, corpo, None, "solicitacao_tratativa")

def tela_tratativa():
    st.title("📤 Solicitacao de Tratativa")
    st.markdown("Identifique a inconsistencia e solicite ao setor que abra um ROC.")
    st.markdown("---")

    setores = buscar_setores()
    if not setores:
        st.warning("Nenhum setor cadastrado com e-mail. Cadastre os setores primeiro.")
        return

    opcoes_setores = {f"{s[0]} ({s[1] or 'sem e-mail'})": s for s in setores}

    tipos = run_query("SELECT nome FROM tipos_inconsistencia WHERE ativo=1 ORDER BY nome", fetch=True)
    tipos_lista = [t[0] for t in tipos] if tipos else []

    st.markdown("#### 📧 Setor Responsavel *")
    setor_sel_key = st.selectbox("Selecione o setor", [""] + list(opcoes_setores.keys()), label_visibility="collapsed")
    setor_dados = opcoes_setores.get(setor_sel_key)

    st.markdown("---")

    st.markdown("#### 🗂️ Tipo de Movimentacao")
    tipo_nota = st.session_state.get("trat_tipo_nota", None)
    cols_nota = st.columns(2)
    for i, op in enumerate(["Compra", "Venda"]):
        with cols_nota[i]:
            ativo = tipo_nota == op
            if st.button(f"{'✓ ' if ativo else ''}{op}", key=f"trat_nota_{i}",
                use_container_width=True, type="primary" if ativo else "secondary"):
                st.session_state["trat_tipo_nota"] = op
                st.rerun()
    tipo_nota = st.session_state.get("trat_tipo_nota", None)

    st.markdown("#### 🏢 Empresa")
    empresa_sel = st.session_state.get("trat_empresa", None)
    cols_emp = st.columns(5)
    for i, op in enumerate(["1","2","6","13","14"]):
        with cols_emp[i]:
            ativo = empresa_sel == op
            if st.button(f"{'✓ ' if ativo else ''}{op}", key=f"trat_emp_{i}",
                use_container_width=True, type="primary" if ativo else "secondary"):
                st.session_state["trat_empresa"] = op
                st.rerun()
    empresa = st.session_state.get("trat_empresa", None)

    st.markdown("#### 📋 Tipo de Inconsistencia")
    tipo_sel = st.session_state.get("trat_tipo", None)
    tipos_com_outros = tipos_lista + ["Outros"]
    cols_tipo = st.columns(min(len(tipos_com_outros), 4))
    for i, op in enumerate(tipos_com_outros):
        with cols_tipo[i % len(cols_tipo)]:
            ativo = tipo_sel == op
            if st.button(f"{'✓ ' if ativo else ''}{op}", key=f"trat_tipo_{i}",
                use_container_width=True, type="primary" if ativo else "secondary"):
                st.session_state["trat_tipo"] = op
                st.rerun()
    tipo = st.session_state.get("trat_tipo", None)

    tipo_outros_desc = ""
    if tipo == "Outros":
        tipo_outros_desc = st.text_area("Descreva a inconsistencia *", key="trat_outros")

    st.markdown("---")

    with st.form("form_tratativa", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            nome_parceiro = st.text_input("👤 Nome do Parceiro")
            numero_nota = st.text_input("📄 Numero da Nota")
        with col2:
            valor = st.text_input("💰 Valor", placeholder="0,00")
        observacao = st.text_area("📝 Observacao para o setor *",
            placeholder="Descreva a inconsistencia identificada e o que o setor deve fazer...")
        enviar = st.form_submit_button("📨 Enviar Solicitacao", use_container_width=True)

    if enviar:
        erros = []
        if not setor_dados: erros.append("Setor responsavel")
        if not observacao.strip(): erros.append("Observacao")
        if tipo == "Outros" and not tipo_outros_desc.strip(): erros.append("Descricao da inconsistencia")
        if erros:
            st.error(f"Preencha: {', '.join(erros)}")
            return

        setor_nome = setor_dados[0]
        email_setor = setor_dados[1]

        if not email_setor:
            st.error(f"O setor {setor_nome} nao tem e-mail cadastrado. Atualize em Administracao.")
            return

        tipo_final = f"Outros: {tipo_outros_desc.strip()}" if tipo == "Outros" else (tipo or "")

        run_query("""INSERT INTO solicitacoes_tratativa
            (setor_destino, empresa, tipo_inconsistencia, nome_parceiro, numero_nota,
            tipo_nota, valor, observacao, criado_por, criado_em, status)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (setor_nome, empresa or "", tipo_final, nome_parceiro.strip(),
             numero_nota.strip(), tipo_nota or "", valor.strip(),
             observacao.strip(), st.session_state.usuario,
             datetime.now(BRASILIA).strftime("%Y-%m-%d %H:%M:%S"), "Pendente"))

        ok = email_solicitacao_tratativa(
            email_setor, setor_nome, empresa or "—", tipo_final,
            nome_parceiro.strip(), numero_nota.strip(),
            tipo_nota or "—", valor.strip(), observacao.strip(),
            st.session_state.usuario)

        for k in ["trat_tipo_nota","trat_empresa","trat_tipo","trat_outros"]:
            st.session_state.pop(k, None)

        if ok:
            st.success(f"✅ Solicitacao enviada para {setor_nome} ({email_setor})!")
            st.balloons()
        else:
            st.warning("Solicitacao registrada mas houve erro no envio do e-mail.")

    st.markdown("---")
    st.subheader("📋 Solicitacoes enviadas")
    solicitacoes = run_query("""SELECT setor_destino, empresa, tipo_inconsistencia,
        nome_parceiro, numero_nota, status, criado_em
        FROM solicitacoes_tratativa ORDER BY criado_em DESC LIMIT 50""", fetch=True)

    if not solicitacoes:
        st.info("Nenhuma solicitacao enviada ainda.")
    else:
        for s in solicitacoes:
            setor_d, emp, tipo_i, parceiro, nf, status, criado_em = s
            cor = "#f59e0b" if status == "Pendente" else "#22c55e"
            st.markdown(f"""
            <div style='background:white;border:1px solid #e8e8e8;border-radius:8px;
            padding:12px 16px;margin-bottom:6px;'>
                <div style='display:flex;justify-content:space-between;align-items:center;'>
                    <span style='font-size:13px;font-weight:600;color:#041747;'>
                    {setor_d} — {parceiro or "—"} | NF: {nf or "—"}</span>
                    <span style='font-size:12px;color:{cor};font-weight:600;'>{status}</span>
                </div>
                <p style='font-size:12px;color:#666;margin:4px 0 0;'>
                Empresa: {emp or "—"} · Tipo: {tipo_i or "—"} · {criado_em}</p>
            </div>
            """, unsafe_allow_html=True)
