import streamlit as st
import os
import calendar
import json
import base64
from datetime import datetime
from zoneinfo import ZoneInfo
from database.connection import run_query
from modules.email_service import (email_novo_chamado, email_atualizacao_chamado,
    email_conclusao_chamado, email_nova_mensagem, email_setor_em_copia)

BRASILIA = ZoneInfo("America/Sao_Paulo")

TIPO_FECHAMENTO = "INFORMAR ENTREGÁVEIS"
TIPO_FOLHA = "Folha de Pagamento"

def empacotar_anexos(arquivos):
    """Recebe 1 ou vários arquivos enviados e devolve (json_dados, nomes) para salvar no banco."""
    if not arquivos:
        return None, None
    if not isinstance(arquivos, list):
        arquivos = [arquivos]
    lista, nomes = [], []
    for a in arquivos:
        if a is None:
            continue
        try:
            b64 = base64.b64encode(a.getvalue()).decode("utf-8")
            lista.append({"nome": a.name, "dados": b64})
            nomes.append(a.name)
        except:
            pass
    if not lista:
        return None, None
    return json.dumps(lista), ", ".join(nomes)

def desempacotar_anexos(arq_dados, arq_nome=None):
    """Devolve lista de {nome, dados(base64)}. Lida com formato antigo (1 arquivo só)."""
    if not arq_dados:
        return []
    s = str(arq_dados).strip()
    if s.startswith("["):
        try:
            return [x for x in json.loads(s) if x.get("dados")]
        except:
            return []
    return [{"nome": arq_nome or "anexo", "dados": arq_dados}]

def anexos_para_email(lista):
    """Converte lista de {nome,dados} em [(nome, bytes)] para o e-mail."""
    out = []
    for it in lista:
        try:
            out.append((it.get("nome") or "anexo", base64.b64decode(it.get("dados"))))
        except:
            pass
    return out or None

def verificar_bloqueio(data_nota):
    if not data_nota: return False, ""
    agora = datetime.now(BRASILIA)
    hoje = agora.date()
    m, a, ma, aa = data_nota.month, data_nota.year, hoje.month, hoje.year
    if a == aa and m == ma: return False, ""
    if a < aa or (a == aa and m < ma - 1):
        return True, "⛔ O prazo para solicitações da competência selecionada foi encerrado."
    if agora > datetime(aa, ma, calendar.monthrange(aa, ma)[1], 17, 48, 0, tzinfo=BRASILIA):
        return True, "⛔ O prazo para solicitações da competência selecionada foi encerrado."
    return False, ""

def converter_valor(valor):
    v = valor.strip().replace(" ", "")
    if "," in v and "." in v: v = v.replace(".", "").replace(",", ".")
    elif "," in v: v = v.replace(",", ".")
    return float(v)

@st.cache_data(ttl=300)
def carregar_tipos():
    return [r[0] for r in run_query("SELECT nome FROM tipos_inconsistencia WHERE ativo=1 ORDER BY nome", fetch=True)]

@st.cache_data(ttl=120)
def carregar_vinculos():
    """Retorna (mapa_mov->set(inconsistencias), set de inconsistencias que têm algum vínculo)."""
    rows = run_query("SELECT inconsistencia, movimentacao FROM vinculo_inconsistencia_movimentacao", fetch=True)
    mapa = {}
    com_vinculo = set()
    if rows:
        for inc, mov in rows:
            mapa.setdefault(mov, set()).add(inc)
            com_vinculo.add(inc)
    return mapa, com_vinculo

def filtrar_inconsistencias(tipos_lista, tipo_mov):
    """Mostra inconsistências vinculadas ao tipo de movimentação + as sem nenhum vínculo (legado)."""
    mapa, com_vinculo = carregar_vinculos()
    vinc_do_tipo = mapa.get(tipo_mov, set())
    return [inc for inc in tipos_lista if (inc in vinc_do_tipo) or (inc not in com_vinculo)]

@st.cache_data(ttl=300)
def carregar_tipos_nota():
    tipos = [r[0] for r in run_query("SELECT nome FROM tipos_nota WHERE ativo=1 ORDER BY nome", fetch=True)]
    # Coloca "INFORMAR ENTREGÁVEIS" em primeiro lugar na fileira
    if TIPO_FECHAMENTO in tipos:
        tipos.remove(TIPO_FECHAMENTO)
        tipos.insert(0, TIPO_FECHAMENTO)
    # Coloca "Folha de Pagamento" por último
    if "Folha de Pagamento" in tipos:
        tipos.remove("Folha de Pagamento")
        tipos.append("Folha de Pagamento")
    return tipos

@st.cache_data(ttl=300)
def carregar_setores_disponiveis(excluir=None):
    rows = run_query("""SELECT DISTINCT setor_nome FROM usuarios
        WHERE perfil='setor' AND ativo=1 AND setor_nome IS NOT NULL AND setor_nome <> ''
        ORDER BY setor_nome""", fetch=True)
    lista = [r[0] for r in rows] if rows else []
    if excluir:
        lista = [s for s in lista if s != excluir]
    return lista

def carregar_copias(protocolo):
    rows = run_query("SELECT setor FROM chamados_copia WHERE protocolo=%s ORDER BY setor", (protocolo,), fetch=True)
    return [r[0] for r in rows] if rows else []

def salvar_copias(protocolo, setores):
    run_query("DELETE FROM chamados_copia WHERE protocolo=%s", (protocolo,))
    for s in setores:
        if s and s.strip():
            run_query("INSERT INTO chamados_copia (protocolo, setor) VALUES (%s, %s)", (protocolo, s.strip()))

@st.cache_data(ttl=60)
def carregar_meus_chamados(setor):
    return run_query("""SELECT protocolo, tipo_inconsistencia, empresa, status, prioridade,
        nome_parceiro, numero_nota, aberto_em, solicitante, financeiro_baixado
        FROM chamados WHERE setor=%s ORDER BY aberto_em DESC""", (setor,), fetch=True)

@st.cache_data(ttl=60)
def carregar_chamados_acompanhamento(setor):
    return run_query("""SELECT c.protocolo, c.tipo_inconsistencia, c.empresa, c.status, c.prioridade,
        c.nome_parceiro, c.numero_nota, c.aberto_em, c.solicitante, c.financeiro_baixado, c.setor
        FROM chamados c
        JOIN chamados_copia cc ON cc.protocolo = c.protocolo
        WHERE cc.setor = %s ORDER BY c.aberto_em DESC""", (setor,), fetch=True)

@st.cache_data(ttl=60)
def carregar_todos_chamados():
    return run_query("""SELECT protocolo, setor, tipo_inconsistencia, empresa, status, prioridade,
        nome_parceiro, numero_nota, aberto_em, solicitante, financeiro_baixado
        FROM chamados ORDER BY aberto_em DESC""", fetch=True)

def buscar_email_contabilidade():
    rows = run_query("SELECT email FROM usuarios WHERE perfil='contabilidade' AND ativo=1 LIMIT 1", fetch=True)
    return rows[0][0] if rows else None

def buscar_email_setor(setor_nome):
    rows = run_query("SELECT email FROM usuarios WHERE setor_nome=%s AND ativo=1 LIMIT 1", (setor_nome,), fetch=True)
    return rows[0][0] if rows else None

def emails_interessados(protocolo, setor_chamado, excluir_email=None):
    """Setor dono + setores em cópia, menos quem está enviando.
    A Contabilidade NÃO entra aqui: ela já recebe cópia (BCC) automática de tudo,
    1 por assunto, evitando e-mails duplicados."""
    emails = set()
    es = buscar_email_setor(setor_chamado)
    if es: emails.add(es)
    for s in carregar_copias(protocolo):
        e = buscar_email_setor(s)
        if e: emails.add(e)
    if excluir_email:
        emails.discard(excluir_email)
    return emails

def carregar_mensagens(protocolo):
    return run_query("SELECT autor, perfil, mensagem, enviado_em, anexo_nome, anexo_dados FROM mensagens WHERE chamado_protocolo=%s ORDER BY enviado_em ASC", (protocolo,), fetch=True)

def enviar_mensagem_db(protocolo, autor, perfil, mensagem, anexo_nome=None, anexo_dados=None):
    run_query("INSERT INTO mensagens (chamado_protocolo,autor,perfil,mensagem,enviado_em,anexo_nome,anexo_dados) VALUES (%s,%s,%s,%s,%s,%s,%s)",
              (protocolo, autor, perfil, mensagem, datetime.now(BRASILIA).strftime("%Y-%m-%d %H:%M:%S"), anexo_nome, anexo_dados))

def _mime_imagem(nome):
    n = (nome or "").lower()
    if n.endswith(".png"): return "image/png"
    if n.endswith(".gif"): return "image/gif"
    if n.endswith(".webp"): return "image/webp"
    return "image/jpeg"

def _eh_imagem(nome):
    n = (nome or "").lower()
    return n.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))

def fmt_data(valor, com_hora=True):
    """Formata data/datetime para o padrão brasileiro dd/mm/aaaa (com hora se houver)."""
    if valor is None or valor == "":
        return "—"
    if hasattr(valor, "strftime"):
        try:
            tem_hora = getattr(valor, "hour", 0) or getattr(valor, "minute", 0) or getattr(valor, "second", 0)
            return valor.strftime("%d/%m/%Y %H:%M") if (com_hora and tem_hora) else valor.strftime("%d/%m/%Y")
        except:
            pass
    s = str(valor).strip()
    # formatos comuns vindos do banco como texto
    for fmt_in, com_h in [("%Y-%m-%d %H:%M:%S", True), ("%Y-%m-%d %H:%M", True), ("%Y-%m-%d", False)]:
        try:
            d = datetime.strptime(s, fmt_in)
            if com_h and com_hora:
                return d.strftime("%d/%m/%Y %H:%M")
            return d.strftime("%d/%m/%Y")
        except:
            continue
    return s

def _fmt_valor(v):
    if v is None or v == "":
        return None
    try:
        return "R$ " + f"{float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return str(v)

def exibir_chat(protocolo, setor_chamado):
    st.markdown("#### 💬 Acompanhamento")
    mensagens = carregar_mensagens(protocolo)
    if not mensagens:
        st.markdown("<div style='background:#f9f9f9;border-radius:10px;padding:16px;text-align:center;color:#999;font-size:13px;'>Nenhuma mensagem ainda.</div>", unsafe_allow_html=True)
    else:
        usuario_atual = st.session_state.get("usuario")
        for idx, (autor, perfil, mensagem, enviado_em, anexo_nome, anexo_dados) in enumerate(mensagens):
            is_mine = (autor == usuario_atual)
            alinha = "flex-end" if is_mine else "flex-start"
            if is_mine:
                bg = "#041747" if perfil == "contabilidade" else "#1d4ed8"
                cor_txt = "white"
                cor_meta = "rgba(255,255,255,0.7)"
                border_r = "14px 14px 4px 14px"
            else:
                bg = "#F0F4FF"
                cor_txt = "#041747"
                cor_meta = "#666"
                border_r = "14px 14px 14px 4px"
            txt_html = f"<p style='font-size:13px;margin:0;'>{mensagem}</p>" if mensagem else ""
            anexos_msg = desempacotar_anexos(anexo_dados, anexo_nome)
            midia_html = ""
            nao_imagens = []
            for an in anexos_msg:
                if _eh_imagem(an.get("nome")):
                    mime = _mime_imagem(an.get("nome"))
                    midia_html += f"<img src='data:{mime};base64,{an.get('dados')}' style='max-width:100%;border-radius:8px;margin-top:8px;display:block;'/>"
                else:
                    midia_html += f"<p style='font-size:12px;margin:8px 0 0;'>📎 {an.get('nome') or 'anexo'}</p>"
                    nao_imagens.append(an)
            st.markdown(f"""
            <div style='display:flex;justify-content:{alinha};margin-bottom:10px;'>
                <div style='max-width:75%;background:{bg};color:{cor_txt};border-radius:{border_r};padding:10px 14px;box-shadow:0 1px 4px rgba(0,0,0,0.08);'>
                    <p style='font-size:11px;font-weight:700;margin:0 0 4px;color:{cor_meta};'>{autor}</p>
                    {txt_html}{midia_html}
                    <p style='font-size:10px;margin:6px 0 0;color:{cor_meta};text-align:right;'>{fmt_data(enviado_em)}</p>
                </div>
            </div>""", unsafe_allow_html=True)
            for j, an in enumerate(nao_imagens):
                try:
                    st.download_button(f"📎 Baixar {an.get('nome') or 'anexo'}",
                        data=base64.b64decode(an.get("dados")),
                        file_name=an.get("nome") or "anexo", key=f"chatdl_{protocolo}_{idx}_{j}")
                except:
                    pass

    st.markdown("<br>", unsafe_allow_html=True)
    with st.form(key=f"chat_{protocolo}", clear_on_submit=True):
        nova_msg = st.text_area("Nova mensagem", placeholder="Digite sua mensagem...", height=80, label_visibility="collapsed")
        img = st.file_uploader("📎 Anexar arquivos (opcional)", type=["png","jpg","jpeg","gif","webp","pdf","xlsx","xls","xml","docx","csv","txt","zip"], accept_multiple_files=True, key=f"chat_img_{protocolo}")
        if st.form_submit_button("📨 Enviar", use_container_width=True):
            tem_texto = bool(nova_msg.strip())
            tem_img = bool(img)
            if not tem_texto and not tem_img:
                st.warning("Digite uma mensagem ou anexe um arquivo antes de enviar.")
            else:
                anexo_dados, anexo_nome = empacotar_anexos(img) if tem_img else (None, None)
                enviar_mensagem_db(protocolo, st.session_state.usuario, st.session_state.perfil,
                                   nova_msg.strip(), anexo_nome, anexo_dados)
                try:
                    texto_email = nova_msg.strip() if tem_texto else "[anexo enviado]"
                    destinos = emails_interessados(protocolo, setor_chamado, st.session_state.get("email"))
                    for email_dest in destinos:
                        email_nova_mensagem(email_dest, protocolo, st.session_state.usuario, texto_email)
                except:
                    pass
                st.rerun()


def registrar_fechamento(parcial, observacao="", arquivos=None, atrasos=""):
    tipo_final = f"{TIPO_FECHAMENTO} - {parcial}"
    total = run_query("SELECT COUNT(*) FROM chamados", fetch=True)[0][0]
    protocolo = f"ROC-{datetime.now(BRASILIA).strftime('%Y%m')}-{str(total+1).zfill(4)}"

    anexo_dados, anexo_nome = empacotar_anexos(arquivos)

    run_query("""INSERT INTO chamados (protocolo,setor,empresa,tipo_inconsistencia,prioridade,nf_retorna,
        solicitante,nome_parceiro,numero_nota,tipo_nota,data_entrada,data_saida,data_negociacao,
        valor,observacao,arquivo_nome,status,aberto_em,financeiro_baixado,anexo_dados,atrasos_entregaveis)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (protocolo, st.session_state.setor, "", tipo_final, "Normal", "",
         st.session_state.usuario, "", "", TIPO_FECHAMENTO,
         None, None, None,
         0, (observacao or "").strip(), anexo_nome, "Aberto",
         datetime.now(BRASILIA).strftime("%Y-%m-%d %H:%M:%S"), "", anexo_dados,
         (atrasos or "").strip() or None))

    try:
        email_cont = buscar_email_contabilidade()
        if email_cont:
            anexos = anexos_para_email(desempacotar_anexos(anexo_dados, anexo_nome))
            email_novo_chamado(email_cont, protocolo, st.session_state.setor,
                tipo_final, "Normal", "", "", st.session_state.usuario, anexos=anexos,
                atrasos=(atrasos or "").strip())
    except:
        pass

    return protocolo

def registrar_folha(empresa, fin_baixado, solicitante, observacao, arquivos=None):
    total = run_query("SELECT COUNT(*) FROM chamados", fetch=True)[0][0]
    protocolo = f"ROC-{datetime.now(BRASILIA).strftime('%Y%m')}-{str(total+1).zfill(4)}"

    anexo_dados, anexo_nome = empacotar_anexos(arquivos)

    run_query("""INSERT INTO chamados (protocolo,setor,empresa,tipo_inconsistencia,prioridade,nf_retorna,
        solicitante,nome_parceiro,numero_nota,tipo_nota,data_entrada,data_saida,data_negociacao,
        valor,observacao,arquivo_nome,status,aberto_em,financeiro_baixado,anexo_dados)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (protocolo, st.session_state.setor, empresa, TIPO_FOLHA, "Normal", "",
         solicitante, "", "", TIPO_FOLHA,
         None, None, None,
         0, observacao, anexo_nome, "Aberto",
         datetime.now(BRASILIA).strftime("%Y-%m-%d %H:%M:%S"), fin_baixado, anexo_dados))

    try:
        email_cont = buscar_email_contabilidade()
        if email_cont:
            anexos = anexos_para_email(desempacotar_anexos(anexo_dados, anexo_nome))
            email_novo_chamado(email_cont, protocolo, st.session_state.setor,
                TIPO_FOLHA, "Normal", "", "", solicitante, anexos=anexos)
    except:
        pass

    return protocolo

def tela_novo_chamado(preview=False, setor_preview=None):
    setor_atual = setor_preview if (preview and setor_preview) else st.session_state.get("setor")
    st.title("➕ Novo Chamado")
    if preview:
        st.info("👁️ Modo visualização — esta é a tela que os setores enxergam. Nenhum chamado será criado aqui.")
    st.markdown(f"**Setor:** {setor_atual}")
    st.markdown("Preencha todos os campos obrigatórios.")
    st.markdown("---")

    tipos = carregar_tipos()
    tipos_movimentacao = carregar_tipos_nota()
    if not tipos_movimentacao:
        st.warning("⚠️ Nenhum tipo de movimentação cadastrado. Solicite o cadastro no painel Admin.")
        return

    # 1) Tipo de Movimentação (sempre no topo)
    st.markdown("#### 🗂️ Tipo de Movimentação *")
    tipo_nota = st.session_state.get("sel_tipo_nota", None)
    cols_mov = st.columns(min(len(tipos_movimentacao), 4))
    for i, op in enumerate(tipos_movimentacao):
        with cols_mov[i % len(cols_mov)]:
            ativo = tipo_nota == op
            if st.button(f"{'✓ ' if ativo else ''}{op}", key=f"sel_tipo_nota_{i}", use_container_width=True, type="primary" if ativo else "secondary"):
                st.session_state["sel_tipo_nota"] = op
                st.rerun()
    tipo_nota = st.session_state.get("sel_tipo_nota", None)
    if not tipo_nota:
        st.info("Selecione o tipo de movimentação para continuar.")
        return

    # === FLUXO ESPECIAL: Informar fechamento de período (só entrega + período) ===
    if tipo_nota == TIPO_FECHAMENTO:
        st.markdown("---")
        st.markdown("#### 📅 Qual fechamento parcial? *")
        parciais = ["1º Parcial", "2º Parcial", "3º Parcial", "4º Parcial"]
        parcial_sel = st.session_state.get("sel_parcial", None)
        cols_p = st.columns(4)
        for i, op in enumerate(parciais):
            with cols_p[i]:
                ativo = parcial_sel == op
                if st.button(f"{'✓ ' if ativo else ''}{op}", key=f"sel_parcial_{i}", use_container_width=True, type="primary" if ativo else "secondary"):
                    st.session_state["sel_parcial"] = op
                    st.rerun()
        parcial = st.session_state.get("sel_parcial", None)

        st.markdown("---")
        obs_fech = st.text_area("📝 Observação (opcional)", placeholder="Informações adicionais sobre a entrega...", key="fech_obs")
        atrasos_fech = st.text_area("⏰ Atrasos de entregáveis (opcional)", placeholder="Descreva eventuais atrasos de entregáveis...", key="fech_atrasos")
        arq_fech = st.file_uploader("📎 Anexar documentos (opcional)",
            type=["pdf","png","jpg","jpeg","xlsx","xml","docx","zip"], accept_multiple_files=True, key="fech_arquivo")

        st.markdown("---")
        if st.button("📨 Enviar Chamado", use_container_width=True, key="enviar_fechamento"):
            if preview:
                st.info("👁️ Modo visualização: nenhum chamado foi criado.")
                return
            if not parcial:
                st.error("⚠️ Selecione o fechamento parcial.")
                return
            protocolo = registrar_fechamento(parcial, obs_fech, arq_fech, atrasos_fech)
            for k in ["sel_tipo_nota", "sel_parcial", "fech_obs", "fech_atrasos", "fech_arquivo"]:
                st.session_state.pop(k, None)
            st.cache_data.clear()
            st.success(f"✅ Chamado registrado! Protocolo: **{protocolo}**")
            st.balloons()
        return

    # === FLUXO ESPECIAL: Folha de Pagamento (campos reduzidos) ===
    if tipo_nota == TIPO_FOLHA:
        st.markdown("---")
        st.markdown("#### 🏢 Empresa *")
        emp_sel = st.session_state.get("folha_empresa", None)
        cols_e = st.columns(5)
        for i, op in enumerate(["1", "2", "6", "13", "14"]):
            with cols_e[i]:
                ativo = emp_sel == op
                if st.button(f"{'✓ ' if ativo else ''}{op}", key=f"folha_emp_{i}",
                    use_container_width=True, type="primary" if ativo else "secondary"):
                    st.session_state["folha_empresa"] = op
                    st.rerun()
        empresa_f = st.session_state.get("folha_empresa", None)

        st.markdown("#### 💰 Financeiro Baixado *")
        fin_sel = st.session_state.get("folha_fin", None)
        cfb = st.columns(2)
        for i, op in enumerate(["Sim", "Não"]):
            with cfb[i]:
                ativo = fin_sel == op
                if st.button(f"{'✓ ' if ativo else ''}{op}", key=f"folha_fin_{i}",
                    use_container_width=True, type="primary" if ativo else "secondary"):
                    st.session_state["folha_fin"] = op
                    st.rerun()
        fin_baixado_f = st.session_state.get("folha_fin", None)

        st.markdown("---")
        solicitante_f = st.text_input("👤 Nome do Solicitante *", key="folha_solic")
        copia_folha = st.multiselect("👥 Setores em cópia (opcional)",
            carregar_setores_disponiveis(setor_atual), key="folha_copia")
        arq_folha = st.file_uploader("📎 Anexos *", type=["pdf","png","jpg","jpeg","xlsx","xml","docx","zip"], accept_multiple_files=True, key="folha_arquivo")
        obs_folha = st.text_area("📝 Observação *", placeholder="Descreva a solicitação...", key="folha_obs")

        st.markdown("---")
        if st.button("📨 Enviar Chamado", use_container_width=True, key="enviar_folha"):
            if preview:
                st.info("👁️ Modo visualização: nenhum chamado foi criado.")
                return
            erros = []
            if not empresa_f: erros.append("Empresa")
            if not fin_baixado_f: erros.append("Financeiro Baixado")
            if not solicitante_f.strip(): erros.append("Nome do Solicitante")
            if not arq_folha: erros.append("Anexo")
            if not obs_folha.strip(): erros.append("Observação")
            if erros:
                st.error(f"⚠️ Preencha: {', '.join(erros)}")
                return
            protocolo = registrar_folha(empresa_f, fin_baixado_f, solicitante_f.strip(),
                                        obs_folha.strip(), arq_folha)
            if copia_folha:
                salvar_copias(protocolo, copia_folha)
                for s in copia_folha:
                    try:
                        email_s = buscar_email_setor(s)
                        if email_s:
                            email_setor_em_copia(email_s, protocolo, s, setor_atual)
                    except:
                        pass
            for k in ["sel_tipo_nota", "folha_empresa", "folha_fin", "folha_solic", "folha_obs", "folha_arquivo", "folha_copia"]:
                st.session_state.pop(k, None)
            st.cache_data.clear()
            st.success(f"✅ Chamado registrado! Protocolo: **{protocolo}**")
            st.balloons()
        return

    # === FLUXO NORMAL ===
    eh_compra = "compra" in tipo_nota.lower()
    if eh_compra:
        data_entrada = st.date_input("📥 Data da Nota *", value=None, key="data_entrada")
        data_negociacao = None
    else:
        data_negociacao = st.date_input("🤝 Data de Negociação *", value=None, key="data_negociacao")
        data_entrada = None

    st.markdown("---")
    st.markdown("#### 📋 Abertura de Período / Descontabilização *")
    tipos_filtrados = filtrar_inconsistencias(tipos, tipo_nota)
    tipos_com_outros = tipos_filtrados + ["Outros"]
    tipo_sel = st.session_state.get("sel_tipo", None)
    cols_tipo = st.columns(min(len(tipos_com_outros), 4))
    for i, op in enumerate(tipos_com_outros):
        with cols_tipo[i % len(cols_tipo)]:
            ativo = tipo_sel == op
            if st.button(f"{'✓ ' if ativo else ''}{op}", key=f"sel_tipo_{i}", use_container_width=True, type="primary" if ativo else "secondary"):
                st.session_state["sel_tipo"] = op
                st.rerun()
    tipo = st.session_state.get("sel_tipo", None)
    tipo_outros_desc = ""
    if tipo == "Outros":
        tipo_outros_desc = st.text_area("📝 Descreva a solicitação *", placeholder="Descreva detalhadamente...", key="outros_desc")

    st.markdown("---")
    st.markdown("#### 🏢 Empresa *")
    empresa_sel = st.session_state.get("sel_empresa", None)
    cols_emp = st.columns(5)
    for i, op in enumerate(["1","2","6","13","14"]):
        with cols_emp[i]:
            ativo = empresa_sel == op
            if st.button(f"{'✓ ' if ativo else ''}{op}", key=f"sel_empresa_{i}", use_container_width=True, type="primary" if ativo else "secondary"):
                st.session_state["sel_empresa"] = op
                st.rerun()
    empresa = st.session_state.get("sel_empresa", None)

    st.markdown("#### 🚦 Prioridade *")
    prio_sel = st.session_state.get("sel_prioridade", None)
    cols_prio = st.columns(2)
    for i, op in enumerate(["Normal","Urgente"]):
        with cols_prio[i]:
            ativo = prio_sel == op
            if st.button(f"{'✓ ' if ativo else ''}{op}", key=f"sel_prio_{i}", use_container_width=True, type="primary" if ativo else "secondary"):
                st.session_state["sel_prioridade"] = op
                st.rerun()
    prioridade = st.session_state.get("sel_prioridade", None)

    st.markdown("#### 🔄 NF retornará ao sistema? *")
    nf_sel = st.session_state.get("sel_nf", None)
    cols_nf = st.columns(2)
    for i, op in enumerate(["Sim","Não"]):
        with cols_nf[i]:
            ativo = nf_sel == op
            if st.button(f"{'✓ ' if ativo else ''}{op}", key=f"sel_nf_{i}", use_container_width=True, type="primary" if ativo else "secondary"):
                st.session_state["sel_nf"] = op
                st.rerun()
    nf_retorna = st.session_state.get("sel_nf", None)

    st.markdown("#### 💰 Financeiro Baixado? *")
    fin_sel = st.session_state.get("sel_fin", None)
    cols_fin = st.columns(2)
    for i, op in enumerate(["Sim","Não"]):
        with cols_fin[i]:
            ativo = fin_sel == op
            if st.button(f"{'✓ ' if ativo else ''}{op}", key=f"sel_fin_{i}", use_container_width=True, type="primary" if ativo else "secondary"):
                st.session_state["sel_fin"] = op
                st.rerun()
    fin_baixado = st.session_state.get("sel_fin", None)

    setores_copia_disp = carregar_setores_disponiveis(setor_atual)

    st.markdown("---")
    with st.form("form_chamado", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            solicitante = st.text_input("🙋 Nome do Solicitante *")
            nome_parceiro = st.text_input("👤 Nome do Parceiro *")
        with col2:
            numero_nota = st.text_input("📄 Número da Nota *")
            valor = st.text_input("💰 Valor *", placeholder="0,00")
        col3, col4 = st.columns(2)
        with col3:
            nu_financeiro = st.text_input("🔢 NU Financeiro (opcional)")
        with col4:
            nu_nota = st.text_input("🔢 NU Nota (opcional)")
        copia_sel = st.multiselect("👥 Setores em cópia (opcional)", setores_copia_disp,
            help="Os setores marcados recebem e-mail e podem acompanhar e responder este chamado.")
        arquivo = st.file_uploader("📎 Anexos (opcional)", type=["pdf","png","jpg","jpeg","xlsx","xml","docx","csv","txt","zip"], accept_multiple_files=True)
        observacao = st.text_area("📝 Observação Complementar", placeholder="Informações adicionais...")
        enviar = st.form_submit_button("📨 Enviar Chamado", use_container_width=True)

    if enviar:
        if preview:
            st.info("👁️ Modo visualização: nenhum chamado foi criado.")
            return
        erros = []
        if not tipo: erros.append("Tipo")
        if tipo == "Outros" and not tipo_outros_desc.strip(): erros.append("Descrição")
        if not empresa: erros.append("Empresa")
        if not prioridade: erros.append("Prioridade")
        if not nf_retorna: erros.append("NF retornará")
        if not fin_baixado: erros.append("Financeiro Baixado")
        if not solicitante.strip(): erros.append("Solicitante")
        if not nome_parceiro.strip(): erros.append("Parceiro")
        if not numero_nota.strip(): erros.append("Número da Nota")
        if not valor.strip(): erros.append("Valor")
        if eh_compra and not data_entrada: erros.append("Data da Nota")
        if not eh_compra and not data_negociacao: erros.append("Data de Negociação")
        if erros:
            st.error(f"⚠️ Preencha: {', '.join(erros)}")
            return

        bloqueado, msg = verificar_bloqueio(data_entrada if eh_compra else data_negociacao)
        if bloqueado:
            st.error(msg)
            return

        anexo_dados, arquivo_nome = empacotar_anexos(arquivo)

        try:
            valor_float = converter_valor(valor)
        except:
            st.error("⚠️ Valor inválido.")
            return

        tipo_final = f"Outros: {tipo_outros_desc.strip()}" if tipo == "Outros" else tipo
        total = run_query("SELECT COUNT(*) FROM chamados", fetch=True)[0][0]
        protocolo = f"ROC-{datetime.now(BRASILIA).strftime('%Y%m')}-{str(total+1).zfill(4)}"

        run_query("""INSERT INTO chamados (protocolo,setor,empresa,tipo_inconsistencia,prioridade,nf_retorna,
            solicitante,nome_parceiro,numero_nota,tipo_nota,data_entrada,data_saida,data_negociacao,
            valor,observacao,arquivo_nome,status,aberto_em,financeiro_baixado,num_unico_financeiro,num_unico_nota,anexo_dados)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (protocolo, st.session_state.setor, empresa, tipo_final, prioridade, nf_retorna,
             solicitante.strip(), nome_parceiro.strip(), numero_nota.strip(), tipo_nota,
             data_entrada or None, None, data_negociacao or None,
             valor_float, observacao.strip(), arquivo_nome, "Aberto",
             datetime.now(BRASILIA).strftime("%Y-%m-%d %H:%M:%S"), fin_baixado,
             nu_financeiro.strip() or None, nu_nota.strip() or None, anexo_dados))

        # Salva setores em cópia e notifica
        if copia_sel:
            salvar_copias(protocolo, copia_sel)
            for s in copia_sel:
                try:
                    email_s = buscar_email_setor(s)
                    if email_s:
                        email_setor_em_copia(email_s, protocolo, s, st.session_state.setor)
                except:
                    pass

        try:
            email_cont = buscar_email_contabilidade()
            if email_cont:
                anexos = anexos_para_email(desempacotar_anexos(anexo_dados, arquivo_nome))
                email_novo_chamado(email_cont, protocolo, st.session_state.setor,
                    tipo_final, prioridade, nome_parceiro.strip(), numero_nota.strip(), solicitante.strip(),
                    anexos=anexos, nu_financeiro=nu_financeiro.strip(), nu_nota=nu_nota.strip())
        except:
            pass

        for k in ["sel_tipo_nota","sel_tipo","sel_parcial","sel_empresa","sel_prioridade","sel_nf","sel_fin","outros_desc","data_entrada","data_negociacao"]:
            st.session_state.pop(k, None)

        st.cache_data.clear()
        st.success(f"✅ Chamado registrado! Protocolo: **{protocolo}**")
        st.balloons()

def exibir_chamado(protocolo, tipo, empresa, status, prioridade, parceiro, nf, aberto_em, solicitante, fin_baixado, setor, eh_contabilidade=False, protocolo_aberto=None):
    status_cor = {"Aberto":"🔴","Em andamento":"🟡","Resolvido":"🟢","Cancelado":"⚫"}
    expanded = protocolo == protocolo_aberto
    label = f"{status_cor.get(status,'⚪')} {protocolo} — {parceiro} | NF: {nf}"
    if eh_contabilidade:
        label += f" | {setor}"
    label += f" | {status}"

    with st.expander(label, expanded=expanded):
        c1,c2,c3,c4 = st.columns(4)
        c1.markdown(f"**Empresa:** {empresa}")
        c2.markdown(f"**Tipo:** {tipo}")
        c3.markdown(f"**Prioridade:** {prioridade}")
        c4.markdown(f"**Solicitante:** {solicitante or '—'}")
        c1.markdown(f"**Fin. Baixado:** {fin_baixado or '—'}")
        c2.markdown(f"**👤 Parceiro:** {parceiro or '—'}")
        c3.markdown(f"**📄 Número da Nota:** {nf or '—'}")
        st.markdown(f"**Aberto em:** {fmt_data(aberto_em)}")

        copias = carregar_copias(protocolo)
        if copias:
            st.markdown(f"**👥 Em cópia:** {', '.join(copias)}")

        # Observação e anexo (se houver)
        det = run_query("""SELECT observacao, arquivo_nome, anexo_dados, num_unico_financeiro, num_unico_nota,
            atrasos_entregaveis, data_entrada, data_negociacao, nf_retorna, tipo_nota, valor, atendente
            FROM chamados WHERE protocolo=%s""", (protocolo,), fetch=True)
        if det:
            (obs_txt, arq_nome, arq_dados, nu_fin, nu_nt, atrasos_txt,
             data_ent, data_neg, nf_ret, tipo_mov, valor_c, atendente_c) = det[0]

            if atendente_c:
                st.markdown(f"**🙋 Atendente da solicitação:** {atendente_c}")
            if tipo_mov:
                st.markdown(f"**🗂️ Tipo de Movimentação:** {tipo_mov}")
            data_ref = data_ent or data_neg
            if data_ref:
                rotulo_data = "📥 Data da Nota" if data_ent else "🤝 Data de Negociação"
                st.markdown(f"**{rotulo_data}:** {fmt_data(data_ref, com_hora=False)}")
            if nf_ret:
                st.markdown(f"**🔄 NF retornará ao sistema:** {nf_ret}")
            valor_fmt = _fmt_valor(valor_c)
            if valor_fmt:
                st.markdown(f"**💰 Valor:** {valor_fmt}")
            if nu_fin:
                st.markdown(f"**🔢 Número Único Financeiro:** {nu_fin}")
            if nu_nt:
                st.markdown(f"**🔢 Número Único da Nota:** {nu_nt}")
            if atrasos_txt:
                st.markdown(f"**⏰ Atrasos de entregáveis:** {atrasos_txt}")
            if obs_txt:
                st.markdown(f"**📝 Observação:** {obs_txt}")
            anexos_ch = desempacotar_anexos(arq_dados, arq_nome)
            if anexos_ch:
                st.markdown("**📎 Anexos:**")
                for i_an, an in enumerate(anexos_ch):
                    try:
                        raw = base64.b64decode(an.get("dados"))
                        if _eh_imagem(an.get("nome")):
                            st.image(raw, use_container_width=True, caption=an.get("nome"))
                        st.download_button("📎 Baixar" + (f" ({an.get('nome')})" if an.get("nome") else ""),
                            data=raw, file_name=an.get("nome") or f"{protocolo}_anexo_{i_an}",
                            key=f"dl_{protocolo}_{i_an}")
                    except:
                        st.caption(f"📎 {an.get('nome') or 'anexo'} (não foi possível carregar)")

        # Atualizar status (somente contabilidade)
        if eh_contabilidade:
            st.markdown("---")
            cs1, cs2 = st.columns(2)
            with cs1:
                novo_status = st.selectbox("Atualizar status", ["Aberto","Em andamento","Resolvido","Cancelado"],
                    index=["Aberto","Em andamento","Resolvido","Cancelado"].index(status), key=f"s_{protocolo}")
            with cs2:
                atendente = st.text_input("🙋 Atendente da solicitação (seu nome)", key=f"atend_{protocolo}")
            if st.button("💾 Salvar status", key=f"b_{protocolo}"):
                if not atendente.strip():
                    st.warning("⚠️ Informe o nome do atendente antes de salvar.")
                    return
                agora = datetime.now(BRASILIA).strftime("%Y-%m-%d %H:%M:%S")
                run_query("""UPDATE chamados SET status=%s, atendente=%s, atendido_em=COALESCE(atendido_em,%s),
                    resolvido_em=CASE WHEN %s='Resolvido' THEN %s ELSE resolvido_em END WHERE protocolo=%s""",
                    (novo_status, atendente.strip(), agora, novo_status, agora, protocolo))
                try:
                    destinos = emails_interessados(protocolo, setor)
                    if novo_status == "Resolvido":
                        for ed in destinos:
                            email_conclusao_chamado(None, ed, protocolo, tipo, agora)
                    else:
                        for ed in destinos:
                            email_atualizacao_chamado(ed, protocolo, novo_status, setor)
                except:
                    pass
                st.cache_data.clear()
                st.success("✅ Atualizado!")
                st.rerun()

        # Editar setores em cópia (contabilidade ou o setor que abriu)
        eh_dono = (st.session_state.perfil != "contabilidade" and st.session_state.setor == setor)
        if eh_contabilidade or eh_dono:
            st.markdown("---")
            setores_disp = carregar_setores_disponiveis(setor)
            default_copias = [c for c in copias if c in setores_disp]
            novas_copias = st.multiselect("👥 Setores em cópia", setores_disp,
                default=default_copias, key=f"copia_{protocolo}")
            if st.button("💾 Salvar cópia", key=f"savecopia_{protocolo}"):
                adicionados = set(novas_copias) - set(copias)
                salvar_copias(protocolo, novas_copias)
                for s in adicionados:
                    try:
                        email_s = buscar_email_setor(s)
                        if email_s:
                            email_setor_em_copia(email_s, protocolo, s, setor)
                    except:
                        pass
                st.cache_data.clear()
                st.success("✅ Cópia atualizada!")
                st.rerun()

        st.markdown("---")
        exibir_chat(protocolo, setor)

def tela_meus_chamados(protocolo_aberto=None):
    st.title("📋 Minhas Solicitações")
    st.markdown("---")
    rows = carregar_meus_chamados(st.session_state.setor)
    if not rows:
        st.info("Nenhum chamado registrado ainda.")
        return
    for protocolo, tipo, empresa, status, prioridade, parceiro, nf, aberto_em, solicitante, fin_baixado in rows:
        exibir_chamado(protocolo, tipo, empresa, status, prioridade, parceiro, nf,
                       aberto_em, solicitante, fin_baixado, st.session_state.setor,
                       eh_contabilidade=False, protocolo_aberto=protocolo_aberto)

def tela_acompanhamento(protocolo_aberto=None):
    st.title("👀 Solicitações em Acompanhamento")
    st.markdown("Chamados em que seu setor foi incluído em cópia.")
    st.markdown("---")
    rows = carregar_chamados_acompanhamento(st.session_state.setor)
    if not rows:
        st.info("Nenhum chamado em acompanhamento.")
        return
    for protocolo, tipo, empresa, status, prioridade, parceiro, nf, aberto_em, solicitante, fin_baixado, setor_dono in rows:
        exibir_chamado(protocolo, tipo, empresa, status, prioridade, parceiro, nf,
                       aberto_em, solicitante, fin_baixado, setor_dono,
                       eh_contabilidade=False, protocolo_aberto=protocolo_aberto)

def tela_todos_chamados(protocolo_aberto=None):
    st.title("📋 Todos os Chamados")
    st.markdown("---")
    rows = carregar_todos_chamados()
    if not rows:
        st.info("Nenhum chamado registrado ainda.")
        return
    c1,c2,c3 = st.columns(3)
    filtro_status = c1.selectbox("Status", ["Todos","Aberto","Em andamento","Resolvido","Cancelado"])
    filtro_empresa = c2.selectbox("Empresa", ["Todas","1","2","6","13","14"])
    filtro_setor = c3.text_input("Setor")
    for protocolo, setor, tipo, empresa, status, prioridade, parceiro, nf, aberto_em, solicitante, fin_baixado in rows:
        if filtro_status != "Todos" and status != filtro_status: continue
        if filtro_empresa != "Todas" and empresa != filtro_empresa: continue
        if filtro_setor and filtro_setor.lower() not in setor.lower(): continue
        exibir_chamado(protocolo, tipo, empresa, status, prioridade, parceiro, nf,
                       aberto_em, solicitante, fin_baixado, setor,
                       eh_contabilidade=True, protocolo_aberto=protocolo_aberto)
