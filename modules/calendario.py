import streamlit as st
from database.connection import run_query
from datetime import datetime, date
from zoneinfo import ZoneInfo

BRASILIA = ZoneInfo("America/Sao_Paulo")

TIPOS = [
    "Fechamento Parcial 1",
    "Fechamento Parcial 2",
    "Fechamento Parcial 3",
    "Fechamento Parcial 4"
]

CORES = {
    "Fechamento Parcial 1": {"borda":"#3B82F6","bg":"#EFF6FF","texto":"#1D4ED8"},
    "Fechamento Parcial 2": {"borda":"#EAB308","bg":"#FEFCE8","texto":"#854D0E"},
    "Fechamento Parcial 3": {"borda":"#F97316","bg":"#FFF7ED","texto":"#9A3412"},
    "Fechamento Parcial 4": {"borda":"#EF4444","bg":"#FEF2F2","texto":"#991B1B"},
}

COR_CONSOLIDACAO = {"borda":"#0F8C3B","bg":"#F0FDF4","texto":"#166534"}

# Datas da Consolidacao (1o, 2o e 3o dia util do mes seguinte), sem horario.
# Chave = mes da competencia (1=Janeiro ... 12=Dezembro)
CONSOLIDACAO = {
    1:  [date(2026, 2, 2),  date(2026, 2, 3),  date(2026, 2, 4)],
    2:  [date(2026, 3, 2),  date(2026, 3, 3),  date(2026, 3, 4)],
    3:  [date(2026, 4, 1),  date(2026, 4, 2),  date(2026, 4, 6)],
    4:  [date(2026, 5, 4),  date(2026, 5, 5),  date(2026, 5, 6)],
    5:  [date(2026, 6, 1),  date(2026, 6, 2),  date(2026, 6, 3)],
    6:  [date(2026, 7, 1),  date(2026, 7, 2),  date(2026, 7, 3)],
    7:  [date(2026, 8, 3),  date(2026, 8, 4),  date(2026, 8, 5)],
    8:  [date(2026, 9, 1),  date(2026, 9, 2),  date(2026, 9, 3)],
    9:  [date(2026, 10, 1), date(2026, 10, 2), date(2026, 10, 5)],
    10: [date(2026, 11, 3), date(2026, 11, 4), date(2026, 11, 5)],
    11: [date(2026, 12, 1), date(2026, 12, 2), date(2026, 12, 3)],
    12: [date(2027, 1, 4),  date(2027, 1, 5),  date(2027, 1, 6)],
}

def normaliza_tipo(t):
    # Compatibilidade: trata o nome antigo como Parcial 4
    if t == "Fechamento Consolidado Corporativo":
        return "Fechamento Parcial 4"
    return t

def fmt(d):
    if not d: return "—"
    return d.strftime("%d/%m/%Y") if hasattr(d,'strftime') else str(d)

def status(d):
    if not d: return "⚪","Não definida","#999"
    hoje = datetime.now(BRASILIA).date()
    data = d.date() if hasattr(d,'date') else d
    if data < hoje: return "✅","Concluída","#22c55e"
    if data == hoje: return "🟡","Hoje","#f59e0b"
    return "🔵",f"Em {(data-hoje).days} dias","#3B82F6"

@st.cache_data(ttl=300)
def buscar_competencias():
    return run_query("SELECT id, mes_ano, ano, mes FROM competencias ORDER BY ano, mes", fetch=True)

@st.cache_data(ttl=300)
def buscar_fechamentos(cid):
    return run_query("""
        SELECT id, tipo, data_fechamento, hora_fechamento, periodo_inicio, periodo_fim, observacao
        FROM fechamentos WHERE competencia_id=%s
        ORDER BY CASE tipo
            WHEN 'Fechamento Parcial 1' THEN 1
            WHEN 'Fechamento Parcial 2' THEN 2
            WHEN 'Fechamento Parcial 3' THEN 3
            WHEN 'Fechamento Parcial 4' THEN 4
            WHEN 'Fechamento Consolidado Corporativo' THEN 4
        END
    """, (cid,), fetch=True)

@st.cache_data(ttl=300)
def buscar_todos_fechamentos():
    return run_query("""
        SELECT competencia_id, id, tipo, data_fechamento, hora_fechamento, periodo_inicio, periodo_fim, observacao
        FROM fechamentos
        ORDER BY competencia_id, CASE tipo
            WHEN 'Fechamento Parcial 1' THEN 1
            WHEN 'Fechamento Parcial 2' THEN 2
            WHEN 'Fechamento Parcial 3' THEN 3
            WHEN 'Fechamento Parcial 4' THEN 4
            WHEN 'Fechamento Consolidado Corporativo' THEN 4
        END
    """, fetch=True)

def card_grande(tipo, f):
    cor = CORES[tipo]
    if f:
        fid,t,df,hf,pi,pf,obs = f
        ic,st_txt,cor_s = status(df)
        hs = f" às {hf}" if hf else ""
        per = f"{fmt(pi)} → {fmt(pf)}"
        obs_h = f"<p style='font-size:11px;color:#888;margin:6px 0 0;font-style:italic;'>{obs}</p>" if obs else ""
    else:
        ic,st_txt,cor_s,hs,per,obs_h,df = "⚪","Não cadastrado","#999","","—","",None
    return f"""
    <div style='border:2px solid {cor["borda"]};border-radius:14px;padding:20px;
    background:{cor["bg"]};text-align:center;box-shadow:0 2px 10px rgba(0,0,0,0.06);min-height:180px;'>
        <p style='font-size:11px;color:{cor["texto"]};font-weight:700;
        text-transform:uppercase;letter-spacing:1px;margin:0 0 10px;'>{tipo}</p>
        <p style='font-size:28px;margin:0 0 6px;'>{ic}</p>
        <p style='font-size:16px;font-weight:700;color:#041747;margin:0;'>{fmt(df)}{hs}</p>
        <p style='font-size:12px;color:{cor_s};font-weight:600;margin:4px 0 8px;'>{st_txt}</p>
        <p style='font-size:11px;color:#555;margin:0;'>📅 {per}</p>{obs_h}
    </div>"""

def card_pequeno(tipo, f):
    cor = CORES[tipo]
    label = tipo.replace("Fechamento ","")
    if f:
        fid,t,df,hf,pi,pf,obs = f
        ic,_,_ = status(df)
        hs = f" às {hf}" if hf else ""
        per = f"{fmt(pi)} → {fmt(pf)}"
    else:
        ic,hs,per,df = "⚪","","—",None
    return f"""
    <div style='border:1.5px solid {cor["borda"]};border-radius:10px;padding:12px;
    background:{cor["bg"]};text-align:center;'>
        <p style='font-size:10px;color:{cor["texto"]};font-weight:700;
        text-transform:uppercase;letter-spacing:0.5px;margin:0 0 4px;'>{label}</p>
        <p style='font-size:18px;margin:0 0 2px;'>{ic}</p>
        <p style='font-size:12px;font-weight:700;color:#041747;margin:0;'>{fmt(df)}{hs}</p>
        <p style='font-size:10px;color:#666;margin:2px 0 0;'>📅 {per}</p>
    </div>"""

def card_consolidacao(mes, grande=True):
    cor = COR_CONSOLIDACAO
    datas = CONSOLIDACAO.get(mes, [])
    pad = 18 if grande else 12
    fs_label = 12 if grande else 10
    fs_data = 14 if grande else 12
    if datas:
        chips = ""
        for d in datas:
            ic,_,_ = status(d)
            chips += f"""<span style='display:inline-block;background:white;border:1.5px solid {cor["borda"]};
            border-radius:8px;padding:6px 12px;margin:4px;font-size:{fs_data}px;font-weight:700;color:#041747;'>{ic} {fmt(d)}</span>"""
    else:
        chips = "<span style='color:#999;font-size:13px;'>Sem datas definidas</span>"
    return f"""
    <div style='border:2px solid {cor["borda"]};border-radius:14px;padding:{pad}px;
    background:{cor["bg"]};text-align:center;margin-top:14px;'>
        <p style='font-size:{fs_label}px;color:{cor["texto"]};font-weight:700;
        text-transform:uppercase;letter-spacing:1px;margin:0 0 8px;'>🔒 Consolidação — 1º, 2º e 3º dia útil</p>
        <div style='display:flex;justify-content:center;flex-wrap:wrap;'>{chips}</div>
    </div>"""

def exibir_mes(comp, todos_fechamentos, grande=True):
    cid, mes_ano, ano, mes = comp
    fd = {normaliza_tipo(f[2]):f[1:] for f in todos_fechamentos if f[0]==cid}
    st.markdown(f"### 📆 {mes_ano}" if grande else f"##### 📅 {mes_ano}")
    cols = st.columns(4)
    for i, tipo in enumerate(TIPOS):
        with cols[i]:
            f = fd.get(tipo)
            html = card_grande(tipo, f) if grande else card_pequeno(tipo, f)
            st.markdown(html, unsafe_allow_html=True)
    st.markdown(card_consolidacao(mes, grande), unsafe_allow_html=True)

def exibir_anual(competencias, todos_fechamentos):
    st.markdown("#### 🗓️ Visão Anual — 2026")
    st.markdown("---")
    for comp in competencias:
        cid, mes_ano, ano, mes = comp
        fd = {normaliza_tipo(f[2]):f[1:] for f in todos_fechamentos if f[0]==cid}
        cols = st.columns([1.2,1,1,1,1,1])
        with cols[0]:
            st.markdown(f"**📆 {mes_ano}**")
        for i, tipo in enumerate(TIPOS):
            cor = CORES[tipo]
            label = tipo.replace("Fechamento ","")
            with cols[i+1]:
                f = fd.get(tipo)
                if f:
                    fid,t,df,hf,pi,pf,obs = f
                    ic,_,_ = status(df)
                    hs = f" {hf}" if hf else ""
                    st.markdown(f"""
                    <div style='border-left:3px solid {cor["borda"]};padding:4px 8px;
                    background:{cor["bg"]};border-radius:6px;margin-bottom:4px;'>
                        <p style='font-size:10px;color:{cor["texto"]};font-weight:700;margin:0;'>{label}</p>
                        <p style='font-size:11px;font-weight:600;color:#041747;margin:1px 0;'>{ic} {fmt(df)}{hs}</p>
                        <p style='font-size:10px;color:#666;margin:0;'>{fmt(pi)} → {fmt(pf)}</p>
                    </div>""", unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div style='border-left:3px solid #ddd;padding:4px 8px;
                    background:#f9f9f9;border-radius:6px;margin-bottom:4px;opacity:0.5;'>
                        <p style='font-size:10px;color:#999;font-weight:700;margin:0;'>{label}</p>
                        <p style='font-size:11px;color:#ccc;margin:1px 0;'>—</p>
                    </div>""", unsafe_allow_html=True)
        cor = COR_CONSOLIDACAO
        datas = CONSOLIDACAO.get(mes, [])
        with cols[5]:
            if datas:
                linhas = "".join(
                    f"<p style='font-size:11px;font-weight:600;color:#041747;margin:1px 0;'>{status(d)[0]} {fmt(d)}</p>"
                    for d in datas)
                st.markdown(f"""
                <div style='border-left:3px solid {cor["borda"]};padding:4px 8px;
                background:{cor["bg"]};border-radius:6px;margin-bottom:4px;'>
                    <p style='font-size:10px;color:{cor["texto"]};font-weight:700;margin:0;'>Consolidação</p>
                    {linhas}
                </div>""", unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style='border-left:3px solid #ddd;padding:4px 8px;
                background:#f9f9f9;border-radius:6px;margin-bottom:4px;opacity:0.5;'>
                    <p style='font-size:10px;color:#999;font-weight:700;margin:0;'>Consolidação</p>
                    <p style='font-size:11px;color:#ccc;margin:1px 0;'>—</p>
                </div>""", unsafe_allow_html=True)
        st.markdown("<hr style='margin:8px 0;border-color:#f0f0f0;'>", unsafe_allow_html=True)

def tela_calendario():
  st.title("📅 Calendário Operacional Corporativo")
    st.markdown("Acompanhe os fechamentos e importações contábeis.")
    st.markdown("---")

    competencias = buscar_competencias()
    if not competencias:
        st.info("Nenhuma competência cadastrada ainda.")
        return

    # Uma única consulta para todos os fechamentos
    todos_fechamentos = buscar_todos_fechamentos()

    hoje = datetime.now(BRASILIA)
    comp_atual = next((c for c in competencias if c[2]==hoje.year and c[3]==hoje.month), competencias[0])
    idx = competencias.index(comp_atual)
    comp_prox = competencias[idx+1] if idx+1 < len(competencias) else None

    exibir_mes(comp_atual, todos_fechamentos, grande=True)
    if comp_prox:
        st.markdown("---")
        exibir_mes(comp_prox, todos_fechamentos, grande=False)
    st.markdown("---")
    exibir_anual(competencias, todos_fechamentos)

    if st.session_state.perfil == "contabilidade":
        st.markdown("---")
        st.subheader("⚙️ Editar Calendário")
        st.caption("A Consolidação (1º/2º/3º dia útil) é fixa e não é editável por aqui.")
        opcoes = {c[1]: c[0] for c in competencias}
        sel = st.selectbox("Selecione o mês", list(opcoes.keys()))
        cid = opcoes[sel]
        fd = {normaliza_tipo(f[2]):f[1:] for f in todos_fechamentos if f[0]==cid}

        for tipo in TIPOS:
            cor = CORES[tipo]
            st.markdown(f"<p style='color:{cor['texto']};font-weight:700;font-size:14px;margin:16px 0 6px;'>📌 {tipo}</p>", unsafe_allow_html=True)
            f = fd.get(tipo)
            fid = f[0] if f else None
            c1,c2,c3,c4 = st.columns(4)
            nd = c1.date_input("Data", value=f[2] if f and f[2] else None, key=f"d_{tipo}_{cid}")
            nh = c2.text_input("Horário", value=f[3] if f and f[3] else "", key=f"h_{tipo}_{cid}", placeholder="ex: 12:00")
            ni = c3.date_input("Período início", value=f[4] if f and f[4] else None, key=f"i_{tipo}_{cid}")
            nf_val = c4.date_input("Período fim", value=f[5] if f and f[5] else None, key=f"f_{tipo}_{cid}")
            no = st.text_input("Observação", value=f[6] if f and f[6] else "", key=f"o_{tipo}_{cid}")

            if st.button(f"💾 Salvar {tipo}", key=f"btn_{tipo}_{cid}"):
                if fid:
                    run_query("""
                        UPDATE fechamentos SET tipo=%s,data_fechamento=%s,hora_fechamento=%s,
                        periodo_inicio=%s,periodo_fim=%s,observacao=%s WHERE id=%s
                    """, (tipo, nd or None, nh.strip() or None, ni or None, nf_val or None, no.strip() or None, fid))
                else:
                    run_query("""
                        INSERT INTO fechamentos (competencia_id,tipo,data_fechamento,hora_fechamento,periodo_inicio,periodo_fim,observacao)
                        VALUES (%s,%s,%s,%s,%s,%s,%s)
                    """, (cid, tipo, nd or None, nh.strip() or None, ni or None, nf_val or None, no.strip() or None))
                st.cache_data.clear()
                st.success(f"✅ {tipo} atualizado!")
                st.rerun()
