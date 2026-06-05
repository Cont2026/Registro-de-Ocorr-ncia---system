import streamlit as st
from database.connection import run_query

def tela_admin():
    st.title("⚙️ Administração")
    st.markdown("---")
    aba = st.tabs(["👥 Usuários e Setores", "📋 Tipos de Inconsistência", "🗂️ Tipos de Nota"])

    with aba[0]:
        st.subheader("Usuários cadastrados")
        usuarios = run_query("SELECT id, nome, email, perfil, setor_nome, ativo FROM usuarios ORDER BY perfil, nome", fetch=True)

        for uid, nome, email, perfil, setor_nome, ativo in usuarios:
            status_icon = "🟢" if ativo else "🔴"
            perfil_icon = "👑" if perfil == "contabilidade" else "🏢"
            label = f"{status_icon} {perfil_icon} {nome}"
            if setor_nome: label += f" — {setor_nome}"
            if email: label += f" ({email})"
            with st.expander(label):
                c1, c2 = st.columns(2)
                nova_senha = c1.text_input("Nova senha do setor", key=f"s_{uid}", placeholder="Deixe em branco para não alterar")
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
        st.subheader("➕ Novo Setor")
        st.markdown("Cadastra um setor com senha padrão. Os colaboradores se auto-cadastram pelo primeiro acesso.")
        with st.form("form_setor"):
            c1, c2, c3 = st.columns(3)
            novo_setor = c1.text_input("Nome do Setor *", placeholder="ex: Fiscal")
            novo_login = c2.text_input("Login do setor *", placeholder="ex: fiscal")
            nova_senha_setor = c3.text_input("Senha padrão do setor *", placeholder="ex: Fiscal@2026")
            if st.form_submit_button("➕ Adicionar Setor", use_container_width=True):
                if not novo_setor.strip() or not novo_login.strip() or not nova_senha_setor.strip():
                    st.error("Preencha todos os campos.")
                else:
                    try:
                        email_setor = f"{novo_login.strip().lower()}@grupolle.com.br"
                        run_query("""INSERT INTO usuarios (nome, email, login, senha, perfil, setor_nome, ativo, primeiro_acesso)
                            VALUES (%s, %s, %s, %s, 'setor', %s, 1, 0)""",
                            (novo_setor.strip(), email_setor, novo_login.strip().lower(),
                             nova_senha_setor.strip(), novo_setor.strip()))
                        st.success(f"✅ Setor '{novo_setor}' criado! Senha padrão: {nova_senha_setor}")
                        st.rerun()
                    except:
                        st.error("Login já existe.")

        st.markdown("---")
        st.subheader("🔑 Alterar senha padrão de um setor")
        st.markdown("Isso atualiza a senha de todos os usuários do setor que ainda não trocaram a senha.")
        setores = run_query("SELECT DISTINCT setor_nome FROM usuarios WHERE perfil='setor' AND setor_nome IS NOT NULL ORDER BY setor_nome", fetch=True)
        if setores:
            with st.form("form_senha_setor"):
                setor_sel = st.selectbox("Setor", [s[0] for s in setores])
                nova_senha_global = st.text_input("Nova senha padrão *", type="password")
                if st.form_submit_button("🔑 Atualizar senha do setor", use_container_width=True):
                    if not nova_senha_global.strip():
                        st.error("Preencha a nova senha.")
                    else:
                        run_query("UPDATE usuarios SET senha=%s WHERE setor_nome=%s AND primeiro_acesso=1",
                                  (nova_senha_global.strip(), setor_sel))
                        st.success(f"✅ Senha padrão do setor '{setor_sel}' atualizada!")

    with aba[1]:
        st.subheader("Gerenciar Tipos de Inconsistência")
        st.markdown("Edite, adicione ou remova os tipos. Clique em **Salvar** quando terminar.")
        st.markdown("---")

        if "lista_tipos" not in st.session_state or st.session_state.get("reload_tipos", True):
            tipos_db = run_query("SELECT id, nome FROM tipos_inconsistencia WHERE ativo=1 ORDER BY nome", fetch=True)
            st.session_state.lista_tipos = [{"id": t[0], "nome": t[1]} for t in tipos_db]
            st.session_state.reload_tipos = False

        indices_remover = []
        for i, item in enumerate(st.session_state.lista_tipos):
            c1, c2 = st.columns([5, 1])
            with c1:
                chave = str(item.get("id", "novo"))
                novo_nome = st.text_input(f"Tipo {i+1}", value=item["nome"],
                    key=f"tipo_edit_{i}_{chave}", label_visibility="collapsed")
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
                        if not nome_item: continue
                        if item["id"]:
                            run_query("UPDATE tipos_inconsistencia SET nome=%s, ativo=1 WHERE id=%s", (nome_item, item["id"]))
                        else:
                            run_query("INSERT INTO tipos_inconsistencia (nome,ativo) VALUES (%s,1) ON CONFLICT (nome) DO UPDATE SET ativo=1", (nome_item,))
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

    with aba[2]:
        st.subheader("Gerenciar Tipos de Nota")
        st.markdown("Edite, adicione ou remova os tipos de nota.")
        st.markdown("---")

        if "lista_tipos_nota" not in st.session_state or st.session_state.get("reload_tipos_nota", True):
            tipos_nota_db = run_query("SELECT id, nome FROM tipos_nota WHERE ativo=1 ORDER BY nome", fetch=True)
            st.session_state.lista_tipos_nota = [{"id": t[0], "nome": t[1]} for t in tipos_nota_db]
            st.session_state.reload_tipos_nota = False

        indices_remover_nota = []
        for i, item in enumerate(st.session_state.lista_tipos_nota):
            c1, c2 = st.columns([5, 1])
            with c1:
                chave = str(item.get("id", "novo"))
                novo_nome = st.text_input(f"Tipo Nota {i+1}", value=item["nome"],
                    key=f"nota_edit_{i}_{chave}", label_visibility="collapsed")
                st.session_state.lista_tipos_nota[i]["nome"] = novo_nome
            with c2:
                if st.button("X", key=f"rem_nota_{i}_{chave}", help="Remover"):
                    indices_remover_nota.append(i)

        if indices_remover_nota:
            for idx in sorted(indices_remover_nota, reverse=True):
                st.session_state.lista_tipos_nota.pop(idx)
            st.rerun()

        st.markdown("---")
        col_add2, col_save2 = st.columns(2)
        with col_add2:
            if st.button("Adicionar novo tipo de nota", use_container_width=True):
                st.session_state.lista_tipos_nota.append({"id": None, "nome": ""})
                st.rerun()
        with col_save2:
            if st.button("Salvar tipos de nota", use_container_width=True, type="primary"):
                st.session_state.confirmar_save_nota = True

        if st.session_state.get("confirmar_save_nota"):
            st.warning("Tem certeza que deseja salvar?")
            cc1, cc2 = st.columns(2)
            with cc1:
                if st.button("Sim, salvar", use_container_width=True, key="confirmar_sim_nota"):
                    run_query("UPDATE tipos_nota SET ativo=0")
                    for item in st.session_state.lista_tipos_nota:
                        nome_item = item["nome"].strip()
                        if not nome_item: continue
                        if item["id"]:
                            run_query("UPDATE tipos_nota SET nome=%s, ativo=1 WHERE id=%s", (nome_item, item["id"]))
                        else:
                            run_query("INSERT INTO tipos_nota (nome,ativo) VALUES (%s,1) ON CONFLICT (nome) DO UPDATE SET ativo=1", (nome_item,))
                    st.session_state.confirmar_save_nota = False
                    st.session_state.reload_tipos_nota = True
                    st.cache_data.clear()
                    st.success("Tipos de nota salvos!")
                    st.rerun()
            with cc2:
                if st.button("Cancelar", use_container_width=True, key="confirmar_nao_nota"):
                    st.session_state.confirmar_save_nota = False
                    st.session_state.reload_tipos_nota = True
                    st.rerun()
