import streamlit as st
from database.connection import get_conn, release_conn, run_query
from datetime import datetime
from zoneinfo import ZoneInfo

BRASILIA = ZoneInfo("America/Sao_Paulo")

TIPOS = [
    "Fechamento Parcial 1",
    "Fechamento Parcial 2",
    "Fechamento Parcial 3",
    "Fechamento Consolidado Corporativo"
]

CORES = {
    "Fechamento Parcial 1":               {"borda":"#3B82F6","bg":"#EFF6FF","texto":"#1D4ED8"},
    "Fechamento Parcial 2":               {"borda":"#EAB308","bg":"#FEFCE8","texto":"#854D0E"},
    "Fechamento Parcial 3":               {"borda":"#F97316","bg":"#FFF7ED","texto":"#9A3412"},
    "Fechamento Consolidado Corporativo": {"borda":"#EF4444","bg":"#FEF2F2","texto":"#991B1B"},
}

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

@st.cache_data(ttl=60)
def buscar_competencias():
    return run_query("SELECT id, mes_ano, ano, mes FROM competencias ORDER BY ano, mes", fetch=True)

def buscar_fechamentos(cid):
    return run_query("""
        SELECT id, tipo, data_fechamento, hora_fechamento, periodo_inicio, periodo_fim, observacao
        FROM fechamentos WHERE competencia_id=%s
        ORDER BY CASE tipo
            WHEN 'Fechamento Parcial 1' THEN 1
            WHEN 'Fechamento Parcial 2' THEN 2
            WHEN 'Fechamento Parcial 3' THEN 3
            WHEN 'Fechamento Consolidado Corporativo' THEN 4
        END
    """, (cid,), fetch=True)

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
    label = tipo.replace("Fechamento ","").replace("Consolidado Corporativo","Consolidado")
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

def exibir_mes(comp, grande=True):
    cid, mes_ano, ano, mes = comp
    fd = {f[1]:f for f in buscar_fechamentos(cid)}
    st.markdown(f"### 📆 {mes_ano}" if grande else f"##### 📅 {mes_ano}")
    cols = st.columns(4)
    for i, tipo in enumerate(TIPOS):
        with cols[i]:
            html = card_grande(tipo, fd.get(tipo)) if grande else card_pequeno(tipo, fd.get(tipo))
            st.markdown(html, unsafe_allow_html=True)

def exibir_anual(competencias):
    st.markdown("#### 🗓️ Visão Anual — 2026")
    st.markdown("---")
    for comp in competencias:
        cid, mes_ano, ano, mes = comp
        fd = {f[1]:f for f in buscar_fechamentos(cid)}
        cols = st.columns([1.2,1,1,1,1])
        with cols[0]:
            st.markdown(f"**📆 {mes_ano}**")
        for i, tipo in enumerate(TIPOS):
            cor = CORES[tipo]
            label = tipo.replace("Fechamento ","").replace("Consolidado Corporativo","Consolidado")
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
        st.markdown("<hr style='margin:8px 0;border-color:#f0f0f0;'>", unsafe_allow_html=True)

def tela_calendario():
    st.title("📅 Calendário Operacional")
    st.markdown("Acompanhe os fechamentos e importações contábeis.")
    st.markdown("---")

    competencias = buscar_competencias()
    if not competencias:
        st.info("Nenhuma competência cadastrada ainda.")
        return

    hoje = datetime.now(BRASILIA)
    comp_atual = next((c for c in competencias if c[2]==hoje.year and c[3]==hoje.month), competencias[0])
    idx = competencias.index(comp_atual)
    comp_prox = competencias[idx+1] if idx+1 < len(competencias) else None

    exibir_mes(comp_atual, grande=True)
    if comp_prox:
        st.markdown("---")
        exibir_mes(comp_prox, grande=False)
    st.markdown("---")
    exibir_anual(competencias)

    if st.session_state.perfil == "contabilidade":
        st.markdown("---")
        st.subheader("⚙️ Editar Calendário")
        opcoes = {c[1]: c[0] for c in competencias}
        sel = st.selectbox("Selecione o mês", list(opcoes.keys()))
        cid = opcoes[sel]
        fd = {f[1]:f for f in buscar_fechamentos(cid)}

        for tipo in TIPOS:
            cor = CORES[tipo]
            st.markdown(f"<p style='color:{cor['texto']};font-weight:700;font-size:14px;margin:16px 0 6px;'>📌 {tipo}</p>", unsafe_allow_html=True)
            f = fd.get(tipo)
            fid = f[0] if f else None
            c1,c2,c3,c4 = st.columns(4)
            nd = c1.date_input("Data", value=f[2] if f and f[2] else None, key=f"d_{tipo}_{cid}")
            nh = c2.text_input("Horário", value=f[3] if f and f[3] else "", key=f"h_{tipo}_{cid}", placeholder="ex: 12:00")
            ni = c3.date_input("Período início", value=f[4] if f and f[4] else None, key=f"i_{tipo}_{cid}")
            nf = c4.date_input("Período fim", value=f[5] if f and f[5] else None, key=f"f_{tipo}_{cid}")
            no = st.text_input("Observação", value=f[6] if f and f[6] else "", key=f"o_{tipo}_{cid}")

            if st.button(f"💾 Salvar {tipo}", key=f"btn_{tipo}_{cid}"):
                if fid:
                    run_query("""
                        UPDATE fechamentos SET data_fechamento=%s,hora_fechamento=%s,
                        periodo_inicio=%s,periodo_fim=%s,observacao=%s WHERE id=%s
                    """, (nd or None, nh.strip() or None, ni or None, nf or None, no.strip() or None, fid))
                else:
                    run_query("""
                        INSERT INTO fechamentos (competencia_id,tipo,data_fechamento,hora_fechamento,periodo_inicio,periodo_fim,observacao)
                        VALUES (%s,%s,%s,%s,%s,%s,%s)
                    """, (cid, tipo, nd or None, nh.strip() or None, ni or None, nf or None, no.strip() or None))
                st.cache_data.clear()
                st.success(f"✅ {tipo} atualizado!")
                st.rerun()
