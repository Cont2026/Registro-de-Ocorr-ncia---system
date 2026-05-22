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
            status_icon = "🟢" if ativo else "🔴"
            perfil_icon = "👑" if perfil == "contabilidade" else "🏢"
            with st.expander(f"{status_icon} {perfil_icon} {nome} — {login}"):
                c1, c2 = st.columns(2)
                nova_senha = c1.text_input("Nova senha", key=f"s_{uid}", placeholder="Deixe em branco para não alterar")
                novo_ativo = c2.selectbox("Status", [1, 0], index=0 if ativo else 1,
                    format_func=lambda x: "Ativo" if x == 1 else "Inativo", key=f"a_{uid}")
                if st.button("💾 Salvar", key=f"u_{uid}"):
                    if nova_senha.strip():
                        run_query("UPDATE usuarios SET senha=%s, ativo=%s WHERE id=%s",
                            (nova_senha.strip(), novo_ativo, uid))
                    else:
                        run_query("UPDATE usuarios SET ativo=%s WHERE id=%s", (novo_ativo, uid))
                    st.success("✅ Atualizado!")
                    st.rerun()

        st.markdown("---")
        st.subheader("Novo Setor")
        with st.form("form_setor"):
            c1, c2, c3 = st.columns(3)
            novo_nome_setor = c1.text_input("Nome *")
            novo_login = c2.text_input("Login *")
            nova_senha_setor = c3.text_input("Senha *")
            if st.form_submit_button("Adicionar", use_container_width=True):
                if not novo_nome_setor.strip() or not novo_login.strip() or not nova_senha_setor.strip():
                    st.error("Preencha todos os campos.")
                else:
                    try:
                        run_query(
                            "INSERT INTO usuarios (nome,login,senha,perfil) VALUES (%s,%s,%s,'setor')",
                            (novo_nome_setor.strip(), novo_login.strip(), nova_senha_setor.strip()))
                        st.success(f"Setor '{novo_nome_setor}' adicionado!")
                        st.rerun()
                    except Exception:
                        st.error("Login ja existe.")

    with aba[1]:
        st.subheader("Gerenciar Tipos")
        st.markdown("Edite, adicione ou remova os tipos. Clique em Salvar quando terminar.")
        st.markdown("---")

        if "lista_tipos" not in st.session_state or st.session_state.get("reload_tipos", True):
            tipos_db = run_query(
                "SELECT id, nome FROM tipos_inconsistencia WHERE ativo=1 ORDER BY nome", fetch=True)
            st.session_state.lista_tipos = [{"id": t[0], "nome": t[1]} for t in tipos_db]
            st.session_state.reload_tipos = False

        indices_remover = []
        for i, item in enumerate(st.session_state.lista_tipos):
            c1, c2 = st.columns([5, 1])
            with c1:
                chave = str(item.get("id", "novo"))
                novo_nome = st.text_input(
                    f"Tipo {i+1}", value=item["nome"],
                    key=f"tipo_edit_{i}_{chave}",
                    label_visibility="collapsed")
                st.session_state.lista_tipos[i]["nome"] = novo_nome
            with c2:
                if st.button("X", key=f"rem_{i}_{chave}", help="Remover"):
                    indices_remover.append(i)

        if indices_remover:
            for idx in sorted(indices_remover, reverse=True):
                st.session_state.lista_tipos.pop(idx)
            st.rerun()

        st.markdown("---")
        col_add, col_save = st.columns(2)

        with col_add:
            if st.button("Adicionar novo tipo", use_container_width=True):
                st.session_state.lista_tipos.append({"id": None, "nome": ""})
                st.rerun()

        with col_save:
            if st.button("Salvar alteracoes", use_container_width=True, type="primary"):
                st.session_state.confirmar_save_tipos = True

        if st.session_state.get("confirmar_save_tipos"):
            st.warning("Tem certeza que deseja salvar todas as alteracoes?")
            cc1, cc2 = st.columns(2)
            with cc1:
                if st.button("Sim, salvar", use_container_width=True, key="confirmar_sim"):
                    run_query("UPDATE tipos_inconsistencia SET ativo=0")
                    for item in st.session_state.lista_tipos:
                        nome_item = item["nome"].strip()
                        if not nome_item:
                            continue
                        if item["id"]:
                            run_query(
                                "UPDATE tipos_inconsistencia SET nome=%s, ativo=1 WHERE id=%s",
                                (nome_item, item["id"]))
                        else:
                            run_query(
                                "INSERT INTO tipos_inconsistencia (nome,ativo) VALUES (%s,1) ON CONFLICT (nome) DO UPDATE SET ativo=1",
                                (nome_item,))
                    st.session_state.confirmar_save_tipos = False
                    st.session_state.reload_tipos = True
                    st.cache_data.clear()
                    st.success("Tipos salvos!")
                    st.rerun()
            with cc2:
                if st.button("Cancelar", use_container_width=True, key="confirmar_nao"):
                    st.session_state.confirmar_save_tipos = False
                    st.session_state.reload_tipos = True
                    st.rerun()
