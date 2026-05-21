import streamlit as st
from database.connection import get_conn
from datetime import datetime, date
from zoneinfo import ZoneInfo

BRASILIA = ZoneInfo("America/Sao_Paulo")

TIPOS_FECHAMENTO = [
    "Fechamento Parcial 1",
    "Fechamento Parcial 2",
    "Fechamento Parcial 3",
    "Fechamento Consolidado Corporativo"
]

CORES_FECHAMENTO = {
    "Fechamento Parcial 1": {"borda": "#3B82F6", "bg": "#EFF6FF", "texto": "#1D4ED8"},
    "Fechamento Parcial 2": {"borda": "#EAB308", "bg": "#FEFCE8", "texto": "#854D0E"},
    "Fechamento Parcial 3": {"borda": "#F97316", "bg": "#FFF7ED", "texto": "#9A3412"},
    "Fechamento Consolidado Corporativo": {"borda": "#EF4444", "bg": "#FEF2F2", "texto": "#991B1B"},
}

def formatar_data(d):
    if d:
        return d.strftime("%d/%m/%Y") if hasattr(d, 'strftime') else str(d)
    return "—"

def status_data(d):
    if not d:
        return "⚪", "Não definida", "#999999"
    hoje = datetime.now(BRASILIA).date()
    data = d.date() if hasattr(d, 'date') else d
    if data < hoje:
        return "✅", "Concluída", "#22c55e"
    elif data == hoje:
        return "🟡", "Hoje", "#f59e0b"
    else:
        dias = (data - hoje).days
        return "🔵", f"Em {dias} dias", "#3B82F6"

def buscar_competencias():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, mes_ano, ano, mes FROM competencias ORDER BY ano DESC, mes DESC")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def buscar_fechamentos(competencia_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, tipo, data_fechamento, periodo_inicio, periodo_fim, observacao
        FROM fechamentos WHERE competencia_id = %s
        ORDER BY CASE tipo
            WHEN 'Fechamento Parcial 1' THEN 1
            WHEN 'Fechamento Parcial 2' THEN 2
            WHEN 'Fechamento Parcial 3' THEN 3
            WHEN 'Fechamento Consolidado Corporativo' THEN 4
        END
    """, (competencia_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def card_fechamento(fech, compacto=False):
    fid, tipo, data_fech, per_ini, per_fim, obs = fech
    cor = CORES_FECHAMENTO.get(tipo, {"borda": "#999", "bg": "#f9f9f9", "texto": "#333"})
    icone, status_txt, cor_status = status_data(data_fech)
    periodo = f"{formatar_data(per_ini)} → {formatar_data(per_fim)}" if per_ini or per_fim else "Período não definido"

    if compacto:
        return f"""
        <div style='border:1.5px solid {cor["borda"]}; border-radius:10px; padding:12px;
        background:{cor["bg"]}; text-align:center;'>
            <p style='font-size:10px; color:{cor["texto"]}; font-weight:700;
            text-transform:uppercase; letter-spacing:0.5px; margin:0 0 6px;'>{tipo}</p>
            <p style='font-size:20px; margin:0 0 2px;'>{icone}</p>
            <p style='font-size:12px; font-weight:700; color:#041747; margin:0;'>{formatar_data(data_fech)}</p>
            <p style='font-size:10px; color:#666; margin:2px 0 0;'>{periodo}</p>
        </div>
        """
    else:
        return f"""
        <div style='border:2px solid {cor["borda"]}; border-radius:14px; padding:20px;
        background:{cor["bg"]}; text-align:center;
        box-shadow:0 2px 10px rgba(0,0,0,0.06);'>
            <p style='font-size:11px; color:{cor["texto"]}; font-weight:700;
            text-transform:uppercase; letter-spacing:1px; margin:0 0 10px;'>{tipo}</p>
            <p style='font-size:28px; margin:0 0 6px;'>{icone}</p>
            <p style='font-size:15px; font-weight:700; color:#041747; margin:0;'>{formatar_data(data_fech)}</p>
            <p style='font-size:11px; color:{cor_status}; font-weight:600; margin:4px 0 6px;'>{status_txt}</p>
            <p style='font-size:11px; color:#555; margin:0;'>📅 {periodo}</p>
            {f'<p style="font-size:10px; color:#888; margin:6px 0 0; font-style:italic;">{obs}</p>' if obs else ''}
        </div>
        """

def secao_competencia(comp, compacto=False):
    cid, mes_ano, ano, mes = comp
    fechamentos = buscar_fechamentos(cid)

    if not fechamentos:
        return

    tamanho = "### " if not compacto else "##### "
    st.markdown(f"{tamanho}📆 {mes_ano}")

    fech_dict = {f[1]: f for f in fechamentos}
    cols = st.columns(4)

    for i, tipo in enumerate(TIPOS_FECHAMENTO):
        with cols[i]:
            if tipo in fech_dict:
                st.markdown(card_fechamento(fech_dict[tipo], compacto), unsafe_allow_html=True)
            else:
                cor = CORES_FECHAMENTO[tipo]
                st.markdown(f"""
                <div style='border:2px dashed {cor["borda"]}; border-radius:14px; padding:20px;
                text-align:center; opacity:0.4;'>
                    <p style='font-size:10px; color:{cor["texto"]}; font-weight:700;
                    text-transform:uppercase; margin:0 0 6px;'>{tipo}</p>
                    <p style='font-size:22px; margin:0;'>⚪</p>
                    <p style='font-size:11px; color:#999; margin:4px 0 0;'>Não cadastrado</p>
                </div>
                """, unsafe_allow_html=True)

def secao_anual(competencias):
    st.markdown("#### 🗓️ Visão Anual")
    st.markdown("---")

    for comp in competencias:
        cid, mes_ano, ano, mes = comp
        fechamentos = buscar_fechamentos(cid)
        fech_dict = {f[1]: f for f in fechamentos}

        partes = []
        for tipo in TIPOS_FECHAMENTO:
            if tipo in fech_dict:
                fid, t, data_fech, per_ini, per_fim, obs = fech_dict[tipo]
                icone, _, cor_s = status_data(data_fech)
                label = tipo.replace("Fechamento ", "").replace("Consolidado Corporativo", "Consolidado")
                cor = CORES_FECHAMENTO[tipo]
                partes.append(f"""
                <span style='font-size:12px; color:{cor["texto"]}; font-weight:600;'>
                {icone} {label}: {formatar_data(data_fech)}</span>""")

        partes_html = " &nbsp;|&nbsp; ".join(partes) if partes else "<span style='color:#999; font-size:12px;'>Sem fechamentos cadastrados</span>"

        st.markdown(f"""
        <div style='background:white; border:1px solid #e8e8e8; border-radius:12px;
        padding:14px 20px; margin-bottom:10px;
        box-shadow:0 2px 6px rgba(0,0,0,0.04);'>
            <div style='display:flex; justify-content:space-between;
            align-items:center; flex-wrap:wrap; gap:10px;'>
                <p style='font-size:14px; font-weight:700; color:#041747;
                margin:0; min-width:110px;'>📆 {mes_ano}</p>
                <div style='display:flex; gap:12px; flex-wrap:wrap; align-items:center;'>
                    {partes_html}
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

def tela_calendario():
    st.title("📅 Calendário Operacional")
    st.markdown("Acompanhe os fechamentos e importações contábeis.")
    st.markdown("---")

    competencias = buscar_competencias()

    # =============================================
    # VISUALIZAÇÃO
    # =============================================
    if not competencias:
        st.info("Nenhuma competência cadastrada ainda.")
    else:
        # MÊS ATUAL
        if len(competencias) >= 1:
            secao_competencia(competencias[0], compacto=False)

        # PRÓXIMO MÊS
        if len(competencias) >= 2:
            st.markdown("---")
            st.markdown("#### 📅 Próximo período")
            secao_competencia(competencias[1], compacto=True)

        # VISÃO ANUAL
        if len(competencias) >= 1:
            st.markdown("---")
            secao_anual(competencias)

    # =============================================
    # GESTÃO — SOMENTE CONTABILIDADE
    # =============================================
    if st.session_state.perfil == "contabilidade":
        st.markdown("---")
        st.subheader("⚙️ Gerenciar Calendário")

        aba_gest = st.tabs(["➕ Nova Competência", "✏️ Editar Fechamentos", "🗑️ Remover Competência"])

        # ABA NOVA COMPETÊNCIA
        with aba_gest[0]:
            st.markdown("##### Cadastrar nova competência")
            with st.form("form_competencia"):
                col1, col2 = st.columns(2)
                with col1:
                    mes_ano_input = st.text_input("Competência *", placeholder="ex: Junho/2026")
                    mes_input = st.number_input("Mês *", min_value=1, max_value=12, value=1)
                with col2:
                    ano_input = st.number_input("Ano *", min_value=2020, max_value=2030, value=2026)

                st.markdown("##### Fechamentos")
                dados_fechamentos = {}
                for tipo in TIPOS_FECHAMENTO:
                    cor = CORES_FECHAMENTO[tipo]
                    st.markdown(f"<p style='color:{cor['texto']}; font-weight:600; margin:8px 0 4px;'>📌 {tipo}</p>", unsafe_allow_html=True)
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        data_f = st.date_input(f"Data", value=None, key=f"data_{tipo}")
                    with c2:
                        per_ini = st.date_input(f"Período início", value=None, key=f"ini_{tipo}")
                    with c3:
                        per_fim = st.date_input(f"Período fim", value=None, key=f"fim_{tipo}")
                    obs = st.text_input(f"Observação", key=f"obs_{tipo}", placeholder="Opcional")
                    dados_fechamentos[tipo] = (data_f, per_ini, per_fim, obs)

                salvar = st.form_submit_button("💾 Salvar Competência", use_container_width=True)

            if salvar:
                if not mes_ano_input.strip():
                    st.error("⚠️ Preencha a competência.")
                else:
                    conn = get_conn()
                    cur = conn.cursor()
                    cur.execute("""
                        INSERT INTO competencias (mes_ano, ano, mes)
                        VALUES (%s, %s, %s) RETURNING id
                    """, (mes_ano_input.strip(), int(ano_input), int(mes_input)))
                    comp_id = cur.fetchone()[0]

                    for tipo, (data_f, per_ini, per_fim, obs) in dados_fechamentos.items():
                        if data_f or per_ini or per_fim:
                            cur.execute("""
                                INSERT INTO fechamentos
                                (competencia_id, tipo, data_fechamento, periodo_inicio, periodo_fim, observacao)
                                VALUES (%s, %s, %s, %s, %s, %s)
                            """, (comp_id, tipo,
                                  data_f if data_f else None,
                                  per_ini if per_ini else None,
                                  per_fim if per_fim else None,
                                  obs.strip() if obs else None))

                    conn.commit()
                    cur.close()
                    conn.close()
                    st.success(f"✅ Competência {mes_ano_input} salva!")
                    st.rerun()

        # ABA EDITAR FECHAMENTOS
        with aba_gest[1]:
            st.markdown("##### Editar fechamentos existentes")
            if not competencias:
                st.info("Nenhuma competência cadastrada.")
            else:
                opcoes = {f"{c[1]}": c[0] for c in competencias}
                sel = st.selectbox("Selecione a competência", list(opcoes.keys()))
                comp_id_sel = opcoes[sel]
                fechamentos = buscar_fechamentos(comp_id_sel)
                fech_dict = {f[1]: f for f in fechamentos}

                for tipo in TIPOS_FECHAMENTO:
                    cor = CORES_FECHAMENTO[tipo]
                    st.markdown(f"<p style='color:{cor['texto']}; font-weight:600; margin:12px 0 4px;'>📌 {tipo}</p>", unsafe_allow_html=True)

                    fech = fech_dict.get(tipo)
                    fid = fech[0] if fech else None
                    val_data = fech[2] if fech and fech[2] else None
                    val_ini = fech[3] if fech and fech[3] else None
                    val_fim = fech[4] if fech and fech[4] else None
                    val_obs = fech[5] if fech and fech[5] else ""

                    c1, c2, c3 = st.columns(3)
                    with c1:
                        nova_data = st.date_input("Data", value=val_data, key=f"edit_data_{tipo}_{comp_id_sel}")
                    with c2:
                        novo_ini = st.date_input("Período início", value=val_ini, key=f"edit_ini_{tipo}_{comp_id_sel}")
                    with c3:
                        novo_fim = st.date_input("Período fim", value=val_fim, key=f"edit_fim_{tipo}_{comp_id_sel}")
                    novo_obs = st.text_input("Observação", value=val_obs, key=f"edit_obs_{tipo}_{comp_id_sel}")

                    if st.button(f"💾 Salvar {tipo}", key=f"btn_edit_{tipo}_{comp_id_sel}"):
                        conn = get_conn()
                        cur = conn.cursor()
                        if fid:
                            cur.execute("""
                                UPDATE fechamentos SET data_fechamento=%s,
                                periodo_inicio=%s, periodo_fim=%s, observacao=%s
                                WHERE id=%s
                            """, (nova_data if nova_data else None,
                                  novo_ini if novo_ini else None,
                                  novo_fim if novo_fim else None,
                                  novo_obs.strip() if novo_obs else None,
                                  fid))
                        else:
                            cur.execute("""
                                INSERT INTO fechamentos
                                (competencia_id, tipo, data_fechamento, periodo_inicio, periodo_fim, observacao)
                                VALUES (%s, %s, %s, %s, %s, %s)
                            """, (comp_id_sel, tipo,
                                  nova_data if nova_data else None,
                                  novo_ini if novo_ini else None,
                                  novo_fim if novo_fim else None,
                                  novo_obs.strip() if novo_obs else None))
                        conn.commit()
                        cur.close()
                        conn.close()
                        st.success(f"✅ {tipo} atualizado!")
                        st.rerun()

        # ABA REMOVER COMPETÊNCIA
        with aba_gest[2]:
            st.markdown("##### Remover competência")
            if not competencias:
                st.info("Nenhuma competência cadastrada.")
            else:
                opcoes_rem = {f"{c[1]}": c[0] for c in competencias}
                sel_rem = st.selectbox("Selecione a competência para remover", list(opcoes_rem.keys()))
                st.warning(f"⚠️ Isso removerá **{sel_rem}** e todos os seus fechamentos permanentemente.")
                if st.button("🗑️ Confirmar Remoção", use_container_width=True):
                    conn = get_conn()
                    cur = conn.cursor()
                    cur.execute("DELETE FROM competencias WHERE id=%s", (opcoes_rem[sel_rem],))
                    conn.commit()
                    cur.close()
                    conn.close()
                    st.success(f"✅ Competência {sel_rem} removida!")
                    st.rerun()
