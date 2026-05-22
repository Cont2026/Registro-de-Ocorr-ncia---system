import streamlit as st
import os
import calendar
from datetime import datetime, date
from zoneinfo import ZoneInfo
from database.connection import get_conn, release_conn, run_query

BRASILIA = ZoneInfo("America/Sao_Paulo")

def verificar_bloqueio(data_nota):
    if not data_nota:
        return False, ""
    agora = datetime.now(BRASILIA)
    hoje = agora.date()
    m, a = data_nota.month, data_nota.year
    ma, aa = hoje.month, hoje.year
    if a == aa and m == ma:
        return False, ""
    if a < aa or (a == aa and m < ma - 1):
        return True, "⛔ O prazo para solicitações da competência selecionada foi encerrado conforme regra de fechamento contábil."
    ultimo = calendar.monthrange(aa, ma)[1]
    if agora > datetime(aa, ma, ultimo, 17, 48, 0, tzinfo=BRASILIA):
        return True, "⛔ O prazo para solicitações da competência selecionada foi encerrado conforme regra de fechamento contábil."
    return False, ""

@st.cache_data(ttl=30)
def carregar_tipos():
    return [r[0] for r in run_query("SELECT nome FROM tipos_inconsistencia WHERE ativo=1 ORDER BY nome", fetch=True)]

@st.cache_data(ttl=30)
def carregar_meus_chamados(setor):
    return run_query("""
        SELECT protocolo, tipo_inconsistencia, empresa, status, prioridade, nome_parceiro, numero_nota, aberto_em
        FROM chamados WHERE setor=%s ORDER BY aberto_em DESC
    """, (setor,), fetch=True)

@st.cache_data(ttl=30)
def carregar_todos_chamados():
    return run_query("""
        SELECT protocolo, setor, tipo_inconsistencia, empresa, status, prioridade, nome_parceiro, numero_nota, aberto_em
        FROM chamados ORDER BY aberto_em DESC
    """, fetch=True)

def tela_novo_chamado():
    st.title("➕ Novo Chamado")
    st.markdown(f"**Setor:** {st.session_state.setor}")
    st.markdown("Preencha todos os campos obrigatórios para registrar a ocorrência.")
    st.markdown("---")

    tipos = carregar_tipos()
    tipo_nota = st.selectbox("Tipo da Nota *", ["", "Compra", "Venda"], key="tipo_nota_select")

    if not tipo_nota:
        st.info("Selecione o tipo da nota para continuar o preenchimento.")
        return

    data_entrada = st.date_input("📥 Data da Nota *", value=None, key="data_entrada") if tipo_nota == "Compra" else None
    data_negociacao = st.date_input("🤝 Data de Negociação *", value=None, key="data_negociacao") if tipo_nota == "Venda" else None

    st.markdown("---")

    with st.form("form_chamado", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            empresa = st.selectbox("🏢 Empresa *", ["", "1", "2", "6", "13", "14"])
            tipo = st.selectbox("📋 Abertura de Período / Descontabilização *", [""] + tipos)
            prioridade = st.selectbox("🚦 Prioridade *", ["Normal", "Urgente"])
            nf_retorna = st.selectbox("🔄 NF retornará ao sistema? *", ["", "Retornará", "Não retornará"])
        with col2:
            nome_parceiro = st.text_input("👤 Nome do Parceiro *")
            numero_nota = st.text_input("📄 Número da Nota *")
            valor = st.text_input("💰 Valor *", placeholder="0,00")
            arquivo = st.file_uploader("📎 Anexo (opcional)", type=["pdf","png","jpg","xlsx","xml"])
        observacao = st.text_area("📝 Observação Complementar", placeholder="Informações adicionais...")
        st.markdown("---")
        enviar = st.form_submit_button("📨 Enviar Chamado", use_container_width=True)

    if enviar:
        erros = []
        if not empresa: erros.append("Empresa")
        if not tipo: erros.append("Abertura de Período / Descontabilização")
        if not nf_retorna: erros.append("NF retornará ao sistema")
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
            valor_float = float(valor.replace(".", "").replace(",", "."))
        except:
            st.error("⚠️ Valor inválido. Use o formato 1.500,00")
            return

        rows = run_query("SELECT COUNT(*) FROM chamados", fetch=True)
        total = rows[0][0]
        protocolo = f"ROC-{datetime.now(BRASILIA).strftime('%Y%m')}-{str(total + 1).zfill(4)}"

        run_query("""
            INSERT INTO chamados (protocolo,setor,empresa,tipo_inconsistencia,prioridade,nf_retorna,
            nome_parceiro,numero_nota,tipo_nota,data_entrada,data_saida,data_negociacao,
            valor,observacao,arquivo_nome,status,aberto_em)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (protocolo, st.session_state.setor, empresa, tipo, prioridade, nf_retorna,
              nome_parceiro.strip(), numero_nota.strip(), tipo_nota,
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
    for protocolo, tipo, empresa, status, prioridade, parceiro, nf, aberto_em in rows:
        with st.expander(f"{status_cor.get(status,'⚪')} {protocolo} — {parceiro} | NF: {nf} | {status}"):
            c1, c2, c3 = st.columns(3)
            c1.markdown(f"**Empresa:** {empresa}")
            c2.markdown(f"**Tipo:** {tipo}")
            c3.markdown(f"**Prioridade:** {prioridade}")
            st.markdown(f"**Aberto em:** {aberto_em}")

def tela_todos_chamados():
    st.title("📋 Todos os Chamados")
    st.markdown("---")
    rows = carregar_todos_chamados()
    if not rows:
        st.info("Nenhum chamado registrado ainda.")
        return

    c1, c2, c3 = st.columns(3)
    filtro_status = c1.selectbox("Status", ["Todos","Aberto","Em andamento","Resolvido","Cancelado"])
    filtro_empresa = c2.selectbox("Empresa", ["Todas","1","2","6","13","14"])
    filtro_setor = c3.text_input("Setor")

    status_cor = {"Aberto":"🔴","Em andamento":"🟡","Resolvido":"🟢","Cancelado":"⚫"}

    for protocolo, setor, tipo, empresa, status, prioridade, parceiro, nf, aberto_em in rows:
        if filtro_status != "Todos" and status != filtro_status: continue
        if filtro_empresa != "Todas" and empresa != filtro_empresa: continue
        if filtro_setor and filtro_setor.lower() not in setor.lower(): continue

        with st.expander(f"{status_cor.get(status,'⚪')} {protocolo} — {parceiro} | NF: {nf} | {setor} | {status}"):
            c1, c2, c3 = st.columns(3)
            c1.markdown(f"**Empresa:** {empresa}")
            c2.markdown(f"**Tipo:** {tipo}")
            c3.markdown(f"**Prioridade:** {prioridade}")
            st.markdown(f"**Aberto em:** {aberto_em}")
            st.markdown("---")
            novo_status = st.selectbox("Atualizar status",
                ["Aberto","Em andamento","Resolvido","Cancelado"],
                index=["Aberto","Em andamento","Resolvido","Cancelado"].index(status),
                key=f"s_{protocolo}")
            resolucao = st.text_area("Resolução", key=f"r_{protocolo}")
            if st.button("💾 Salvar", key=f"b_{protocolo}"):
                agora = datetime.now(BRASILIA).strftime("%Y-%m-%d %H:%M:%S")
                run_query("""
                    UPDATE chamados SET status=%s, resolucao=%s,
                    atendido_em=COALESCE(atendido_em,%s),
                    resolvido_em=CASE WHEN %s='Resolvido' THEN %s ELSE resolvido_em END
                    WHERE protocolo=%s
                """, (novo_status, resolucao, agora, novo_status, agora, protocolo))
                st.cache_data.clear()
                st.success("✅ Atualizado!")
                st.rerun()
