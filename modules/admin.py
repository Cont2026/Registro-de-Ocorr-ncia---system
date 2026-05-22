import streamlit as st
from database.connection import run_query

def tela_admin():
    st.title("⚙️ Administração")
    st.markdown("---")

    aba = st.tabs(["👥 Usuários e Setores", "📋 Abertura de Período / Descontabilização"])

    with aba[0]:
        st.subheader("Usuários e Setores cadastrados")
        usuarios = run_query("SELECT id, nome, login, perfil, ativo FROM usuarios ORDER BY perfil, nome", fetch=True)

        for uid, nome, login, perfil, ativo in usuarios:
            icone = "🟢" if ativo else "🔴"
            perfil_icon = "👑" if perfil == "contabilidade" else "🏢"
            with st.expander(f"{icone} {perfil_icon} {nome} — `{login}`"):
                c1, c2 = st.columns(2)
                nova_senha = c1.text_input("Nova senha", key=f"s_{uid}", placeholder="Deixe em branco para não alterar")
                novo_ativo = c2.selectbox("Status", [1, 0], index=0 if ativo else 1,
                                          format_func=lambda x: "Ativo" if x == 1 else "Inativo",
                                          key=f"a_{uid}")
                if st.button("💾 Salvar", key=f"u_{uid}"):
                    if nova_senha.strip():
                        run_query("UPDATE usuarios SET senha=%s, ativo=%s WHERE id=%s", (nova_senha.strip(), novo_ativo, uid))
                    else:
                        run_query("UPDATE usuarios SET ativo=%s WHERE id=%s", (novo_ativo, uid))
                    st.success("✅ Atualizado!")
                    st.rerun()

        st.markdown("---")
        st.subheader("➕ Novo Setor")
        with st.form("form_setor"):
            c1, c2, c3 = st.columns(3)
            nome = c1.text_input("Nome *")
            login = c2.text_input("Login *")
            senha = c3.text_input("Senha *")
            if st.form_submit_button("➕ Adicionar", use_container_width=True):
                if not nome.strip() or not login.strip() or not senha.strip():
                    st.error("⚠️ Preencha todos os campos.")
                else:
                    try:
                        run_query("INSERT INTO usuarios (nome,login,senha,perfil) VALUES (%s,%s,%s,'setor')",
                                  (nome.strip(), login.strip(), senha.strip()))
                        st.success(f"✅ Setor '{nome}' adicionado!")
                        st.rerun()
                    except:
                        st.error("⚠️ Login já existe.")

    with aba[1]:
        st.subheader("Tipos cadastrados")
        tipos = run_query("SELECT id, nome, ativo FROM tipos_inconsistencia ORDER BY nome", fetch=True)

        for tid, nome, ativo in tipos:
            icone = "🟢" if ativo else "🔴"
            with st.expander(f"{icone} {nome}"):
                c1, c2 = st.columns(2)
                novo_nome = c1.text_input("Nome", value=nome, key=f"tn_{tid}")
                novo_ativo = c2.selectbox("Status", [1, 0], index=0 if ativo else 1,
                                          format_func=lambda x: "Ativo" if x == 1 else "Inativo",
                                          key=f"ta_{tid}")
                col_salvar, col_excluir = st.columns(2)
                with col_salvar:
                    if st.button("💾 Salvar", key=f"ts_{tid}"):
                        run_query("UPDATE tipos_inconsistencia SET nome=%s, ativo=%s WHERE id=%s",
                                  (novo_nome.strip(), novo_ativo, tid))
                        st.cache_data.clear()
                        st.success("✅ Atualizado!")
                        st.rerun()
                with col_excluir:
                    if st.button("🗑️ Excluir", key=f"tex_{tid}", type="secondary"):
                        st.session_state[f"confirmar_exclusao_{tid}"] = True
                        st.rerun()

                if st.session_state.get(f"confirmar_exclusao_{tid}"):
                    st.warning(f"⚠️ Tem certeza que deseja excluir **{nome}**? Esta ação não pode ser desfeita.")
                    cc1, cc2 = st.columns(2)
                        with cc1:
                        if st.button("✅ Confirmar exclusão", key=f"conf_{tid}"):
                            try:
                                run_query("DELETE FROM tipos_inconsistencia WHERE id=%s", (tid,))
                                st.session_state.pop(f"confirmar_exclusao_{tid}", None)
                                st.cache_data.clear()
                                st.cache_resource.clear()
                                st.success("✅ Excluído!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"⚠️ Não foi possível excluir. Este tipo pode estar em uso em chamados existentes.")
                    with cc2:
                        if st.button("❌ Cancelar", key=f"canc_{tid}"):
                            st.session_state.pop(f"confirmar_exclusao_{tid}", None)
                            st.rerun()

        st.markdown("---")
        st.subheader("➕ Novo Tipo")
        with st.form("form_tipo"):
            novo = st.text_input("Nome *")
            if st.form_submit_button("➕ Adicionar", use_container_width=True):
                if not novo.strip():
                    st.error("⚠️ Preencha o nome.")
                else:
                    try:
                        run_query("INSERT INTO tipos_inconsistencia (nome) VALUES (%s)", (novo.strip(),))
                        st.cache_data.clear()
                        st.success(f"✅ '{novo}' adicionado!")
                        st.rerun()
                    except:
                        st.error("⚠️ Já existe.")
