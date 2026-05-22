import streamlit as st
import os
import calendar
from datetime import datetime
from zoneinfo import ZoneInfo
from database.connection import run_query

BRASILIA = ZoneInfo("America/Sao_Paulo")

def verificar_bloqueio(data_nota):
    if not data_nota: return False, ""
    agora = datetime.now(BRASILIA)
    hoje = agora.date()
    m, a, ma, aa = data_nota.month, data_nota.year, hoje.month, hoje.year
    if a == aa and m == ma: return False, ""
    if a < aa or (a == aa and m < ma - 1):
        return True, "⛔ O prazo para solicitações da competência selecionada foi encerrado conforme regra de fechamento contábil."
    if agora > datetime(aa, ma, calendar.monthrange(aa, ma)[1], 17, 48, 0, tzinfo=BRASILIA):
        return True, "⛔ O prazo para solicitações da competência selecionada foi encerrado conforme regra de fechamento contábil."
    return False, ""

def converter_valor(valor):
    v = valor.strip().replace(" ", "")
    if "," in v and "." in v: v = v.replace(".", "").replace(",", ".")
    elif "," in v: v = v.replace(",", ".")
    return float(v)

@st.cache_data(ttl=300)
def carregar_tipos():
    return [r[0] for r in run_query("SELECT nome FROM tipos_inconsistencia WHERE ativo=1 ORDER BY nome", fetch=True)]

@st.cache_data(ttl=60)
def carregar_meus_chamados(setor):
    return run_query("SELECT protocolo, tipo_inconsistencia, empresa, status, prioridade, nome_parceiro, numero_nota, aberto_em, solicitante FROM chamados WHERE setor=%s ORDER BY aberto_em DESC", (setor,), fetch=True)

@st.cache_data(ttl=60)
def carregar_todos_chamados():
    return run_query("SELECT protocolo, setor, tipo_inconsistencia, empresa, status, prioridade, nome_parceiro, numero_nota, aberto_em, solicitante FROM chamados ORDER BY aberto_em DESC", fetch=True)

def carregar_mensagens(protocolo):
    return run_query("SELECT autor, perfil, mensagem, enviado_em FROM mensagens WHERE chamado_protocolo=%s ORDER BY enviado_em ASC", (protocolo,), fetch=True)

def enviar_mensagem(protocolo, autor, perfil, mensagem):
    run_query("INSERT INTO mensagens (chamado_protocolo,autor,perfil,mensagem,enviado_em) VALUES (%s,%s,%s,%s,%s)",
              (protocolo, autor, perfil, mensagem, datetime.now(BRASILIA).strftime("%Y-%m-%d %H:%M:%S")))

def exibir_chat(protocolo):
    st.markdown("#### 💬 Acompanhamento")
    mensagens = carregar_mensagens(protocolo)
    if not mensagens:
        st.markdown("<div style='background:#f9f9f9;border-radius:10px;padding:16px;text-align:center;color:#999;font-size:13px;'>Nenhuma mensagem ainda.</div>", unsafe_allow_html=True)
    else:
        for autor, perfil, mensagem, enviado_em in mensagens:
            is_cont = perfil == "contabilidade"
            alinha = "flex-end" if is_cont else "flex-start"
            bg = "#041747" if is_cont else "#F0F4FF"
            cor_txt = "white" if is_cont else "#041747"
            cor_meta = "rgba(255,255,255,0.7)" if is_cont else "#666"
            border_r = "14px 14px 4px 14px" if is_cont else "14px 14px 14px 4px"
            st.markdown(f"""
            <div style='display:flex;justify-content:{alinha};margin-bottom:10px;'>
                <div style='max-width:75%;background:{bg};color:{cor_txt};border-radius:{border_r};padding:10px 14px;box-shadow:0 1px 4px rgba(0,0,0,0.08);'>
                    <p style='font-size:11px;font-weight:700;margin:0 0 4px;color:{cor_meta};'>{autor}</p>
                    <p style='font-size:13px;margin:0;'>{mensagem}</p>
                    <p style='font-size:10px;margin:6px 0 0;color:{cor_meta};text-align:right;'>{enviado_em}</p>
                </div>
            </div>""", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    with st.form(key=f"chat_{protocolo}", clear_on_submit=True):
        nova_msg = st.text_area("Nova mensagem", placeholder="Digite sua mensagem...", height=80, label_visibility="collapsed")
        if st.form_submit_button("📨 Enviar", use_container_width=True):
            if nova_msg.strip():
                enviar_mensagem(protocolo, st.session_state.usuario, st.session_state.perfil, nova_msg.strip())
                st.rerun()
            else:
                st.warning("Digite uma mensagem antes de enviar.")

def tela_novo_chamado():
    st.title("➕ Novo Chamado")
    st.markdown(f"**Setor:** {st.session_state.setor}")
    st.markdown("Preencha todos os campos obrigatórios.")
    st.markdown("---")
    tipos = carregar_tipos()
    tipo_nota = st.selectbox("Tipo da Nota *", ["", "Compra", "Venda"], key="tipo_nota_select")
    if not tipo_nota:
        st.info("Selecione o tipo da nota para continuar.")
        return
    data_entrada = st.date_input("📥 Data da Nota *", value=None, key="data_entrada") if tipo_nota == "Compra" else None
    data_negociacao = st.date_input("🤝 Data de Negociação *", value=None, key="data_negociacao") if tipo_nota == "Venda" else None
    st.markdown("---")
    with st.form("form_chamado", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            empresa = st.selectbox("🏢 Empresa *", ["", "1", "2", "6", "13", "14"])
            tipo = st.selectbox("📋 Abertura de Período / Descontabilização *", [""] + tipos + ["Outros"])
            prioridade = st.selectbox("🚦 Prioridade *", ["Normal", "Urgente"])
            nf_retorna = st.selectbox("🔄 NF retornará ao sistema? *", ["", "Sim", "Não"])
        with col2:
            solicitante = st.text_input("🙋 Nome do Solicitante *")
            nome_parceiro = st.text_input("👤 Nome do Parceiro *")
            numero_nota = st.text_input("📄 Número da Nota *")
            valor = st.text_input("💰 Valor *", placeholder="0,00")
            arquivo = st.file_uploader("📎 Anexo (opcional)", type=["pdf","png","jpg","xlsx","xml"])
        tipo_outros_desc = st.text_area("📝 Descreva a solicitação *", placeholder="Descreva detalhadamente...") if tipo == "Outros" else ""
        observacao = st.text_area("📝 Observação Complementar", placeholder="Informações adicionais...")
        enviar = st.form_submit_button("📨 Enviar Chamado", use_container_width=True)

    if enviar:
        erros = []
        if not empresa: erros.append("Empresa")
        if not tipo: erros.append("Tipo")
        if tipo == "Outros" and not tipo_outros_desc.strip(): erros.append("Descrição da solicitação")
        if not nf_retorna: erros.append("NF retornará ao sistema")
        if not solicitante.strip(): erros.append("Nome do Solicitante")
        if not nome_parceiro.strip(): erros.append("Nome do Parceiro")
        if not numero_nota.strip(): erros.append("Número da Nota")
        if not valor.strip(): erros.append("Valor")
        if tipo_nota == "Compra" and not data_entrada: erros.append("Data da Nota")
        if tipo_nota == "Venda" and not data_negociacao: erros.append("Data de Negociação")
        if erros:
            st.error(f"⚠️ Preencha: {', '.join(erros)}")
            return
        bloqueado, msg = verificar_bloqueio(data_entrada if tipo_nota == "Compra" else data_negociacao)
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
            st.error("⚠️ Valor inválido. Exemplos: 1500 / 1500,00 / 1.500,00")
            return
        tipo_final = f"Outros: {tipo_outros_desc.strip()}" if tipo == "Outros" else tipo
        total = run_query("SELECT COUNT(*) FROM chamados", fetch=True)[0][0]
        protocolo = f"ROC-{datetime.now(BRASILIA).strftime('%Y%m')}-{str(total+1).zfill(4)}"
        run_query("""INSERT INTO chamados (protocolo,setor,empresa,tipo_inconsistencia,prioridade,nf_retorna,
            solicitante,nome_parceiro,numero_nota,tipo_nota,data_entrada,data_saida,data_negociacao,
            valor,observacao,arquivo_nome,status,aberto_em) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (protocolo, st.session_state.setor, empresa, tipo_final, prioridade, nf_retorna,
             solicitante.strip(), nome_parceiro.strip(), numero_nota.strip(), tipo_nota,
             data_entrada or None, None, data_negociacao or None,
             valor_float, observacao.strip(), arquivo_nome, "Aberto",
             datetime.now(BRASILIA).strftime("%Y-%m-%d %H:%M:%S")))
        st.cache_data.clear()
        st.success(f"✅ Chamado registrado! Protocolo: **{protocolo}**")
        st.balloons()

def tela_meus_chamados():
    st.title("📋 Meus Chamados")
    st.markdown("---")
    rows = carregar_meus_chamados(st.session_state.setor)
    if not rows:
        st.info("Nenhum chamado registrado ainda.")
        return
    status_cor = {"Aberto":"🔴","Em andamento":"🟡","Resolvido":"🟢","Cancelado":"⚫"}
    for protocolo, tipo, empresa, status, prioridade, parceiro, nf, aberto_em, solicitante in rows:
        with st.expander(f"{status_cor.get(status,'⚪')} {protocolo} — {parceiro} | NF: {nf} | {status}"):
            c1,c2,c3,c4 = st.columns(4)
            c1.markdown(f"**Empresa:** {empresa}")
            c2.markdown(f"**Tipo:** {tipo}")
            c3.markdown(f"**Prioridade:** {prioridade}")
            c4.markdown(f"**Solicitante:** {solicitante or '—'}")
            st.markdown(f"**Aberto em:** {aberto_em}")
            st.markdown("---")
            exibir_chat(protocolo)

def tela_todos_chamados():
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
    status_cor = {"Aberto":"🔴","Em andamento":"🟡","Resolvido":"🟢","Cancelado":"⚫"}
    for protocolo, setor, tipo, empresa, status, prioridade, parceiro, nf, aberto_em, solicitante in rows:
        if filtro_status != "Todos" and status != filtro_status: continue
        if filtro_empresa != "Todas" and empresa != filtro_empresa: continue
        if filtro_setor and filtro_setor.lower() not in setor.lower(): continue
        with st.expander(f"{status_cor.get(status,'⚪')} {protocolo} — {parceiro} | NF: {nf} | {setor} | {status}"):
            c1,c2,c3,c4 = st.columns(4)
            c1.markdown(f"**Empresa:** {empresa}")
            c2.markdown(f"**Tipo:** {tipo}")
            c3.markdown(f"**Prioridade:** {prioridade}")
            c4.markdown(f"**Solicitante:** {solicitante or '—'}")
            st.markdown(f"**Aberto em:** {aberto_em}")
            st.markdown("---")
            novo_status = st.selectbox("Atualizar status", ["Aberto","Em andamento","Resolvido","Cancelado"],
                index=["Aberto","Em andamento","Resolvido","Cancelado"].index(status), key=f"s_{protocolo}")
            if st.button("💾 Salvar status", key=f"b_{protocolo}"):
                agora = datetime.now(BRASILIA).strftime("%Y-%m-%d %H:%M:%S")
                run_query("""UPDATE chamados SET status=%s, atendido_em=COALESCE(atendido_em,%s),
                    resolvido_em=CASE WHEN %s='Resolvido' THEN %s ELSE resolvido_em END WHERE protocolo=%s""",
                    (novo_status, agora, novo_status, agora, protocolo))
                st.cache_data.clear()
                st.success("✅ Atualizado!")
                st.rerun()
            st.markdown("---")
            exibir_chat(protocolo)
