import streamlit as st
import os
import calendar
from datetime import datetime
from zoneinfo import ZoneInfo
from database.connection import run_query
from modules.email_service import (email_novo_chamado, email_atualizacao_chamado,
    email_conclusao_chamado, email_nova_mensagem, email_setor_em_copia)

BRASILIA = ZoneInfo("America/Sao_Paulo")

TIPO_FECHAMENTO = "INFORMAR ENTREGÁVEIS"
TIPO_FOLHA = "Folha de Pagamento"

def verificar_bloqueio(data_nota):
    if not data_nota: return False, ""
    agora = datetime.now(BRASILIA)
    hoje = agora.date()
    m, a, ma, aa = data_nota.month, data_nota.year, hoje.month, hoje.year
    if a == aa and m == ma: return False, ""
    if a < aa or (a == aa and m < ma - 1):
        return True, "⛔ O prazo para solicitações da competência selecionada foi encerrado."
    if agora > datetime(aa, ma, calendar.monthrange(aa, ma)[1], 17, 48, 0, tzinfo=BRASILIA):
        return True, "⛔ O prazo para solicitações da competência selecionada foi encerrado."
    return False, ""

def converter_valor(valor):
    v = valor.strip().replace(" ", "")
    if "," in v and "." in v: v = v.replace(".", "").replace(",", ".")
    elif "," in v: v = v.replace(",", ".")
    return float(v)

@st.cache_data(ttl=300)
def carregar_tipos():
    return [r[0] for r in run_query("SELECT nome FROM tipos_inconsistencia WHERE ativo=1 ORDER BY nome", fetch=True)]

@st.cache_data(ttl=120)
def carregar_vinculos():
    """Retorna (mapa_mov->set(inconsistencias), set de inconsistencias que têm algum vínculo)."""
    rows = run_query("SELECT inconsistencia, movimentacao FROM vinculo_inconsistencia_movimentacao", fetch=True)
    mapa = {}
    com_vinculo = set()
    if rows:
        for inc, mov in rows:
            mapa.setdefault(mov, set()).add(inc)
            com_vinculo.add(inc)
    return mapa, com_vinculo

def filtrar_inconsistencias(tipos_lista, tipo_mov):
    """Mostra inconsistências vinculadas ao tipo de movimentação + as sem nenhum vínculo (legado)."""
    mapa, com_vinculo = carregar_vinculos()
    vinc_do_tipo = mapa.get(tipo_mov, set())
    return [inc for inc in tipos_lista if (inc in vinc_do_tipo) or (inc not in com_vinculo)]

@st.cache_data(ttl=300)
def carregar_tipos_nota():
    tipos = [r[0] for r in run_query("SELECT nome FROM tipos_nota WHERE ativo=1 ORDER BY nome", fetch=True)]
    # Coloca "INFORMAR ENTREGÁVEIS" em primeiro lugar na fileira
    if TIPO_FECHAMENTO in tipos:
        tipos.remove(TIPO_FECHAMENTO)
        tipos.insert(0, TIPO_FECHAMENTO)
    # Coloca "Folha de Pagamento" por último
    if "Folha de Pagamento" in tipos:
        tipos.remove("Folha de Pagamento")
        tipos.append("Folha de Pagamento")
    return tipos

@st.cache_data(ttl=300)
def carregar_setores_disponiveis(excluir=None):
    rows = run_query("""SELECT DISTINCT setor_nome FROM usuarios
        WHERE perfil='setor' AND ativo=1 AND setor_nome IS NOT NULL AND setor_nome <> ''
        ORDER BY setor_nome""", fetch=True)
    lista = [r[0] for r in rows] if rows else []
    if excluir:
        lista = [s for s in lista if s != excluir]
    return lista

def carregar_copias(protocolo):
    rows = run_query("SELECT setor FROM chamados_copia WHERE protocolo=%s ORDER BY setor", (protocolo,), fetch=True)
    return [r[0] for r in rows] if rows else []

def salvar_copias(protocolo, setores):
    run_query("DELETE FROM chamados_copia WHERE protocolo=%s", (protocolo,))
    for s in setores:
        if s and s.strip():
            run_query("INSERT INTO chamados_copia (protocolo, setor) VALUES (%s, %s)", (protocolo, s.strip()))

@st.cache_data(ttl=60)
def carregar_meus_chamados(setor):
    return run_query("""SELECT protocolo, tipo_inconsistencia, empresa, status, prioridade,
        nome_parceiro, numero_nota, aberto_em, solicitante, financeiro_baixado
        FROM chamados WHERE setor=%s ORDER BY aberto_em DESC""", (setor,), fetch=True)

@st.cache_data(ttl=60)
def carregar_chamados_acompanhamento(setor):
    return run_query("""SELECT c.protocolo, c.tipo_inconsistencia, c.empresa, c.status, c.prioridade,
        c.nome_parceiro, c.numero_nota, c.aberto_em, c.solicitante, c.financeiro_baixado, c.setor
        FROM chamados c
        JOIN chamados_copia cc ON cc.protocolo = c.protocolo
        WHERE cc.setor = %s ORDER BY c.aberto_em DESC""", (setor,), fetch=True)

@st.cache_data(ttl=60)
def carregar_todos_chamados():
    return run_query("""SELECT protocolo, setor, tipo_inconsistencia, empresa, status, prioridade,
        nome_parceiro, numero_nota, aberto_em, solicitante, financeiro_baixado
        FROM chamados ORDER BY aberto_em DESC""", fetch=True)

def buscar_email_contabilidade():
    rows = run_query("SELECT email FROM usuarios WHERE perfil='contabilidade' AND ativo=1 LIMIT 1", fetch=True)
    return rows[0][0] if rows else None

def buscar_email_setor(setor_nome):
    rows = run_query("SELECT email FROM usuarios WHERE setor_nome=%s AND ativo=1 LIMIT 1", (setor_nome,), fetch=True)
    return rows[0][0] if rows else None

def emails_interessados(protocolo, setor_chamado, excluir_email=None):
    """Contabilidade (sempre) + setor dono + setores em cópia, menos quem está enviando."""
    emails = set()
    ec = buscar_email_contabilidade()
    if ec: emails.add(ec)
    es = buscar_email_setor(setor_chamado)
    if es: emails.add(es)
    for s in carregar_copias(protocolo):
        e = buscar_email_setor(s)
        if e: emails.add(e)
    if excluir_email:
        emails.discard(excluir_email)
    return emails

def carregar_mensagens(protocolo):
    return run_query("SELECT autor, perfil, mensagem, enviado_em, anexo_nome, anexo_dados FROM mensagens WHERE chamado_protocolo=%s ORDER BY enviado_em ASC", (protocolo,), fetch=True)

def enviar_mensagem_db(protocolo, autor, perfil, mensagem, anexo_nome=None, anexo_dados=None):
    run_query("INSERT INTO mensagens (chamado_protocolo,autor,perfil,mensagem,enviado_em,anexo_nome,anexo_dados) VALUES (%s,%s,%s,%s,%s,%s,%s)",
              (protocolo, autor, perfil, mensagem, datetime.now(BRASILIA).strftime("%Y-%m-%d %H:%M:%S"), anexo_nome, anexo_dados))

def _mime_imagem(nome):
    n = (nome or "").lower()
    if n.endswith(".png"): return "image/png"
    if n.endswith(".gif"): return "image/gif"
    if n.endswith(".webp"): return "image/webp"
    return "image/jpeg"

def _eh_imagem(nome):
    n = (nome or "").lower()
    return n.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))

def _fmt_valor(v):
    if v is None or v == "":
        return None
    try:
        return "R$ " + f"{float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return str(v)

def exibir_chat(protocolo, setor_chamado):
    st.markdown("#### 💬 Acompanhamento")
    mensagens = carregar_mensagens(protocolo)
    if not mensagens:
        st.markdown("<div style='background:#f9f9f9;border-radius:10px;padding:16px;text-align:center;color:#999;font-size:13px;'>Nenhuma mensagem ainda.</div>", unsafe_allow_html=True)
    else:
        import base64
        for idx, (autor, perfil, mensagem, enviado_em, anexo_nome, anexo_dados) in enumerate(mensagens):
            is_cont = perfil == "contabilidade"
            alinha = "flex-end" if is_cont else "flex-start"
            bg = "#041747" if is_cont else "#F0F4FF"
            cor_txt = "white" if is_cont else "#041747"
            cor_meta = "rgba(255,255,255,0.7)" if is_cont else "#666"
            border_r = "14px 14px 4px 14px" if is_cont else "14px 14px 14px 4px"
            txt_html = f"<p style='font-size:13px;margin:0;'>{mensagem}</p>" if mensagem else ""
            img_html = ""
            if anexo_dados and _eh_imagem(anexo_nome):
                mime = _mime_imagem(anexo_nome)
                img_html = f"<img src='data:{mime};base64,{anexo_dados}' style='max-width:100%;border-radius:8px;margin-top:8px;display:block;'/>"
            arq_html = ""
            if anexo_dados and not _eh_imagem(anexo_nome):
                arq_html = f"<p style='font-size:12px;margin:8px 0 0;'>📎 {anexo_nome or 'anexo'}</p>"
            st.markdown(f"""
            <div style='display:flex;justify-content:{alinha};margin-bottom:10px;'>
                <div style='max-width:75%;background:{bg};color:{cor_txt};border-radius:{border_r};padding:10px 14px;box-shadow:0 1px 4px rgba(0,0,0,0.08);'>
                    <p style='font-size:11px;font-weight:700;margin:0 0 4px;color:{cor_meta};'>{autor}</p>
                    {txt_html}{img_html}{arq_html}
                    <p style='font-size:10px;margin:6px 0 0;color:{cor_meta};text-align:right;'>{enviado_em}</p>
                </div>
            </div>""", unsafe_allow_html=True)
            if anexo_dados and not _eh_imagem(anexo_nome):
                try:
                    st.download_button(f"📎 Baixar {anexo_nome or 'anexo'}",
                        data=base64.b64decode(anexo_dados),
                        file_name=anexo_nome or "anexo", key=f"chatdl_{protocolo}_{idx}")
                except:
                    pass

    st.markdown("<br>", unsafe_allow_html=True)
    with st.form(key=f"chat_{protocolo}", clear_on_submit=True):
        nova_msg = st.text_area("Nova mensagem", placeholder="Digite sua mensagem...", height=80, label_visibility="collapsed")
        img = st.file_uploader("📎 Anexar arquivo (opcional)", type=["png","jpg","jpeg","gif","webp","pdf","xlsx","xls","xml","docx","csv","txt"], key=f"chat_img_{protocolo}")
        if st.form_submit_button("📨 Enviar", use_container_width=True):
            tem_texto = bool(nova_msg.strip())
            tem_img = img is not None
            if not tem_texto and not tem_img:
                st.warning("Digite uma mensagem ou anexe um arquivo antes de enviar.")
            else:
                anexo_nome = None
                anexo_dados = None
                if tem_img:
                    import base64
                    anexo_nome = img.name
                    anexo_dados = base64.b64encode(img.getvalue()).decode("utf-8")
                enviar_mensagem_db(protocolo, st.session_state.usuario, st.session_state.perfil,
                                   nova_msg.strip(), anexo_nome, anexo_dados)
                try:
                    texto_email = nova_msg.strip() if tem_texto else "[anexo enviado]"
                    destinos = emails_interessados(protocolo, setor_chamado, st.session_state.get("email"))
                    for email_dest in destinos:
                        email_nova_mensagem(email_dest, protocolo, st.session_state.usuario, texto_email)
                except:
                    pass
                st.rerun()


def registrar_fechamento(parcial, observacao="", anexo_nome=None, anexo_bytes=None, atrasos=""):
    tipo_final = f"{TIPO_FECHAMENTO} - {parcial}"
    total = run_query("SELECT COUNT(*) FROM chamados", fetch=True)[0][0]
    protocolo = f"ROC-{datetime.now(BRASILIA).strftime('%Y%m')}-{str(total+1).zfill(4)}"

    anexo_dados = None
    if anexo_bytes:
        import base64
        anexo_dados = base64.b64encode(anexo_bytes).decode("utf-8")

    run_query("""INSERT INTO chamados (protocolo,setor,empresa,tipo_inconsistencia,prioridade,nf_retorna,
        solicitante,nome_parceiro,numero_nota,tipo_nota,data_entrada,data_saida,data_negociacao,
        valor,observacao,arquivo_nome,status,aberto_em,financeiro_baixado,anexo_dados,atrasos_entregaveis)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (protocolo, st.session_state.setor, "", tipo_final, "Normal", "",
         st.session_state.usuario, "", "", TIPO_FECHAMENTO,
         None, None, None,
         None, (observacao or "").strip(), anexo_nome, "Aberto",
         datetime.now(BRASILIA).strftime("%Y-%m-%d %H:%M:%S"), "", anexo_dados,
         (atrasos or "").strip() or None))

    try:
        email_cont = buscar_email_contabilidade()
        if email_cont:
            anexos = [(anexo_nome, anexo_bytes)] if anexo_bytes else None
            email_novo_chamado(email_cont, protocolo, st.session_state.setor,
                tipo_final, "Normal", "", "", st.session_state.usuario, anexos=anexos,
                atrasos=(atrasos or "").strip())
    except:
        pass

    return protocolo

def registrar_folha(empresa, fin_baixado, solicitante, observacao, anexo_nome, anexo_bytes):
    total = run_query("SELECT COUNT(*) FROM chamados", fetch=True)[0][0]
    protocolo = f"ROC-{datetime.now(BRASILIA).strftime('%Y%m')}-{str(total+1).zfill(4)}"

    anexo_dados = None
    if anexo_bytes:
        import base64
        anexo_dados = base64.b64encode(anexo_bytes).decode("utf-8")

    run_query("""INSERT INTO chamados (protocolo,setor,empresa,tipo_inconsistencia,prioridade,nf_retorna,
        solicitante,nome_parceiro,numero_nota,tipo_nota,data_entrada,data_saida,data_negociacao,
        valor,observacao,arquivo_nome,status,aberto_em,financeiro_baixado,anexo_dados)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (protocolo, st.session_state.setor, empresa, TIPO_FOLHA, "Normal", "",
         solicitante, "", "", TIPO_FOLHA,
         None, None, None,
         None, observacao, anexo_nome, "Aberto",
         datetime.now(BRASILIA).strftime("%Y-%m-%d %H:%M:%S"), fin_baixado, anexo_dados))

    try:
        email_cont = buscar_email_contabilidade()
        if email_cont:
            anexos = [(anexo_nome, anexo_bytes)] if anexo_bytes else None
            email_novo_chamado(email_cont, protocolo, st.session_state.setor,
                TIPO_FOLHA, "Normal", "", "", solicitante, anexos=anexos)
    except:
        pass

    return protocolo

def tela_novo_chamado(preview=False, setor_preview=None):
    setor_atual = setor_preview if (preview and setor_preview) else st.session_state.get("setor")
    st.title("➕ Novo Chamado")
    if preview:
        st.info("👁️ Modo visualização — esta é a tela que os setores enxergam. Nenhum chamado será criado aqui.")
    st.markdown(f"**Setor:** {setor_atual}")
    st.markdown("Preencha todos os campos obrigatórios.")
    st.markdown("---")

    tipos = carregar_tipos()
    tipos_movimentacao = carregar_tipos_nota()
    if not tipos_movimentacao:
        st.warning("⚠️ Nenhum tipo de movimentação cadastrado. Solicite o cadastro no painel Admin.")
        return

    # 1) Tipo de Movimentação (sempre no topo)
    st.markdown("#### 🗂️ Tipo de Movimentação *")
    tipo_nota = st.session_state.get("sel_tipo_nota", None)
    cols_mov = st.columns(min(len(tipos_movimentacao), 4))
    for i, op in enumerate(tipos_movimentacao):
        with cols_mov[i % len(cols_mov)]:
            ativo = tipo_nota == op
            if st.button(f"{'✓ ' if ativo else ''}{op}", key=f"sel_tipo_nota_{i}", use_container_width=True, type="primary" if ativo else "secondary"):
                st.session_state["sel_tipo_nota"] = op
                st.rerun()
    tipo_nota = st.session_state.get("sel_tipo_nota", None)
    if not tipo_nota:
        st.info("Selecione o tipo de movimentação para continuar.")
        return

    # === FLUXO ESPECIAL: Informar fechamento de período (só entrega + período) ===
    if tipo_nota == TIPO_FECHAMENTO:
        st.markdown("---")
        st.markdown("#### 📅 Qual fechamento parcial? *")
        parciais = ["1º Parcial", "2º Parcial", "3º Parcial", "4º Parcial"]
        parcial_sel = st.session_state.get("sel_parcial", None)
        cols_p = st.columns(4)
        for i, op in enumerate(parciais):
            with cols_p[i]:
                ativo = parcial_sel == op
                if st.button(f"{'✓ ' if ativo else ''}{op}", key=f"sel_parcial_{i}", use_container_width=True, type="primary" if ativo else "secondary"):
                    st.session_state["sel_parcial"] = op
                    st.rerun()
        parcial = st.session_state.get("sel_parcial", None)

        st.markdown("---")
        obs_fech = st.text_area("📝 Observação (opcional)", placeholder="Informações adicionais sobre a entrega...", key="fech_obs")
        atrasos_fech = st.text_area("⏰ Atrasos de entregáveis (opcional)", placeholder="Descreva eventuais atrasos de entregáveis...", key="fech_atrasos")
        arq_fech = st.file_uploader("📎 Anexo de documentos (opcional)",
            type=["pdf","png","jpg","jpeg","xlsx","xml","docx"], key="fech_arquivo")

        st.markdown("---")
        if st.button("📨 Enviar Chamado", use_container_width=True, key="enviar_fechamento"):
            if preview:
                st.info("👁️ Modo visualização: nenhum chamado foi criado.")
                return
            if not parcial:
                st.error("⚠️ Selecione o fechamento parcial.")
                return
            anexo_nome = None
            anexo_bytes = None
            if arq_fech is not None:
                anexo_nome = arq_fech.name
                anexo_bytes = arq_fech.getvalue()
            protocolo = registrar_fechamento(parcial, obs_fech, anexo_nome, anexo_bytes, atrasos_fech)
            for k in ["sel_tipo_nota", "sel_parcial", "fech_obs", "fech_atrasos", "fech_arquivo"]:
                st.session_state.pop(k, None)
            st.cache_data.clear()
            st.success(f"✅ Chamado registrado! Protocolo: **{protocolo}**")
            st.balloons()
        return

    # === FLUXO ESPECIAL: Folha de Pagamento (campos reduzidos) ===
    if tipo_nota == TIPO_FOLHA:
        st.markdown("---")
        st.markdown("#### 🏢 Empresa *")
        emp_sel = st.session_state.get("folha_empresa", None)
        cols_e = st.columns(5)
        for i, op in enumerate(["1", "2", "6", "13", "14"]):
            with cols_e[i]:
                ativo = emp_sel == op
                if st.button(f"{'✓ ' if ativo else ''}{op}", key=f"folha_emp_{i}",
                    use_container_width=True, type="primary" if ativo else "secondary"):
                    st.session_state["folha_empresa"] = op
                    st.rerun()
        empresa_f = st.session_state.get("folha_empresa", None)

        st.markdown("#### 💰 Financeiro Baixado *")
        fin_sel = st.session_state.get("folha_fin", None)
        cfb = st.columns(2)
        for i, op in enumerate(["Sim", "Não"]):
            with cfb[i]:
                ativo = fin_sel == op
                if st.button(f"{'✓ ' if ativo else ''}{op}", key=f"folha_fin_{i}",
                    use_container_width=True, type="primary" if ativo else "secondary"):
                    st.session_state["folha_fin"] = op
                    st.rerun()
        fin_baixado_f = st.session_state.get("folha_fin", None)

        st.markdown("---")
        solicitante_f = st.text_input("👤 Nome do Solicitante *", key="folha_solic")
        arq_folha = st.file_uploader("📎 Anexo *", type=["pdf","png","jpg","jpeg","xlsx","xml","docx"], key="folha_arquivo")
        obs_folha = st.text_area("📝 Observação *", placeholder="Descreva a solicitação...", key="folha_obs")

        st.markdown("---")
        if st.button("📨 Enviar Chamado", use_container_width=True, key="enviar_folha"):
            if preview:
                st.info("👁️ Modo visualização: nenhum chamado foi criado.")
                return
            erros = []
            if not empresa_f: erros.append("Empresa")
            if not fin_baixado_f: erros.append("Financeiro Baixado")
            if not solicitante_f.strip(): erros.append("Nome do Solicitante")
            if arq_folha is None: erros.append("Anexo")
            if not obs_folha.strip(): erros.append("Observação")
            if erros:
                st.error(f"⚠️ Preencha: {', '.join(erros)}")
                return
            anexo_nome = arq_folha.name
            anexo_bytes = arq_folha.getvalue()
            protocolo = registrar_folha(empresa_f, fin_baixado_f, solicitante_f.strip(),
                                        obs_folha.strip(), anexo_nome, anexo_bytes)
            for k in ["sel_tipo_nota", "folha_empresa", "folha_fin", "folha_solic", "folha_obs", "folha_arquivo"]:
                st.session_state.pop(k, None)
            st.cache_data.clear()
            st.success(f"✅ Chamado registrado! Protocolo: **{protocolo}**")
            st.balloons()
        return

    # === FLUXO NORMAL ===
    eh_compra = "compra" in tipo_nota.lower()
    if eh_compra:
        data_entrada = st.date_input("📥 Data da Nota *", value=None, key="data_entrada")
        data_negociacao = None
    else:
        data_negociacao = st.date_input("🤝 Data de Negociação *", value=None, key="data_negociacao")
        data_entrada = None

    st.markdown("---")
    st.markdown("#### 📋 Abertura de Período / Descontabilização *")
    tipos_filtrados = filtrar_inconsistencias(tipos, tipo_nota)
    tipos_com_outros = tipos_filtrados + ["Outros"]
    tipo_sel = st.session_state.get("sel_tipo", None)
    cols_tipo = st.columns(min(len(tipos_com_outros), 4))
    for i, op in enumerate(tipos_com_outros):
        with cols_tipo[i % len(cols_tipo)]:
            ativo = tipo_sel == op
            if st.button(f"{'✓ ' if ativo else ''}{op}", key=f"sel_tipo_{i}", use_container_width=True, type="primary" if ativo else "secondary"):
                st.session_state["sel_tipo"] = op
                st.rerun()
    tipo = st.session_state.get("sel_tipo", None)
    tipo_outros_desc = ""
    if tipo == "Outros":
        tipo_outros_desc = st.text_area("📝 Descreva a solicitação *", placeholder="Descreva detalhadamente...", key="outros_desc")

    st.markdown("---")
    st.markdown("#### 🏢 Empresa *")
    empresa_sel = st.session_state.get("sel_empresa", None)
    cols_emp = st.columns(5)
    for i, op in enumerate(["1","2","6","13","14"]):
        with cols_emp[i]:
            ativo = empresa_sel == op
            if st.button(f"{'✓ ' if ativo else ''}{op}", key=f"sel_empresa_{i}", use_container_width=True, type="primary" if ativo else "secondary"):
                st.session_state["sel_empresa"] = op
                st.rerun()
    empresa = st.session_state.get("sel_empresa", None)

    st.markdown("#### 🚦 Prioridade *")
    prio_sel = st.session_state.get("sel_prioridade", None)
    cols_prio = st.columns(2)
    for i, op in enumerate(["Normal","Urgente"]):
        with cols_prio[i]:
            ativo = prio_sel == op
            if st.button(f"{'✓ ' if ativo else ''}{op}", key=f"sel_prio_{i}", use_container_width=True, type="primary" if ativo else "secondary"):
                st.session_state["sel_prioridade"] = op
                st.rerun()
    prioridade = st.session_state.get("sel_prioridade", None)

    st.markdown("#### 🔄 NF retornará ao sistema? *")
    nf_sel = st.session_state.get("sel_nf", None)
    cols_nf = st.columns(2)
    for i, op in enumerate(["Sim","Não"]):
        with cols_nf[i]:
            ativo = nf_sel == op
            if st.button(f"{'✓ ' if ativo else ''}{op}", key=f"sel_nf_{i}", use_container_width=True, type="primary" if ativo else "secondary"):
                st.session_state["sel_nf"] = op
                st.rerun()
    nf_retorna = st.session_state.get("sel_nf", None)

    st.markdown("#### 💰 Financeiro Baixado? *")
    fin_sel = st.session_state.get("sel_fin", None)
    cols_fin = st.columns(2)
    for i, op in enumerate(["Sim","Não"]):
        with cols_fin[i]:
            ativo = fin_sel == op
            if st.button(f"{'✓ ' if ativo else ''}{op}", key=f"sel_fin_{i}", use_container_width=True, type="primary" if ativo else "secondary"):
                st.session_state["sel_fin"] = op
                st.rerun()
    fin_baixado = st.session_state.get("sel_fin", None)

    setores_copia_disp = carregar_setores_disponiveis(setor_atual)

    st.markdown("---")
    with st.form("form_chamado", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            solicitante = st.text_input("🙋 Nome do Solicitante *")
            nome_parceiro = st.text_input("👤 Nome do Parceiro *")
        with col2:
            numero_nota = st.text_input("📄 Número da Nota *")
            valor = st.text_input("💰 Valor *", placeholder="0,00")
        col3, col4 = st.columns(2)
        with col3:
            nu_financeiro = st.text_input("🔢 NU Financeiro (opcional)")
        with col4:
            nu_nota = st.text_input("🔢 NU Nota (opcional)")
        copia_sel = st.multiselect("👥 Setores em cópia (opcional)", setores_copia_disp,
            help="Os setores marcados recebem e-mail e podem acompanhar e responder este chamado.")
        arquivo = st.file_uploader("📎 Anexo (opcional)", type=["pdf","png","jpg","xlsx","xml"])
        observacao = st.text_area("📝 Observação Complementar", placeholder="Informações adicionais...")
        enviar = st.form_submit_button("📨 Enviar Chamado", use_container_width=True)

    if enviar:
        if preview:
            st.info("👁️ Modo visualização: nenhum chamado foi criado.")
            return
        erros = []
        if not tipo: erros.append("Tipo")
        if tipo == "Outros" and not tipo_outros_desc.strip(): erros.append("Descrição")
        if not empresa: erros.append("Empresa")
        if not prioridade: erros.append("Prioridade")
        if not nf_retorna: erros.append("NF retornará")
        if not fin_baixado: erros.append("Financeiro Baixado")
        if not solicitante.strip(): erros.append("Solicitante")
        if not nome_parceiro.strip(): erros.append("Parceiro")
        if not numero_nota.strip(): erros.append("Número da Nota")
        if not valor.strip(): erros.append("Valor")
        if eh_compra and not data_entrada: erros.append("Data da Nota")
        if not eh_compra and not data_negociacao: erros.append("Data de Negociação")
        if erros:
            st.error(f"⚠️ Preencha: {', '.join(erros)}")
            return

        bloqueado, msg = verificar_bloqueio(data_entrada if eh_compra else data_negociacao)
        if bloqueado:
            st.error(msg)
            return

        arquivo_nome = None
        if arquivo:
            os.makedirs("uploads", exist_ok=True)
            arquivo_nome = f"{datetime.now(BRASILIA).strftime('%Y%m%d%H%M%S')}_{arquivo.name}"
            with open(f"uploads/{arquivo_nome}", "wb") as f:
                f.write(arquivo.getbuffer())

        try:
            valor_float = converter_valor(valor)
        except:
            st.error("⚠️ Valor inválido.")
            return

        tipo_final = f"Outros: {tipo_outros_desc.strip()}" if tipo == "Outros" else tipo
        total = run_query("SELECT COUNT(*) FROM chamados", fetch=True)[0][0]
        protocolo = f"ROC-{datetime.now(BRASILIA).strftime('%Y%m')}-{str(total+1).zfill(4)}"

        run_query("""INSERT INTO chamados (protocolo,setor,empresa,tipo_inconsistencia,prioridade,nf_retorna,
            solicitante,nome_parceiro,numero_nota,tipo_nota,data_entrada,data_saida,data_negociacao,
            valor,observacao,arquivo_nome,status,aberto_em,financeiro_baixado,num_unico_financeiro,num_unico_nota)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (protocolo, st.session_state.setor, empresa, tipo_final, prioridade, nf_retorna,
             solicitante.strip(), nome_parceiro.strip(), numero_nota.strip(), tipo_nota,
             data_entrada or None, None, data_negociacao or None,
             valor_float, observacao.strip(), arquivo_nome, "Aberto",
             datetime.now(BRASILIA).strftime("%Y-%m-%d %H:%M:%S"), fin_baixado,
             nu_financeiro.strip() or None, nu_nota.strip() or None))

        # Salva setores em cópia e notifica
        if copia_sel:
            salvar_copias(protocolo, copia_sel)
            for s in copia_sel:
                try:
                    email_s = buscar_email_setor(s)
                    if email_s:
                        email_setor_em_copia(email_s, protocolo, s, st.session_state.setor)
                except:
                    pass

        try:
            email_cont = buscar_email_contabilidade()
            if email_cont:
                email_novo_chamado(email_cont, protocolo, st.session_state.setor,
                    tipo_final, prioridade, nome_parceiro.strip(), numero_nota.strip(), solicitante.strip(),
                    nu_financeiro=nu_financeiro.strip(), nu_nota=nu_nota.strip())
        except:
            pass

        for k in ["sel_tipo_nota","sel_tipo","sel_parcial","sel_empresa","sel_prioridade","sel_nf","sel_fin","outros_desc","data_entrada","data_negociacao"]:
            st.session_state.pop(k, None)

        st.cache_data.clear()
        st.success(f"✅ Chamado registrado! Protocolo: **{protocolo}**")
        st.balloons()

def exibir_chamado(protocolo, tipo, empresa, status, prioridade, parceiro, nf, aberto_em, solicitante, fin_baixado, setor, eh_contabilidade=False, protocolo_aberto=None):
    status_cor = {"Aberto":"🔴","Em andamento":"🟡","Resolvido":"🟢","Cancelado":"⚫"}
    expanded = protocolo == protocolo_aberto
    label = f"{status_cor.get(status,'⚪')} {protocolo} — {parceiro} | NF: {nf}"
    if eh_contabilidade:
        label += f" | {setor}"
    label += f" | {status}"

    with st.expander(label, expanded=expanded):
        c1,c2,c3,c4 = st.columns(4)
        c1.markdown(f"**Empresa:** {empresa}")
        c2.markdown(f"**Tipo:** {tipo}")
        c3.markdown(f"**Prioridade:** {prioridade}")
        c4.markdown(f"**Solicitante:** {solicitante or '—'}")
        c1.markdown(f"**Fin. Baixado:** {fin_baixado or '—'}")
        st.markdown(f"**Aberto em:** {aberto_em}")

        copias = carregar_copias(protocolo)
        if copias:
            st.markdown(f"**👥 Em cópia:** {', '.join(copias)}")

        # Observação e anexo (se houver)
        det = run_query("""SELECT observacao, arquivo_nome, anexo_dados, num_unico_financeiro, num_unico_nota,
            atrasos_entregaveis, data_entrada, data_negociacao, nf_retorna, tipo_nota, valor
            FROM chamados WHERE protocolo=%s""", (protocolo,), fetch=True)
        if det:
            (obs_txt, arq_nome, arq_dados, nu_fin, nu_nt, atrasos_txt,
             data_ent, data_neg, nf_ret, tipo_mov, valor_c) = det[0]

            if tipo_mov:
                st.markdown(f"**🗂️ Tipo de Movimentação:** {tipo_mov}")
            data_ref = data_ent or data_neg
            if data_ref:
                rotulo_data = "📥 Data da Nota" if data_ent else "🤝 Data de Negociação"
                st.markdown(f"**{rotulo_data}:** {data_ref}")
            if nf_ret:
                st.markdown(f"**🔄 NF retornará ao sistema:** {nf_ret}")
            valor_fmt = _fmt_valor(valor_c)
            if valor_fmt:
                st.markdown(f"**💰 Valor:** {valor_fmt}")
            if nu_fin:
                st.markdown(f"**🔢 Número Único Financeiro:** {nu_fin}")
            if nu_nt:
                st.markdown(f"**🔢 Número Único da Nota:** {nu_nt}")
            if atrasos_txt:
                st.markdown(f"**⏰ Atrasos de entregáveis:** {atrasos_txt}")
            if obs_txt:
                st.markdown(f"**📝 Observação:** {obs_txt}")
            if arq_dados:
                import base64
                try:
                    raw = base64.b64decode(arq_dados)
                    if _eh_imagem(arq_nome):
                        st.markdown("**📎 Anexo:**")
                        st.image(raw, use_container_width=True)
                    st.download_button("📎 Baixar anexo" + (f" ({arq_nome})" if arq_nome else ""),
                        data=raw, file_name=arq_nome or f"{protocolo}_anexo", key=f"dl_{protocolo}")
                except:
                    st.caption("📎 Anexo disponível, mas não foi possível carregá-lo.")
            elif arq_nome:
                st.caption(f"📎 Anexo: {arq_nome}")

        # Atualizar status (somente contabilidade)
        if eh_contabilidade:
            st.markdown("---")
            novo_status = st.selectbox("Atualizar status", ["Aberto","Em andamento","Resolvido","Cancelado"],
                index=["Aberto","Em andamento","Resolvido","Cancelado"].index(status), key=f"s_{protocolo}")
            if st.button("💾 Salvar status", key=f"b_{protocolo}"):
                agora = datetime.now(BRASILIA).strftime("%Y-%m-%d %H:%M:%S")
                run_query("""UPDATE chamados SET status=%s, atendido_em=COALESCE(atendido_em,%s),
                    resolvido_em=CASE WHEN %s='Resolvido' THEN %s ELSE resolvido_em END WHERE protocolo=%s""",
                    (novo_status, agora, novo_status, agora, protocolo))
                try:
                    destinos = emails_interessados(protocolo, setor)
                    if novo_status == "Resolvido":
                        for ed in destinos:
                            email_conclusao_chamado(None, ed, protocolo, tipo, agora)
                    else:
                        for ed in destinos:
                            email_atualizacao_chamado(ed, protocolo, novo_status, setor)
                except:
                    pass
                st.cache_data.clear()
                st.success("✅ Atualizado!")
                st.rerun()

        # Editar setores em cópia (contabilidade ou o setor que abriu)
        eh_dono = (st.session_state.perfil != "contabilidade" and st.session_state.setor == setor)
        if eh_contabilidade or eh_dono:
            st.markdown("---")
            setores_disp = carregar_setores_disponiveis(setor)
            default_copias = [c for c in copias if c in setores_disp]
            novas_copias = st.multiselect("👥 Setores em cópia", setores_disp,
                default=default_copias, key=f"copia_{protocolo}")
            if st.button("💾 Salvar cópia", key=f"savecopia_{protocolo}"):
                adicionados = set(novas_copias) - set(copias)
                salvar_copias(protocolo, novas_copias)
                for s in adicionados:
                    try:
                        email_s = buscar_email_setor(s)
                        if email_s:
                            email_setor_em_copia(email_s, protocolo, s, setor)
                    except:
                        pass
                st.cache_data.clear()
                st.success("✅ Cópia atualizada!")
                st.rerun()

        st.markdown("---")
        exibir_chat(protocolo, setor)

def tela_meus_chamados(protocolo_aberto=None):
    st.title("📋 Minhas Solicitações")
    st.markdown("---")
    rows = carregar_meus_chamados(st.session_state.setor)
    if not rows:
        st.info("Nenhum chamado registrado ainda.")
        return
    for protocolo, tipo, empresa, status, prioridade, parceiro, nf, aberto_em, solicitante, fin_baixado in rows:
        exibir_chamado(protocolo, tipo, empresa, status, prioridade, parceiro, nf,
                       aberto_em, solicitante, fin_baixado, st.session_state.setor,
                       eh_contabilidade=False, protocolo_aberto=protocolo_aberto)

def tela_acompanhamento(protocolo_aberto=None):
    st.title("👀 Solicitações em Acompanhamento")
    st.markdown("Chamados em que seu setor foi incluído em cópia.")
    st.markdown("---")
    rows = carregar_chamados_acompanhamento(st.session_state.setor)
    if not rows:
        st.info("Nenhum chamado em acompanhamento.")
        return
    for protocolo, tipo, empresa, status, prioridade, parceiro, nf, aberto_em, solicitante, fin_baixado, setor_dono in rows:
        exibir_chamado(protocolo, tipo, empresa, status, prioridade, parceiro, nf,
                       aberto_em, solicitante, fin_baixado, setor_dono,
                       eh_contabilidade=False, protocolo_aberto=protocolo_aberto)

def tela_todos_chamados(protocolo_aberto=None):
    st.title("📋 Todos os Chamados")
    st.markdown("---")
    rows = carregar_todos_chamados()
    if not rows:
        st.info("Nenhum chamado registrado ainda.")
        return
    c1,c2,c3 = st.columns(3)
    filtro_status = c1.selectbox("Status", ["Todos","Aberto","Em andamento","Resolvido","Cancelado"])
    filtro_empresa = c2.selectbox("Empresa", ["Todas","1","2","6","13","14"])
    filtro_setor = c3.text_input("Setor")
    for protocolo, setor, tipo, empresa, status, prioridade, parceiro, nf, aberto_em, solicitante, fin_baixado in rows:
        if filtro_status != "Todos" and status != filtro_status: continue
        if filtro_empresa != "Todas" and empresa != filtro_empresa: continue
        if filtro_setor and filtro_setor.lower() not in setor.lower(): continue
        exibir_chamado(protocolo, tipo, empresa, status, prioridade, parceiro, nf,
                       aberto_em, solicitante, fin_baixado, setor,
                       eh_contabilidade=True, protocolo_aberto=protocolo_aberto)
