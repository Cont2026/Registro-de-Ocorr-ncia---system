import streamlit as st
import base64
from database.connection import init_db, run_query

st.set_page_config(page_title="ROC - Registro de Ocorrencias Contabeis", page_icon="📋", layout="wide", initial_sidebar_state="expanded")

try:
    protocolo_url = st.query_params.get("protocolo", None)
except:
    protocolo_url = None

st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;500;600;700;800&family=Inter:wght@400;500;600&display=swap');
        html, body, [class*="css"], .stApp { font-family: 'Montserrat', sans-serif !important; }
        h1, h2, h3, h4, h5, h6 { font-family: 'Montserrat', sans-serif !important; font-weight: 600 !important; color: #041747 !important; }
        .stButton > button { font-family: 'Montserrat', sans-serif !important; font-weight: 600 !important; border-radius: 8px !important; background-color: #041747 !important; color: white !important; border: none !important; padding: 0.5rem 1rem !important; transition: all 0.2s ease !important; }
        .stButton > button:hover { background-color: #FAC318 !important; color: #041747 !important; }
        .stTextInput > div > input, .stTextArea > div > textarea { font-family: 'Montserrat', sans-serif !important; border-radius: 8px !important; border: 1.5px solid #e0e0e0 !important; }
        .stSelectbox > div { font-family: 'Montserrat', sans-serif !important; }
        section[data-testid="stSidebar"] { background-color: #041747 !important; }
        section[data-testid="stSidebar"] * { color: white !important; }
        section[data-testid="stSidebar"] .stButton > button { background-color: transparent !important; color: white !important; border: 1px solid rgba(255,255,255,0.2) !important; text-align: left !important; font-weight: 500 !important; }
        section[data-testid="stSidebar"] .stButton > button:hover { background-color: #FAC318 !important; color: #041747 !important; border-color: #FAC318 !important; }
        section[data-testid="stSidebar"] > div:first-child { padding-top: 0 !important; }
        section[data-testid="stSidebar"] > div > div:first-child { padding-top: 0 !important; margin-top: 0 !important; }
        section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] { padding-top: 0 !important; gap: 0 !important; }
        .login-card { background: white; border-radius: 16px; padding: 40px; box-shadow: 0 4px 24px rgba(4,23,71,0.10); border-top: 4px solid #041747; }
        div[data-testid="metric-container"] { background: white; border-radius: 12px; padding: 16px; border-left: 4px solid #FAC318; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
        div[data-testid="metric-container"] label { color: #041747 !important; font-weight: 600 !important; }
        .stExpander { border-radius: 10px !important; border: 1px solid #e8e8e8 !important; }
        .stTabs [data-baseweb="tab"] { font-family: 'Montserrat', sans-serif !important; font-weight: 500 !important; }
        .stTabs [aria-selected="true"] { color: #041747 !important; border-bottom-color: #FAC318 !important; }
        hr { border-color: rgba(4,23,71,0.1) !important; }
    </style>
""", unsafe_allow_html=True)

if "logado" not in st.session_state:
    st.session_state.logado = False
    st.session_state.usuario = None
    st.session_state.perfil = None
    st.session_state.setor = None
    st.session_state.pagina = None
    st.session_state.email = None
    st.session_state.user_id = None
    st.session_state.protocolo_aberto = protocolo_url

@st.cache_resource
def inicializar_banco():
    init_db()
    return True

@st.cache_resource
def carregar_logo_colorida():
    try:
        with open("assets/LOGO-GRUPO-LLE-COR-OFICIAL-PRINCIPAL.png", "rb") as f:
            return base64.b64encode(f.read()).decode()
    except:
        return None

@st.cache_resource
def get_chamados():
    from modules import chamados
    return chamados

@st.cache_resource
def get_dashboard():
    from modules import dashboard
    return dashboard

@st.cache_resource
def get_calendario():
    from modules import calendario
    return calendario

@st.cache_resource
def get_admin():
    from modules import admin
    return admin

@st.cache_resource
def get_tratativa():
    from modules import tratativa
    return tratativa

@st.cache_data(ttl=300, show_spinner=False)
def buscar_usuario(email, senha):
    rows = run_query(
        "SELECT id, nome, perfil, setor_nome, primeiro_acesso FROM usuarios WHERE email=%s AND senha=%s AND ativo=1",
        (email, senha), fetch=True)
    return rows[0] if rows else None

def tela_login():
    logo_b64 = carregar_logo_colorida()
    logo_html = f"<img src='data:image/png;base64,{logo_b64}' style='width:200px;display:block;margin:0 auto 8px;'/>" if logo_b64 else ""
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown(f"""
            <div class='login-card'>
                <div style='text-align:center;margin-bottom:32px;'>
                    {logo_html}
                    <p style='font-family:Montserrat,sans-serif;font-weight:800;font-size:2.2rem;letter-spacing:6px;color:#041747;margin:20px 0 8px;'>ROC</p>
                    <p style='font-family:Montserrat,sans-serif;font-weight:600;font-size:0.95rem;color:#041747;margin:0;'>Registro de Ocorrencias Contabeis</p>
                    <p style='font-family:Montserrat,sans-serif;font-weight:300;font-size:0.8rem;color:gray;margin:4px 0 0;'>Grupo LLE</p>
                </div>
        """, unsafe_allow_html=True)
        with st.form("form_login"):
            email = st.text_input("E-mail", placeholder="setor@grupolle.com.br")
            senha = st.text_input("Senha", type="password", placeholder="...")
            entrar = st.form_submit_button("Entrar", use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
        if entrar:
            if not email.strip().endswith("@grupolle.com.br"):
                st.error("Use seu e-mail corporativo @grupolle.com.br")
            else:
                usuario = buscar_usuario(email.strip().lower(), senha.strip())
                if usuario:
                    uid, nome, perfil, setor_nome, primeiro_acesso = usuario
                    st.session_state.logado = True
                    st.session_state.user_id = uid
                    st.session_state.usuario = nome
                    st.session_state.perfil = perfil
                    st.session_state.setor = setor_nome or nome
                    st.session_state.email = email.strip().lower()
                    st.session_state.primeiro_acesso = primeiro_acesso
                    if primeiro_acesso:
                        st.session_state.pagina = "trocar_senha"
                    elif protocolo_url:
                        st.session_state.pagina = "todos_chamados" if perfil == "contabilidade" else "meus_chamados"
                        st.session_state.protocolo_aberto = protocolo_url
                    else:
                        st.session_state.pagina = "dashboard" if perfil == "contabilidade" else "novo_chamado"
                    st.rerun()
                else:
                    st.error("E-mail ou senha incorretos.")

def tela_trocar_senha():
    st.title("Troque sua senha")
    st.markdown("Este e seu primeiro acesso. Por seguranca, defina uma senha pessoal.")
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        with st.form("form_trocar_senha"):
            nova = st.text_input("Nova senha", type="password", placeholder="Minimo 6 caracteres")
            confirma = st.text_input("Confirme a senha", type="password")
            salvar = st.form_submit_button("Salvar senha", use_container_width=True)
        if salvar:
            if not nova.strip() or len(nova.strip()) < 6:
                st.error("A senha deve ter no minimo 6 caracteres.")
            elif nova.strip() != confirma.strip():
                st.error("As senhas nao coincidem.")
            else:
                run_query("UPDATE usuarios SET senha=%s, primeiro_acesso=0 WHERE id=%s",
                          (nova.strip(), st.session_state.user_id))
                st.session_state.primeiro_acesso = 0
                st.session_state.pagina = "dashboard" if st.session_state.perfil == "contabilidade" else "novo_chamado"
                st.cache_data.clear()
                st.success("Senha alterada com sucesso!")
                st.rerun()

def sidebar():
    logo_b64 = carregar_logo_colorida()
    with st.sidebar:
        if logo_b64:
            st.markdown(f"""
                <div style='background:#041747;padding:24px 16px 20px;margin:-1rem -1rem 20px -1rem;border-bottom:1px solid rgba(255,255,255,0.15);'>
                    <div style='background:white;border-radius:12px;padding:10px 14px;display:inline-block;margin-bottom:16px;'>
                        <img src='data:image/png;base64,{logo_b64}' style='width:140px;display:block;'/>
                    </div>
                    <p style='font-family:Montserrat,sans-serif;font-weight:800;font-size:2rem;letter-spacing:5px;color:#FAC318;margin:0;'>ROC</p>
                    <p style='font-family:Montserrat,sans-serif;font-weight:300;font-size:0.72rem;color:rgba(255,255,255,0.55);margin:4px 0 0;'>Registro de Ocorrencias Contabeis</p>
                </div>
            """, unsafe_allow_html=True)

        st.markdown(f"""
            <div style='margin-bottom:16px;'>
                <p style='font-size:0.75rem;color:rgba(255,255,255,0.5);font-family:Montserrat,sans-serif;margin:0;'>Logado como</p>
                <p style='font-size:0.9rem;font-weight:600;color:white;font-family:Montserrat,sans-serif;margin:0;'>👤 {st.session_state.usuario}</p>
                <p style='font-size:0.75rem;color:rgba(255,255,255,0.4);font-family:Montserrat,sans-serif;margin:2px 0 0;'>{st.session_state.email or ""}</p>
            </div>
        """, unsafe_allow_html=True)

        if st.session_state.perfil == "contabilidade":
            abertos = run_query("SELECT COUNT(*) FROM chamados WHERE status='Aberto'", fetch=True)[0][0]
            em_andamento = run_query("SELECT COUNT(*) FROM chamados WHERE status='Em andamento'", fetch=True)[0][0]
            if abertos > 0 or em_andamento > 0:
                txt_abertos = f"<p style='font-size:12px;color:white;margin:0;'>🔴 {abertos} aberto(s)</p>" if abertos > 0 else ""
                txt_andamento = f"<p style='font-size:12px;color:white;margin:0;'>🟡 {em_andamento} em andamento</p>" if em_andamento > 0 else ""
                st.markdown(f"""
                <div style='background:rgba(250,195,24,0.15);border:1px solid rgba(250,195,24,0.4);
                border-radius:10px;padding:10px 14px;margin-bottom:12px;'>
                    <p style='font-size:12px;font-weight:700;color:#FAC318;margin:0 0 6px;'>⚡ Chamados pendentes</p>
                    {txt_abertos}{txt_andamento}
                </div>
                """, unsafe_allow_html=True)

        st.markdown("---")

        if st.session_state.perfil == "contabilidade":
            paginas = {
                "📊 Dashboard": "dashboard",
                "📋 Todos os Chamados": "todos_chamados",
                "📤 Solicitacao de Tratativa": "tratativa",
                "📅 Calendario": "calendario",
                "⚙️ Administracao": "admin",
            }
        else:
            paginas = {
                "➕ Novo Chamado": "novo_chamado",
                "📋 Meus Chamados": "meus_chamados",
                "📅 Calendario": "calendario",
            }

        for label, key in paginas.items():
            if st.button(label, use_container_width=True, key=f"nav_{key}"):
                st.session_state.pagina = key
                st.session_state.protocolo_aberto = None
                st.rerun()

        st.markdown("---")
        if st.button("Sair", use_container_width=True):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()

        st.markdown("""
            <div style='position:fixed;bottom:20px;left:0;width:260px;text-align:center;padding:0 16px;'>
                <p style='font-size:0.65rem;color:rgba(255,255,255,0.3);font-family:Montserrat,sans-serif;margin:0;'>ROC 2026 Grupo LLE</p>
            </div>
        """, unsafe_allow_html=True)

def main():
    inicializar_banco()
    if not st.session_state.logado:
        tela_login()
        return
    if st.session_state.get("primeiro_acesso"):
        tela_trocar_senha()
        return
    if not st.session_state.pagina:
        st.session_state.pagina = "dashboard" if st.session_state.perfil == "contabilidade" else "novo_chamado"
    sidebar()
    p = st.session_state.pagina
    protocolo_aberto = st.session_state.get("protocolo_aberto")
    if p == "dashboard":
        get_dashboard().tela_dashboard()
    elif p == "todos_chamados":
        get_chamados().tela_todos_chamados(protocolo_aberto)
    elif p == "meus_chamados":
        get_chamados().tela_meus_chamados(protocolo_aberto)
    elif p == "novo_chamado":
        get_chamados().tela_novo_chamado()
    elif p == "calendario":
        get_calendario().tela_calendario()
    elif p == "admin":
        get_admin().tela_admin()
    elif p == "tratativa":
        get_tratativa().tela_tratativa()

if __name__ == "__main__":
    main()
