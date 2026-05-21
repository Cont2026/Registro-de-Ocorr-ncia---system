import streamlit as st
from database.connection import get_conn
from datetime import datetime
from zoneinfo import ZoneInfo

BRASILIA = ZoneInfo("America/Sao_Paulo")

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

    # =============================================
    # QUADRO VISÍVEL PARA TODOS
    # =============================================

    if not registros:
        st.info("Nenhuma data de fechamento cadastrada ainda. Aguarde a Contabilidade inserir as datas.")
    else:
        for reg in registros:
            mes_ano, imp1, imp2, imp3, fechamento = reg

            st.markdown(f"### 📆 {mes_ano}")

            col1, col2, col3, col4 = st.columns(4)

            def formatar_data(d):
                if d:
                    return d.strftime("%d/%m/%Y") if hasattr(d, 'strftime') else str(d)
                return "—"

            def status_data(d):
                if not d:
                    return "⚪"
                hoje = datetime.now(BRASILIA).date()
                data = d if isinstance(d, type(hoje)) else d
                if hasattr(data, 'date'):
                    data = data.date()
                if data < hoje:
                    return "✅"
                elif data == hoje:
                    return "🟡"
                else:
                    return "🔵"

            with col1:
                st.markdown(f"""
                <div style='background: var(--background-color); border: 1px solid #333;
                border-radius: 10px; padding: 16px; text-align: center;'>
                    <p style='font-size:12px; color:gray; margin:0;'>Importação 1</p>
                    <p style='font-size:22px; margin:4px 0;'>{status_data(imp1)}</p>
                    <p style='font-size:14px; font-weight:600; margin:0;'>{formatar_data(imp1)}</p>
                </div>
                """, unsafe_allow_html=True)

            with col2:
                st.markdown(f"""
                <div style='background: var(--background-color); border: 1px solid #333;
                border-radius: 10px; padding: 16px; text-align: center;'>
                    <p style='font-size:12px; color:gray; margin:0;'>Importação 2</p>
                    <p style='font-size:22px; margin:4px 0;'>{status_data(imp2)}</p>
                    <p style='font-size:14px; font-weight:600; margin:0;'>{formatar_data(imp2)}</p>
                </div>
                """, unsafe_allow_html=True)

            with col3:
                st.markdown(f"""
                <div style='background: var(--background-color); border: 1px solid #333;
                border-radius: 10px; padding: 16px; text-align: center;'>
                    <p style='font-size:12px; color:gray; margin:0;'>Importação 3</p>
                    <p style='font-size:22px; margin:4px 0;'>{status_data(imp3)}</p>
                    <p style='font-size:14px; font-weight:600; margin:0;'>{formatar_data(imp3)}</p>
                </div>
                """, unsafe_allow_html=True)

            with col4:
                st.markdown(f"""
                <div style='background: var(--background-color); border: 1px solid #333;
                border-radius: 10px; padding: 16px; text-align: center;'>
                    <p style='font-size:12px; color:gray; margin:0;'>Fechamento</p>
                    <p style='font-size:22px; margin:4px 0;'>{status_data(fechamento)}</p>
                    <p style='font-size:14px; font-weight:600; margin:0;'>{formatar_data(fechamento)}</p>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

    # =============================================
    # FORMULÁRIO — SOMENTE CONTABILIDADE
    # =============================================

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
                imp3 = st.date_input("�
