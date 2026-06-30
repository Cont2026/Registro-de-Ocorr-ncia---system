import streamlit as st
from database.connection import run_query
from modules.email_service import email_troca_setor

def tela_admin():
    st.title("⚙️ Administracao")
    st.markdown("---")
    aba = st.tabs(["👥 Setores", "📋 Tipos de Inconsistencia", "🗂️ Tipos de Movimentacao", "📧 Notificacoes", "🗑️ Excluir Chamados", "📦 Exportar e Limpar", "👁️ Visualizar Tela do Setor"])

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
        st.subheader("🔄 Trocar Setor Responsável")
        st.markdown("Transfere um chamado **ativo** (Aberto ou Em andamento) para outro setor responsável. "
                    "O novo setor e o setor anterior são avisados por e-mail. "
                    "Use quando a pendência for, na verdade, de outro setor.")
        st.markdown("---")

        # Setores ativos disponíveis para receber o chamado
        setores_ativos = run_query("""SELECT DISTINCT setor_nome FROM usuarios
            WHERE perfil='setor' AND ativo=1 AND setor_nome IS NOT NULL AND setor_nome <> ''
            ORDER BY setor_nome""", fetch=True)
        lista_setores = [s[0] for s in setores_ativos] if setores_ativos else []

        ativos = run_query("""SELECT protocolo, setor, tipo_inconsistencia, empresa, status,
            nome_parceiro, numero_nota, aberto_em
            FROM chamados WHERE status IN ('Aberto','Em andamento') ORDER BY aberto_em DESC""", fetch=True)

        if not ativos:
            st.info("Não há chamados ativos (Aberto/Em andamento) para transferir.")
        elif not lista_setores:
            st.warning("Nenhum setor ativo cadastrado para receber a transferência.")
        else:
            busca_t = st.text_input("🔎 Buscar chamado (protocolo, setor, parceiro ou NF)", key="busca_troca",
                placeholder="ex: ROC-202606-0011 ou MKM")
            termo_t = (busca_t or "").strip().lower()
            mostrados_t = 0
            for (protocolo, setor, tipo_inc, empresa, status, parceiro, nf, aberto_em) in ativos:
                if termo_t:
                    alvo = " ".join(str(x or "").lower() for x in [protocolo, setor, tipo_inc, empresa, status, parceiro, nf])
                    if termo_t not in alvo:
                        continue
                mostrados_t += 1

                st.markdown(f"**{protocolo}** — {parceiro or '—'} · NF: {nf or '—'} · "
                            f"Setor atual: **{setor}** · _{status}_")
                ct1, ct2 = st.columns([3, 1])
                with ct1:
                    opcoes_destino = [s for s in lista_setores if s != setor]
                    novo_setor = st.selectbox("Novo setor responsável", opcoes_destino,
                        key=f"troca_dest_{protocolo}", label_visibility="collapsed")
                with ct2:
                    if st.button("🔄 Transferir", key=f"troca_btn_{protocolo}", use_container_width=True):
                        st.session_state["confirmar_troca"] = protocolo
                        st.session_state["troca_destino_sel"] = novo_setor
                        st.rerun()

                if st.session_state.get("confirmar_troca") == protocolo:
                    destino = st.session_state.get("troca_destino_sel")
                    st.warning(f"⚠️ Transferir **{protocolo}** de **{setor}** para **{destino}**? "
                               "Os dois setores serão avisados por e-mail.")
                    cct1, cct2 = st.columns(2)
                    with cct1:
                        if st.button("Sim, transferir", key=f"troca_sim_{protocolo}",
                                     use_container_width=True, type="primary"):
                            try:
                                # E-mails dos setores antigo e novo (antes de alterar)
                                e_novo = run_query("SELECT email FROM usuarios WHERE setor_nome=%s AND ativo=1 LIMIT 1",
                                                   (destino,), fetch=True)
                                e_antigo = run_query("SELECT email FROM usuarios WHERE setor_nome=%s AND ativo=1 LIMIT 1",
                                                     (setor,), fetch=True)
                                email_novo = e_novo[0][0] if e_novo and e_novo[0] else None
                                email_antigo = e_antigo[0][0] if e_antigo and e_antigo[0] else None
                                # Troca o setor responsável
                                run_query("UPDATE chamados SET setor=%s WHERE protocolo=%s", (destino, protocolo))
                                # Avisa novo e antigo setor
                                try:
                                    email_troca_setor(email_novo, email_antigo, protocolo, destino, setor)
                                except:
                                    pass
                                st.session_state["confirmar_troca"] = None
                                st.cache_data.clear()
                                st.success(f"✅ {protocolo} transferido para {destino}. Setores avisados por e-mail.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Não foi possível transferir: {e}")
                    with cct2:
                        if st.button("Cancelar", key=f"troca_nao_{protocolo}", use_container_width=True):
                            st.session_state["confirmar_troca"] = None
                            st.rerun()

                st.markdown("<hr style='margin:6px 0;border:none;border-top:1px solid #eee;'>", unsafe_allow_html=True)

            if termo_t and mostrados_t == 0:
                st.info("Nenhum chamado ativo encontrado para essa busca.")

        st.markdown("---")
        st.subheader("🗑️ Excluir Chamados")
        st.markdown("Exclua chamados (por exemplo, duplicados). A exclusão é **permanente** e remove também "
                    "as mensagens, cópias e notificações ligadas ao chamado. O número do protocolo excluído "
                    "**não é reaproveitado** (fica um espaço vago na sequência, o que é normal).")
        st.markdown("---")

        busca = st.text_input("🔎 Buscar (protocolo, setor, parceiro ou NF)", key="busca_excluir",
            placeholder="ex: ROC-202606-0011 ou MKM ou NF 9")

        chamados = run_query("""SELECT protocolo, setor, tipo_inconsistencia, empresa, status,
            nome_parceiro, numero_nota, aberto_em, solicitante
            FROM chamados ORDER BY aberto_em DESC""", fetch=True)

        if not chamados:
            st.info("Nenhum chamado registrado ainda.")
        else:
            termo = (busca or "").strip().lower()
            mostrados = 0
            for (protocolo, setor, tipo_inc, empresa, status,
                 parceiro, nf, aberto_em, solicitante) in chamados:
                if termo:
                    alvo = " ".join(str(x or "").lower() for x in
                        [protocolo, setor, tipo_inc, empresa, status, parceiro, nf, solicitante])
                    if termo not in alvo:
                        continue
                mostrados += 1

                c1, c2 = st.columns([6, 1])
                with c1:
                    st.markdown(
                        f"**{protocolo}** — {parceiro or '—'} · NF: {nf or '—'} · "
                        f"{setor} · {empresa or '—'} · _{status}_")
                    st.caption(f"{tipo_inc or '—'} · Solicitante: {solicitante or '—'} · Aberto em: {aberto_em}")
                with c2:
                    if st.button("🗑️ Apagar", key=f"del_{protocolo}", use_container_width=True):
                        st.session_state["confirmar_excluir"] = protocolo
                        st.rerun()

                # Confirmação inline, logo abaixo do chamado escolhido
                if st.session_state.get("confirmar_excluir") == protocolo:
                    st.warning(f"⚠️ Tem certeza que deseja excluir **{protocolo}**? "
                               "Esta ação é permanente e não pode ser desfeita.")
                    cc1, cc2 = st.columns(2)
                    with cc1:
                        if st.button("Sim, excluir", key=f"delsim_{protocolo}",
                                     use_container_width=True, type="primary"):
                            try:
                                run_query("DELETE FROM mensagens WHERE chamado_protocolo=%s", (protocolo,))
                                run_query("DELETE FROM chamados_copia WHERE protocolo=%s", (protocolo,))
                                run_query("DELETE FROM notificacoes WHERE protocolo=%s", (protocolo,))
                                run_query("DELETE FROM chamados WHERE protocolo=%s", (protocolo,))
                                st.session_state["confirmar_excluir"] = None
                                st.cache_data.clear()
                                st.success(f"✅ Chamado {protocolo} excluído.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Não foi possível excluir: {e}")
                    with cc2:
                        if st.button("Cancelar", key=f"delnao_{protocolo}", use_container_width=True):
                            st.session_state["confirmar_excluir"] = None
                            st.rerun()

                st.markdown("<hr style='margin:6px 0;border:none;border-top:1px solid #eee;'>", unsafe_allow_html=True)

            if termo and mostrados == 0:
                st.info("Nenhum chamado encontrado para essa busca.")

    with aba[5]:
        st.subheader("📦 Exportar e Limpar Encerrados")
        st.markdown("Gera uma planilha Excel (abas **Chamados** e **Mensagens**) com os chamados "
                    "**Resolvidos** e **Cancelados**, para servir de histórico. Depois de **baixar** a planilha, "
                    "o botão de apagar é liberado. Chamados **Abertos** e **Em andamento** NUNCA são tocados. "
                    "Os arquivos anexados não vão na planilha — apenas o **nome** deles fica registrado.")
        st.markdown("---")

        encerrados = run_query("""SELECT protocolo, setor, empresa, tipo_inconsistencia, tipo_nota, status,
            prioridade, nome_parceiro, numero_nota, valor, solicitante, atendente, financeiro_baixado,
            nf_retorna, data_entrada, data_negociacao, aberto_em, atendido_em, resolvido_em, observacao,
            num_unico_financeiro, num_unico_nota, atrasos_entregaveis, arquivo_nome
            FROM chamados WHERE status IN ('Resolvido','Cancelado') ORDER BY aberto_em""", fetch=True)

        qtd = len(encerrados) if encerrados else 0
        st.markdown(f"**Chamados encerrados (Resolvidos/Cancelados) no momento: {qtd}**")

        if qtd == 0:
            st.info("Não há chamados encerrados para exportar.")
        else:
            if st.button("📊 Gerar planilha dos encerrados", use_container_width=True, key="btn_gerar_export"):
                try:
                    import io
                    from datetime import datetime as _dt
                    from openpyxl import Workbook
                    from openpyxl.styles import Font

                    protocolos = [r[0] for r in encerrados]
                    msgs = run_query("""SELECT chamado_protocolo, autor, perfil, mensagem, enviado_em, anexo_nome
                        FROM mensagens
                        WHERE chamado_protocolo IN (
                            SELECT protocolo FROM chamados WHERE status IN ('Resolvido','Cancelado'))
                        ORDER BY chamado_protocolo, enviado_em""", fetch=True) or []

                    def _cel(v):
                        if v is None:
                            return ""
                        if isinstance(v, _dt) and v.tzinfo is not None:
                            return v.replace(tzinfo=None)
                        return v

                    wb = Workbook()
                    ws1 = wb.active
                    ws1.title = "Chamados"
                    cab1 = ["Protocolo", "Setor", "Empresa", "Tipo de Inconsistência", "Tipo de Movimentação",
                            "Status", "Prioridade", "Parceiro", "Número NF", "Valor", "Solicitante", "Atendente",
                            "Financeiro Baixado", "NF Retorna", "Data da Nota", "Data Negociação", "Aberto em",
                            "Atendido em", "Resolvido em", "Observação", "NU Financeiro", "NU Nota",
                            "Atrasos Entregáveis", "Anexos (nomes)"]
                    ws1.append(cab1)
                    for c in ws1[1]:
                        c.font = Font(bold=True)
                    for r in encerrados:
                        ws1.append([_cel(v) for v in r])

                    ws2 = wb.create_sheet("Mensagens")
                    cab2 = ["Protocolo", "Autor", "Perfil", "Mensagem", "Enviado em", "Anexo (nome)"]
                    ws2.append(cab2)
                    for c in ws2[1]:
                        c.font = Font(bold=True)
                    for m in msgs:
                        ws2.append([_cel(v) for v in m])

                    buffer = io.BytesIO()
                    wb.save(buffer)
                    st.session_state["export_xlsx"] = buffer.getvalue()
                    st.session_state["export_protocolos"] = protocolos
                    st.session_state["export_baixado"] = False
                    st.success(f"✅ Planilha gerada com {qtd} chamado(s) e {len(msgs)} mensagem(ns). "
                               "Baixe abaixo para liberar a limpeza.")
                except ModuleNotFoundError:
                    st.error("⚠️ A biblioteca 'openpyxl' não está instalada. Adicione 'openpyxl' ao requirements.txt e reinicie o app.")
                except Exception as e:
                    st.error(f"Não foi possível gerar a planilha: {type(e).__name__}: {e}")

            # Botão de download (aparece depois de gerar). Baixar libera a limpeza.
            if st.session_state.get("export_xlsx"):
                nome_arq = f"ROC_encerrados_{__import__('datetime').datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
                baixou = st.download_button("⬇️ Baixar planilha", data=st.session_state["export_xlsx"],
                    file_name=nome_arq,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True, key="btn_baixar_export")
                if baixou:
                    st.session_state["export_baixado"] = True

            # Limpeza: só liberada após baixar a planilha.
            if st.session_state.get("export_baixado"):
                st.markdown("---")
                protos = st.session_state.get("export_protocolos", [])
                st.markdown(f"✅ Planilha baixada. Agora você pode **apagar os {len(protos)} chamado(s) encerrado(s)** "
                            "que foram exportados. Os Abertos/Em andamento não serão tocados.")
                if st.button("🗑️ Apagar encerrados do banco", use_container_width=True, key="btn_apagar_encerrados"):
                    st.session_state["confirmar_limpeza"] = True

                if st.session_state.get("confirmar_limpeza"):
                    st.warning("⚠️ Tem certeza? Esta ação é permanente. Os chamados encerrados exportados "
                               "(e suas mensagens) serão removidos do banco.")
                    lc1, lc2 = st.columns(2)
                    with lc1:
                        if st.button("Sim, apagar", use_container_width=True, type="primary", key="limpeza_sim"):
                            try:
                                apagados = 0
                                for p in protos:
                                    run_query("DELETE FROM mensagens WHERE chamado_protocolo=%s", (p,))
                                    run_query("DELETE FROM chamados_copia WHERE protocolo=%s", (p,))
                                    run_query("DELETE FROM notificacoes WHERE protocolo=%s", (p,))
                                    run_query("DELETE FROM chamados WHERE protocolo=%s", (p,))
                                    apagados += 1
                                st.session_state["confirmar_limpeza"] = False
                                st.session_state["export_baixado"] = False
                                st.session_state["export_xlsx"] = None
                                st.session_state["export_protocolos"] = []
                                st.cache_data.clear()
                                st.success(f"✅ {apagados} chamado(s) encerrado(s) removido(s) do banco.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Não foi possível apagar: {type(e).__name__}: {e}")
                    with lc2:
                        if st.button("Cancelar", use_container_width=True, key="limpeza_nao"):
                            st.session_state["confirmar_limpeza"] = False
                            st.rerun()

    with aba[6]:
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
