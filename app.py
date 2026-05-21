import streamlit as st
from datetime import datetime
from database.connection import get_conn, init_db

st.set_page_config(
    page_title="ROC - Registro de Ocorrências Contábeis",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =============================================
# FONTE POPPINS
# =============================================

st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&family=Inter:wght@400;500&display=swap');

        html, body, [class*="css"], .stApp {
            font-family: 'Poppins', sans-serif !important;
        }
        h1, h2, h3, h4, h5, h6 {
            font-family: 'Poppins', sans-serif !important;
            font-weight: 600 !important;
        }
        .stDataFrame, .stTable {
            font-family: 'Inter', sans-serif !important;
        }
        .stButton > button {
            font-family: 'Poppins', sans-serif !important;
            font-weight: 500 !important;
            border-radius: 8px !important;
        }
        .stTextInput > div > input,
        .stSelectbox > div,
        .stTextArea > div > textarea {
            font-family: 'Poppins', sans-serif !important;
        }
        .roc-logo {
            font-family: 'Poppins', sans-serif;
            font-weight: 700;
            font-size: 2rem;
            letter-spacing: 2px;
            margin: 0;
        }
        .roc-subtitle {
            font-family: 'Poppins', sans-serif;
            font-weight: 300;
            font-size: 0.9rem;
            color: gray;
            margin: 0;
        }
        section[data-testid="stSidebar"] {
            font-family: 'Poppins', sans-serif !important;
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
            <div style='text-align:center; margin-bottom: 32px;'>
                <p class='roc-logo'>ROC</p>
                <p class='roc-subtitle'>Registro de Ocorrências Contábeis</p>
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
                <p class='roc-logo' style='font-size:1.5rem;'>ROC</p>
                <p class='roc-subtitle'>Registro de Ocorrências</p>
            </div>
        """, unsafe_allow_html=True)

        st.markdown(f"👤 **{st.session_state.usuario}**")
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
