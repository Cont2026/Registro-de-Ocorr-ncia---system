import streamlit as st
from database.connection import get_conn
from datetime import datetime, date
from zoneinfo import ZoneInfo

BRASILIA = ZoneInfo("America/Sao_Paulo")

def formatar_data(d):
    if d:
        return d.strftime("%d/%m/%Y") if hasattr(d, 'strftime') else str(d)
    return "—"

def card_calendario(titulo, data, cor_borda, cor_titulo):
    hoje = datetime.now(BRASILIA).date()

    if not data:
        icone = "⚪"
        status = "Não definida"
    else:
        d = data.date() if hasattr(data, 'date') else data
        if d < hoje:
            icone = "✅"
            status = "Concluída"
        elif d == hoje:
            icone = "🟡"
            status = "Hoje"
        else:
            icone = "🔵"
            status = "Pendente"

    return f"""
    <div style='border: 2px solid {cor_borda}; border-radius: 12px; padding: 18px;
    text-align: center; margin: 4px;'>
        <p style='font-size:12px; color:{cor_titulo}; font-weight:600;
        text-transform:uppercase; letter-spacing:1px; margin:0;'>{titulo}</p>
        <p style='font-size:26px; margin:8px 0 4px;'>{icone}</p>
        <p style='font-size:15px; font-weight:600; margin:0;'>{formatar_data(data)}</p>
        <p style='font-size:11px; color:gray; margin:4px 0 0;'>{status}</p>
    </div>
    """

def tela_calendario():
    st.title("📅 Calendário de Fechamento")
    st.markdown("Acompanhe as datas de importação e fechamento contábil do mês.")
    st.markdown("---")

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT mes_ano, importacao_1, importacao_2, importacao_3, fechamento
        FROM calendario_fechamento
        ORDER BY criado_em DESC
        LIMIT 3
    """)
    registros = cur.fetchall()
    cur.close()
    conn.close()

    if not registros:
        st.info("Nenhuma data de fechamento cadastrada ainda. Aguarde a Contabilidade inserir as datas.")
    else:
        for reg in registros:
            mes_ano, imp1, imp2, imp3, fechamento = reg
            st.markdown(f"### 📆 {mes_ano}")
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.markdown(card_calendario("Importação 1", imp1, "#3B82F6", "#3B82F6"), unsafe_allow_html=True)
            with col2:
                st.markdown(card_calendario("Importação 2", imp2, "#EAB308", "#EAB308"), unsafe_allow_html=True)
            with col3:
                st.markdown(card_calendario("Importação 3", imp3, "#F97316", "#F97316"), unsafe_allow_html=True)
            with col4:
                st.markdown(card_calendario("Fechamento", fechamento, "#EF4444", "#EF4444"), unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

    if st.session_state.perfil == "contabilidade":
        st.markdown("---")
        st.subheader("➕ Inserir datas do mês")

        with st.form("form_calendario"):
            col1, col2 = st.columns(2)
            with col1:
                mes_ano = st.text_input("Mês/Ano *", placeholder="ex: Maio/2026")
                imp1 = st.date_input("📥 Importação 1", value=None)
                imp2 = st.date_input("📥 Importação 2", value=None)
            with col2:
                imp3 = st.date_input("📥 Importação 3", value=None)
                fechamento = st.date_input("🔒 Fechamento", value=None)

            salvar = st.form_submit_button("💾 Salvar Calendário", use_container_width=True)

        if salvar:
            if not mes_ano.strip():
                st.error("⚠️ Preencha o Mês/Ano.")
            else:
                conn = get_conn()
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO calendario_fechamento
                    (mes_ano, importacao_1, importacao_2, importacao_3, fechamento)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    mes_ano.strip(),
                    imp1 if imp1 else None,
                    imp2 if imp2 else None,
                    imp3 if imp3 else None,
                    fechamento if fechamento else None
                ))
                conn.commit()
                cur.close()
                conn.close()
                st.success(f"✅ Calendário de {mes_ano} salvo!")
                st.rerun()
