import psycopg2
import streamlit as st

def get_conn():
    return psycopg2.connect(st.secrets["DATABASE_URL"])

def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id SERIAL PRIMARY KEY,
            nome TEXT NOT NULL,
            login TEXT NOT NULL UNIQUE,
            senha TEXT NOT NULL,
            perfil TEXT NOT NULL CHECK(perfil IN ('contabilidade', 'setor')),
            ativo INTEGER DEFAULT 1,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS tipos_inconsistencia (
            id SERIAL PRIMARY KEY,
            nome TEXT NOT NULL UNIQUE,
            ativo INTEGER DEFAULT 1
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS motivos (
            id SERIAL PRIMARY KEY,
            nome TEXT NOT NULL UNIQUE,
            ativo INTEGER DEFAULT 1
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS chamados (
            id SERIAL PRIMARY KEY,
            protocolo TEXT NOT NULL UNIQUE,
            setor TEXT NOT NULL,
            empresa TEXT NOT NULL,
            tipo_inconsistencia TEXT NOT NULL,
            motivo TEXT NOT NULL,
            prioridade TEXT NOT NULL,
            nf_retorna TEXT NOT NULL,
            nome_parceiro TEXT NOT NULL,
            numero_nota TEXT NOT NULL,
            tipo_nota TEXT,
            data_entrada DATE,
            data_saida DATE,
            data_negociacao DATE,
            valor REAL NOT NULL,
            observacao TEXT,
            arquivo_nome TEXT,
            status TEXT NOT NULL DEFAULT 'Aberto',
            aberto_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            atendido_em TIMESTAMP,
            resolvido_em TIMESTAMP,
            resolucao TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS calendario_fechamento (
            id SERIAL PRIMARY KEY,
            mes_ano TEXT NOT NULL,
            importacao_1 DATE,
            importacao_2 DATE,
            importacao_3 DATE,
            fechamento DATE,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Dados iniciais
    usuarios = [
        ('Contabilidade', 'contabilidade', 'roc2024', 'contabilidade'),
        ('Adm Logistica King', 'adm.logistica.king', 'setor123', 'setor'),
        ('Administrativo', 'administrativo', 'setor123', 'setor'),
        ('Comercial', 'comercial', 'setor123', 'setor'),
        ('Compras', 'compras', 'setor123', 'setor'),
        ('Controladoria', 'controladoria', 'setor123', 'setor'),
        ('DP', 'dp', 'setor123', 'setor'),
        ('Financeiro', 'financeiro', 'setor123', 'setor'),
        ('Fiscal', 'fiscal', 'setor123', 'setor'),
        ('Logistica King', 'logistica.king', 'setor123', 'setor'),
        ('Logistica Pisa', 'logistica.pisa', 'setor123', 'setor'),
        ('Marketing', 'marketing', 'setor123', 'setor'),
    ]
    for u in usuarios:
        cur.execute("""
            INSERT INTO usuarios (nome, login, senha, perfil)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (login) DO NOTHING
        """, u)

    tipos = [
        'Descontabilização', 'Correção', 'Alteração Natureza',
        'Abertura de Período', 'Folha de Pagamento', 'Nota Fiscal',
        'Conciliação', 'Revisão', 'Livro Fiscal', 'Custo',
        'Exclusão', 'Atraso fechamento'
    ]
    for t in tipos:
        cur.execute("INSERT INTO tipos_inconsistencia (nome) VALUES (%s) ON CONFLICT (nome) DO NOTHING", (t,))

    motivos = [
        'Parceiro incorreto', 'Valor incorreto', 'Documento fora do prazo',
        'Divergência de XML', 'Duplicidade', 'Erro de importação'
    ]
    for m in motivos:
        cur.execute("INSERT INTO motivos (nome) VALUES (%s) ON CONFLICT (nome) DO NOTHING", (m,))

    conn.commit()
    cur.close()
    conn.close()
