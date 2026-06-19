import streamlit as st
from database.connection import run_query

def tela_admin():
    st.title("⚙️ Administracao")
    st.markdown("---")
    aba = st.tabs(["👥 Setores", "📋 Tipos de Inconsistencia", "🗂️ Tipos de Movimentacao", "📧 Notificacoes", "👁️ Visualizar Tela do Setor"])

    with aba[0]:
        st.subheader("Setores cadastrados")
        usuarios = run_query("SELECT id, nome, email, setor_nome, ativo FROM usuarios WHERE perfil='setor' ORDER BY nome", fetch=True)

        for uid, nome, email, setor_nome, ativo in usuarios:
            status_icon = "🟢" if ativo else "🔴"
            with st.expander(f"{status_icon} {nome} — {email or '—'}"):
                c1, c2 = st.columns(2)
                novo_email = c1.text_input("E-mail do setor", value=email or "", key=f"email_{uid}", placeholder="setor@grupolle.com.br")
                nova_senha = c2.text_input("Nova senha", key=f"s_{uid}", placeholder="Deixe em branco para nao alterar")
                novo_ativo = st.selectbox("Status", [1, 0], index=0 if ativo else 1,
                    format_func=lambda x: "Ativo" if x == 1 else "Inativo", key=f"a_{uid}")
                if st.button("💾 Salvar", key=f"u_{uid}"):
                    if nova_senha.strip():
                        run_query("UPDATE usuarios SET email=%s, senha=%s, ativo=%s, primeiro_acesso=1 WHERE id=%s",
                            (novo_email.strip().lower(), nova_senha.strip(), novo_ativo, uid))
                    else:
                        run_query("UPDATE usuarios SET email=%s, ativo=%s WHERE id=%s",
                            (novo_email.strip().lower(), novo_ativo, uid))
                    st.cache_data.clear()
                    st.success("✅ Atualizado!")
                    st.rerun()

        st.markdown("---")
        st.subheader("➕ Novo Setor")
        with st.form("form_setor"):
            c1, c2, c3 = st.columns(3)
            novo_nome = c1.text_input("Nome do Setor *", placeholder="ex: Fiscal")
            novo_email_s = c2.text_input("E-mail *", placeholder="fiscal@grupolle.com.br")
            nova_senha_s = c3.text_input("Senha *", placeholder="ex: Fiscal@2026")
            if st.form_submit_button("➕ Adicionar Setor", use_container_width=True):
                if not novo_nome.strip() or not novo_email_s.strip() or not nova_senha_s.strip():
                    st.error("Preencha todos os campos.")
                elif not novo_email_s.strip().endswith("@grupolle.com.br"):
                    st.error("Use e-mail @grupolle.com.br")
                else:
                    try:
                        run_query("""INSERT INTO usuarios (nome, email, login, senha, perfil, setor_nome, ativo, primeiro_acesso)
                            VALUES (%s, %s, %s, %s, 'setor', %s, 1, 0)""",
                            (novo_nome.strip(), novo_email_s.strip().lower(),
                             novo_email_s.strip().lower(), nova_senha_s.strip(), novo_nome.strip()))
                        st.success(f"✅ Setor '{novo_nome}' criado!")
                        st.rerun()
                    except:
                        st.error("E-mail ja existe.")

    with aba[1]:
        st.subheader("Gerenciar Tipos de Inconsistencia")
        st.markdown("Edite o nome e selecione a quais **Tipos de Movimentacao** cada inconsistencia pertence. "
                    "Inconsistencias sem nenhum vinculo aparecem em todos os tipos.")
        st.markdown("---")

        # Opcoes de tipos de movimentacao para o vinculo
        movs_db = run_query("SELECT nome FROM tipos_nota WHERE ativo=1 ORDER BY nome", fetch=True)
        movs_opcoes = [m[0] for m in movs_db] if movs_db else []

        if "lista_tipos" not in st.session_state or st.session_state.get("reload_tipos", True):
            tipos_db = run_query("SELECT id, nome FROM tipos_inconsistencia WHERE ativo=1 ORDER BY nome", fetch=True)
            vinc_db = run_query("SELECT inconsistencia, movimentacao FROM vinculo_inconsistencia_movimentacao", fetch=True)
            mapa_vinc = {}
            if vinc_db:
                for inc, mov in vinc_db:
                    mapa_vinc.setdefault(inc, []).append(mov)
            st.session_state.lista_tipos = [{"id": t[0], "nome": t[1], "movs": mapa_vinc.get(t[1], [])} for t in tipos_db]
            st.session_state.reload_tipos = False

        indices_remover = []
        for i, item in enumerate(st.session_state.lista_tipos):
            chave = str(item.get("id", "novo"))
            c1, c2, c3 = st.columns([4, 4, 1])
            with c1:
                novo_nome = st.text_input(f"Inconsistencia {i+1}", value=item["nome"],
                    key=f"tipo_edit_{i}_{chave}", label_visibility="collapsed", placeholder="Nome da inconsistencia")
                st.session_state.lista_tipos[i]["nome"] = novo_nome
            with c2:
                movs_validas = [m for m in item.get("movs", []) if m in movs_opcoes]
                sel = st.multiselect("Tipos de Movimentacao", movs_opcoes, default=movs_validas,
                    key=f"tipo_movs_{i}_{chave}", label_visibility="collapsed",
                    placeholder="Pertence a quais tipos? (vazio = todos)")
                st.session_state.lista_tipos[i]["movs"] = sel
            with c3:
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
                st.session_state.lista_tipos.append({"id": None, "nome": "", "movs": []})
                st.rerun()
        with col_save:
            if st.button("Salvar alteracoes", use_container_width=True, type="primary"):
                st.session_state.confirmar_save_tipos = True

        if st.session_state.get("confirmar_save_tipos"):
            st.warning("Tem certeza que deseja salvar?")
            cc1, cc2 = st.columns(2)
            with cc1:
                if st.button("Sim, salvar", use_container_width=True, key="confirmar_sim"):
                    run_query("UPDATE tipos_inconsistencia SET ativo=0")
                    # Reescreve todos os vinculos a partir da tela
                    run_query("DELETE FROM vinculo_inconsistencia_movimentacao")
                    for item in st.session_state.lista_tipos:
                        nome_item = item["nome"].strip()
                        if not nome_item:
                            continue
                        if item["id"]:
                            run_query("UPDATE tipos_inconsistencia SET nome=%s, ativo=1 WHERE id=%s",
                                      (nome_item, item["id"]))
                        else:
                            run_query("INSERT INTO tipos_inconsistencia (nome,ativo) VALUES (%s,1) ON CONFLICT (nome) DO UPDATE SET ativo=1",
                                      (nome_item,))
                        for mov in item.get("movs", []):
                            run_query("INSERT INTO vinculo_inconsistencia_movimentacao (inconsistencia, movimentacao) VALUES (%s,%s)",
                                      (nome_item, mov))
                    st.session_state.confirmar_save_tipos = False
                    st.session_state.reload_tipos = True
                    st.cache_data.clear()
                    st.cache_resource.clear()
                    st.success("✅ Tipos e vinculos salvos!")
                    st.rerun()
            with cc2:
                if st.button("Cancelar", use_container_width=True, key="confirmar_nao"):
                    st.session_state.confirmar_save_tipos = False
                    st.session_state.reload_tipos = True
                    st.rerun()

    with aba[2]:
        st.subheader("Gerenciar Tipos de Movimentacao")
        st.markdown("Edite, adicione ou remova os tipos de movimentacao.")
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
                novo_nome = st.text_input(f"Tipo {i+1}", value=item["nome"],
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
            if st.button("Adicionar novo tipo", use_container_width=True, key="add_nota"):
                st.session_state.lista_tipos_nota.append({"id": None, "nome": ""})
                st.rerun()
        with col_save2:
            if st.button("Salvar tipos de movimentacao", use_container_width=True, type="primary"):
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
                            run_query("UPDATE tipos_nota SET nome=%s, ativo=1 WHERE id=%s",
                                      (nome_item, item["id"]))
                        else:
                            run_query("INSERT INTO tipos_nota (nome,ativo) VALUES (%s,1) ON CONFLICT (nome) DO UPDATE SET ativo=1",
                                      (nome_item,))
                    st.session_state.confirmar_save_nota = False
                    st.session_state.reload_tipos_nota = True
                    st.cache_data.clear()
                    st.cache_resource.clear()
                    st.success("✅ Tipos de movimentacao salvos!")
                    st.rerun()
            with cc2:
                if st.button("Cancelar", use_container_width=True, key="confirmar_nao_nota"):
                    st.session_state.confirmar_save_nota = False
                    st.session_state.reload_tipos_nota = True
                    st.rerun()

    with aba[3]:
        st.subheader("📧 Historico de Notificacoes")
        st.markdown("---")
        c1, c2 = st.columns(2)
        filtro_tipo = c1.selectbox("Tipo", ["Todos","novo_chamado","atualizacao_status","nova_mensagem","conclusao","solicitacao_tratativa"])
        filtro_sucesso = c2.selectbox("Status envio", ["Todos","Enviado","Falhou"])

        notifs = run_query("""SELECT protocolo, destinatario, assunto, tipo, enviado_em, sucesso
            FROM notificacoes ORDER BY enviado_em DESC LIMIT 100""", fetch=True)

        if not notifs:
            st.info("Nenhuma notificacao registrada ainda.")
        else:
            for protocolo, destinatario, assunto, tipo, enviado_em, sucesso in notifs:
                if filtro_tipo != "Todos" and tipo != filtro_tipo: continue
                if filtro_sucesso == "Enviado" and not sucesso: continue
                if filtro_sucesso == "Falhou" and sucesso: continue
                icone = "✅" if sucesso else "❌"
                st.markdown(f"""
                <div style='background:white;border:1px solid #e8e8e8;border-radius:8px;
                padding:10px 14px;margin-bottom:6px;'>
                    <div style='display:flex;justify-content:space-between;align-items:center;'>
                        <span style='font-size:13px;font-weight:600;color:#041747;'>{icone} {assunto}</span>
                        <span style='font-size:11px;color:#999;'>{enviado_em}</span>
                    </div>
                    <p style='font-size:12px;color:#666;margin:4px 0 0;'>
                    Para: {destinatario} · Tipo: {tipo} · Protocolo: {protocolo or "—"}</p>
                </div>
                """, unsafe_allow_html=True)

    with aba[4]:
        st.subheader("👁️ Visualizar Tela do Setor")
        st.markdown("Veja exatamente como os setores enxergam a tela de abertura de chamado. "
                    "É apenas uma simulação — **nenhum chamado é criado** aqui.")
        st.markdown("---")
        setores_db = run_query("SELECT setor_nome, nome FROM usuarios WHERE perfil='setor' AND ativo=1 ORDER BY nome", fetch=True)
        opcoes = [ (s[0] or s[1]) for s in setores_db ] if setores_db else []
        if not opcoes:
            st.info("Nenhum setor ativo cadastrado para simular.")
        else:
            setor_sim = st.selectbox("Simular como qual setor?", opcoes, key="preview_setor_sel")
            st.markdown("---")
            try:
                from modules.chamados import tela_novo_chamado
                tela_novo_chamado(preview=True, setor_preview=setor_sim)
            except Exception as e:
                st.error(f"Não foi possível carregar a visualização: {e}")
