import psycopg2
import psycopg2.pool
import streamlit as st

@st.cache_resource
def get_pool():
    return psycopg2.pool.SimpleConnectionPool(
        minconn=1,
        maxconn=10,
        host=st.secrets["DB_HOST"],
        dbname=st.secrets["DB_NAME"],
        user=st.secrets["DB_USER"],
        password=st.secrets["DB_PASSWORD"],
        port=st.secrets["DB_PORT"]
    )

def get_conn():
    pool = get_pool()
    return pool.getconn()

def release_conn(conn):
    pool = get_pool()
    pool.putconn(conn)

def init_db():
    conn = get_conn()
    cur = conn.cursor()

    try:
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
            CREATE TABLE IF NOT EXISTS chamados (
                id SERIAL PRIMARY KEY,
                protocolo TEXT NOT NULL UNIQUE,
                setor TEXT NOT NULL,
                empresa TEXT NOT NULL,
                tipo_inconsistencia TEXT NOT NULL,
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
            CREATE TABLE IF NOT EXISTS competencias (
                id SERIAL PRIMARY KEY,
                mes_ano TEXT NOT NULL,
                ano INTEGER NOT NULL,
                mes INTEGER NOT NULL,
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS fechamentos (
                id SERIAL PRIMARY KEY,
                competencia_id INTEGER NOT NULL REFERENCES competencias(id) ON DELETE CASCADE,
                tipo TEXT NOT NULL CHECK(tipo IN (
                    'Fechamento Parcial 1',
                    'Fechamento Parcial 2',
                    'Fechamento Parcial 3',
                    'Fechamento Consolidado Corporativo'
                )),
                data_fechamento DATE,
                hora_fechamento TEXT,
                periodo_inicio DATE,
                periodo_fim DATE,
                observacao TEXT,
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

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

        calendario_2026 = {
            ("Janeiro/2026", 1, 2026): [
                ("Fechamento Parcial 1", "2026-01-16", "12:00", "2026-01-01", "2026-01-14"),
                ("Fechamento Parcial 2", "2026-01-23", "10:00", "2026-01-15", "2026-01-21"),
                ("Fechamento Parcial 3", "2026-01-29", "10:00", "2026-01-22", "2026-01-27"),
                ("Fechamento Consolidado Corporativo", "2026-02-02", "10:00", "2026-01-28", "2026-01-31"),
            ],
            ("Fevereiro/2026", 2, 2026): [
                ("Fechamento Parcial 1", "2026-02-13", "12:00", "2026-02-01", "2026-02-11"),
                ("Fechamento Parcial 2", "2026-02-23", "10:00", "2026-02-12", "2026-02-19"),
                ("Fechamento Parcial 3", "2026-02-26", "10:00", "2026-02-20", "2026-02-24"),
                ("Fechamento Consolidado Corporativo", "2026-03-02", "10:00", "2026-02-25", "2026-02-28"),
            ],
            ("Março/2026", 3, 2026): [
                ("Fechamento Parcial 1", "2026-03-17", "12:00", "2026-03-01", "2026-03-15"),
                ("Fechamento Parcial 2", "2026-03-24", "10:00", "2026-03-16", "2026-03-22"),
                ("Fechamento Parcial 3", "2026-03-30", "10:00", "2026-03-23", "2026-03-26"),
                ("Fechamento Consolidado Corporativo", "2026-04-01", "10:00", "2026-03-27", "2026-03-31"),
            ],
            ("Abril/2026", 4, 2026): [
                ("Fechamento Parcial 1", "2026-04-14", "12:00", "2026-04-01", "2026-04-12"),
                ("Fechamento Parcial 2", "2026-04-22", "10:00", "2026-04-13", "2026-04-19"),
                ("Fechamento Parcial 3", "2026-04-29", "10:00", "2026-04-20", "2026-04-27"),
                ("Fechamento Consolidado Corporativo", "2026-05-04", "10:00", "2026-04-28", "2026-04-30"),
            ],
            ("Maio/2026", 5, 2026): [
                ("Fechamento Parcial 1", "2026-05-14", "12:00", "2026-
