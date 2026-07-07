import streamlit as st
import base64
from database.connection import run_query
from datetime import datetime
from zoneinfo import ZoneInfo
from modules.email_service import enviar_email, email_novo_chamado, email_setor_em_copia
from modules.chamados import empacotar_anexos, desempacotar_anexos, anexos_para_email

BRASILIA = ZoneInfo("America/Sao_Paulo")
TIPO_FOLHA = "Folha de Pagamento"
TIPO_FECHAMENTO = "INFORMAR ENTREGÁVEIS"
TIPO_CONTA70 = "Divergência na conta 70"

def buscar_setores():
    rows = run_query(
        "SELECT nome, email, setor_nome FROM usuarios WHERE perfil='setor' AND ativo=1 ORDER BY nome",
        fetch=True)
    return rows if rows else []

@st.cache_data(ttl=120)
def carregar_vinculos_trat():
    rows = run_query("SELECT inconsistencia, movimentacao FROM vinculo_inconsistencia_movimentacao", fetch=True)
    mapa = {}
    com_vinculo = set()
    if rows:
        for inc, mov in rows:
            mapa.setdefault(mov, set()).add(inc)
            com_vinculo.add(inc)
    return mapa, com_vinculo

def filtrar_inconsistencias_trat(tipos_lista, tipo_mov):
    mapa, com_vinculo = carregar_vinculos_trat()
    vinc_do_tipo = mapa.get(tipo_mov, set())
    return [inc for inc in tipos_lista if (inc in vinc_do_tipo) or (inc not in com_vinculo)]

def _valor_float(v):
    v = (v or "").strip() if isinstance(v, str) else v
    if not v:
        return None
    try:
        return float(str(v).replace(".", "").replace(",", "."))
    except:
        try:
            return float(v)
        except:
            return None

def fmt_data(valor, com_hora=True):
    """Formata data/datetime para o padrão brasileiro dd/mm/aaaa."""
    if valor is None or valor == "":
        return "—"
    if hasattr(valor, "strftime"):
        try:
            tem_hora = getattr(valor, "hour", 0) or getattr(valor, "minute", 0)
            return valor.strftime("%d/%m/%Y %H:%M") if (com_hora and tem_hora) else valor.strftime("%d/%m/%Y")
        except:
            pass
    s = str(valor).strip()
    for fmt_in, com_h in [("%Y-%m-%d %H:%M:%S", True), ("%Y-%m-%d %H:%M", True), ("%Y-%m-%d", False)]:
        try:
            d = datetime.strptime(s, fmt_in)
            return d.strftime("%d/%m/%Y %H:%M") if (com_h and com_hora) else d.strftime("%d/%m/%Y")
        except:
            continue
    return s

def gerar_protocolo():
    """Gera o próximo protocolo do mês no formato ROC-AAAAMM-XXXX.
    Em vez de contar todos os chamados (COUNT+1, que colide depois de exclusões),
    pega o MAIOR número já usado no mês atual e soma 1. Reinicia a cada mês e
    nunca colide, mesmo que chamados tenham sido apagados."""
    prefixo = f"ROC-{datetime.now(BRASILIA).strftime('%Y%m')}-"
    try:
        r = run_query(
            "SELECT MAX(CAST(SUBSTRING(protocolo FROM %s) AS INTEGER)) "
            "FROM chamados WHERE protocolo LIKE %s",
            (len(prefixo) + 1, prefixo + "%"), fetch=True)
        ultimo = r[0][0] if r and r[0] and r[0][0] is not None else 0
    except:
        ultimo = 0
    return f"{prefixo}{str(ultimo + 1).zfill(4)}"

def salvar_copia(protocolo, setor):
    try:
        run_query("INSERT INTO chamados_copia (protocolo, setor) VALUES (%s,%s)", (protocolo, setor))
    except:
        pass

def criar_chamado_tratativa(setor_destino, empresa, tipo_inconsistencia, tipo_nota,
                            nome_parceiro, numero_nota, valor, observacao,
                            nu_financeiro, nu_nota, arquivos, solicitante,
                            prioridade="Normal", nf_retorna="", financeiro_baixado="",
                            data_entrada=None, data_negociacao=None, atrasos=""):
    """Cria o chamado direto no setor responsavel, ja em 'Em andamento' (aberto pela Contabilidade)."""
    protocolo = gerar_protocolo()
    anexo_dados, anexo_nome = empacotar_anexos(arquivos)
    valor_num = _valor_float(valor)
    if valor_num is None:
        valor_num = 0

    run_query("""INSERT INTO chamados (protocolo,setor,empresa,tipo_inconsistencia,prioridade,nf_retorna,
        solicitante,nome_parceiro,numero_nota,tipo_nota,data_entrada,data_saida,data_negociacao,
        valor,observacao,arquivo_nome,status,aberto_em,financeiro_baixado,anexo_dados,
        num_unico_financeiro,num_unico_nota,atrasos_entregaveis)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (protocolo, setor_destino, empresa or "", tipo_inconsistencia, prioridade or "Normal", nf_retorna or "",
         solicitante, (nome_parceiro or "").strip(), (numero_nota or "").strip(), tipo_nota or "",
         data_entrada or None, None, data_negociacao or None,
         valor_num, (observacao or "").strip(), anexo_nome, "Em andamento",
         datetime.now(BRASILIA).strftime("%Y-%m-%d %H:%M:%S"), financeiro_baixado or "", anexo_dados,
         (nu_financeiro or "").strip() or None, (nu_nota or "").strip() or None,
         (atrasos or "").strip() or None))

    # Log para a lista "Chamados abertos pela Contabilidade"
    try:
        run_query("""INSERT INTO solicitacoes_tratativa
            (setor_destino, empresa, tipo_inconsistencia, nome_parceiro, numero_nota,
            tipo_nota, valor, observacao, criado_por, criado_em, status, num_unico_financeiro, num_unico_nota)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (setor_destino, empresa or "", tipo_inconsistencia, (nome_parceiro or "").strip(),
             (numero_nota or "").strip(), tipo_nota or "", (valor or "").strip(),
             (observacao or "").strip(), solicitante,
             datetime.now(BRASILIA).strftime("%Y-%m-%d %H:%M:%S"), "Em andamento",
             (nu_financeiro or "").strip() or None, (nu_nota or "").strip() or None))
    except:
        pass

    return protocolo

def abrir_chamados_para_setores(setores_sel, copia_nomes, mapa_email, *,
        empresa, tipo_inconsistencia, tipo_nota,
        nome_parceiro="", numero_nota="", valor="", observacao="",
        nu_financeiro="", nu_nota="", arquivos=None, solicitante="",
        prioridade="Normal", nf_retorna="", financeiro_baixado="",
        data_entrada=None, data_negociacao=None, atrasos=""):
    """Cria um chamado INDEPENDENTE para CADA setor selecionado (mesmo conteúdo).
    Notifica cada setor e aplica os setores em cópia — ignorando, em cada chamado,
    o setor que já é o responsável dele (evita duplicar). Retorna [(setor, protocolo)]."""
    anexos_email = anexos_para_email(desempacotar_anexos(*empacotar_anexos(arquivos)))
    criados = []
    for s in setores_sel:
        setor_nome = s[0]
        email_setor = s[1]
        protocolo = criar_chamado_tratativa(setor_nome, empresa, tipo_inconsistencia, tipo_nota,
            nome_parceiro, numero_nota, valor, observacao,
            nu_financeiro, nu_nota, arquivos, solicitante,
            prioridade=prioridade, nf_retorna=nf_retorna, financeiro_baixado=financeiro_baixado,
            data_entrada=data_entrada, data_negociacao=data_negociacao, atrasos=atrasos)
        try:
            if email_setor:
                email_novo_chamado(email_setor, protocolo, setor_nome, tipo_inconsistencia,
                    prioridade or "Normal", (nome_parceiro or "").strip(), (numero_nota or "").strip(),
                    solicitante, anexos=anexos_email,
                    nu_financeiro=(nu_financeiro or "").strip(), nu_nota=(nu_nota or "").strip(),
                    atrasos=(atrasos or "").strip())
        except:
            pass
        # Setores em cópia: ignora o que já é responsável deste chamado.
        for n in copia_nomes:
            if n == setor_nome:
                continue
            em = mapa_email.get(n)
            if em and em != email_setor:
                try:
                    salvar_copia(protocolo, n)
                    email_setor_em_copia(em, protocolo, n, setor_nome)
                except:
                    pass
        criados.append((setor_nome, protocolo))
    return criados

def tela_tratativa():
    st.title("📤 Abertura de Chamado pela Contabilidade")
    st.markdown("A Contabilidade abre o chamado **direto para o setor responsável** — ele aparece em "
                "**Minhas Solicitações** do setor, já em andamento.")
    st.markdown("---")

    setores = buscar_setores()
    if not setores:
        st.warning("Nenhum setor cadastrado com e-mail. Cadastre os setores primeiro.")
        return

    opcoes_setores = {f"{s[0]} ({s[1] or 'sem e-mail'})": s for s in setores}
    mapa_email = {s[0]: s[1] for s in setores}

    tipos = run_query("SELECT nome FROM tipos_inconsistencia WHERE ativo=1 ORDER BY nome", fetch=True)
    tipos_lista = [t[0] for t in tipos] if tipos else []

    st.markdown("#### 📧 Setores Responsáveis * (pode marcar mais de um)")
    st.caption("Se marcar vários, será criado um chamado independente para cada setor (mesmo conteúdo).")
    setores_sel_keys = st.multiselect("Selecione o(s) setor(es)", list(opcoes_setores.keys()),
        label_visibility="collapsed")
    setores_sel = [opcoes_setores[k] for k in setores_sel_keys]
    nomes_resp = [s[0] for s in setores_sel]
    nomes_copia = [s[0] for s in setores if s[1] and s[0] not in nomes_resp]

    st.markdown("---")
    st.markdown("#### 🗂️ Tipo de Movimentacao")
    tipos_nota_rows = run_query("SELECT nome FROM tipos_nota WHERE ativo=1 ORDER BY nome", fetch=True)
    tipos_movimentacao = [t[0] for t in tipos_nota_rows] if tipos_nota_rows else []
    if "INFORMAR ENTREGÁVEIS" in tipos_movimentacao:
        tipos_movimentacao.remove("INFORMAR ENTREGÁVEIS")
        tipos_movimentacao.insert(0, "INFORMAR ENTREGÁVEIS")
    if TIPO_FOLHA in tipos_movimentacao:
        tipos_movimentacao.remove(TIPO_FOLHA)
        tipos_movimentacao.append(TIPO_FOLHA)
    tipo_nota = st.session_state.get("trat_tipo_nota", None)
    if not tipos_movimentacao:
        st.warning("⚠️ Nenhum tipo de movimentacao cadastrado. Cadastre no painel Admin.")
        return
    cols_nota = st.columns(min(len(tipos_movimentacao), 4))
    for i, op in enumerate(tipos_movimentacao):
        with cols_nota[i % len(cols_nota)]:
            ativo = tipo_nota == op
            if st.button(f"{'✓ ' if ativo else ''}{op}", key=f"trat_nota_{i}",
                use_container_width=True, type="primary" if ativo else "secondary"):
                st.session_state["trat_tipo_nota"] = op
                st.rerun()
    tipo_nota = st.session_state.get("trat_tipo_nota", None)
    if not tipo_nota:
        st.info("Selecione o tipo de movimentação para continuar.")
        _lista_enviados()
        return

    # ===== FLUXO INFORMAR ENTREGÁVEIS (igual à tela do setor) =====
    if tipo_nota == TIPO_FECHAMENTO:
        st.markdown("#### 📅 Qual fechamento parcial? *")
        parciais = ["1º Parcial", "2º Parcial", "3º Parcial", "4º Parcial"]
        parcial_sel = st.session_state.get("trat_fech_parcial", None)
        cols_p = st.columns(4)
        for i, op in enumerate(parciais):
            with cols_p[i]:
                ativo = parcial_sel == op
                if st.button(f"{'✓ ' if ativo else ''}{op}", key=f"trat_fech_parcial_{i}",
                    use_container_width=True, type="primary" if ativo else "secondary"):
                    st.session_state["trat_fech_parcial"] = op
                    st.rerun()
        parcial = st.session_state.get("trat_fech_parcial", None)

        st.markdown("#### 🏢 Empresa * (pode marcar mais de uma)")
        emps_fe = st.session_state.get("trat_fech_emps", [])
        cols_efe = st.columns(5)
        for i, op in enumerate(["1","2","6","13","14"]):
            with cols_efe[i]:
                ativo = op in emps_fe
                if st.button(f"{'✓ ' if ativo else ''}{op}", key=f"trat_fech_emp_{i}",
                    use_container_width=True, type="primary" if ativo else "secondary"):
                    if ativo:
                        emps_fe.remove(op)
                    else:
                        emps_fe.append(op)
                    st.session_state["trat_fech_emps"] = emps_fe
                    st.rerun()
        empresa_fe = ", ".join(st.session_state.get("trat_fech_emps", []))

        st.markdown("---")
        copia_fe = st.multiselect("👥 Setores em cópia (opcional)", nomes_copia, key="trat_fech_copia",
            help="Esses setores recebem aviso do chamado em cópia.")
        obs_fe = st.text_area("📝 Observação (opcional)", placeholder="Informações adicionais sobre a entrega...", key="trat_fech_obs")
        atrasos_fe = st.text_area("⏰ Atrasos de entregáveis (opcional)", placeholder="Descreva eventuais atrasos de entregáveis...", key="trat_fech_atrasos")
        arq_fe = st.file_uploader("📎 Anexar documentos (opcional)", type=["pdf","png","jpg","jpeg","gif","webp","xlsx","xls","csv","ods","xml","docx","txt","zip"], accept_multiple_files=True, key="trat_fech_arq")

        st.markdown("---")
        if st.button("📨 Abrir Chamado para o(s) Setor(es)", use_container_width=True, key="trat_fech_enviar"):
            erros = []
            if not setores_sel: erros.append("Setor responsavel")
            if not parcial: erros.append("Fechamento parcial")
            if not empresa_fe: erros.append("Empresa")
            if erros:
                st.error(f"Preencha: {', '.join(erros)}")
                return
            tipo_final = f"{TIPO_FECHAMENTO} - {parcial}"
            criados = abrir_chamados_para_setores(setores_sel, copia_fe, mapa_email,
                empresa=empresa_fe, tipo_inconsistencia=tipo_final, tipo_nota=TIPO_FECHAMENTO,
                observacao=obs_fe.strip(), arquivos=arq_fe, solicitante=st.session_state.usuario,
                atrasos=atrasos_fe.strip())
            for k in ["trat_tipo_nota","trat_fech_parcial","trat_fech_obs","trat_fech_atrasos","trat_fech_arq","trat_fech_copia","trat_fech_emps"]:
                st.session_state.pop(k, None)
            st.cache_data.clear()
            resumo = " · ".join(f"{s}: {p}" for s, p in criados)
            st.success(f"✅ {len(criados)} chamado(s) aberto(s) (Em andamento). {resumo}")
            st.balloons()
        st.markdown("---")
        _lista_enviados()
        return

    # ===== FLUXO Folha de Pagamento (igual à tela do setor) =====
    if tipo_nota == TIPO_FOLHA:
        st.markdown("#### 🏢 Empresa *")
        emp_sel = st.session_state.get("trat_folha_emp", None)
        cols_e = st.columns(5)
        for i, op in enumerate(["1","2","6","13","14"]):
            with cols_e[i]:
                ativo = emp_sel == op
                if st.button(f"{'✓ ' if ativo else ''}{op}", key=f"trat_folha_emp_{i}",
                    use_container_width=True, type="primary" if ativo else "secondary"):
                    st.session_state["trat_folha_emp"] = op
                    st.rerun()
        empresa_f = st.session_state.get("trat_folha_emp", None)

        st.markdown("#### 📋 Tipo de Inconsistencia *")
        inc_sel = st.session_state.get("trat_folha_inc", None)
        incs_f = filtrar_inconsistencias_trat(tipos_lista, TIPO_FOLHA) + ["Outros"]
        cols_if = st.columns(min(len(incs_f), 4))
        for i, op in enumerate(incs_f):
            with cols_if[i % len(cols_if)]:
                ativo = inc_sel == op
                if st.button(f"{'✓ ' if ativo else ''}{op}", key=f"trat_folha_inc_{i}",
                    use_container_width=True, type="primary" if ativo else "secondary"):
                    st.session_state["trat_folha_inc"] = op
                    st.rerun()
        inc_f = st.session_state.get("trat_folha_inc", None)
        inc_f_outros = ""
        if inc_f == "Outros":
            inc_f_outros = st.text_input("Descreva a inconsistencia *", key="trat_folha_inc_outros")

        st.markdown("#### 💰 Financeiro Baixado? *")
        fin_sel_f = st.session_state.get("trat_folha_fin", None)
        cols_ff = st.columns(2)
        for i, op in enumerate(["Sim","Não"]):
            with cols_ff[i]:
                ativo = fin_sel_f == op
                if st.button(f"{'✓ ' if ativo else ''}{op}", key=f"trat_folha_fin_{i}",
                    use_container_width=True, type="primary" if ativo else "secondary"):
                    st.session_state["trat_folha_fin"] = op
                    st.rerun()
        fin_baixado_f = st.session_state.get("trat_folha_fin", None)

        st.markdown("---")
        solicitante_f = st.text_input("👤 Nome do Solicitante *", key="trat_folha_solic")
        copia_f = st.multiselect("👥 Setores em cópia (opcional)", nomes_copia, key="trat_folha_copia",
            help="Esses setores recebem aviso do chamado em cópia.")
        arq_f = st.file_uploader("📎 Anexos *", type=["pdf","png","jpg","jpeg","gif","webp","xlsx","xls","csv","ods","xml","docx","txt","zip"], accept_multiple_files=True, key="trat_folha_arq")
        obs_f = st.text_area("📝 Observacao *", placeholder="Descreva a solicitação...", key="trat_folha_obs")

        st.markdown("---")
        if st.button("📨 Abrir Chamado para o(s) Setor(es)", use_container_width=True, key="trat_folha_enviar"):
            erros = []
            if not setores_sel: erros.append("Setor responsavel")
            if not empresa_f: erros.append("Empresa")
            if not inc_f: erros.append("Tipo de Inconsistencia")
            if inc_f == "Outros" and not inc_f_outros.strip(): erros.append("Descricao da inconsistencia")
            if not fin_baixado_f: erros.append("Financeiro Baixado")
            if not solicitante_f.strip(): erros.append("Nome do Solicitante")
            if not arq_f: erros.append("Anexo")
            if not obs_f.strip(): erros.append("Observacao")
            if erros:
                st.error(f"Preencha: {', '.join(erros)}")
                return
            inc_final = f"Outros: {inc_f_outros.strip()}" if inc_f == "Outros" else inc_f
            criados = abrir_chamados_para_setores(setores_sel, copia_f, mapa_email,
                empresa=empresa_f, tipo_inconsistencia=inc_final, tipo_nota=TIPO_FOLHA,
                observacao=obs_f.strip(), arquivos=arq_f, solicitante=solicitante_f.strip(),
                financeiro_baixado=fin_baixado_f)
            for k in ["trat_tipo_nota","trat_folha_emp","trat_folha_obs","trat_folha_arq","trat_folha_copia","trat_folha_inc","trat_folha_inc_outros","trat_folha_fin","trat_folha_solic"]:
                st.session_state.pop(k, None)
            st.cache_data.clear()
            resumo = " · ".join(f"{s}: {p}" for s, p in criados)
            st.success(f"✅ {len(criados)} chamado(s) aberto(s) (Em andamento). {resumo}")
            st.balloons()
        st.markdown("---")
        _lista_enviados()
        return

    # ===== FLUXO NORMAL (todos os campos da tela do setor) =====
    # Se a inconsistência "Divergência na conta 70" já está selecionada, este é um
    # fluxo reduzido: não mostra a data (nem o restante dos campos do fluxo normal).
    eh_conta70 = (st.session_state.get("trat_tipo") == TIPO_CONTA70)

    eh_compra = "compra" in tipo_nota.lower()
    if not eh_conta70:
        if eh_compra:
            data_ent = st.date_input("📥 Data da Nota *", value=None, format="DD/MM/YYYY", key="trat_data_ent")
            data_neg = None
        else:
            data_neg = st.date_input("🤝 Data de Negociação *", value=None, format="DD/MM/YYYY", key="trat_data_neg")
            data_ent = None
    else:
        data_ent = None
        data_neg = None

    st.markdown("---")
    st.markdown("#### 📋 Tipo de Inconsistencia *")
    tipo_sel = st.session_state.get("trat_tipo", None)
    tipos_filtrados = filtrar_inconsistencias_trat(tipos_lista, tipo_nota)
    tipos_com_outros = tipos_filtrados + ["Outros"]
    cols_tipo = st.columns(min(len(tipos_com_outros), 4))
    for i, op in enumerate(tipos_com_outros):
        with cols_tipo[i % len(cols_tipo)]:
            ativo = tipo_sel == op
            if st.button(f"{'✓ ' if ativo else ''}{op}", key=f"trat_tipo_{i}",
                use_container_width=True, type="primary" if ativo else "secondary"):
                st.session_state["trat_tipo"] = op
                st.rerun()
    tipo = st.session_state.get("trat_tipo", None)
    tipo_outros_desc = ""
    if tipo == "Outros":
        tipo_outros_desc = st.text_area("Descreva a inconsistencia *", key="trat_outros")

    # ===== FLUXO REDUZIDO: Divergência na conta 70 =====
    # Só aparecem: Empresa (múltipla), Solicitante, Setores em cópia, Anexos e Observação.
    if tipo == TIPO_CONTA70:
        st.markdown("#### 🏢 Empresa * (pode marcar mais de uma)")
        emps_c70 = st.session_state.get("trat_c70_emps", [])
        cols_c70 = st.columns(5)
        for i, op in enumerate(["1", "2", "6", "13", "14"]):
            with cols_c70[i]:
                ativo = op in emps_c70
                if st.button(f"{'✓ ' if ativo else ''}{op}", key=f"trat_c70_emp_{i}",
                    use_container_width=True, type="primary" if ativo else "secondary"):
                    if ativo:
                        emps_c70.remove(op)
                    else:
                        emps_c70.append(op)
                    st.session_state["trat_c70_emps"] = emps_c70
                    st.rerun()
        empresa_c70 = ", ".join(st.session_state.get("trat_c70_emps", []))

        st.markdown("---")
        solicitante_c70 = st.text_input("🙋 Nome do Solicitante *", key="trat_c70_solic")
        copia_c70 = st.multiselect("👥 Setores em cópia (opcional)", nomes_copia, key="trat_c70_copia",
            help="Esses setores recebem aviso do chamado em cópia.")
        arq_c70 = st.file_uploader("📎 Anexos *",
            type=["pdf","png","jpg","jpeg","gif","webp","xlsx","xls","csv","ods","xml","docx","txt","zip"],
            accept_multiple_files=True, key="trat_c70_arq")
        obs_c70 = st.text_area("📝 Observação *", placeholder="Descreva a divergência...", key="trat_c70_obs")

        st.markdown("---")
        if st.button("📨 Abrir Chamado para o(s) Setor(es)", use_container_width=True, key="trat_c70_enviar"):
            erros = []
            if not setores_sel: erros.append("Setor responsavel")
            if not empresa_c70: erros.append("Empresa")
            if not solicitante_c70.strip(): erros.append("Nome do Solicitante")
            if not arq_c70: erros.append("Anexo")
            if not obs_c70.strip(): erros.append("Observação")
            if erros:
                st.error(f"Preencha: {', '.join(erros)}")
                return
            criados = abrir_chamados_para_setores(setores_sel, copia_c70, mapa_email,
                empresa=empresa_c70, tipo_inconsistencia=TIPO_CONTA70, tipo_nota=tipo_nota,
                observacao=obs_c70.strip(), arquivos=arq_c70, solicitante=solicitante_c70.strip())
            for k in ["trat_tipo_nota","trat_tipo","trat_c70_emps","trat_c70_solic",
                      "trat_c70_copia","trat_c70_arq","trat_c70_obs"]:
                st.session_state.pop(k, None)
            st.cache_data.clear()
            resumo = " · ".join(f"{s}: {p}" for s, p in criados)
            st.success(f"✅ {len(criados)} chamado(s) aberto(s) (Em andamento). {resumo}")
            st.balloons()
        st.markdown("---")
        _lista_enviados()
        return

    st.markdown("#### 🏢 Empresa *")
    empresa_sel = st.session_state.get("trat_empresa", None)
    cols_emp = st.columns(5)
    for i, op in enumerate(["1","2","6","13","14"]):
        with cols_emp[i]:
            ativo = empresa_sel == op
            if st.button(f"{'✓ ' if ativo else ''}{op}", key=f"trat_emp_{i}",
                use_container_width=True, type="primary" if ativo else "secondary"):
                st.session_state["trat_empresa"] = op
                st.rerun()
    empresa = st.session_state.get("trat_empresa", None)

    st.markdown("#### 🚦 Prioridade *")
    prio_sel = st.session_state.get("trat_prioridade", None)
    cols_prio = st.columns(2)
    for i, op in enumerate(["Normal","Urgente"]):
        with cols_prio[i]:
            ativo = prio_sel == op
            if st.button(f"{'✓ ' if ativo else ''}{op}", key=f"trat_prio_{i}",
                use_container_width=True, type="primary" if ativo else "secondary"):
                st.session_state["trat_prioridade"] = op
                st.rerun()
    prioridade = st.session_state.get("trat_prioridade", None)

    st.markdown("#### 🔄 NF retornará ao sistema? *")
    nf_sel = st.session_state.get("trat_nf", None)
    cols_nf = st.columns(2)
    for i, op in enumerate(["Sim","Não"]):
        with cols_nf[i]:
            ativo = nf_sel == op
            if st.button(f"{'✓ ' if ativo else ''}{op}", key=f"trat_nf_{i}",
                use_container_width=True, type="primary" if ativo else "secondary"):
                st.session_state["trat_nf"] = op
                st.rerun()
    nf_retorna = st.session_state.get("trat_nf", None)

    st.markdown("#### 💰 Financeiro Baixado? *")
    fin_sel = st.session_state.get("trat_fin", None)
    cols_fin = st.columns(2)
    for i, op in enumerate(["Sim","Não"]):
        with cols_fin[i]:
            ativo = fin_sel == op
            if st.button(f"{'✓ ' if ativo else ''}{op}", key=f"trat_fin_{i}",
                use_container_width=True, type="primary" if ativo else "secondary"):
                st.session_state["trat_fin"] = op
                st.rerun()
    fin_baixado = st.session_state.get("trat_fin", None)

    st.markdown("---")
    with st.form("form_tratativa", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            solicitante = st.text_input("🙋 Nome do Solicitante *")
            nome_parceiro = st.text_input("👤 Nome do Parceiro *")
        with col2:
            numero_nota = st.text_input("📄 Numero da Nota *")
            valor = st.text_input("💰 Valor *", placeholder="0,00")
        col3, col4 = st.columns(2)
        with col3:
            nu_financeiro = st.text_input("🔢 NU Financeiro (opcional)")
        with col4:
            nu_nota = st.text_input("🔢 NU Nota (opcional)")
        copia_sel = st.multiselect("👥 Setores em cópia (opcional)", nomes_copia,
            help="Esses setores recebem aviso do chamado em cópia.")
        arquivo = st.file_uploader("📎 Anexos (opcional)", type=["pdf","png","jpg","jpeg","gif","webp","xlsx","xls","csv","ods","xml","docx","txt","zip"], accept_multiple_files=True)
        observacao = st.text_area("📝 Observacao para o setor *",
            placeholder="Descreva a inconsistencia identificada e o que o setor deve fazer...")
        enviar = st.form_submit_button("📨 Abrir Chamado para o Setor", use_container_width=True)

    if enviar:
        erros = []
        if not setores_sel: erros.append("Setor responsavel")
        if not tipo: erros.append("Tipo de Inconsistencia")
        if tipo == "Outros" and not tipo_outros_desc.strip(): erros.append("Descricao da inconsistencia")
        if not empresa: erros.append("Empresa")
        if not prioridade: erros.append("Prioridade")
        if not nf_retorna: erros.append("NF retornará")
        if not fin_baixado: erros.append("Financeiro Baixado")
        if not solicitante.strip(): erros.append("Nome do Solicitante")
        if not nome_parceiro.strip(): erros.append("Nome do Parceiro")
        if not numero_nota.strip(): erros.append("Numero da Nota")
        if not valor.strip(): erros.append("Valor")
        if eh_compra and not data_ent: erros.append("Data da Nota")
        if not eh_compra and not data_neg: erros.append("Data de Negociação")
        if not observacao.strip(): erros.append("Observacao")
        if erros:
            st.error(f"Preencha: {', '.join(erros)}")
            return

        tipo_final = f"Outros: {tipo_outros_desc.strip()}" if tipo == "Outros" else (tipo or "")

        criados = abrir_chamados_para_setores(setores_sel, copia_sel, mapa_email,
            empresa=empresa, tipo_inconsistencia=tipo_final, tipo_nota=tipo_nota,
            nome_parceiro=nome_parceiro, numero_nota=numero_nota, valor=valor,
            observacao=observacao, nu_financeiro=nu_financeiro, nu_nota=nu_nota,
            arquivos=arquivo, solicitante=solicitante.strip(),
            prioridade=prioridade, nf_retorna=nf_retorna, financeiro_baixado=fin_baixado,
            data_entrada=data_ent or None, data_negociacao=data_neg or None)

        for k in ["trat_tipo_nota","trat_empresa","trat_tipo","trat_outros","trat_prioridade",
                  "trat_nf","trat_fin","trat_data_ent","trat_data_neg"]:
            st.session_state.pop(k, None)
        st.cache_data.clear()
        resumo = " · ".join(f"{s}: {p}" for s, p in criados)
        st.success(f"✅ {len(criados)} chamado(s) aberto(s) (Em andamento). {resumo}")
        st.balloons()

    st.markdown("---")
    _lista_enviados()

def _lista_enviados():
    st.subheader("📋 Chamados abertos pela Contabilidade")
    solicitacoes = run_query("""SELECT setor_destino, empresa, tipo_inconsistencia,
        nome_parceiro, numero_nota, status, criado_em
        FROM solicitacoes_tratativa ORDER BY criado_em DESC LIMIT 50""", fetch=True)
    if not solicitacoes:
        st.info("Nenhum chamado aberto pela Contabilidade ainda.")
        return
    for s in solicitacoes:
        setor_d, emp, tipo_i, parceiro, nf, status, criado_em = s
        cor = "#f59e0b" if status == "Em andamento" else "#22c55e"
        st.markdown(f"""
        <div style='background:white;border:1px solid #e8e8e8;border-radius:8px;
        padding:12px 16px;margin-bottom:6px;'>
            <div style='display:flex;justify-content:space-between;align-items:center;'>
                <span style='font-size:13px;font-weight:600;color:#041747;'>
                {setor_d} — {parceiro or "—"} | NF: {nf or "—"}</span>
                <span style='font-size:12px;color:{cor};font-weight:600;'>{status}</span>
            </div>
            <p style='font-size:12px;color:#666;margin:4px 0 0;'>
            Empresa: {emp or "—"} · Tipo: {tipo_i or "—"} · {fmt_data(criado_em)}</p>
        </div>
        """, unsafe_allow_html=True)
