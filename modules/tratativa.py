import streamlit as st
import base64
from database.connection import run_query
from datetime import datetime
from zoneinfo import ZoneInfo
from modules.email_service import enviar_email, email_novo_chamado, email_setor_em_copia

BRASILIA = ZoneInfo("America/Sao_Paulo")
TIPO_FOLHA = "Folha de Pagamento"

def buscar_setores():
    rows = run_query(
        "SELECT nome, email, setor_nome FROM usuarios WHERE perfil='setor' AND ativo=1 ORDER BY nome",
        fetch=True)
    return rows if rows else []

@st.cache_data(ttl=120)
def carregar_vinculos_trat():
    rows = run_query("SELECT inconsistencia, movimentacao FROM vinculo_inconsistencia_movimentacao", fetch=True)
    mapa = {}
    com_vinculo = set()
    if rows:
        for inc, mov in rows:
            mapa.setdefault(mov, set()).add(inc)
            com_vinculo.add(inc)
    return mapa, com_vinculo

def filtrar_inconsistencias_trat(tipos_lista, tipo_mov):
    mapa, com_vinculo = carregar_vinculos_trat()
    vinc_do_tipo = mapa.get(tipo_mov, set())
    return [inc for inc in tipos_lista if (inc in vinc_do_tipo) or (inc not in com_vinculo)]

def _valor_float(v):
    v = (v or "").strip()
    if not v:
        return None
    try:
        return float(v.replace(".", "").replace(",", "."))
    except:
        try:
            return float(v)
        except:
            return None

def gerar_protocolo():
    total = run_query("SELECT COUNT(*) FROM chamados", fetch=True)[0][0]
    return f"ROC-{datetime.now(BRASILIA).strftime('%Y%m')}-{str(total+1).zfill(4)}"

def salvar_copia(protocolo, setor):
    try:
        run_query("INSERT INTO chamados_copia (protocolo, setor) VALUES (%s,%s)", (protocolo, setor))
    except:
        pass

def criar_chamado_tratativa(setor_destino, empresa, tipo_inconsistencia, tipo_nota,
                            nome_parceiro, numero_nota, valor, observacao,
                            nu_financeiro, nu_nota, anexo_nome, anexo_bytes, solicitante,
                            prioridade="Normal", nf_retorna="", financeiro_baixado="",
                            data_entrada=None, data_negociacao=None):
    """Cria o chamado direto no setor responsavel, ja em 'Em andamento' (aberto pela Contabilidade)."""
    protocolo = gerar_protocolo()
    anexo_dados = None
    if anexo_bytes:
        anexo_dados = base64.b64encode(anexo_bytes).decode("utf-8")

    run_query("""INSERT INTO chamados (protocolo,setor,empresa,tipo_inconsistencia,prioridade,nf_retorna,
        solicitante,nome_parceiro,numero_nota,tipo_nota,data_entrada,data_saida,data_negociacao,
        valor,observacao,arquivo_nome,status,aberto_em,financeiro_baixado,anexo_dados,
        num_unico_financeiro,num_unico_nota)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (protocolo, setor_destino, empresa or "", tipo_inconsistencia, prioridade or "Normal", nf_retorna or "",
         solicitante, (nome_parceiro or "").strip(), (numero_nota or "").strip(), tipo_nota or "",
         data_entrada or None, None, data_negociacao or None,
         _valor_float(valor), (observacao or "").strip(), anexo_nome, "Em andamento",
         datetime.now(BRASILIA).strftime("%Y-%m-%d %H:%M:%S"), financeiro_baixado or "", anexo_dados,
         (nu_financeiro or "").strip() or None, (nu_nota or "").strip() or None))

    # Log para a lista "Chamados abertos pela Contabilidade"
    try:
        run_query("""INSERT INTO solicitacoes_tratativa
            (setor_destino, empresa, tipo_inconsistencia, nome_parceiro, numero_nota,
            tipo_nota, valor, observacao, criado_por, criado_em, status, num_unico_financeiro, num_unico_nota)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (setor_destino, empresa or "", tipo_inconsistencia, (nome_parceiro or "").strip(),
             (numero_nota or "").strip(), tipo_nota or "", (valor or "").strip(),
             (observacao or "").strip(), solicitante,
             datetime.now(BRASILIA).strftime("%Y-%m-%d %H:%M:%S"), "Em andamento",
             (nu_financeiro or "").strip() or None, (nu_nota or "").strip() or None))
    except:
        pass

    return protocolo

def tela_tratativa():
    st.title("📤 Abertura de Chamado pela Contabilidade")
    st.markdown("A Contabilidade abre o chamado **direto para o setor responsável** — ele aparece em "
                "**Minhas Solicitações** do setor, já em andamento.")
    st.markdown("---")

    setores = buscar_setores()
    if not setores:
        st.warning("Nenhum setor cadastrado com e-mail. Cadastre os setores primeiro.")
        return

    opcoes_setores = {f"{s[0]} ({s[1] or 'sem e-mail'})": s for s in setores}
    mapa_email = {s[0]: s[1] for s in setores}

    tipos = run_query("SELECT nome FROM tipos_inconsistencia WHERE ativo=1 ORDER BY nome", fetch=True)
    tipos_lista = [t[0] for t in tipos] if tipos else []

    st.markdown("#### 📧 Setor Responsavel *")
    setor_sel_key = st.selectbox("Selecione o setor", [""] + list(opcoes_setores.keys()), label_visibility="collapsed")
    setor_dados = opcoes_setores.get(setor_sel_key)
    nome_resp = setor_dados[0] if setor_dados else None
    nomes_copia = [s[0] for s in setores if s[1] and s[0] != nome_resp]

    st.markdown("---")
    st.markdown("#### 🗂️ Tipo de Movimentacao")
    tipos_nota_rows = run_query("SELECT nome FROM tipos_nota WHERE ativo=1 ORDER BY nome", fetch=True)
    tipos_movimentacao = [t[0] for t in tipos_nota_rows] if tipos_nota_rows else []
    if "INFORMAR ENTREGÁVEIS" in tipos_movimentacao:
        tipos_movimentacao.remove("INFORMAR ENTREGÁVEIS")
        tipos_movimentacao.insert(0, "INFORMAR ENTREGÁVEIS")
    if TIPO_FOLHA in tipos_movimentacao:
        tipos_movimentacao.remove(TIPO_FOLHA)
        tipos_movimentacao.append(TIPO_FOLHA)
    tipo_nota = st.session_state.get("trat_tipo_nota", None)
    if not tipos_movimentacao:
        st.warning("⚠️ Nenhum tipo de movimentacao cadastrado. Cadastre no painel Admin.")
        return
    cols_nota = st.columns(min(len(tipos_movimentacao), 4))
    for i, op in enumerate(tipos_movimentacao):
        with cols_nota[i % len(cols_nota)]:
            ativo = tipo_nota == op
            if st.button(f"{'✓ ' if ativo else ''}{op}", key=f"trat_nota_{i}",
                use_container_width=True, type="primary" if ativo else "secondary"):
                st.session_state["trat_tipo_nota"] = op
                st.rerun()
    tipo_nota = st.session_state.get("trat_tipo_nota", None)
    if not tipo_nota:
        st.info("Selecione o tipo de movimentação para continuar.")
        _lista_enviados()
        return

    # ===== FLUXO REDUZIDO: Folha de Pagamento (Setor + Empresa + Anexo + Observacao) =====
    if tipo_nota == TIPO_FOLHA:
        st.markdown("#### 🏢 Empresa *")
        emp_sel = st.session_state.get("trat_folha_emp", None)
        cols_e = st.columns(5)
        for i, op in enumerate(["1","2","6","13","14"]):
            with cols_e[i]:
                ativo = emp_sel == op
                if st.button(f"{'✓ ' if ativo else ''}{op}", key=f"trat_folha_emp_{i}",
                    use_container_width=True, type="primary" if ativo else "secondary"):
                    st.session_state["trat_folha_emp"] = op
                    st.rerun()
        empresa_f = st.session_state.get("trat_folha_emp", None)

        st.markdown("---")
        arq_f = st.file_uploader("📎 Anexo *", type=["pdf","png","jpg","jpeg","xlsx","xml","docx"], key="trat_folha_arq")
        obs_f = st.text_area("📝 Observacao *", placeholder="Descreva a solicitação...", key="trat_folha_obs")

        st.markdown("---")
        if st.button("📨 Abrir Chamado para o Setor", use_container_width=True, key="trat_folha_enviar"):
            erros = []
            if not setor_dados: erros.append("Setor responsavel")
            if not empresa_f: erros.append("Empresa")
            if arq_f is None: erros.append("Anexo")
            if not obs_f.strip(): erros.append("Observacao")
            if erros:
                st.error(f"Preencha: {', '.join(erros)}")
                return
            setor_nome = setor_dados[0]
            email_setor = setor_dados[1]
            anexo_bytes = arq_f.getvalue()
            anexo_nome = arq_f.name
            protocolo = criar_chamado_tratativa(setor_nome, empresa_f, TIPO_FOLHA, TIPO_FOLHA,
                "", "", "", obs_f.strip(), "", "", anexo_nome, anexo_bytes, st.session_state.usuario)
            try:
                if email_setor:
                    email_novo_chamado(email_setor, protocolo, setor_nome, TIPO_FOLHA, "Normal",
                        "", "", st.session_state.usuario, anexos=[(anexo_nome, anexo_bytes)])
            except:
                pass
            for k in ["trat_tipo_nota","trat_folha_emp","trat_folha_obs","trat_folha_arq"]:
                st.session_state.pop(k, None)
            st.cache_data.clear()
            st.success(f"✅ Chamado **{protocolo}** aberto para {setor_nome} (Em andamento).")
            st.balloons()
        st.markdown("---")
        _lista_enviados()
        return

    # ===== FLUXO NORMAL (todos os campos da tela do setor) =====
    eh_compra = "compra" in tipo_nota.lower()
    if eh_compra:
        data_ent = st.date_input("📥 Data da Nota *", value=None, key="trat_data_ent")
        data_neg = None
    else:
        data_neg = st.date_input("🤝 Data de Negociação *", value=None, key="trat_data_neg")
        data_ent = None

    st.markdown("---")
    st.markdown("#### 📋 Tipo de Inconsistencia *")
    tipo_sel = st.session_state.get("trat_tipo", None)
    tipos_filtrados = filtrar_inconsistencias_trat(tipos_lista, tipo_nota)
    tipos_com_outros = tipos_filtrados + ["Outros"]
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

    st.markdown("#### 🏢 Empresa *")
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

    st.markdown("#### 🚦 Prioridade *")
    prio_sel = st.session_state.get("trat_prioridade", None)
    cols_prio = st.columns(2)
    for i, op in enumerate(["Normal","Urgente"]):
        with cols_prio[i]:
            ativo = prio_sel == op
            if st.button(f"{'✓ ' if ativo else ''}{op}", key=f"trat_prio_{i}",
                use_container_width=True, type="primary" if ativo else "secondary"):
                st.session_state["trat_prioridade"] = op
                st.rerun()
    prioridade = st.session_state.get("trat_prioridade", None)

    st.markdown("#### 🔄 NF retornará ao sistema? *")
    nf_sel = st.session_state.get("trat_nf", None)
    cols_nf = st.columns(2)
    for i, op in enumerate(["Sim","Não"]):
        with cols_nf[i]:
            ativo = nf_sel == op
            if st.button(f"{'✓ ' if ativo else ''}{op}", key=f"trat_nf_{i}",
                use_container_width=True, type="primary" if ativo else "secondary"):
                st.session_state["trat_nf"] = op
                st.rerun()
    nf_retorna = st.session_state.get("trat_nf", None)

    st.markdown("#### 💰 Financeiro Baixado? *")
    fin_sel = st.session_state.get("trat_fin", None)
    cols_fin = st.columns(2)
    for i, op in enumerate(["Sim","Não"]):
        with cols_fin[i]:
            ativo = fin_sel == op
            if st.button(f"{'✓ ' if ativo else ''}{op}", key=f"trat_fin_{i}",
                use_container_width=True, type="primary" if ativo else "secondary"):
                st.session_state["trat_fin"] = op
                st.rerun()
    fin_baixado = st.session_state.get("trat_fin", None)

    st.markdown("---")
    with st.form("form_tratativa", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            solicitante = st.text_input("🙋 Nome do Solicitante *")
            nome_parceiro = st.text_input("👤 Nome do Parceiro *")
        with col2:
            numero_nota = st.text_input("📄 Numero da Nota *")
            valor = st.text_input("💰 Valor *", placeholder="0,00")
        col3, col4 = st.columns(2)
        with col3:
            nu_financeiro = st.text_input("🔢 NU Financeiro (opcional)")
        with col4:
            nu_nota = st.text_input("🔢 NU Nota (opcional)")
        copia_sel = st.multiselect("👥 Setores em cópia (opcional)", nomes_copia,
            help="Esses setores recebem aviso do chamado em cópia.")
        arquivo = st.file_uploader("📎 Anexo (opcional)", type=["pdf","png","jpg","jpeg","xlsx","xml","docx"])
        observacao = st.text_area("📝 Observacao para o setor *",
            placeholder="Descreva a inconsistencia identificada e o que o setor deve fazer...")
        enviar = st.form_submit_button("📨 Abrir Chamado para o Setor", use_container_width=True)

    if enviar:
        erros = []
        if not setor_dados: erros.append("Setor responsavel")
        if not tipo: erros.append("Tipo de Inconsistencia")
        if tipo == "Outros" and not tipo_outros_desc.strip(): erros.append("Descricao da inconsistencia")
        if not empresa: erros.append("Empresa")
        if not prioridade: erros.append("Prioridade")
        if not nf_retorna: erros.append("NF retornará")
        if not fin_baixado: erros.append("Financeiro Baixado")
        if not solicitante.strip(): erros.append("Nome do Solicitante")
        if not nome_parceiro.strip(): erros.append("Nome do Parceiro")
        if not numero_nota.strip(): erros.append("Numero da Nota")
        if not valor.strip(): erros.append("Valor")
        if eh_compra and not data_ent: erros.append("Data da Nota")
        if not eh_compra and not data_neg: erros.append("Data de Negociação")
        if not observacao.strip(): erros.append("Observacao")
        if erros:
            st.error(f"Preencha: {', '.join(erros)}")
            return

        setor_nome = setor_dados[0]
        email_setor = setor_dados[1]
        tipo_final = f"Outros: {tipo_outros_desc.strip()}" if tipo == "Outros" else (tipo or "")
        anexo_bytes = arquivo.getvalue() if arquivo is not None else None
        anexo_nome = arquivo.name if arquivo is not None else None

        protocolo = criar_chamado_tratativa(setor_nome, empresa, tipo_final, tipo_nota,
            nome_parceiro, numero_nota, valor, observacao,
            nu_financeiro, nu_nota, anexo_nome, anexo_bytes, solicitante.strip(),
            prioridade=prioridade, nf_retorna=nf_retorna, financeiro_baixado=fin_baixado,
            data_entrada=data_ent or None, data_negociacao=data_neg or None)

        try:
            if email_setor:
                anexos = [(anexo_nome, anexo_bytes)] if anexo_bytes else None
                email_novo_chamado(email_setor, protocolo, setor_nome, tipo_final, prioridade,
                    nome_parceiro.strip(), numero_nota.strip(), solicitante.strip(), anexos=anexos,
                    nu_financeiro=nu_financeiro.strip(), nu_nota=nu_nota.strip())
        except:
            pass

        copias_enviadas = []
        for n in copia_sel:
            em = mapa_email.get(n)
            if em and em != email_setor:
                try:
                    salvar_copia(protocolo, n)
                    email_setor_em_copia(em, protocolo, n, setor_nome)
                    copias_enviadas.append(n)
                except:
                    pass

        for k in ["trat_tipo_nota","trat_empresa","trat_tipo","trat_outros","trat_prioridade",
                  "trat_nf","trat_fin","trat_data_ent","trat_data_neg"]:
            st.session_state.pop(k, None)
        st.cache_data.clear()
        msg = f"✅ Chamado **{protocolo}** aberto para {setor_nome} (Em andamento)."
        if copias_enviadas:
            msg += f" Em cópia: {', '.join(copias_enviadas)}."
        st.success(msg)
        st.balloons()

    st.markdown("---")
    _lista_enviados()

def _lista_enviados():
    st.subheader("📋 Chamados abertos pela Contabilidade")
    solicitacoes = run_query("""SELECT setor_destino, empresa, tipo_inconsistencia,
        nome_parceiro, numero_nota, status, criado_em
        FROM solicitacoes_tratativa ORDER BY criado_em DESC LIMIT 50""", fetch=True)
    if not solicitacoes:
        st.info("Nenhum chamado aberto pela Contabilidade ainda.")
        return
    for s in solicitacoes:
        setor_d, emp, tipo_i, parceiro, nf, status, criado_em = s
        cor = "#f59e0b" if status == "Em andamento" else "#22c55e"
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
