import streamlit as st
import base64
from datetime import datetime
from zoneinfo import ZoneInfo
from database.connection import run_query

BRASILIA = ZoneInfo("America/Sao_Paulo")

@st.cache_data(ttl=60)
def carregar_fluxogramas():
    rows = run_query("SELECT id, titulo, nome_arquivo, enviado_em FROM fluxogramas ORDER BY titulo", fetch=True)
    return rows if rows else []

def carregar_imagem(fid):
    r = run_query("SELECT nome_arquivo, dados FROM fluxogramas WHERE id=%s", (fid,), fetch=True)
    return r[0] if r else None

def tela_fluxogramas():
    st.title("🗺️ Fluxogramas dos Processos")
    eh_contabilidade = st.session_state.get("perfil") == "contabilidade"

    # === Área de envio (apenas Contabilidade) ===
    if eh_contabilidade:
        with st.expander("➕ Enviar / Gerenciar fluxogramas"):
            st.markdown("**Enviar novo fluxograma**")
            titulo = st.text_input("Título do processo *", placeholder="ex: Alteração de NF pelo Setor", key="flux_titulo")
            arquivo = st.file_uploader("Imagem do fluxograma *", type=["png", "jpg", "jpeg", "webp"], key="flux_arquivo")
            if st.button("📤 Enviar fluxograma", use_container_width=True):
                if not titulo.strip():
                    st.error("Informe o título do processo.")
                elif arquivo is None:
                    st.error("Selecione uma imagem.")
                else:
                    dados = base64.b64encode(arquivo.getvalue()).decode("utf-8")
                    run_query("""INSERT INTO fluxogramas (titulo, nome_arquivo, dados, enviado_em)
                        VALUES (%s,%s,%s,%s)""",
                        (titulo.strip(), arquivo.name, dados,
                         datetime.now(BRASILIA).strftime("%Y-%m-%d %H:%M:%S")))
                    st.cache_data.clear()
                    st.success(f"✅ Fluxograma '{titulo.strip()}' enviado!")
                    st.rerun()

            st.markdown("---")
            st.markdown("**Fluxogramas cadastrados** (para remover)")
            lista_g = carregar_fluxogramas()
            if not lista_g:
                st.caption("Nenhum fluxograma cadastrado.")
            else:
                for fid, tit, narq, env in lista_g:
                    c1, c2 = st.columns([5, 1])
                    c1.markdown(f"📄 {tit}  \n<span style='font-size:11px;color:#999;'>{narq or ''} · {env or ''}</span>", unsafe_allow_html=True)
                    if c2.button("🗑️", key=f"del_flux_{fid}", help="Remover"):
                        run_query("DELETE FROM fluxogramas WHERE id=%s", (fid,))
                        st.cache_data.clear()
                        st.rerun()
        st.markdown("---")

    # === Visualização (todos) ===
    st.markdown("Selecione um processo para visualizar o fluxograma.")
    lista = carregar_fluxogramas()
    if not lista:
        st.info("Nenhum fluxograma disponível no momento.")
        return

    opcoes = {tit: fid for fid, tit, narq, env in lista}
    escolha = st.selectbox("Processo:", list(opcoes.keys()))
    if escolha:
        info = carregar_imagem(opcoes[escolha])
        if not info:
            st.error("Não foi possível carregar a imagem.")
            return
        narq, dados = info
        try:
            img_bytes = base64.b64decode(dados)
            st.markdown(f"#### {escolha}")
            st.image(img_bytes, use_container_width=True)
            st.download_button("⬇️ Baixar imagem", img_bytes,
                file_name=narq or f"{escolha}.png", use_container_width=True)
        except Exception:
            st.error("Não foi possível exibir esta imagem.")
