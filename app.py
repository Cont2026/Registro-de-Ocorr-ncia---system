import streamlit as st
from datetime import datetime
from database.connection import get_conn, init_db
import base64
import os

st.set_page_config(
    page_title="ROC - Registro de Ocorrências Contábeis",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =============================================
# IDENTIDADE VISUAL GRUPO LLE
# =============================================

st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;500;600;700;800&family=Inter:wght@400;500;600&display=swap');

        html, body, [class*="css"], .stApp {
            font-family: 'Montserrat', sans-serif !important;
        }
        h1, h2, h3, h4, h5, h6 {
            font-family: 'Montserrat', sans-serif !important;
            font-weight: 600 !important;
            color: #041747 !important;
        }
        .stDataFrame, .stTable {
            font-family: 'Inter', sans-serif !important;
        }
        .stButton > button {
            font-family: 'Montserrat', sans-serif !important;
            font-weight: 600 !important;
            border-radius: 8px !important;
            background-color: #041747 !important;
            color: white !important;
            border: none !important;
            padding: 0.5rem 1rem !important;
            transition: all 0.2s ease !important;
        }
        .stButton > button:hover {
            background-color: #FAC318 !important;
            color: #041747 !important;
        }
        .stTextInput > div > input,
        .stTextArea > div > textarea {
            font-family: 'Montserrat', sans-serif !important;
            border-radius: 8px !important;
            border: 1.5px solid #e0e0e0 !important;
        }
        .stSelectbox > div {
            font-family: 'Montserrat', sans-serif !important;
        }
        section[data-testid="stSidebar"] {
            background-color: #041747 !important;
            font-family: 'Montserrat', sans-serif !important;
        }
        section[data-testid="stSidebar"] * {
            color: white !important;
        }
        section[data-testid="stSidebar"] .stButton > button {
            background-color: transparent !important;
            color: white !important;
            border: 1px solid rgba(255,255,255,0.2) !important;
            text-align: left !important;
            font-weight: 500 !important;
        }
        section[data-testid="stSidebar"] .stButton > button:hover {
            background-color: #FAC318 !important;
            color: #041747 !important;
            border-color: #FAC318 !important;
        }
        .roc-logo {
            font-family: 'Montserrat', sans-serif;
            font-weight: 800;
            font-size: 2rem;
            letter-spacing: 3px;
            color: #041747;
            margin: 0;
        }
        .roc-logo-sidebar {
            font-family: 'Montserrat', sans-serif;
            font-weight: 800;
            font-size: 1.4rem;
            letter-spacing: 3px;
            color: #FAC318;
            margin: 0;
        }
        .roc-subtitle {
            font-family: 'Montserrat', sans-serif;
            font-weight: 300;
            font-size: 0.85rem;
            color: gray;
            margin: 0;
        }
        .roc-subtitle-sidebar {
            font-family: 'Montserrat', sans-serif;
            font-weight: 300;
            font-size: 0.75rem;
            color: rgba(255,255,255,0.6);
            margin: 0;
        }
        .login-card {
            background: white;
            border-radius: 16px;
            padding: 40px;
            box-shadow: 0 4px 24px rgba(4,23,71,0.10);
            border-top: 4px solid #FAC318;
        }
        .metric-card {
            background: white;
            border-radius: 12px;
            padding: 20px;
            border-left: 4px solid #0071FE;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        }
        div[data-testid="metric-container"] {
            background: white;
            border-radius: 12px;
            padding: 16px;
            border-left: 4px solid #FAC318;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        }
        div[data-testid="metric-container"] label {
            color: #041747 !important;
            font-weight: 600 !important;
            font-family: 'Montserrat', sans-serif !important;
        }
        .stExpander {
            border-radius: 10px !important;
            border: 1px solid #e8e8e8 !important;
        }
        .stTabs [data-baseweb="tab"] {
            font-family: 'Montserrat', sans-serif !important;
            font-weight: 500 !important;
        }
        .stTabs [aria-selected="true"] {
            color: #041747 !important;
            border-bottom-color: #FAC318 !important;
        }
        hr {
            border-color: rgba(4,23,71,0.1) !important;
        }
    </style>
""", unsafe_allow_html=True)

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
            <div class='login-card'>
                <div style='text-align:center; margin-bottom: 32px;'>
                    <div style='display:inline-block; background:#041747;
                    border-radius:12px; padding:12px 24px; margin-bottom:16px;'>
                        <p style='font-family:Montserrat,sans-serif; font-weight:800;
                        font-size:1.8rem; letter-spacing:4px; color:#FAC318; margin:0;'>ROC</p>
                    </div>
                    <p style='font-family:Montserrat,sans-serif; font-weight:600;
                    font-size:1rem; color:#041747; margin:0;'>Registro de Ocorrências Contábeis</p>
                    <p style='font-family:Montserrat,sans-serif; font-weight:300;
                    font-size:0.8rem; color:gray; margin:4px 0 0;'>Grupo LLE</p>
                </div>
        """, unsafe_allow_html=True)

        with st.form("form_login"):
            login = st.text_input("Usuário", placeholder="seu.login")
            senha = st.text_input("Senha", type="password", placeholder="••••••••")
            entrar = st.form_submit_button("Entrar", use_container_width=True)

        st.markdown("</div>", unsafe_allow_html=True)

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
            <div style='padding: 16px 0 24px; border-bottom: 1px solid rgba(255,255,255,0.15); margin-bottom: 16px;'>
                <div style='background: rgba(250,195,24,0.15); border-radius: 10px;
                padding: 10px 16px; margin-bottom: 12px; display:inline-block;'>
                    <p style='font-family:Montserrat,sans-serif; font-weight:800;
                    font-size:1.3rem; letter-spacing:3px; color:#FAC318; margin:0;'>ROC</p>
                </div>
                <p style='font-family:Montserrat,sans-serif; font-weight:300;
                font-size:0.72rem; color:rgba(255,255,255,0.55); margin:0;'>
                Registro de Ocorrências Contábeis</p>
                <p style='font-family:Montserrat,sans-serif; font-weight:400;
                font-size:0.7rem; color:rgba(250,195,24,0.7); margin:4px 0 0;'>Grupo LLE</p>
            </div>
        """, unsafe_allow_html=True)

        st.markdown(f"""
            <div style='margin-bottom:16px;'>
                <p style='font-size:0.75rem; color:rgba(255,255,255,0.5);
                font-family:Montserrat,sans-serif; margin:0;'>Logado como</p>
                <p style='font-size:0.9rem; font-weight:600; color:white;
                font-family:Montserrat,sans-serif; margin:0;'>👤 {st.session_state.usuario}</p>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("---")

        if st.session_state.perfil == "contabilidade":
            paginas = {
                "📊 Dashboard": "dashboard",
                "📋 Todos os Chamados": "todos_chamados",
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

        st.markdown("""
            <div style='position:fixed; bottom:20px; left:0; width:260px;
            text-align:center; padding: 0 16px;'>
                <p style='font-size:0.65rem; color:rgba(255,255,255,0.3);
                font-family:Montserrat,sans-serif; margin:0;'>
                ROC © 2026 · Grupo LLE</p>
            </div>
        """, unsafe_allow_html=True)

# =============================================
# IMPORTAR MÓDULOS
# =============================================

from modules.chamados import tela_novo_chamado, tela_meus_chamados, tela_todos_chamados

# =============================================
# PÁGINAS
# =============================================

def pagina_dashboard():
    from modules.dashboard import tela_dashboard
    tela_dashboard()

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
