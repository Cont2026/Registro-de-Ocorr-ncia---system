import streamlit as st
from database.connection import get_conn

def tela_admin():
    st.title("⚙️ Administração")
    st.markdown("---")

    aba = st.tabs(["👥 Usuários e Setores", "📌 Tipos de Inconsistência", "🔍 Motivos"])

    # =============================================
    # ABA 1 — USUÁRIOS E SETORES
    # =============================================
    with aba[0]:
        st.subheader("Usuários e Setores cadastrados")

        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT id, nome, login, perfil, ativo FROM usuarios ORDER BY perfil, nome")
        usuarios = cur.fetchall()
        cur.close()
        conn.close()

        for u in usuarios:
            uid, nome, login, perfil, ativo = u
            status_icon = "🟢" if ativo else "🔴"
            perfil_icon = "👑" if perfil == "contabilidade" else "🏢"
            with st.expander(f"{status_icon} {perfil_icon} {nome} — `{login}`"):
                col1, col2 = st.columns(2)
                with col1:
                    nova_senha = st.text_input("Nova senha", key=f"senha_{uid}", placeholder="Deixe em branco para não alterar")
                with col2:
                    novo_ativo = st.selectbox("Status", [1, 0], index=0 if ativo else 1,
                                              format_func=lambda x: "Ativo" if x == 1 else "Inativo",
                                              key=f"ativo_{uid}")
                if st.button("💾 Salvar", key=f"salvar_user_{uid}"):
                    conn = get_conn()
                    cur = conn.cursor()
                    if nova_senha.strip():
                        cur.execute("UPDATE usuarios SET senha=%s, ativo=%s WHERE id=%s",
                                    (nova_senha.strip(), novo_ativo, uid))
                    else:
                        cur.execute("UPDATE usuarios SET ativo=%s WHERE id=%s",
                                    (novo_ativo, uid))
                    conn.commit()
                    cur.close()
                    conn.close()
                    st.success("✅ Usuário atualizado!")
                    st.rerun()

        st.markdown("---")
        st.subheader("➕ Novo Setor")
        with st.form("form_novo_setor"):
            col1, col2, col3 = st.columns(3)
            with col1:
                novo_nome = st.text_input("Nome do setor *")
            with col2:
                novo_login = st.text_input("Login *", placeholder="ex: fiscal")
            with col3:
                nova_senha_setor = st.text_input("Senha *", placeholder="senha inicial")
            salvar_setor = st.form_submit_button("➕ Adicionar Setor", use_container_width=True)

        if salvar_setor:
            erros = []
            if not novo_nome.strip(): erros.append("Nome")
            if not novo_login.strip(): erros.append("Login")
            if not nova_senha_setor.strip(): erros.append("Senha")
            if erros:
                st.error(f"⚠️ Preencha: {', '.join(erros)}")
            else:
                try:
                    conn = get_conn()
                    cur = conn.cursor()
                    cur.execute("""
                        INSERT INTO usuarios (nome, login, senha, perfil)
                        VALUES (%s, %s, %s, 'setor')
                    """, (novo_nome.strip(), novo_login.strip(), nova_senha_setor.strip()))
                    conn.commit()
                    cur.close()
                    conn.close()
                    st.success(f"✅ Setor '{novo_nome}' adicionado!")
                    st.rerun()
                except Exception as e:
                    st.error("⚠️ Login já existe. Escolha outro login.")

    # =============================================
    # ABA 2 — TIPOS DE INCONSISTÊNCIA
    # =============================================
    with aba[1]:
        st.subheader("Tipos de Inconsistência cadastrados")

        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT id, nome, ativo FROM tipos_inconsistencia ORDER BY nome")
        tipos = cur.fetchall()
        cur.close()
        conn.close()

        for t in tipos:
            tid, nome, ativo = t
            status_icon = "🟢" if ativo else "🔴"
            with st.expander(f"{status_icon} {nome}"):
                col1, col2 = st.columns(2)
                with col1:
                    novo_nome_tipo = st.text_input("Nome", value=nome, key=f"tipo_nome_{tid}")
                with col2:
                    novo_ativo_tipo = st.selectbox("Status", [1, 0], index=0 if ativo else 1,
                                                   format_func=lambda x: "Ativo" if x == 1 else "Inativo",
                                                   key=f"tipo_ativo_{tid}")
                if st.button("💾 Salvar", key=f"salvar_tipo_{tid}"):
                    conn = get_conn()
                    cur = conn.cursor()
                    cur.execute("UPDATE tipos_inconsistencia SET nome=%s, ativo=%s WHERE id=%s",
                                (novo_nome_tipo.strip(), novo_ativo_tipo, tid))
                    conn.commit()
                    cur.close()
                    conn.close()
                    st.success("✅ Tipo atualizado!")
                    st.rerun()

        st.markdown("---")
        st.subheader("➕ Novo Tipo de Inconsistência")
        with st.form("form_novo_tipo"):
            novo_tipo = st.text_input("Nome do tipo *")
            salvar_tipo = st.form_submit_button("➕ Adicionar", use_container_width=True)

        if salvar_tipo:
            if not novo_tipo.strip():
                st.error("⚠️ Preencha o nome.")
            else:
                try:
                    conn = get_conn()
                    cur = conn.cursor()
                    cur.execute("INSERT INTO tipos_inconsistencia (nome) VALUES (%s)", (novo_tipo.strip(),))
                    conn.commit()
                    cur.close()
                    conn.close()
                    st.success(f"✅ Tipo '{novo_tipo}' adicionado!")
                    st.rerun()
                except Exception:
                    st.error("⚠️ Esse tipo já existe.")

    # =============================================
    # ABA 3 — MOTIVOS
    # =============================================
    with aba[2]:
        st.subheader("Motivos cadastrados")

        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT id, nome, ativo FROM motivos ORDER BY nome")
        motivos = cur.fetchall()
        cur.close()
        conn.close()

        for m in motivos:
            mid, nome, ativo = m
            status_icon = "🟢" if ativo else "🔴"
            with st.expander(f"{status_icon} {nome}"):
                col1, col2 = st.columns(2)
                with col1:
                    novo_nome_motivo = st.text_input("Nome", value=nome, key=f"motivo_nome_{mid}")
                with col2:
                    novo_ativo_motivo = st.selectbox("Status", [1, 0], index=0 if ativo else 1,
                                                     format_func=lambda x: "Ativo" if x == 1 else "Inativo",
                                                     key=f"motivo_ativo_{mid}")
                if st.button("💾 Salvar", key=f"salvar_motivo_{mid}"):
                    conn = get_conn()
                    cur = conn.cursor()
                    cur.execute("UPDATE motivos SET nome=%s, ativo=%s WHERE id=%s",
                                (novo_nome_motivo.strip(), novo_ativo_motivo, mid))
                    conn.commit()
                    cur.close()
                    conn.close()
                    st.success("✅ Motivo atualizado!")
                    st.rerun()

        st.markdown("---")
        st.subheader("➕ Novo Motivo")
        with st.form("form_novo_motivo"):
            novo_motivo = st.text_input("Nome do motivo *")
            salvar_motivo = st.form_submit_button("➕ Adicionar", use_container_width=True)

        if salvar_motivo:
            if not novo_motivo.strip():
                st.error("⚠️ Preencha o nome.")
            else:
                try:
                    conn = get_conn()
                    cur = conn.cursor()
                    cur.execute("INSERT INTO motivos (nome) VALUES (%s)", (novo_motivo.strip(),))
                    conn.commit()
                    cur.close()
                    conn.close()
                    st.success(f"✅ Motivo '{novo_motivo}' adicionado!")
                    st.rerun()
                except Exception:
                    st.error("⚠️ Esse motivo já existe.")
