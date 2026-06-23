import psycopg2
from psycopg2 import pool as pgpool
import streamlit as st


def _params():
    """Parâmetros de conexão com o Neon (lidos dos secrets do Streamlit)."""
    return dict(
        host=st.secrets["DB_HOST"],
        dbname=st.secrets["DB_NAME"],
        user=st.secrets["DB_USER"],
        password=st.secrets["DB_PASSWORD"],
        port=st.secrets["DB_PORT"],
        sslmode="require",
        connect_timeout=10,
        # Keepalives ajudam a manter a conexão viva contra o tempo de ociosidade do Neon.
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=5,
    )


@st.cache_resource
def get_pool():
    """Pool de conexões reaproveitadas entre reruns e entre usuários.
    Fica vivo no processo do Streamlit, evitando abrir uma conexão nova
    (com handshake SSL) a cada query — principal causa de lentidão."""
    return pgpool.ThreadedConnectionPool(minconn=1, maxconn=5, **_params())


def get_conn():
    """Compatibilidade: devolve uma conexão avulsa (não usar em código novo;
    o caminho recomendado é run_query, que usa o pool)."""
    return psycopg2.connect(**_params())


def _executar(sql, params, fetch):
    """Executa 1 query usando uma conexão emprestada do pool e a devolve no fim."""
    p = get_pool()
    conn = p.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            rows = cur.fetchall() if fetch else None
        conn.commit()  # encerra a transação (evita "idle in transaction" na conexão reaproveitada)
        return rows
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        try:
            p.putconn(conn)
        except Exception:
            pass


def run_query(sql, params=None, fetch=False):
    """Executa uma query reaproveitando conexões do pool.
    Se o Neon tiver derrubado as conexões ociosas, recria o pool e tenta 1x mais."""
    try:
        return _executar(sql, params, fetch)
    except (psycopg2.OperationalError, psycopg2.InterfaceError, pgpool.PoolError):
        # Conexões mortas/ociosas: descarta o pool inteiro e reconstrói.
        try:
            get_pool().closeall()
        except Exception:
            pass
        get_pool.clear()
        return _executar(sql, params, fetch)


def init_db():
    # Usa uma conexão própria (fora do pool) para preservar a transação manual.
    conn = psycopg2.connect(**_params())
    cur = conn.cursor()
    try:
        cur.execute("""CREATE TABLE IF NOT EXISTS usuarios (
            id SERIAL PRIMARY KEY, nome TEXT NOT NULL, login TEXT NOT NULL UNIQUE,
            senha TEXT NOT NULL, perfil TEXT NOT NULL CHECK(perfil IN ('contabilidade','setor')),
            ativo INTEGER DEFAULT 1, criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS tipos_inconsistencia (
            id SERIAL PRIMARY KEY, nome TEXT NOT NULL UNIQUE, ativo INTEGER DEFAULT 1)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS chamados (
            id SERIAL PRIMARY KEY, protocolo TEXT NOT NULL UNIQUE, setor TEXT NOT NULL,
            empresa TEXT NOT NULL, tipo_inconsistencia TEXT NOT NULL, prioridade TEXT NOT NULL,
            nf_retorna TEXT NOT NULL, nome_parceiro TEXT NOT NULL, numero_nota TEXT NOT NULL,
            tipo_nota TEXT, data_entrada DATE, data_saida DATE, data_negociacao DATE,
            valor REAL NOT NULL, observacao TEXT, arquivo_nome TEXT, solicitante TEXT,
            status TEXT NOT NULL DEFAULT 'Aberto', aberto_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            atendido_em TIMESTAMP, resolvido_em TIMESTAMP, resolucao TEXT)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS competencias (
            id SERIAL PRIMARY KEY, mes_ano TEXT NOT NULL, ano INTEGER NOT NULL,
            mes INTEGER NOT NULL, criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS fechamentos (
            id SERIAL PRIMARY KEY, competencia_id INTEGER NOT NULL REFERENCES competencias(id) ON DELETE CASCADE,
            tipo TEXT NOT NULL CHECK(tipo IN ('Fechamento Parcial 1','Fechamento Parcial 2',
            'Fechamento Parcial 3','Fechamento Consolidado Corporativo')),
            data_fechamento DATE, hora_fechamento TEXT, periodo_inicio DATE, periodo_fim DATE,
            observacao TEXT, criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS mensagens (
            id SERIAL PRIMARY KEY, chamado_protocolo TEXT NOT NULL REFERENCES chamados(protocolo) ON DELETE CASCADE,
            autor TEXT NOT NULL, perfil TEXT NOT NULL, mensagem TEXT NOT NULL,
            enviado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

        for u in [
            ('Contabilidade','contabilidade','roc2024','contabilidade'),
            ('Adm Logistica King','adm.logistica.king','setor123','setor'),
            ('Administrativo','administrativo','setor123','setor'),
            ('Comercial','comercial','setor123','setor'),
            ('Compras','compras','setor123','setor'),
            ('Controladoria','controladoria','setor123','setor'),
            ('DP','dp','setor123','setor'),
            ('Financeiro','financeiro','setor123','setor'),
            ('Fiscal','fiscal','setor123','setor'),
            ('Logistica King','logistica.king','setor123','setor'),
            ('Logistica Pisa','logistica.pisa','setor123','setor'),
            ('Marketing','marketing','setor123','setor'),
        ]:
            cur.execute("INSERT INTO usuarios (nome,login,senha,perfil) VALUES (%s,%s,%s,%s) ON CONFLICT (login) DO NOTHING", u)

        for t in ['Descontabilização','Correção','Alteração Natureza','Abertura de Período',
                  'Folha de Pagamento','Nota Fiscal','Conciliação','Revisão',
                  'Livro Fiscal','Custo','Exclusão','Atraso fechamento']:
            cur.execute("INSERT INTO tipos_inconsistencia (nome) VALUES (%s) ON CONFLICT (nome) DO NOTHING", (t,))

        cal = {
            ("Janeiro/2026",1,2026):[("Fechamento Parcial 1","2026-01-16","12:00","2026-01-01","2026-01-14"),("Fechamento Parcial 2","2026-01-23","10:00","2026-01-15","2026-01-21"),("Fechamento Parcial 3","2026-01-29","10:00","2026-01-22","2026-01-27"),("Fechamento Consolidado Corporativo","2026-02-02","10:00","2026-01-28","2026-01-31")],
            ("Fevereiro/2026",2,2026):[("Fechamento Parcial 1","2026-02-13","12:00","2026-02-01","2026-02-11"),("Fechamento Parcial 2","2026-02-23","10:00","2026-02-12","2026-02-19"),("Fechamento Parcial 3","2026-02-26","10:00","2026-02-20","2026-02-24"),("Fechamento Consolidado Corporativo","2026-03-02","10:00","2026-02-25","2026-02-28")],
            ("Março/2026",3,2026):[("Fechamento Parcial 1","2026-03-17","12:00","2026-03-01","2026-03-15"),("Fechamento Parcial 2","2026-03-24","10:00","2026-03-16","2026-03-22"),("Fechamento Parcial 3","2026-03-30","10:00","2026-03-23","2026-03-26"),("Fechamento Consolidado Corporativo","2026-04-01","10:00","2026-03-27","2026-03-31")],
            ("Abril/2026",4,2026):[("Fechamento Parcial 1","2026-04-14","12:00","2026-04-01","2026-04-12"),("Fechamento Parcial 2","2026-04-22","10:00","2026-04-13","2026-04-19"),("Fechamento Parcial 3","2026-04-29","10:00","2026-04-20","2026-04-27"),("Fechamento Consolidado Corporativo","2026-05-04","10:00","2026-04-28","2026-04-30")],
            ("Maio/2026",5,2026):[("Fechamento Parcial 1","2026-05-14","12:00","2026-05-01","2026-05-12"),("Fechamento Parcial 2","2026-05-22","10:00","2026-05-13","2026-05-20"),("Fechamento Parcial 3","2026-05-28","10:00","2026-05-21","2026-05-26"),("Fechamento Consolidado Corporativo","2026-06-01","10:00","2026-05-27","2026-05-31")],
            ("Junho/2026",6,2026):[("Fechamento Parcial 1","2026-06-15","12:00","2026-06-01","2026-06-11"),("Fechamento Parcial 2","2026-06-23","10:00","2026-06-12","2026-06-21"),("Fechamento Parcial 3","2026-06-29","10:00","2026-06-22","2026-06-25"),("Fechamento Consolidado Corporativo","2026-07-01","10:00","2026-06-26","2026-06-30")],
            ("Julho/2026",7,2026):[("Fechamento Parcial 1","2026-07-16","12:00","2026-07-01","2026-07-14"),("Fechamento Parcial 2","2026-07-24","10:00","2026-07-15","2026-07-22"),("Fechamento Parcial 3","2026-07-30","10:00","2026-07-23","2026-07-28"),("Fechamento Consolidado Corporativo","2026-08-03","10:00","2026-07-29","2026-07-31")],
            ("Agosto/2026",8,2026):[("Fechamento Parcial 1","2026-08-13","12:00","2026-08-01","2026-08-11"),("Fechamento Parcial 2","2026-08-21","10:00","2026-08-12","2026-08-19"),("Fechamento Parcial 3","2026-08-28","10:00","2026-08-20","2026-08-26"),("Fechamento Consolidado Corporativo","2026-09-01","10:00","2026-08-27","2026-08-31")],
            ("Setembro/2026",9,2026):[("Fechamento Parcial 1","2026-09-15","12:00","2026-09-01","2026-09-13"),("Fechamento Parcial 2","2026-09-23","10:00","2026-09-14","2026-09-21"),("Fechamento Parcial 3","2026-09-29","10:00","2026-09-22","2026-09-25"),("Fechamento Consolidado Corporativo","2026-10-01","10:00","2026-09-26","2026-09-30")],
            ("Outubro/2026",10,2026):[("Fechamento Parcial 1","2026-10-16","12:00","2026-10-01","2026-10-12"),("Fechamento Parcial 2","2026-10-22","10:00","2026-10-13","2026-10-20"),("Fechamento Parcial 3","2026-10-29","10:00","2026-10-21","2026-10-27"),("Fechamento Consolidado Corporativo","2026-11-03","10:00","2026-10-28","2026-10-31")],
            ("Novembro/2026",11,2026):[("Fechamento Parcial 1","2026-11-16","12:00","2026-11-01","2026-11-13"),("Fechamento Parcial 2","2026-11-24","10:00","2026-11-14","2026-11-19"),("Fechamento Parcial 3","2026-11-27","10:00","2026-11-20","2026-11-25"),("Fechamento Consolidado Corporativo","2026-12-01","10:00","2026-11-26","2026-11-30")],
            ("Dezembro/2026",12,2026):[("Fechamento Parcial 1","2026-12-15","12:00","2026-12-01","2026-12-13"),("Fechamento Parcial 2","2026-12-23","10:00","2026-12-14","2026-12-21"),("Fechamento Parcial 3","2026-12-30","10:00","2026-12-22","2026-12-28"),("Fechamento Consolidado Corporativo","2027-01-04","10:00","2026-12-29","2026-12-31")],
        }
        for (mes_ano,mes,ano), fechs in cal.items():
            cur.execute("SELECT id FROM competencias WHERE mes_ano=%s", (mes_ano,))
            if not cur.fetchone():
                cur.execute("INSERT INTO competencias (mes_ano,ano,mes) VALUES (%s,%s,%s) RETURNING id", (mes_ano,ano,mes))
                comp_id = cur.fetchone()[0]
                for tipo,df,hf,pi,pf in fechs:
                    cur.execute("INSERT INTO fechamentos (competencia_id,tipo,data_fechamento,hora_fechamento,periodo_inicio,periodo_fim) VALUES (%s,%s,%s,%s,%s,%s)", (comp_id,tipo,df,hf,pi,pf))
        conn.commit()
    except:
        conn.rollback()
    finally:
        cur.close()
        conn.close()
