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

CORES = {
    "Fechamento Parcial 1":              {"borda": "#3B82F6", "bg": "#EFF6FF", "texto": "#1D4ED8"},
    "Fechamento Parcial 2":              {"borda": "#EAB308", "bg": "#FEFCE8", "texto": "#854D0E"},
    "Fechamento Parcial 3":              {"borda": "#F97316", "bg": "#FFF7ED", "texto": "#9A3412"},
    "Fechamento Consolidado Corporativo":{"borda": "#EF4444", "bg": "#FEF2F2", "texto": "#991B1B"},
}

def formatar_data(d):
    if not d:
        return "—"
    return d.strftime("%d/%m/%Y") if hasattr(d, 'strftime') else str(d)

def status_data(d):
    if not d:
        return "⚪", "Não definida", "#999"
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
    cur.execute("SELECT id, mes_ano, ano, mes FROM competencias ORDER BY ano, mes")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def buscar_fechamentos(competencia_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, tipo, data_fechamento, hora_fechamento, periodo_inicio, periodo_fim, observacao
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

def card_grande(tipo, fech):
    cor = CORES[tipo]
    if fech:
        fid, t, data_f, hora_f, per_ini, per_fim, obs = fech
        icone, status_txt, cor_status = status_data(data_f)
        data_str = formatar_data(data_f)
        hora_str = f" às {hora_f}" if hora_f else ""
        periodo = f"{formatar_data(per_ini)} → {formatar_data(per_fim)}"
        obs_html = f"<p style='font-size:11px; color:#888; margin:6px 0 0; font-style:italic;'>{obs}</p>" if obs else ""
    else:
        icone, status_txt, cor_status = "⚪", "Não cadastrado", "#999"
        data_str = "—"
        hora_str = ""
        periodo = "—"
        obs_html = ""

    return f"""
    <div style='border:2px solid {cor["borda"]}; border-radius:14px; padding:20px;
    background:{cor["bg"]}; text-align:center;
    box-shadow:0 2px 10px rgba(0,0,0,0.06); height:100%; min-height:180px;'>
        <p style='font-size:11px; color:{cor["texto"]}; font-weight:700;
        text-transform:uppercase; letter-spacing:1px; margin:0 0 10px;'>{tipo}</p>
        <p style='font-size:28px; margin:0 0 6px;'>{icone}</p>
        <p style='font-size:16px; font-weight:700; color:#041747; margin:0;'>{data_str}{hora_str}</p>
        <p style='font-size:12px; color:{cor_status}; font-weight:600; margin:4px 0 8px;'>{status_txt}</p>
        <p style='font-size:11px; color:#555; margin:0;'>📅 {periodo}</p>
        {obs_html}
    </div>
    """

def card_pequeno(tipo, fech):
    cor = CORES[tipo]
    if fech:
        fid, t, data_f, hora_f, per_ini, per_fim, obs = fech
        icone, status_txt, cor_status = status_data(data_f)
        data_str = formatar_data(data_f)
        hora_str = f" às {hora_f}" if hora_f else ""
        periodo = f"{formatar_data(per_ini)} → {formatar_data(per_fim)}"
    else:
        icone, status_txt, cor_status = "⚪", "Não cadastrado", "#999"
        data_str = "—"
        hora_str = ""
        periodo = "—"

    label = tipo.replace("Fechamento ", "").replace("Consolidado Corporativo", "Consolidado")

    return f"""
    <div style='border:1.5px solid {cor["borda"]}; border-radius:10px; padding:12px;
    background:{cor["bg"]}; text-align:center;'>
        <p style='font-size:10px; color:{cor["texto"]}; font-weight:700;
        text-transform:uppercase; letter-spacing:0.5px; margin:0 0 4px;'>{label}</p>
        <p style='font-size:18px; margin:0 0 2px;'>{icone}</p>
        <p style='font-size:12px; font-weight:700; color:#041747; margin:0;'>{data_str}{hora_str}</p>
        <p style='font-size:10px; color:#666; margin:2px 0 0;'>📅 {periodo}</p>
    </div>
    """

def exibir_mes(comp, grande=True):
    cid, mes_ano, ano, mes = comp
    fechamentos = buscar_fechamentos(cid)
    fech_dict = {f[1]: f for f in fechamentos}

    if grande:
        st.markdown(f"### 📆 {mes_ano}")
    else:
        st.markdown(f"##### 📅 {mes_ano}")

    cols = st.columns(4)
    for i, tipo in enumerate(TIPOS_FECHAMENTO):
        with cols[i]:
            fech = fech_dict.get(tipo)
            if grande:
                st.markdown(card_grande(tipo, fech), unsafe_allow_html=True)
            else:
                st.markdown(card_pequeno(tipo, fech), unsafe_allow_html=True)

def exibir_anual(competencias):
    st.markdown("#### 🗓️ Visão Anual — 2026")
    st.markdown("---")

    for comp in competencias:
        cid, mes_ano, ano, mes = comp
        fechamentos = buscar_fechamentos(cid)
        fech_dict = {f[1]: f for f in fechamentos}

        cols = st.columns([1.2, 1, 1, 1, 1])
        with cols[0]:
            st.markdown(f"**📆 {mes_ano}**")

        for i, tipo in enumerate(TIPOS_FECHAMENTO):
            cor = CORES[tipo]
            fech = fech_dict.get(tipo)
            label = tipo.replace("Fechamento ", "").replace("Consolidado Corporativo", "Consolidado")

            with cols[i + 1]:
                if fech:
                    fid, t, data_f, hora_f, per_ini, per_fim, obs = fech
                    icone, _, _ = status_data(data_f)
                    hora_str = f" {hora_f}" if hora_f else ""
                    st.markdown(f"""
                    <div style='border-left:3px solid {cor["borda"]}; padding:4px 8px;
                    background:{cor["bg"]}; border-radius:6px; margin-bottom:4px;'>
                        <p style='font-size:10px; color:{cor["texto"]}; font-weight:700; margin:0;'>{label}</p>
                        <p style='font-size:11px; font-weight:600; color:#041747; margin:1px 0;'>
                        {icone} {formatar_data(data_f)}{hora_str}</p>
                        <p style='font-size:10px; color:#666; margin:0;'>
                        {formatar_data(per_ini)} → {formatar_data(per_fim)}</p>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div style='border-left:3px solid #ddd; padding:4px 8px;
                    background:#f9f9f9; border-radius:6px; margin-bottom:4px; opacity:0.5;'>
                        <p style='font-size:10px; color:#999; font-weight:700; margin:0;'>{label}</p>
                        <p style='font-size:11px; color:#ccc; margin:1px 0;'>—</p>
                    </div>
                    """, unsafe_allow_html=True)

        st.markdown("<hr style='margin:8px 0; border-color:#f0f0f0;'>", unsafe_allow_html=True)

def tela_calendario():
    st.title("📅 Calendário Operacional")
    st.markdown("Acompanhe os fechamentos e importações contábeis.")
    st.markdown("---")

    competencias = buscar_competencias()

    if not competencias:
        st.info("Nenhuma competência cadastrada ainda.")
        return

    # Identificar mês atual e próximo
    hoje = datetime.now(BRASILIA)
    mes_atual = hoje.month
    ano_atual = hoje.year

    comp_atual = None
    comp_proximo = None

    for i, comp in enumerate(competencias):
        cid, mes_ano, ano, mes = comp
        if ano == ano_atual and mes == mes_atual:
            comp_atual = comp
            if i + 1 < len(competencias):
                comp_proximo = competencias[i + 1]
            break

    # Fallback: usar o primeiro se não encontrar o mês atual
    if not comp_atual and competencias:
        comp_atual = competencias[0]
        if len(competencias) > 1:
            comp_proximo = competencias[1]

    # MÊS ATUAL — cards grandes
    exibir_mes(comp_atual, grande=True)

    # PRÓXIMO MÊS — cards pequenos
    if comp_proximo:
        st.markdown("---")
        exibir_mes(comp_proximo, grande=False)

    # VISÃO ANUAL
    st.markdown("---")
    exibir_anual(competencias)

    # =============================================
    # GESTÃO — SOMENTE CONTABILIDADE
    # =============================================
    if st.session_state.perfil == "contabilidade":
        st.markdown("---")
        st.subheader("⚙️ Editar Calendário")

        if not competencias:
            st.info("Nenhuma competência cadastrada.")
        else:
            opcoes = {f"{c[1]}": c[0] for c in competencias}
            sel = st.selectbox("Selecione o mês para editar", list(opcoes.keys()))
            comp_id_sel = opcoes[sel]
            fechamentos = buscar_fechamentos(comp_id_sel)
            fech_dict = {f[1]: f for f in fechamentos}

            for tipo in TIPOS_FECHAMENTO:
                cor = CORES[tipo]
                st.markdown(f"""
                <p style='color:{cor["texto"]}; font-weight:700;
                font-size:14px; margin:16px 0 6px;'>📌 {tipo}</p>
                """, unsafe_allow_html=True)

                fech = fech_dict.get(tipo)
                fid = fech[0] if fech else None
                val_data = fech[2] if fech and fech[2] else None
                val_hora = fech[3] if fech and fech[3] else ""
                val_ini = fech[4] if fech and fech[4] else None
                val_fim = fech[5] if fech and fech[5] else None
                val_obs = fech[6] if fech and fech[6] else ""

                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    nova_data = st.date_input("Data", value=val_data, key=f"ed_{tipo}_{comp_id_sel}")
                with c2:
                    nova_hora = st.text_input("Horário", value=val_hora, key=f"eh_{tipo}_{comp_id_sel}", placeholder="ex: 12:00")
                with c3:
                    novo_ini = st.date_input("Período início", value=val_ini, key=f"ei_{tipo}_{comp_id_sel}")
                with c4:
                    novo_fim = st.date_input("Período fim", value=val_fim, key=f"ef_{tipo}_{comp_id_sel}")

                novo_obs = st.text_input("Observação", value=val_obs, key=f"eo_{tipo}_{comp_id_sel}", placeholder="Opcional")

                if st.button(f"💾 Salvar {tipo}", key=f"btn_{tipo}_{comp_id_sel}"):
                    conn = get_conn()
                    cur = conn.cursor()
                    if fid:
                        cur.execute("""
                            UPDATE fechamentos SET
                            data_fechamento=%s, hora_fechamento=%s,
                            periodo_inicio=%s, periodo_fim=%s, observacao=%s
                            WHERE id=%s
                        """, (
                            nova_data if nova_data else None,
                            nova_hora.strip() if nova_hora else None,
                            novo_ini if novo_ini else None,
                            novo_fim if novo_fim else None,
                            novo_obs.strip() if novo_obs else None,
                            fid
                        ))
                    else:
                        cur.execute("""
                            INSERT INTO fechamentos
                            (competencia_id, tipo, data_fechamento, hora_fechamento,
                            periodo_inicio, periodo_fim, observacao)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (
                            comp_id_sel, tipo,
                            nova_data if nova_data else None,
                            nova_hora.strip() if nova_hora else None,
                            novo_ini if novo_ini else None,
                            novo_fim if novo_fim else None,
                            novo_obs.strip() if novo_obs else None
                        ))
                    conn.commit()
                    cur.close()
                    conn.close()
                    st.success(f"✅ {tipo} atualizado!")
                    st.rerun()
