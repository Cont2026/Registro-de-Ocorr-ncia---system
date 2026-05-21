import streamlit as st
from database.connection import get_conn
from datetime import datetime, date
from zoneinfo import ZoneInfo
import calendar

BRASILIA = ZoneInfo("America/Sao_Paulo")
MESES_PT = ["Janeiro","Fevereiro","Março","Abril","Maio","Junho",
            "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]

def formatar_data(d):
    if d:
        return d.strftime("%d/%m/%Y") if hasattr(d, 'strftime') else str(d)
    return "—"

def status_data(d):
    if not d:
        return "⚪", "Não definida", "#999"
    hoje = datetime.now(BRASILIA).date()
    data = d.date() if hasattr(d, 'date') else d
    if data < hoje:
        return "✅", "Concluída", "#22c55e"
    elif data == hoje:
        return "🟡", "Hoje", "#f59e0b"
    else:
        dias = (data - hoje).days
        return "🔵", f"Em {dias} dias", "#3B82F6"

def card_evento(titulo, data, cor_borda):
    icone, status_txt, cor_status = status_data(data)
    return f"""
    <div style='border:2px solid {cor_borda}; border-radius:12px; padding:16px;
    text-align:center; background:white; box-shadow:0 2px 8px rgba(0,0,0,0.06);'>
        <p style='font-size:11px; color:{cor_borda}; font-weight:700;
        text-transform:uppercase; letter-spacing:1px; margin:0 0 8px;'>{titulo}</p>
        <p style='font-size:24px; margin:0 0 4px;'>{icone}</p>
        <p style='font-size:14px; font-weight:700; color:#041747; margin:0;'>{formatar_data(data)}</p>
        <p style='font-size:11px; color:{cor_status}; font-weight:600; margin:4px 0 0;'>{status_txt}</p>
    </div>
    """

def tela_calendario():
    st.title("📅 Calendário Operacional")
    st.markdown("Acompanhe importações e fechamentos contábeis.")
    st.markdown("---")

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT mes_ano, importacao_1, importacao_2, importacao_3, fechamento
        FROM calendario_fechamento
        ORDER BY criado_em DESC
    """)
    registros = cur.fetchall()
    cur.close()
    conn.close()

    aba1, aba2, aba3 = st.tabs(["📆 Mensal", "📅 Próximo Mês", "🗓️ Visão Anual"])

    # =============================================
    # ABA MENSAL
    # =============================================
    with aba1:
        if not registros:
            st.info("Nenhuma data cadastrada ainda.")
        else:
            reg = registros[0]
            mes_ano, imp1, imp2, imp3, fechamento = reg
            st.markdown(f"### 📆 {mes_ano}")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.markdown(card_evento("Importação 1", imp1, "#3B82F6"), unsafe_allow_html=True)
            with col2:
                st.markdown(card_evento("Importação 2", imp2, "#EAB308"), unsafe_allow_html=True)
            with col3:
                st.markdown(card_evento("Importação 3", imp3, "#F97316"), unsafe_allow_html=True)
            with col4:
                st.markdown(card_evento("Fechamento", fechamento, "#EF4444"), unsafe_allow_html=True)

    # =============================================
    # ABA PRÓXIMO MÊS
    # =============================================
    with aba2:
        if len(registros) < 2:
            st.info("Cadastre as datas do próximo mês para visualizar aqui.")
        else:
            reg = registros[1]
            mes_ano, imp1, imp2, imp3, fechamento = reg
            st.markdown(f"### 📅 {mes_ano}")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.markdown(card_evento("Importação 1", imp1, "#3B82F6"), unsafe_allow_html=True)
            with col2:
                st.markdown(card_evento("Importação 2", imp2, "#EAB308"), unsafe_allow_html=True)
            with col3:
                st.markdown(card_evento("Importação 3", imp3, "#F97316"), unsafe_allow_html=True)
            with col4:
                st.markdown(card_evento("Fechamento", fechamento, "#EF4444"), unsafe_allow_html=True)

    # =============================================
    # ABA VISÃO ANUAL
    # =============================================
    with aba3:
        if not registros:
            st.info("Nenhuma data cadastrada ainda.")
        else:
            st.markdown("#### 🗓️ Visão Anual — Todos os períodos cadastrados")
            st.markdown("---")

            for reg in registros:
                mes_ano, imp1, imp2, imp3, fechamento = reg

                icone_imp1, _, _ = status_data(imp1)
                icone_imp2, _, _ = status_data(imp2)
                icone_imp3, _, _ = status_data(imp3)
                icone_fech, _, _ = status_data(fechamento)

                st.markdown(f"""
                <div style='background:white; border:1px solid #e8e8e8; border-radius:12px;
                padding:16px 20px; margin-bottom:12px;
                box-shadow:0 2px 6px rgba(0,0,0,0.05);'>
                    <div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;'>
                        <p style='font-size:15px; font-weight:700; color:#041747; margin:0; min-width:120px;'>
                        📆 {mes_ano}</p>
                        <div style='display:flex; gap:16px; flex-wrap:wrap;'>
                            <span style='font-size:12px; color:#3B82F6; font-weight:600;'>
                            {icone_imp1} Imp.1: {formatar_data(imp1)}</span>
                            <span style='font-size:12px; color:#EAB308; font-weight:600;'>
                            {icone_imp2} Imp.2: {formatar_data(imp2)}</span>
                            <span style='font-size:12px; color:#F97316; font-weight:600;'>
                            {icone_imp3} Imp.3: {formatar_data(imp3)}</span>
                            <span style='font-size:12px; color:#EF4444; font-weight:600;'>
                            {icone_fech} Fechamento: {formatar_data(fechamento)}</span>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

    # =============================================
    # FORMULÁRIO — SOMENTE CONTABILIDADE
    # =============================================
    if st.session_state.perfil == "contabilidade":
        st.markdown("---")
        st.subheader("➕ Inserir datas do período")

        with st.form("form_calendario"):
            col1, col2 = st.columns(2)
            with col1:
                mes_ano_input = st.text_input("Mês/Ano *", placeholder="ex: Junho/2026")
                imp1_input = st.date_input("📥 Importação 1", value=None)
                imp2_input = st.date_input("📥 Importação 2", value=None)
            with col2:
                imp3_input = st.date_input("📥 Importação 3", value=None)
                fechamento_input = st.date_input("🔒 Fechamento", value=None)

            salvar = st.form_submit_button("💾 Salvar Período", use_container_width=True)

        if salvar:
            if not mes_ano_input.strip():
                st.error("⚠️ Preencha o Mês/Ano.")
            else:
                conn = get_conn()
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO calendario_fechamento
                    (mes_ano, importacao_1, importacao_2, importacao_3, fechamento)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    mes_ano_input.strip(),
                    imp1_input if imp1_input else None,
                    imp2_input if imp2_input else None,
                    imp3_input if imp3_input else None,
                    fechamento_input if fechamento_input else None
                ))
                conn.commit()
                cur.close()
                conn.close()
                st.success(f"✅ Período {mes_ano_input} salvo!")
                st.rerun()
