-- =============================================
-- RO - Registro de Ocorrências
-- Estrutura do banco de dados
-- =============================================

-- USUÁRIOS
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    login TEXT NOT NULL UNIQUE,
    senha TEXT NOT NULL,
    perfil TEXT NOT NULL CHECK(perfil IN ('contabilidade', 'setor')),
    ativo INTEGER DEFAULT 1,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- TIPOS DE INCONSISTÊNCIA (gerenciado pela contabilidade)
CREATE TABLE IF NOT EXISTS tipos_inconsistencia (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL UNIQUE,
    ativo INTEGER DEFAULT 1
);

-- MOTIVOS (gerenciado pela contabilidade)
CREATE TABLE IF NOT EXISTS motivos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL UNIQUE,
    ativo INTEGER DEFAULT 1
);

-- CHAMADOS
CREATE TABLE IF NOT EXISTS chamados (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    protocolo TEXT NOT NULL UNIQUE,
    setor TEXT NOT NULL,
    empresa TEXT NOT NULL CHECK(empresa IN ('1','2','6','13','14')),
    tipo_inconsistencia TEXT NOT NULL,
    motivo TEXT NOT NULL,
    prioridade TEXT NOT NULL CHECK(prioridade IN ('Normal','Urgente')),
    nf_retorna TEXT NOT NULL CHECK(nf_retorna IN ('Retornará','Não retornará')),
    nome_parceiro TEXT NOT NULL,
    numero_nota TEXT NOT NULL,
    competencia TEXT NOT NULL,
    data_entrada DATE,
    tipo_nota TEXT CHECK(tipo_nota IN ('Compra','Venda')),
    data_saida DATE,
    data_negociacao DATE,
    valor REAL NOT NULL,
    observacao TEXT,
    arquivo_nome TEXT,
    status TEXT NOT NULL DEFAULT 'Aberto' CHECK(status IN ('Aberto','Em andamento','Resolvido','Cancelado')),
    aberto_em DATETIME DEFAULT CURRENT_TIMESTAMP,
    atendido_em DATETIME,
    resolvido_em DATETIME,
    resolucao TEXT
);

-- CALENDÁRIO DE FECHAMENTO
CREATE TABLE IF NOT EXISTS calendario_fechamento (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mes_ano TEXT NOT NULL,
    importacao_1 DATE,
    importacao_2 DATE,
    importacao_3 DATE,
    fechamento DATE,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- =============================================
-- DADOS INICIAIS
-- =============================================

-- Usuário contabilidade
INSERT OR IGNORE INTO usuarios (nome, login, senha, perfil)
VALUES ('Contabilidade', 'contabilidade', 'roc2024', 'contabilidade');

-- Setores
INSERT OR IGNORE INTO usuarios (nome, login, senha, perfil) VALUES ('Adm Logistica King','adm.logistica.king','setor123','setor');
INSERT OR IGNORE INTO usuarios (nome, login, senha, perfil) VALUES ('Administrativo','administrativo','setor123','setor');
INSERT OR IGNORE INTO usuarios (nome, login, senha, perfil) VALUES ('Comercial','comercial','setor123','setor');
INSERT OR IGNORE INTO usuarios (nome, login, senha, perfil) VALUES ('Compras','compras','setor123','setor');
INSERT OR IGNORE INTO usuarios (nome, login, senha, perfil) VALUES ('Controladoria','controladoria','setor123','setor');
INSERT OR IGNORE INTO usuarios (nome, login, senha, perfil) VALUES ('DP','dp','setor123','setor');
INSERT OR IGNORE INTO usuarios (nome, login, senha, perfil) VALUES ('Financeiro','financeiro','setor123','setor');
INSERT OR IGNORE INTO usuarios (nome, login, senha, perfil) VALUES ('Fiscal','fiscal','setor123','setor');
INSERT OR IGNORE INTO usuarios (nome, login, senha, perfil) VALUES ('Logistica King','logistica.king','setor123','setor');
INSERT OR IGNORE INTO usuarios (nome, login, senha, perfil) VALUES ('Logistica Pisa','logistica.pisa','setor123','setor');
INSERT OR IGNORE INTO usuarios (nome, login, senha, perfil) VALUES ('Marketing','marketing','setor123','setor');

-- Tipos de inconsistência
INSERT OR IGNORE INTO tipos_inconsistencia (nome) VALUES ('Descontabilização');
INSERT OR IGNORE INTO tipos_inconsistencia (nome) VALUES ('Correção');
INSERT OR IGNORE INTO tipos_inconsistencia (nome) VALUES ('Alteração Natureza');
INSERT OR IGNORE INTO tipos_inconsistencia (nome) VALUES ('Abertura de Período');
INSERT OR IGNORE INTO tipos_inconsistencia (nome) VALUES ('Folha de Pagamento');
INSERT OR IGNORE INTO tipos_inconsistencia (nome) VALUES ('Nota Fiscal');
INSERT OR IGNORE INTO tipos_inconsistencia (nome) VALUES ('Conciliação');
INSERT OR IGNORE INTO tipos_inconsistencia (nome) VALUES ('Revisão');
INSERT OR IGNORE INTO tipos_inconsistencia (nome) VALUES ('Livro Fiscal');
INSERT OR IGNORE INTO tipos_inconsistencia (nome) VALUES ('Custo');
INSERT OR IGNORE INTO tipos_inconsistencia (nome) VALUES ('Exclusão');
INSERT OR IGNORE INTO tipos_inconsistencia (nome) VALUES ('Atraso fechamento');

-- Motivos
INSERT OR IGNORE INTO motivos (nome) VALUES ('Parceiro incorreto');
INSERT OR IGNORE INTO motivos (nome) VALUES ('Valor incorreto');
INSERT OR IGNORE INTO motivos (nome) VALUES ('Documento fora do prazo');
INSERT OR IGNORE INTO motivos (nome) VALUES ('Divergência de XML');
INSERT OR IGNORE INTO motivos (nome) VALUES ('Duplicidade');
INSERT OR IGNORE INTO motivos (nome) VALUES ('Erro de importação');
