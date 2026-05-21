import streamlit as st
import os
from datetime import datetime
from database.connection import get_conn, init_db

# =============================================
# CONFIGURAÇÃO DA PÁGINA
# =============================================

st.set_page_config(
    page_title="RO - Registro de Ocorrências",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =============================================
# SESSÃO
# =============================================

if "logado" not in st.session_state:
    st.session_state.logado = False
    st.session_state.usuario = None
    st.session_state.perfil = None
    st.session_state.setor = None

# =============================================
# LOGIN
# =============================================

def tela_login():
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("""
            <div style='text-align:center; margin-bottom: 32px;'>
                <h1 style='font-size:2rem; font-weight:700; margin-bottom:4px;'>RO</h1>
                <p style='color:gray; font-size:0.95rem;'>Registro de Ocorrências Contábeis</p>
            </div>
        """, unsafe_allow_html=True)

        with st.form("form_login"):
            login = st.text_input("Usuário", placeholder="seu.login")
            senha = st.text_input("Senha", type="password", placeholder="••••••••")
            entrar = st.form_submit_button("Entrar", use_container_width=True)

        if entrar:
            conn = get_conn()
            cur = conn.cursor()
            cur.execute(
                "SELECT nome, perfil FROM usuarios WHERE login=%s AND senha=%s AND ativo=1",
                (login.strip(), senha.strip())
            )
            row = cur.fetchone()
            cur.close()
            conn.close()

            if row:
                st.session_state.logado = True
                st.session_state.usuario = row[0]
                st.session_state.perfil = row[1]
                st.session_state.setor = row[0]
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")

# =============================================
# SIDEBAR
# =============================================

def sidebar():
    with st.sidebar:
        st.markdown("""
            <div style='padding: 12px 0 20px;'>
                <h2 style='font-size:1.3rem; font-weight:700; margin:0;'>RO</h2>
                <p style='color:gray; font-size:0.8rem; margin:2px 0 0;'>Registro de Ocorrências</p>
            </div>
        """, unsafe_allow_html=True)

        st.markdown(f"👤 **{st.session_state.usuario}**")
        st.markdown("---")

        if st.session_state.perfil == "contabilidade":
            paginas = {
                "📊 Dashboard": "dashboard",
                "📋 Todos os Chamados": "todos_chamados",
                "➕ Novo Chamado": "novo_chamado",
                "📅 Calendário": "calendario",
                "⚙️ Administração": "admin",
            }
        else:
            paginas = {
                "➕ Novo Chamado": "novo_chamado",
                "📋 Meus Chamados": "meus_chamados",
                "📅 Calendário": "calendario",
            }

        for label, key in paginas.items():
            if st.button(label, use_container_width=True, key=f"nav_{key}"):
                st.session_state.pagina = key
                st.rerun()

        st.markdown("---")
        if st.button("🚪 Sair", use_container_width=True):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()

# =============================================
# IMPORTAR MÓDULOS
# =============================================

from modules.chamados import (
    tela_novo_chamado,
    tela_meus_chamados,
    tela_todos_chamados
)

# =============================================
# PÁGINAS PLACEHOLDER
# =============================================

def pagina_dashboard():
    st.title("📊 Dashboard")
    st.info("Em construção — próximo passo.")

def pagina_calendario():
    from modules.calendario import tela_calendario
    tela_calendario()

def pagina_admin():
    from modules.admin import tela_admin
    tela_admin()

# =============================================
# ROTEADOR
# =============================================

def main():
    init_db()

    if not st.session_state.logado:
        tela_login()
        return

    if "pagina" not in st.session_state:
        if st.session_state.perfil == "contabilidade":
            st.session_state.pagina = "dashboard"
        else:
            st.session_state.pagina = "novo_chamado"

    sidebar()

    pagina = st.session_state.pagina

    if pagina == "dashboard":
        pagina_dashboard()
    elif pagina == "todos_chamados":
        tela_todos_chamados()
    elif pagina == "meus_chamados":
        tela_meus_chamados()
    elif pagina == "novo_chamado":
        tela_novo_chamado()
    elif pagina == "calendario":
        pagina_calendario()
    elif pagina == "admin":
        pagina_admin()

if __name__ == "__main__":
    main()
