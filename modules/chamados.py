import streamlit as st
import os
import calendar
from datetime import datetime, date
from zoneinfo import ZoneInfo
from database.connection import get_conn

BRASILIA = ZoneInfo("America/Sao_Paulo")

def gerar_protocolo():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM chamados")
    total = cur.fetchone()[0]
    cur.close()
    conn.close()
    agora = datetime.now(BRASILIA)
    return f"RO-{agora.strftime('%Y%m')}-{str(total + 1).zfill(4)}"

def verificar_bloqueio(data_nota):
    agora = datetime.now(BRASILIA)
    hoje = agora.date()

    if data_nota is None:
        return False, ""

    mes_nota = data_nota.month
    ano_nota = data_nota.year
    mes_atual = hoje.month
    ano_atual = hoje.year

    if ano_nota == ano_atual and mes_nota == mes_atual:
        return False, ""

    if (ano_nota < ano_atual) or (ano_nota == ano_atual and mes_nota < mes_atual - 1):
        return True, "⛔ O prazo para solicitações da competência selecionada foi encerrado conforme regra de fechamento contábil."

    ultimo_dia = calendar.monthrange(ano_atual, mes_atual)[1]
    prazo_final = datetime(ano_atual, mes_atual, ultimo_dia, 17, 48, 0, tzinfo=BRASILIA)

    if agora > prazo_final:
        return True, "⛔ O prazo para solicitações da competência selecionada foi encerrado conforme regra de fechamento contábil."

    return False, ""

def tela_novo_chamado():
    st.title("➕ Novo Chamado")

    # Setor identificado automaticamente pelo login
    setor_logado = st.session_state.setor
    st.markdown(f"**Setor:** {setor_logado}")
    st.markdown("Preencha todos os campos obrigatórios para registrar a ocorrência.")
    st.markdown("---")

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT nome FROM tipos_inconsistencia WHERE ativo=1 ORDER BY nome")
    tipos = [r[0] for r in cur.fetchall()]
    cur.execute("SELECT nome FROM motivos WHERE ativo=1 ORDER BY nome")
    motivos_lista = [r[0] for r in cur.fetchall()]
    cur.close()
    conn.close()

    tipo_nota = st.selectbox("Tipo da Nota *", ["", "Compra", "Venda"], key="tipo_nota_select")

    if not tipo_nota:
        st.info("Selecione o tipo da nota para continuar o preenchimento.")
        return

    data_entrada = None
    data_saida = None
    data_negociacao = None

    if tipo_nota == "Compra":
        data_entrada = st.date_input("📥 Data da Nota *", value=None, key="data_entrada")
    elif tipo_nota == "Venda":
        data_negociacao = st.date_input("🤝 Data de Negociação *", value=None, key="data_negociacao")

    st.markdown("---")

    with st.form("form_chamado", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            empresa = st.selectbox("🏢 Empresa *", ["", "1", "2", "6", "13", "14"])
            tipo = st.selectbox("📌 Tipo de Inconsistência *", [""] + tipos)
            motivo = st.selectbox("🔍 Motivo *", [""] + motivos_lista)
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
        if not tipo: erros.append("Tipo de Inconsistência")
        if not motivo: erros.append("Motivo")
        if not nf_retorna: erros.append("NF retornará ao sistema")
        if not nome_parceiro.strip(): erros.append("Nome do Parceiro")
        if not numero_nota.strip(): erros.append("Número da Nota")
        if not valor.strip(): erros.append("Valor")
        if tipo_nota == "Compra" and data_entrada is None:
            erros.append("Data da Nota")
        if tipo_nota == "Venda" and data_negociacao is None:
            erros.append("Data de Negociação")

        if erros:
            st.error(f"⚠️ Preencha os campos obrigatórios: {', '.join(erros)}")
            return

        data_referencia = data_entrada if tipo_nota == "Compra" else data_negociacao
        bloqueado, msg_bloqueio = verificar_bloqueio(data_referencia)
        if bloqueado:
            st.error(msg_bloqueio)
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

        protocolo = gerar_protocolo()
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO chamados (
                protocolo, setor, empresa, tipo_inconsistencia, motivo,
                prioridade, nf_retorna, nome_parceiro, numero_nota,
                tipo_nota, data_entrada, data_saida, data_negociacao,
                valor, observacao, arquivo_nome, status, aberto_em
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            protocolo, setor_logado,
            empresa, tipo, motivo, prioridade, nf_retorna,
            nome_parceiro.strip(), numero_nota.strip(), tipo_nota,
            data_entrada if data_entrada else None,
            data_saida if data_saida else None,
            data_negociacao if data_negociacao else None,
            valor_float, observacao.strip(), arquivo_nome, "Aberto",
            datetime.now(BRASILIA).strftime("%Y-%m-%d %H:%M:%S")
        ))
        conn.commit()
        cur.close()
        conn.close()

        st.success(f"✅ Chamado registrado com sucesso! Protocolo: **{protocolo}**")
        st.balloons()

def tela_meus_chamados():
    st.title("📋 Meus Chamados")
    st.markdown("---")

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT protocolo, tipo_inconsistencia, motivo, empresa,
               status, prioridade, aberto_em
        FROM chamados WHERE setor = %s
        ORDER BY aberto_em DESC
    """, (st.session_state.setor,))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    if not rows:
        st.info("Nenhum chamado registrado ainda.")
        return

    status_cor = {"Aberto": "🔴", "Em andamento": "🟡", "Resolvido": "🟢", "Cancelado": "⚫"}

    for row in rows:
        protocolo, tipo, motivo, empresa, status, prioridade, aberto_em = row
        icone = status_cor.get(status, "⚪")
        with st.expander(f"{icone} {protocolo} — {tipo} | {status}"):
            col1, col2, col3 = st.columns(3)
            col1.markdown(f"**Empresa:** {empresa}")
            col2.markdown(f"**Motivo:** {motivo}")
            col3.markdown(f"**Prioridade:** {prioridade}")
            st.markdown(f"**Aberto em:** {aberto_em}")

def tela_todos_chamados():
    st.title("📋 Todos os Chamados")
    st.markdown("---")

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT protocolo, setor, tipo_inconsistencia, motivo,
               empresa, status, prioridade, aberto_em
        FROM chamados ORDER BY aberto_em DESC
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    if not rows:
        st.info("Nenhum chamado registrado ainda.")
        return

    col1, col2, col3 = st.columns(3)
    with col1:
        filtro_status = st.selectbox("Filtrar por status", ["Todos", "Aberto", "Em andamento", "Resolvido", "Cancelado"])
    with col2:
        filtro_empresa = st.selectbox("Filtrar por empresa", ["Todas", "1", "2", "6", "13", "14"])
    with col3:
        filtro_setor = st.text_input("Filtrar por setor")

    status_cor = {"Aberto": "🔴", "Em andamento": "🟡", "Resolvido": "🟢", "Cancelado": "⚫"}

    for row in rows:
        protocolo, setor, tipo, motivo, empresa, status, prioridade, aberto_em = row
        if filtro_status != "Todos" and status != filtro_status:
            continue
        if filtro_empresa != "Todas" and empresa != filtro_empresa:
            continue
        if filtro_setor and filtro_setor.lower() not in setor.lower():
            continue

        icone = status_cor.get(status, "⚪")
        with st.expander(f"{icone} {protocolo} — {setor} | {tipo} | {status}"):
            col1, col2, col3 = st.columns(3)
            col1.markdown(f"**Empresa:** {empresa}")
            col2.markdown(f"**Motivo:** {motivo}")
            col3.markdown(f"**Prioridade:** {prioridade}")
            st.markdown(f"**Aberto em:** {aberto_em}")
            st.markdown("---")
            novo_status = st.selectbox(
                "Atualizar status",
                ["Aberto", "Em andamento", "Resolvido", "Cancelado"],
                index=["Aberto", "Em andamento", "Resolvido", "Cancelado"].index(status),
                key=f"status_{protocolo}"
            )
            resolucao = st.text_area("Resolução / Observação", key=f"res_{protocolo}")
            if st.button("💾 Salvar", key=f"salvar_{protocolo}"):
                agora = datetime.now(BRASILIA).strftime("%Y-%m-%d %H:%M:%S")
                conn = get_conn()
                cur = conn.cursor()
                cur.execute("""
                    UPDATE chamados SET status=%s, resolucao=%s,
                    atendido_em=COALESCE(atendido_em, %s),
                    resolvido_em=CASE WHEN %s='Resolvido' THEN %s ELSE resolvido_em END
                    WHERE protocolo=%s
                """, (novo_status, resolucao, agora, novo_status, agora, protocolo))
                conn.commit()
                cur.close()
                conn.close()
                st.success("✅ Chamado atualizado!")
                st.rerun()
