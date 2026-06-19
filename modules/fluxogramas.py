import streamlit as st
import os

# Pasta no repositório onde ficam as imagens dos fluxogramas (PNG/JPG).
# Crie a pasta "fluxogramas" na raiz do repositório e coloque as imagens lá.
PASTA = "fluxogramas"
EXTS = (".png", ".jpg", ".jpeg", ".webp")

def _titulo(arquivo):
    nome = os.path.splitext(arquivo)[0]
    return nome.replace("_", " ").replace("-", " ").strip()

@st.cache_data(ttl=60)
def _listar_arquivos():
    if not os.path.isdir(PASTA):
        return []
    return sorted([f for f in os.listdir(PASTA) if f.lower().endswith(EXTS)])

def tela_fluxogramas():
    st.title("🗺️ Fluxogramas dos Processos")
    st.markdown("Selecione um processo para visualizar o fluxograma.")
    st.markdown("---")

    arquivos = _listar_arquivos()
    if not arquivos:
        st.info("Nenhum fluxograma disponível no momento. "
                "As imagens são adicionadas pela equipe responsável.")
        return

    opcoes = {_titulo(a): a for a in arquivos}
    escolha = st.selectbox("Processo:", list(opcoes.keys()))

    if escolha:
        caminho = os.path.join(PASTA, opcoes[escolha])
        st.markdown(f"#### {escolha}")
        try:
            st.image(caminho, use_container_width=True)
            with open(caminho, "rb") as f:
                st.download_button("⬇️ Baixar imagem", f.read(),
                    file_name=opcoes[escolha], use_container_width=True)
        except Exception:
            st.error("Não foi possível carregar esta imagem.")
