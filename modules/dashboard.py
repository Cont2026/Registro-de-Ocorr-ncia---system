import streamlit as st
import pandas as pd
import plotly.express as px
import io
from database.connection import get_conn
from datetime import datetime
from zoneinfo import ZoneInfo

BRASILIA = ZoneInfo("America/Sao_Paulo")

def tela_dashboard():
    st.title("📊 Dashboard")
    st.markdown("---")

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT protocolo, setor, empresa, tipo_inconsistencia, motivo,
               prioridade, status, aberto_em, atendido_em, resolvido_em
        FROM chamados
        ORDER BY aberto_em DESC
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    if not rows:
        st.info("Nenhum chamado registrado ainda.")
        return

    df = pd.DataFrame(rows, columns=[
        "protocolo", "setor", "empresa", "tipo", "motivo",
        "prioridade", "status", "aberto_em", "atendido_em", "resolvido_em"
    ])

    df["aberto_em"] = pd.to_datetime(df["aberto_em"])
    df["resolvido_em"] = pd.to_datetime(df["resolvido_em"])
    df["tempo_resolucao"] = (df["resolvido_em"] - df["aberto_em"]).dt.total_seconds() / 3600

    # =============================================
    # FILTROS
    # =============================================
    st.markdown("#### 🔎 Filtros")
    col1, col2, col3 = st.columns(3)
    with col1:
        filtro_status = st.multiselect("Status", df["status"].unique().tolist(), default=df["status"].unique().tolist())
    with col2:
        filtro_empresa = st.multiselect("Empresa", df["empresa"].unique().tolist(), default=df["empresa"].unique().tolist())
    with col3:
        filtro_setor = st.multiselect("Setor", df["setor"].unique().tolist(), default=df["setor"].unique().tolist())

    df_f = df[
        df["status"].isin(filtro_status) &
        df["empresa"].isin(filtro_empresa) &
        df["setor"].isin(filtro_setor)
    ]

    st.markdown("---")

    # =============================================
    # KPIs
    # =============================================
    st.markdown("#### 📈 Indicadores")
    k1, k2, k3, k4, k5 = st.columns(5)

    total = len(df_f)
    abertos = len(df_f[df_f["status"] == "Aberto"])
    em_andamento = len(df_f[df_f["status"] == "Em andamento"])
    resolvidos = len(df_f[df_f["status"] == "Resolvido"])
    tempo_medio = df_f[df_f["tempo_resolucao"].notna()]["tempo_resolucao"].mean()

    k1.metric("Total", total)
    k2.metric("🔴 Abertos", abertos)
    k3.metric("🟡 Em andamento", em_andamento)
    k4.metric("🟢 Resolvidos", resolvidos)
    k5.metric("⏱️ Tempo médio", f"{tempo_medio:.1f}h" if not pd.isna(tempo_medio) else "—")

    st.markdown("---")

    # =============================================
    # GRÁFICOS
    # =============================================
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("##### Chamados por Tipo")
        df_tipo = df_f.groupby("tipo").size().reset_index(name="qtd").sort_values("qtd", ascending=False)
        fig1 = px.bar(df_tipo, x="qtd", y="tipo", orientation="h",
                      color="qtd", color_continuous_scale="Blues",
                      labels={"qtd": "Qtd", "tipo": ""})
        fig1.update_layout(showlegend=False, coloraxis_showscale=False,
                           margin=dict(l=0, r=0, t=0, b=0), height=300)
        st.plotly_chart(fig1, use_container_width=True)

    with col_b:
        st.markdown("##### Chamados por Setor")
        df_setor = df_f.groupby("setor").size().reset_index(name="qtd").sort_values("qtd", ascending=False)
        fig2 = px.bar(df_setor, x="qtd", y="setor", orientation="h",
                      color="qtd", color_continuous_scale="Greens",
                      labels={"qtd": "Qtd", "setor": ""})
        fig2.update_layout(showlegend=False, coloraxis_showscale=False,
                           margin=dict(l=0, r=0, t=0, b=0), height=300)
        st.plotly_chart(fig2, use_container_width=True)

    col_c, col_d = st.columns(2)

    with col_c:
        st.markdown("##### Chamados por Empresa")
        df_emp = df_f.groupby("empresa").size().reset_index(name="qtd")
        fig3 = px.pie(df_emp, names="empresa", values="qtd",
                      color_discrete_sequence=px.colors.sequential.Blues_r)
        fig3.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=300)
        st.plotly_chart(fig3, use_container_width=True)

    with col_d:
        st.markdown("##### Chamados por Status")
        df_status = df_f.groupby("status").size().reset_index(name="qtd")
        cores = {"Aberto": "#ef4444", "Em andamento": "#f59e0b",
                 "Resolvido": "#22c55e", "Cancelado": "#6b7280"}
        fig4 = px.pie(df_status, names="status", values="qtd",
                      color="status", color_discrete_map=cores)
        fig4.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=300)
        st.plotly_chart(fig4, use_container_width=True)

    st.markdown("---")

    st.markdown("##### Evolução Mensal de Chamados")
    df_f["mes"] = df_f["aberto_em"].dt.to_period("M").astype(str)
    df_mes = df_f.groupby("mes").size().reset_index(name="qtd").sort_values("mes")
    fig5 = px.line(df_mes, x="mes", y="qtd", markers=True,
                   labels={"mes": "Mês", "qtd": "Chamados"})
    fig5.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=250)
    st.plotly_chart(fig5, use_container_width=True)

    st.markdown("---")

    # =============================================
    # EXPORTAÇÃO EXCEL — 2 ABAS
    # =============================================
    st.markdown("##### 📥 Exportar dados")

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT protocolo, setor, empresa, tipo_inconsistencia, motivo,
               prioridade, nf_retorna, nome_parceiro, numero_nota,
               tipo_nota, data_entrada, data_saida, data_negociacao,
               valor, observacao, status, aberto_em, atendido_em,
               resolvido_em, resolucao
        FROM chamados ORDER BY aberto_em DESC
    """)
    todos = cur.fetchall()
    cur.close()
    conn.close()

    df_export = pd.DataFrame(todos, columns=[
        "Protocolo", "Setor", "Empresa", "Tipo Inconsistência", "Motivo",
        "Prioridade", "NF Retorna", "Parceiro", "Número Nota",
        "Tipo Nota", "Data Entrada", "Data Saída", "Data Negociação",
        "Valor", "Observação", "Status", "Aberto Em", "Atendido Em",
        "Resolvido Em", "Resolução"
    ])

    df_kpi = pd.DataFrame({
        "Indicador": ["Total de Chamados", "Abertos", "Em Andamento", "Resolvidos", "Tempo Médio (h)"],
        "Valor": [total, abertos, em_andamento, resolvidos,
                  f"{tempo_medio:.1f}" if not pd.isna(tempo_medio) else "—"]
    })

    df_tipo_exp = df_f.groupby("tipo").size().reset_index(name="Quantidade").sort_values("Quantidade", ascending=False).rename(columns={"tipo": "Tipo de Inconsistência"})
    df_setor_exp = df_f.groupby("setor").size().reset_index(name="Quantidade").sort_values("Quantidade", ascending=False).rename(columns={"setor": "Setor"})
    df_empresa_exp = df_f.groupby("empresa").size().reset_index(name="Quantidade").rename(columns={"empresa": "Empresa"})
    df_status_exp = df_f.groupby("status").size().reset_index(name="Quantidade").rename(columns={"status": "Status"})

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        # Aba 1 — Chamados
        df_export.to_excel(writer, index=False, sheet_name="Chamados")

        # Aba 2 — Dashboard
        ws = writer.book.create_sheet("Dashboard")
        writer.sheets["Dashboard"] = ws

        linha = 0
        df_kpi.to_excel(writer, index=False, sheet_name="Dashboard", startrow=linha)
        linha += len(df_kpi) + 3

        ws.cell(row=linha + 1, column=1, value="Por Tipo de Inconsistência")
        linha += 1
        df_tipo_exp.to_excel(writer, index=False, sheet_name="Dashboard", startrow=linha)
        linha += len(df_tipo_exp) + 3

        ws.cell(row=linha + 1, column=1, value="Por Setor")
        linha += 1
        df_setor_exp.to_excel(writer, index=False, sheet_name="Dashboard", startrow=linha)
        linha += len(df_setor_exp) + 3

        ws.cell(row=linha + 1, column=1, value="Por Empresa")
        linha += 1
        df_empresa_exp.to_excel(writer, index=False, sheet_name="Dashboard", startrow=linha)
        linha += len(df_empresa_exp) + 3

        ws.cell(row=linha + 1, column=1, value="Por Status")
        linha += 1
        df_status_exp.to_excel(writer, index=False, sheet_name="Dashboard", startrow=linha)

    buffer.seek(0)

    st.download_button(
        label="📥 Baixar Excel completo",
        data=buffer,
        file_name=f"RO_chamados_{datetime.now(BRASILIA).strftime('%Y%m%d_%H%M')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )
