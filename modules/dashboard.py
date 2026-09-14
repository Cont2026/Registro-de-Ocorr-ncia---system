import streamlit as st
import pandas as pd
import plotly.express as px
import io
from database.connection import run_query
from datetime import datetime
from zoneinfo import ZoneInfo
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

BRASILIA = ZoneInfo("America/Sao_Paulo")
PREFIXO_FECHAMENTO = "INFORMAR ENTREGÁVEIS"
LABEL_ENTREGAVEIS = "📦 Entregáveis (todos)"

CORES_NIVEL = {
    "Dentro do esperado": "#0F8C3B",
    "Atenção": "#FAC318",
    "Alerta": "#F97316",
    "Crítico": "#EF4444",
}
CORES_NIVEL_XL = {k: v.lstrip("#") for k, v in CORES_NIVEL.items()}

LABELS_NOTIF = {
    "novo_chamado": "Novo chamado",
    "nova_mensagem": "Mensagens (chat por e-mail)",
    "atualizacao_status": "Atualização de status",
    "conclusao": "Conclusão",
    "solicitacao_tratativa": "Solicitação de tratativa",
    "copia_chamado": "Cópia em chamado",
    "troca_setor": "Troca de setor responsável",
    "alerta_fechamento": "Alerta de fechamento",
}

# Nota sobre o retrabalho: o campo 'reaberturas' soma tanto as REABERTURAS (chamado
# que estava Resolvido/Cancelado e voltou) quanto as ABERTURAS DE PENDÊNCIA (chamado
# que estava Pendente e voltou). Nos dois casos houve retrabalho, então o peso é o
# mesmo: 1 + reaberturas, ou seja, um chamado retomado uma vez conta como 2.
NOTA_PESO = "Inclui o retrabalho: chamado reaberto ou com pendência aberta conta como 2."

def classificar_performance(qtd):
    if qtd <= 3:
        return "Dentro do esperado", "100%", "Processo controlado e aderente"
    if qtd <= 8:
        return "Atenção", "85%", "Indícios de falha pontual de conferência"
    if qtd <= 15:
        return "Alerta", "70%", "Deficiência recorrente de conferência"
    return "Crítico", "40%", "Ausência de processo estruturado"

HEADER_FILL = PatternFill("solid", fgColor="041747")
HEADER_FONT = Font(name="Calibri", bold=True, color="FFFFFF", size=12)
HEADER_ALIGN = Alignment(horizontal="center", vertical="center", wrap_text=True)
DATA_FONT = Font(name="Calibri", size=11, color="000000")
DATA_ALIGN = Alignment(horizontal="left", vertical="center")
ALT_FILL = PatternFill("solid", fgColor="F2F4F8")
BORDER = Border(
    left=Side(style="thin", color="DDDDDD"),
    right=Side(style="thin", color="DDDDDD"),
    top=Side(style="thin", color="DDDDDD"),
    bottom=Side(style="thin", color="DDDDDD")
)

@st.cache_data(ttl=30)
def carregar_chamados():
    return run_query("""
        SELECT protocolo, setor, empresa, tipo_inconsistencia,
               prioridade, status, aberto_em, atendido_em, resolvido_em,
               COALESCE(reaberturas,0)
        FROM chamados ORDER BY aberto_em DESC
    """, fetch=True)

@st.cache_data(ttl=30)
def carregar_notificacoes_raw():
    return run_query("SELECT protocolo, tipo, enviado_em FROM notificacoes", fetch=True)

@st.cache_data(ttl=30)
def carregar_mensagens_todas():
    """Histórico COMPLETO do chat, para a aba Mensagens da exportação.
    Traz apenas o NOME do anexo, nunca o conteúdo (anexo_dados): o conteúdo é
    base64 e trafegar isso a cada carregamento de tela foi o que esgotou o
    limite de transferência do banco no passado."""
    return run_query("""
        SELECT chamado_protocolo, enviado_em, autor, perfil, mensagem, anexo_nome
        FROM mensagens ORDER BY chamado_protocolo, enviado_em
    """, fetch=True)

@st.cache_data(ttl=30)
def carregar_chamados_completo():
    return run_query("""
        SELECT protocolo, setor, empresa, tipo_inconsistencia,
               prioridade, nf_retorna, nome_parceiro, numero_nota,
               tipo_nota, data_entrada, data_saida, data_negociacao,
               valor, observacao, status, aberto_em, atendido_em,
               resolvido_em, resolucao
        FROM chamados ORDER BY aberto_em DESC
    """, fetch=True)

def estilo_cabecalho(ws, row, num_cols):
    for col in range(1, num_cols + 1):
        cell = ws.cell(row=row, column=col)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = HEADER_ALIGN
        cell.border = BORDER

def estilo_dados(ws, row_start, row_end, num_cols):
    for row in range(row_start, row_end + 1):
        fill = ALT_FILL if row % 2 == 0 else PatternFill("solid", fgColor="FFFFFF")
        for col in range(1, num_cols + 1):
            cell = ws.cell(row=row, column=col)
            cell.font = DATA_FONT
            cell.alignment = DATA_ALIGN
            cell.fill = fill
            cell.border = BORDER

def ajustar_colunas(ws):
    for col in ws.columns:
        max_len = max((len(str(c.value)) if c.value else 0) for c in col)
        ws.column_dimensions[get_column_letter(col[0].column)].width = min(max_len + 4, 45)

def inserir_cabecalho_relatorio(ws, titulo):
    try:
        img = XLImage("assets/LOGO-GRUPO-LLE-COR-OFICIAL-PRINCIPAL.png")
        img.width = 160
        img.height = 55
        ws.add_image(img, "A1")
    except:
        pass
    ws.row_dimensions[1].height = 35
    ws["E1"] = titulo
    ws["E1"].font = Font(name="Calibri", bold=True, size=14, color="041747")
    ws["E2"] = "Grupo LLE"
    ws["E2"].font = Font(name="Calibri", size=11, color="0071FE", bold=True)
    ws["E3"] = f"Gerado em: {datetime.now(BRASILIA).strftime('%d/%m/%Y às %H:%M')}"
    ws["E3"].font = Font(name="Calibri", size=10, color="999999")

def montar_performance(df_filtrado):
    """Conta chamados (erros) por setor, excluindo fechamentos de período, e classifica.
    Usa o 'peso' (1 + reaberturas): um chamado retomado conta como 2, pois gerou
    retrabalho — vale tanto para reabertura quanto para abertura de pendência."""
    df_err = df_filtrado[~df_filtrado["tipo"].astype(str).str.startswith(PREFIXO_FECHAMENTO)]
    base = df_err.groupby("setor")["peso"].sum().reset_index(name="qtd")
    regs = []
    for _, r in base.iterrows():
        nivel, indice, diag = classificar_performance(int(r["qtd"]))
        regs.append({
            "Setor": r["setor"],
            "Qtd. Erros": int(r["qtd"]),
            "Nível": nivel,
            "Índice": indice,
            "Diagnóstico": diag,
        })
    if not regs:
        return pd.DataFrame(columns=["Setor","Qtd. Erros","Nível","Índice","Diagnóstico"])
    return pd.DataFrame(regs).sort_values("Qtd. Erros", ascending=False).reset_index(drop=True)

def tabela_performance_html(df_perf):
    linhas = ""
    for _, r in df_perf.iterrows():
        hexc = CORES_NIVEL.get(r["Nível"], "#999")
        txt = "#041747" if r["Nível"] == "Atenção" else "white"
        linhas += f"""<tr>
            <td style='padding:8px 10px;border-bottom:1px solid #eee;'>{r['Setor']}</td>
            <td style='padding:8px 10px;border-bottom:1px solid #eee;text-align:center;font-weight:700;color:#041747;'>{r['Qtd. Erros']}</td>
            <td style='padding:8px 10px;border-bottom:1px solid #eee;text-align:center;'>
                <span style='background:{hexc};color:{txt};padding:3px 12px;border-radius:12px;font-size:12px;font-weight:700;'>{r['Nível']}</span>
            </td>
            <td style='padding:8px 10px;border-bottom:1px solid #eee;text-align:center;font-weight:700;color:{hexc};'>{r['Índice']}</td>
            <td style='padding:8px 10px;border-bottom:1px solid #eee;font-size:13px;color:#555;'>{r['Diagnóstico']}</td>
        </tr>"""
    return f"""
    <table style='width:100%;border-collapse:collapse;font-family:Arial,sans-serif;'>
        <thead>
            <tr style='background:#041747;color:white;'>
                <th style='padding:10px;text-align:left;'>Setor</th>
                <th style='padding:10px;'>Qtd. Erros</th>
                <th style='padding:10px;'>Nível</th>
                <th style='padding:10px;'>Índice</th>
                <th style='padding:10px;text-align:left;'>Diagnóstico</th>
            </tr>
        </thead>
        <tbody>{linhas}</tbody>
    </table>"""

def escrever_aba_performance(writer, df_perf):
    ws = writer.book.create_sheet("Performance")
    writer.sheets["Performance"] = ws
    inserir_cabecalho_relatorio(ws, "ROC — Performance por Setor")
    start = 7
    df_perf.to_excel(writer, index=False, sheet_name="Performance", startrow=start-1)
    n_cols = len(df_perf.columns)
    for col_num in range(1, n_cols + 1):
        cell = ws.cell(row=start, column=col_num)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = HEADER_ALIGN
        cell.border = BORDER
    ws.row_dimensions[start].height = 28
    nivel_idx = list(df_perf.columns).index("Nível") + 1
    for i, (_, r) in enumerate(df_perf.iterrows()):
        row_n = start + 1 + i
        for col_num in range(1, n_cols + 1):
            cell = ws.cell(row=row_n, column=col_num)
            cell.font = DATA_FONT
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.fill = PatternFill("solid", fgColor="FFFFFF")
            cell.border = BORDER
        nivel = r["Nível"]
        hexc = CORES_NIVEL_XL.get(nivel)
        if hexc:
            c = ws.cell(row=row_n, column=nivel_idx)
            c.fill = PatternFill("solid", fgColor=hexc)
            c.font = Font(name="Calibri", bold=True,
                          color=("041747" if nivel == "Atenção" else "FFFFFF"), size=11)
    ajustar_colunas(ws)

def escrever_aba_tabela(writer, sheet_name, titulo, df, alinhar="center"):
    ws = writer.book.create_sheet(sheet_name)
    writer.sheets[sheet_name] = ws
    inserir_cabecalho_relatorio(ws, titulo)
    start = 7
    df.to_excel(writer, index=False, sheet_name=sheet_name, startrow=start-1)
    n_cols = len(df.columns)
    for col_num in range(1, n_cols + 1):
        cell = ws.cell(row=start, column=col_num)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = HEADER_ALIGN
        cell.border = BORDER
    ws.row_dimensions[start].height = 28
    for i in range(len(df)):
        row_n = start + 1 + i
        fill = ALT_FILL if (row_n % 2 == 0) else PatternFill("solid", fgColor="FFFFFF")
        for col_num in range(1, n_cols + 1):
            cell = ws.cell(row=row_n, column=col_num)
            cell.font = DATA_FONT
            cell.alignment = Alignment(horizontal=alinhar, vertical="center",
                                       wrap_text=(alinhar == "left"))
            cell.fill = fill
            cell.border = BORDER
    ajustar_colunas(ws)

def tela_dashboard():
    st.title("📊 Dashboard")
    st.markdown("---")

    rows = carregar_chamados()
    if not rows:
        st.info("Nenhum chamado registrado ainda.")
        return

    df = pd.DataFrame(rows, columns=[
        "protocolo","setor","empresa","tipo",
        "prioridade","status","aberto_em","atendido_em","resolvido_em","reaberturas"
    ])
    df["reaberturas"] = pd.to_numeric(df["reaberturas"], errors="coerce").fillna(0).astype(int)
    df["peso"] = 1 + df["reaberturas"]
    df["aberto_em"] = pd.to_datetime(df["aberto_em"])
    df["resolvido_em"] = pd.to_datetime(df["resolvido_em"])
    df["tempo_resolucao"] = (df["resolvido_em"] - df["aberto_em"]).dt.total_seconds() / 3600

    # Marca se o chamado é entregável (INFORMAR ENTREGÁVEIS, em qualquer parcial).
    df["eh_entregavel"] = df["tipo"].astype(str).str.startswith(PREFIXO_FECHAMENTO)

    # Período do chamado, lido do próprio protocolo (ROC-202608-0001 -> 202608).
    # O período é definido pela Contabilidade e não acompanha o mês do calendário:
    # um chamado aberto em setembro pode pertencer à competência de agosto.
    df["periodo"] = df["protocolo"].astype(str).str.extract(r"^ROC-(\d{6})-", expand=False)
    df["periodo"] = df["periodo"].fillna("—")

    # O seletor Tudo / Só inconsistências / Só entregáveis foi removido: o fluxo
    # INFORMAR ENTREGÁVEIS saiu do ROC e a entrega passou a ser feita por e-mail,
    # então o recorte deixou de ter uso. A coluna eh_entregavel continua existindo
    # para os registros históricos e para o cálculo da Performance por Setor.

    # === Filtros detalhados, recolhíveis (começam fechados) ===
    with st.expander("🔎 Filtros detalhados", expanded=False):
        c1, c2, c3 = st.columns(3)
        filtro_status = c1.multiselect("Status", df["status"].unique().tolist(), default=df["status"].unique().tolist())
        filtro_empresa = c2.multiselect("Empresa", df["empresa"].unique().tolist(), default=df["empresa"].unique().tolist())
        filtro_setor = c3.multiselect("Setor", df["setor"].unique().tolist(), default=df["setor"].unique().tolist())

        # Filtro de Tipo detalhado (entregáveis agrupados como 1 item). Começa tudo marcado.
        tipos_incons = sorted([t for t in df.loc[~df["eh_entregavel"], "tipo"].dropna().unique().tolist() if t])
        tem_entregaveis = bool(df["eh_entregavel"].any())
        opcoes_tipo = ([LABEL_ENTREGAVEIS] if tem_entregaveis else []) + tipos_incons
        filtro_tipo = st.multiselect(
            "Tipo (filtro detalhado — opcional)",
            opcoes_tipo, default=opcoes_tipo, key="dash_filtro_tipo")

        # Recorte do tempo: por DATA (intervalo no calendário) ou por PERÍODO
        # (a competência gravada no protocolo). Períodos são mais práticos no dia a
        # dia, porque um chamado aberto em setembro pode ser da competência de agosto.
        modo_tempo = st.radio("Recortar por", ["Período", "Data"], horizontal=True,
            key="dash_modo_tempo",
            help="Período usa a competência do protocolo. Data usa o calendário.")

        periodos_disp = sorted([p for p in df["periodo"].dropna().unique().tolist() if p and p != "—"],
                               reverse=True)
        if "—" in df["periodo"].values:
            periodos_disp = periodos_disp + ["—"]

        def rotulo_periodo(p):
            if p == "—":
                return "— (sem período no protocolo)"
            return f"{p[4:]}/{p[:4]}  ·  {p}"

        if modo_tempo == "Período" and periodos_disp:
            periodos_sel = st.multiselect("Período (competência)", periodos_disp,
                default=periodos_disp, format_func=rotulo_periodo, key="dash_periodos")
            mask_tempo = df["periodo"].isin(periodos_sel)
            # Mantidas para as seções que mostram intervalo de datas.
            data_ini = df["aberto_em"].min().date()
            data_fim = df["aberto_em"].max().date()
        else:
            d1, d2, d3 = st.columns(3)
            campo_label = d1.selectbox("Filtrar data por", ["Abertura", "Resolução"])
            col_data = "aberto_em" if campo_label == "Abertura" else "resolvido_em"
            data_min = df["aberto_em"].min().date()
            data_max = df["aberto_em"].max().date()
            data_ini = d2.date_input("De", value=data_min, key="dash_data_ini")
            data_fim = d3.date_input("Até", value=data_max, key="dash_data_fim")
            mask_tempo = df[col_data].dt.date.between(data_ini, data_fim)

    # Máscara do filtro de tipo detalhado (entregáveis agrupados).
    incons_sel = [t for t in filtro_tipo if t != LABEL_ENTREGAVEIS]
    inclui_entregaveis = LABEL_ENTREGAVEIS in filtro_tipo
    mask_tipo = df["tipo"].isin(incons_sel)
    if inclui_entregaveis:
        mask_tipo = mask_tipo | df["eh_entregavel"]

    df_f = df[
        df["status"].isin(filtro_status) &
        df["empresa"].isin(filtro_empresa) &
        df["setor"].isin(filtro_setor) &
        mask_tipo &
        mask_tempo
    ]

    # df_status é a base dos indicadores e do gráfico por status. Hoje é uma cópia
    # simples de df_f — o ajuste que forçava os entregáveis para "Resolvido" existia
    # apenas no modo "Só entregáveis", que deixou de existir.
    df_status = df_f.copy()

    st.markdown("---")
    st.markdown("#### 📈 Indicadores")
    k1, k2, k3, k4, k5, k6, k7 = st.columns(7)
    total = len(df_f)
    abertos = len(df_status[df_status["status"] == "Aberto"])
    em_andamento = len(df_status[df_status["status"] == "Em andamento"])
    pendentes = len(df_status[df_status["status"] == "Pendente"])
    resolvidos = len(df_status[df_status["status"] == "Resolvido"])
    retrabalho = int(df_f["reaberturas"].sum())
    tempo_medio = df_f[df_f["tempo_resolucao"].notna()]["tempo_resolucao"].mean()
    k1.metric("Total", total)
    k2.metric("🔴 Abertos", abertos)
    k3.metric("🟡 Em andamento", em_andamento)
    k4.metric("🟠 Pendentes", pendentes,
              help="Houve retorno do setor, mas o assunto não foi finalizado: ficou uma "
                   "pendência. O chamado precisa ser retomado pela Abertura de pendência.")
    k5.metric("🟢 Resolvidos", resolvidos)
    k6.metric("🔄 Retrabalho", retrabalho,
              help="Quantas vezes chamados voltaram para Em andamento no período — "
                   "somando reaberturas e aberturas de pendência.")
    k7.metric("⏱️ Tempo médio", f"{tempo_medio:.1f}h" if not pd.isna(tempo_medio) else "—")

    st.markdown("---")
    if df_f.empty:
        st.info("Sem dados para os filtros selecionados.")
    else:
        ca, cb = st.columns(2)
        with ca:
            st.markdown("##### Chamados por Tipo")
            st.caption(NOTA_PESO)
            df_t = df_f.groupby("tipo")["peso"].sum().reset_index(name="qtd").sort_values("qtd", ascending=False)
            fig1 = px.bar(df_t, x="qtd", y="tipo", orientation="h", color="qtd", color_continuous_scale="Blues", labels={"qtd":"Qtd","tipo":""})
            fig1.update_layout(showlegend=False, coloraxis_showscale=False, margin=dict(l=0,r=0,t=0,b=0), height=300)
            st.plotly_chart(fig1, use_container_width=True)
        with cb:
            st.markdown("##### Chamados por Setor")
            st.caption(NOTA_PESO)
            df_s = df_f.groupby("setor")["peso"].sum().reset_index(name="qtd").sort_values("qtd", ascending=False)
            fig2 = px.bar(df_s, x="qtd", y="setor", orientation="h", color="qtd", color_continuous_scale="Greens", labels={"qtd":"Qtd","setor":""})
            fig2.update_layout(showlegend=False, coloraxis_showscale=False, margin=dict(l=0,r=0,t=0,b=0), height=300)
            st.plotly_chart(fig2, use_container_width=True)

    # === Performance por Setor (régua de erros) ===
    st.markdown("##### 🎯 Performance por Setor")
    st.caption("Baseada na quantidade de chamados (erros) por setor. Chamados retomados contam como 2 "
               "(retrabalho), seja por reabertura ou por abertura de pendência. "
               "Fechamentos de período não entram na contagem.")
    df_perf = montar_performance(df_f)
    if df_perf.empty:
        st.info("Sem chamados para classificar no período selecionado.")
    else:
        st.markdown(tabela_performance_html(df_perf), unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("##### 🍕 Tipos de chamado por Setor")
    setores_unicos = sorted([s for s in df_f["setor"].dropna().unique().tolist() if s])
    if not setores_unicos:
        st.info("Sem dados para o período selecionado.")
    else:
        n_cols = 2
        for inicio in range(0, len(setores_unicos), n_cols):
            grupo = setores_unicos[inicio:inicio+n_cols]
            cols = st.columns(n_cols)
            for j, setor in enumerate(grupo):
                with cols[j]:
                    try:
                        df_pie = df_f[df_f["setor"] == setor].groupby("tipo").size().reset_index(name="qtd")
                        if df_pie.empty:
                            continue
                        fig = px.pie(df_pie, names="tipo", values="qtd")
                        fig.update_traces(textposition="inside", textinfo="percent")
                        fig.update_layout(
                            title=dict(text=setor, font=dict(size=14, color="#041747")),
                            margin=dict(l=0, r=0, t=40, b=0), height=320,
                            legend=dict(orientation="h", y=-0.1, font=dict(size=9))
                        )
                        st.plotly_chart(fig, use_container_width=True, key=f"pie_setor_{inicio+j}")
                    except Exception:
                        st.caption(f"Sem dados para {setor}.")

    st.markdown("---")
    st.markdown("##### 📈 Evolução Mensal")
    if df_f.empty:
        st.info("Sem dados para o período selecionado.")
    else:
        df_evo = df_f.copy()
        df_evo["mes"] = df_evo["aberto_em"].dt.to_period("M").astype(str)
        df_m = df_evo.groupby("mes").size().reset_index(name="qtd").sort_values("mes")
        fig5 = px.line(df_m, x="mes", y="qtd", markers=True, labels={"mes":"Mês","qtd":"Chamados"})
        fig5.update_layout(margin=dict(l=0,r=0,t=0,b=0), height=250)
        st.plotly_chart(fig5, use_container_width=True)

    # === Registro de entregas de fechamento de período ===
    st.markdown("---")
    st.markdown("##### 🗂️ Entregas de Fechamento de Período")
    st.caption("Respeita o recorte de tempo e os setores selecionados nos filtros.")
    df_entregas = df[
        df["setor"].isin(filtro_setor) &
        mask_tempo &
        df["tipo"].astype(str).str.startswith(PREFIXO_FECHAMENTO)
    ].copy()

    if df_entregas.empty:
        st.info("Nenhuma entrega de fechamento de período no período/setores selecionados.")
    else:
        df_entregas["Período"] = (
            df_entregas["tipo"].astype(str)
            .str.replace(f"{PREFIXO_FECHAMENTO} - ", "", regex=False)
            .str.replace(PREFIXO_FECHAMENTO, "—", regex=False)
        )
        df_entregas["Data/Hora"] = df_entregas["aberto_em"].dt.strftime("%d/%m/%Y %H:%M")
        tabela_entregas = (
            df_entregas[["setor","Período","Data/Hora","protocolo"]]
            .rename(columns={"setor":"Setor","protocolo":"Protocolo"})
            .sort_values("Data/Hora", ascending=False)
        )
        st.dataframe(tabela_entregas, use_container_width=True, hide_index=True)
        st.caption(f"Total de entregas: {len(tabela_entregas)}")

    # === Consolidado de notificações por protocolo (com filtro de tipo) ===
    st.markdown("---")
    st.markdown("##### 🔔 Notificações por Protocolo")
    st.caption("Notificações enviadas, agrupadas por protocolo. Use o filtro para ver só um tipo (ex: mensagens trocadas por e-mail).")
    notifs_raw = carregar_notificacoes_raw()
    if not notifs_raw:
        st.info("Nenhuma notificação registrada ainda.")
    else:
        dfn = pd.DataFrame(notifs_raw, columns=["protocolo", "tipo", "enviado_em"])
        dfn = dfn[dfn["tipo"] != "alerta_sla"]
        dfn["protocolo"] = dfn["protocolo"].replace("", None)
        dfn["protocolo"] = dfn["protocolo"].fillna("(sem protocolo)")

        tipos_presentes = sorted([t for t in dfn["tipo"].dropna().unique().tolist()])
        opcoes_label = ["Todas"] + [LABELS_NOTIF.get(t, t) for t in tipos_presentes]
        label_para_tipo = {LABELS_NOTIF.get(t, t): t for t in tipos_presentes}

        filtro_notif = st.selectbox("Filtrar por tipo de notificação", opcoes_label, key="filtro_notif_tipo")
        if filtro_notif != "Todas":
            dfn = dfn[dfn["tipo"] == label_para_tipo.get(filtro_notif, filtro_notif)]

        if dfn.empty:
            st.info("Nenhuma notificação desse tipo.")
        else:
            dfn["_evt"] = dfn["tipo"].astype(str) + "|" + dfn["enviado_em"].astype(str).str.slice(0, 16)
            cons = dfn.groupby("protocolo").agg(
                total=("_evt", "nunique"),
                ultima=("enviado_em", "max")
            ).reset_index().sort_values(["total", "ultima"], ascending=[False, False])
            try:
                cons["ultima"] = pd.to_datetime(cons["ultima"]).dt.strftime("%d/%m/%Y %H:%M")
            except:
                pass
            df_notif = cons.rename(columns={
                "protocolo": "Protocolo",
                "total": "Total de Notificações",
                "ultima": "Última Notificação"
            })
            st.dataframe(df_notif, use_container_width=True, hide_index=True)
            st.caption(f"Protocolos: {len(df_notif)} · Total geral: {int(df_notif['Total de Notificações'].sum())}")

    st.markdown("---")
    st.markdown("##### 📥 Exportar dados")
    st.caption("A planilha respeita os filtros da tela e inclui as abas Chamados (com a coluna "
               "Período), Mensagens (histórico completo do chat), Dashboard, Performance e "
               "Notificações.")
    # A aba "Chamados" respeita os filtros da tela: exporta apenas os chamados que
    # estão em df_f (mesmos filtros de status, empresa, setor, tipo e data).
    protocolos_filtrados = set(df_f["protocolo"].tolist())
    todos = carregar_chamados_completo()
    todos_filtrados = [linha for linha in (todos or []) if linha[0] in protocolos_filtrados]
    df_export = pd.DataFrame(todos_filtrados, columns=[
        "Protocolo","Setor","Empresa","Abertura de Período / Descontabilização",
        "Prioridade","NF Retorna","Parceiro","Número Nota",
        "Tipo Nota","Data Entrada","Data Saída","Data Negociação",
        "Valor","Observação","Status","Aberto Em","Atendido Em",
        "Resolvido Em","Resolução"
    ])

    # Total de notificações por protocolo (1 por movimentação: agrupa cópias do
    # mesmo evento = protocolo + tipo + minuto), para virar coluna na aba Chamados.
    mapa_notif = {}
    if notifs_raw:
        dfc = pd.DataFrame(notifs_raw, columns=["protocolo", "tipo", "enviado_em"])
        dfc = dfc[dfc["tipo"] != "alerta_sla"]
        dfc = dfc[dfc["protocolo"].notna() & (dfc["protocolo"] != "")]
        dfc["_evt"] = (dfc["protocolo"].astype(str) + "|" + dfc["tipo"].astype(str)
                       + "|" + dfc["enviado_em"].astype(str).str.slice(0, 16))
        contagem = dfc.groupby("protocolo")["_evt"].nunique()
        mapa_notif = contagem.to_dict()
    # Período (competência) lido do protocolo, logo depois da coluna Protocolo —
    # é por ele que a Contabilidade organiza o controle, não pelo mês do calendário.
    df_export["Período"] = (df_export["Protocolo"].astype(str)
                            .str.extract(r"^ROC-(\d{6})-", expand=False).fillna("—"))
    colunas = ["Protocolo", "Período"] + [c for c in df_export.columns
                                          if c not in ("Protocolo", "Período")]
    df_export = df_export[colunas]

    df_export["Notificações"] = df_export["Protocolo"].map(lambda p: int(mapa_notif.get(p, 0)))

    # === Aba Mensagens: histórico COMPLETO do chat dos chamados filtrados ===
    # Antes a exportação não trazia mensagem nenhuma — só a contagem de
    # notificações e a data da última. Agora vai a conversa inteira, uma linha
    # por mensagem, na ordem em que foi enviada.
    msgs_raw = carregar_mensagens_todas() or []
    msgs_filtradas = [m for m in msgs_raw if m[0] in protocolos_filtrados]
    df_msgs = pd.DataFrame(msgs_filtradas, columns=[
        "Protocolo", "Data/Hora", "Autor", "Perfil", "Mensagem", "Anexo"])
    if not df_msgs.empty:
        try:
            df_msgs["Data/Hora"] = pd.to_datetime(df_msgs["Data/Hora"]).dt.strftime("%d/%m/%Y %H:%M")
        except:
            pass
        df_msgs["Anexo"] = df_msgs["Anexo"].fillna("")
        df_msgs["Mensagem"] = df_msgs["Mensagem"].fillna("")
    # Quantidade de mensagens por chamado, como coluna na aba Chamados.
    contagem_msgs = {}
    for m in msgs_filtradas:
        contagem_msgs[m[0]] = contagem_msgs.get(m[0], 0) + 1
    df_export["Mensagens"] = df_export["Protocolo"].map(lambda p: int(contagem_msgs.get(p, 0)))
    # Deixa a coluna "Resolução" por último (Notificações vem antes dela).
    if "Resolução" in df_export.columns:
        colunas = [c for c in df_export.columns if c != "Resolução"] + ["Resolução"]
        df_export = df_export[colunas]
    # KPIs da planilha: os MESMOS da tela, na mesma ordem (antes faltavam
    # Pendentes e Retrabalho, o que fazia a planilha divergir do dashboard).
    df_kpi = pd.DataFrame({
        "Indicador": ["Total","Abertos","Em Andamento","Pendentes","Resolvidos",
                      "Retrabalho","Tempo Médio (h)"],
        "Valor": [total, abertos, em_andamento, pendentes, resolvidos, retrabalho,
                  f"{tempo_medio:.1f}" if not pd.isna(tempo_medio) else "—"]
    })
    df_te = df_f.groupby("tipo").size().reset_index(name="Quantidade").sort_values("Quantidade",ascending=False).rename(columns={"tipo":"Tipo"})
    df_se = df_f.groupby("setor").size().reset_index(name="Quantidade").sort_values("Quantidade",ascending=False).rename(columns={"setor":"Setor"})
    df_ee = df_f.groupby("empresa").size().reset_index(name="Quantidade").rename(columns={"empresa":"Empresa"})
    df_ste = df_status.groupby("status").size().reset_index(name="Quantidade").rename(columns={"status":"Status"})
    df_pe = (df_f.groupby("periodo").size().reset_index(name="Quantidade")
             .sort_values("periodo", ascending=False).rename(columns={"periodo":"Período"}))

    df_notif_total = None
    df_notif_tipo = None
    if notifs_raw:
        dft = pd.DataFrame(notifs_raw, columns=["protocolo", "tipo", "enviado_em"])
        dft = dft[dft["tipo"] != "alerta_sla"]
        dft["protocolo"] = dft["protocolo"].replace("", None).fillna("(sem protocolo)")
        dft["tipo_label"] = dft["tipo"].map(lambda t: LABELS_NOTIF.get(t, t) if t else "—")
        dft["_evt"] = dft["protocolo"].astype(str) + "|" + dft["tipo"].astype(str) + "|" + dft["enviado_em"].astype(str).str.slice(0, 16)
        dft_evt = dft.drop_duplicates(subset="_evt")
        df_notif_total = (
            dft_evt.groupby("protocolo")
            .agg(total=("tipo", "size"), ultima=("enviado_em", "max"))
            .reset_index()
            .rename(columns={"protocolo": "Protocolo", "total": "Total de Notificações", "ultima": "Última Notificação"})
            .sort_values("Total de Notificações", ascending=False)
        )
        try:
            df_notif_total["Última Notificação"] = pd.to_datetime(df_notif_total["Última Notificação"]).dt.strftime("%d/%m/%Y %H:%M")
        except:
            pass
        piv = dft_evt.pivot_table(index="protocolo", columns="tipo_label",
                              values="enviado_em", aggfunc="count", fill_value=0).reset_index()
        piv = piv.rename(columns={"protocolo": "Protocolo"})
        cols_tipos = [c for c in piv.columns if c != "Protocolo"]
        piv["Total"] = piv[cols_tipos].sum(axis=1)
        df_notif_tipo = piv.sort_values("Total", ascending=False)

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df_export.to_excel(writer, index=False, sheet_name="Chamados", startrow=6)
        ws1 = writer.sheets["Chamados"]
        inserir_cabecalho_relatorio(ws1, "ROC — Registro de Ocorrências Contábeis")
        estilo_cabecalho(ws1, 7, len(df_export.columns))
        estilo_dados(ws1, 8, 7+len(df_export), len(df_export.columns))
        ws1.row_dimensions[7].height = 30
        ajustar_colunas(ws1)
        ws1.freeze_panes = "A8"

        ws2 = writer.book.create_sheet("Dashboard")
        writer.sheets["Dashboard"] = ws2
        inserir_cabecalho_relatorio(ws2, "ROC — Dashboard Operacional")
        secoes = [("📊 KPIs",df_kpi,"041747",False),("🗓️ Por Período",df_pe,"041747",True),
                  ("📌 Por Tipo",df_te,"041747",True),
                  ("🏢 Por Setor",df_se,"0F8C3B",True),("🏭 Por Empresa",df_ee,"0071FE",True),
                  ("🔘 Por Status",df_ste,"FAC318",True)]
        linha = 6
        for titulo, df_sec, cor_hex, usa_alt in secoes:
            ws2.cell(row=linha,column=1,value=titulo).font = Font(name="Calibri",bold=True,size=12,color="041747")
            ws2.cell(row=linha,column=1).fill = PatternFill("solid",fgColor="F0F4FF")
            ws2.row_dimensions[linha].height = 22
            linha += 1
            df_sec.to_excel(writer, index=False, sheet_name="Dashboard", startrow=linha-1)
            font_cor = "041747" if cor_hex == "FAC318" else "FFFFFF"
            for col_num in range(1, len(df_sec.columns)+1):
                cell = ws2.cell(row=linha, column=col_num)
                cell.fill = PatternFill("solid", fgColor=cor_hex)
                cell.font = Font(name="Calibri", bold=True, color=font_cor, size=11)
                cell.alignment = HEADER_ALIGN
                cell.border = BORDER
            ws2.row_dimensions[linha].height = 25
            for r in range(linha+1, linha+len(df_sec)+1):
                alt = ALT_FILL if (r%2==0 and usa_alt) else PatternFill("solid",fgColor="FFFFFF")
                for col_num in range(1, len(df_sec.columns)+1):
                    cell = ws2.cell(row=r, column=col_num)
                    cell.font = DATA_FONT
                    cell.alignment = Alignment(horizontal="center",vertical="center")
                    cell.fill = alt
                    cell.border = BORDER
            linha += len(df_sec) + 3
        ajustar_colunas(ws2)

        if not df_perf.empty:
            escrever_aba_performance(writer, df_perf)

        if not df_msgs.empty:
            escrever_aba_tabela(writer, "Mensagens", "ROC — Histórico de Mensagens",
                                df_msgs, alinhar="left")

        if df_notif_total is not None and not df_notif_total.empty:
            escrever_aba_tabela(writer, "Notificações", "ROC — Notificações por Protocolo", df_notif_total)
        if df_notif_tipo is not None and not df_notif_tipo.empty:
            escrever_aba_tabela(writer, "Notif. por Tipo", "ROC — Notificações por Tipo", df_notif_tipo)

    buffer.seek(0)
    st.download_button(
        label="📥 Baixar Excel completo",
        data=buffer,
        file_name=f"ROC_{datetime.now(BRASILIA).strftime('%Y%m%d_%H%M')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )
