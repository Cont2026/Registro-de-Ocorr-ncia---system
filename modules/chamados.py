import streamlit as st
import sqlite3
import os
from datetime import datetime, date

DB_PATH = "database/ro.db"

def get_conn():
    return sqlite3.connect(DB_PATH)

# =============================================
# GERAR PROTOCOLO AUTOMÁTICO
# =============================================

def gerar_protocolo():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM chamados")
    total = cur.fetchone()[0]
    conn.close()
    agora = datetime.now()
    return f"RO-{agora.strftime('%Y%m')}-{str(total + 1).zfill(4)}"

# =============================================
# VERIFICAR BLOQUEIO DE PRAZO
# =============================================

def verificar_bloqueio(data_entrada):
    agora = datetime.now()

    if agora.hour > 17 or (agora.hour == 17 and agora.minute >= 48):
        return True, "⛔ Fora do horário de atendimento. O sistema aceita chamados até as 17h48."

    if agora.day == 31 or (agora.month in [4,6,9,11] and agora.day == 30) or \
       (agora.month == 2 and agora.day in [28,29]):
        return True, "⛔ Não é possível abrir chamados no último dia do mês."

    if data_entrada:
        mes_nota = data_entrada.month
        ano_nota = data_entrada.year
        mes_atual = agora.month
        ano_atual = agora.year

        if (ano_atual > ano_nota) or (ano_atual == ano_nota and mes_atual > mes_nota):
            dia = 1
            dias_uteis = 0
            while dias_uteis < 2:
                d = date(ano_atual, mes_atual, dia)
                if d.weekday() < 5:
                    dias_uteis += 1
                if dias_uteis < 2:
                    dia += 1

            segundo_dia_util = date(ano_atual, mes_atual, dia)
            hoje = agora.date()

            if hoje > segundo_dia_util:
                return True, f"⛔ Prazo encerrado. Notas de {data_entrada.strftime('%m/%Y')} não são aceitas após o 2° dia útil de {segundo_dia_util.strftime('%m/%Y')} ({segundo_dia_util.strftime('%d/%m/%Y')})."
            elif hoje == segundo_dia_util and agora.hour >= 12:
                return True, f"⛔ Prazo encerrado. No 2° dia útil do mês, notas do mês anterior não são aceitas após as 12h."

    return False, ""

# =============================================
# TELA NOVO CHAMADO
# =============================================

def tela_novo_chamado():
    st.title("➕ Novo Chamado")
    st.markdown("Preencha todos os campos obrigatórios para registrar a ocorrência.")
    st.markdown("---")

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT nome FROM tipos_inconsistencia WHERE ativo=1 ORDER BY nome")
    tipos = [r[0] for r in cur.fetchall()]
    cur.execute("SELECT nome FROM motivos WHERE ativo=1 ORDER BY nome")
    motivos_lista = [r[0] for r in cur.fetchall()]
    conn.close()

    # ── Tipo da Nota fora do form para renderização condicional ──
    st.markdown("#### Tipo da Nota")
    tipo_nota = st.selectbox(
        "Tipo da Nota *",
        ["", "Compra", "Venda"],
        key="tipo_nota_select",
        label_visibility="collapsed"
    )

    if not tipo_nota:
        st.info("Selecione o tipo da nota para continuar o preenchimento.")
        return

    # ── Campos condicionais fora do form ──
    data_entrada = None
    data_saida = None
    data_negociacao = None

    if tipo_nota == "Compra":
        st.markdown("#### 📥 Data de Entrada / Saída")
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            data_entrada = st.date_input("Data de Entrada *", value=None, key="data_entrada")
        with col_d2:
            data_saida = st.date_input("Data de Saída", value=None, key="data_saida")

    elif tipo_nota == "Venda":
        st.markdown("#### 🤝 Data de Negociação")
        data_negociacao = st.date_input("Data de Negociação *", value=None, key="data_negociacao")

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
            competencia = st.text_input("📅 Competência *", placeholder="MM/AAAA")
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
        if not competencia.strip(): erros.append("Competência")
        if not valor.strip(): erros.append("Valor")

        # Validação condicional por tipo de nota
        if tipo_nota == "Compra" and data_entrada is None:
            erros.append("Data de Entrada")
        if tipo_nota == "Venda" and data_negociacao is None:
            erros.append("Data de Negociação")

        if erros:
            st.error(f"⚠️ Preencha os campos obrigatórios: {', '.join(erros)}")
            return

        # Verificar bloqueio de prazo (apenas para Compra, que tem data de entrada)
        if tipo_nota == "Compra":
            bloqueado, msg_bloqueio = verificar_bloqueio(data_entrada)
            if bloqueado:
                st.error(msg_bloqueio)
                return

        # Salvar arquivo
        arquivo_nome = None
        if arquivo:
            os.makedirs("uploads", exist_ok=True)
            arquivo_nome = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{arquivo.name}"
            with open(f"uploads/{arquivo_nome}", "wb") as f:
                f.write(arquivo.getbuffer())

        # Converter valor
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
                competencia, tipo_nota, data_entrada, data_saida,
                data_negociacao, valor, observacao, arquivo_nome,
                status, aberto_em
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            protocolo,
            st.session_state.setor,
            empresa, tipo, motivo, prioridade, nf_retorna,
            nome_parceiro.strip(), numero_nota.strip(),
            competencia.strip(), tipo_nota,
            data_entrada.strftime("%Y-%m-%d") if data_entrada else None,
            data_saida.strftime("%Y-%m-%d") if data_saida else None,
            data_negociacao.strftime("%Y-%m-%d") if data_negociacao else None,
            valor_float, observacao.strip(),
            arquivo_nome, "Aberto",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
        conn.commit()
        conn.close()

        st.success(f"✅ Chamado registrado com sucesso! Protocolo: **{protocolo}**")
        st.balloons()

# =============================================
# TELA MEUS CHAMADOS (setor)
# =============================================

def tela_meus_chamados():
    st.title("📋 Meus Chamados")
    st.markdown("---")

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT protocolo, tipo_inconsistencia, motivo, empresa,
               status, prioridade, aberto_em
        FROM chamados
        WHERE setor = ?
        ORDER BY aberto_em DESC
    """, (st.session_state.setor,))
    rows = cur.fetchall()
    conn.close()

    if not rows:
        st.info("Nenhum chamado registrado ainda.")
        return

    status_cor = {
        "Aberto": "🔴",
        "Em andamento": "🟡",
        "Resolvido": "🟢",
        "Cancelado": "⚫"
    }

    for row in rows:
        protocolo, tipo, motivo, empresa, status, prioridade, aberto_em = row
        icone = status_cor.get(status, "⚪")
        with st.expander(f"{icone} {protocolo} — {tipo} | {status}"):
            col1, col2, col3 = st.columns(3)
            col1.markdown(f"**Empresa:** {empresa}")
            col2.markdown(f"**Motivo:** {motivo}")
            col3.markdown(f"**Prioridade:** {prioridade}")
            st.markdown(f"**Aberto em:** {aberto_em}")

# =============================================
# TELA TODOS OS CHAMADOS (contabilidade)
# =============================================

def tela_todos_chamados():
    st.title("📋 Todos os Chamados")
    st.markdown("---")

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT protocolo, setor, tipo_inconsistencia, motivo,
               empresa, status, prioridade, aberto_em
        FROM chamados
        ORDER BY aberto_em DESC
    """)
    rows = cur.fetchall()
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

    status_cor = {
        "Aberto": "🔴",
        "Em andamento": "🟡",
        "Resolvido": "🟢",
        "Cancelado": "⚫"
    }

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
                agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                conn = get_conn()
                cur = conn.cursor()
                cur.execute("""
                    UPDATE chamados SET status=?, resolucao=?,
                    atendido_em=COALESCE(atendido_em, ?),
                    resolvido_em=CASE WHEN ?='Resolvido' THEN ? ELSE resolvido_em END
                    WHERE protocolo=?
                """, (novo_status, resolucao, agora, novo_status, agora, protocolo))
                conn.commit()
                conn.close()
                st.success("✅ Chamado atualizado!")
                st.rerun()
