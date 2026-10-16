"""Conexão com o banco SQLite e criação das tabelas."""
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CAMINHO_BANCO = Path(os.environ.get("DB_PATH", RAIZ / "data" / "receita-segura.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    papel          TEXT NOT NULL CHECK (papel IN ('medico', 'paciente')),
    nome           TEXT NOT NULL,
    email          TEXT UNIQUE,
    senha_hash     TEXT,              -- NULL = paciente cadastrado pelo médico que ainda não criou senha
    crm            TEXT,
    especialidade  TEXT,
    chave_publica  TEXT,              -- só médicos
    chave_privada  TEXT,              -- só médicos (em produção ficaria num cofre/HSM, nunca no banco)
    codigo_convite TEXT UNIQUE,       -- código que o médico entrega ao paciente para ele criar a senha
    criado_em      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sessoes (
    token      TEXT PRIMARY KEY,      -- guardamos o SHA-256 do token, nunca o token em si
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    expira_em  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS medico_pacientes (
    medico_id          INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    paciente_id        INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    ultimo_atendimento TEXT,
    PRIMARY KEY (medico_id, paciente_id)
);

CREATE TABLE IF NOT EXISTS medicamentos (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    nome               TEXT NOT NULL UNIQUE,   -- ex.: Amoxicilina 500mg
    classe             TEXT NOT NULL,          -- ex.: Antibiótico
    posologia_sugerida TEXT NOT NULL,
    controlado         INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS receitas (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo       TEXT NOT NULL UNIQUE,   -- ex.: RS-2299
    medico_id    INTEGER NOT NULL REFERENCES usuarios(id),
    paciente_id  INTEGER NOT NULL REFERENCES usuarios(id),
    conteudo     TEXT NOT NULL,          -- JSON canônico exatamente como foi assinado
    hash         TEXT NOT NULL,          -- SHA-256 do conteúdo
    assinatura   TEXT NOT NULL,          -- Ed25519 (base64) do conteúdo
    emitida_em   TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'ativa' CHECK (status IN ('ativa', 'cancelada', 'dispensada')),
    status_motivo TEXT,
    status_em    TEXT
);

CREATE TABLE IF NOT EXISTS compartilhamentos (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    token_hash    TEXT NOT NULL UNIQUE,  -- SHA-256 do token do link
    receita_id    INTEGER NOT NULL REFERENCES receitas(id) ON DELETE CASCADE,
    criado_por    INTEGER NOT NULL REFERENCES usuarios(id),
    criado_em     TEXT NOT NULL,
    expira_em     TEXT NOT NULL,
    acessos       INTEGER NOT NULL DEFAULT 0,
    revogado      INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS auditoria (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    quando         TEXT NOT NULL,
    usuario_id     INTEGER REFERENCES usuarios(id),   -- NULL = acesso público (ex.: farmácia)
    acao           TEXT NOT NULL,
    receita_codigo TEXT,
    detalhe        TEXT,
    ip             TEXT
);
CREATE INDEX IF NOT EXISTS idx_auditoria_receita ON auditoria (receita_codigo);
CREATE INDEX IF NOT EXISTS idx_auditoria_usuario ON auditoria (usuario_id);
"""


def conectar() -> sqlite3.Connection:
    CAMINHO_BANCO.parent.mkdir(parents=True, exist_ok=True)
    # isolation_level=None = autocommit; transações explícitas com transacao()
    con = sqlite3.connect(CAMINHO_BANCO, isolation_level=None, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def get_db():
    """Dependência do FastAPI: uma conexão por requisição."""
    con = conectar()
    try:
        yield con
    finally:
        con.close()


@contextmanager
def transacao(con: sqlite3.Connection):
    con.execute("BEGIN IMMEDIATE")
    try:
        yield
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise


def criar_tabelas() -> None:
    con = conectar()
    con.execute("PRAGMA journal_mode = WAL")
    con.executescript(SCHEMA)
    con.close()
