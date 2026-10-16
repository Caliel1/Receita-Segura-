"""1 — API de Autenticação: login, primeiro acesso do paciente, logout."""
import sqlite3
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ..database import get_db
from ..dependencias import agora_iso, dados_publicos, registrar_auditoria, usuario_logado
from ..seguranca import conferir_senha, gerar_hash_senha, gerar_token, sha256

router = APIRouter(prefix="/api/auth", tags=["1. Autenticação"])

DURACAO_SESSAO = timedelta(hours=8)
EMAIL_REGEX = r"^[^\s@]+@[^\s@]+\.[^\s@]+$"


class Login(BaseModel):
    email: str = Field(max_length=200)
    senha: str = Field(max_length=200)
    papel: str | None = Field(default=None, pattern="^(medico|paciente)$")


class Ativacao(BaseModel):
    codigo: str = Field(max_length=20)
    email: str = Field(max_length=200, pattern=EMAIL_REGEX)
    senha: str = Field(min_length=6, max_length=200)


def criar_sessao(db: sqlite3.Connection, usuario_id: int) -> str:
    token = gerar_token()
    expira = (datetime.now(timezone.utc) + DURACAO_SESSAO).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    db.execute("DELETE FROM sessoes WHERE expira_em < ?", (agora_iso(),))
    db.execute("INSERT INTO sessoes (token, usuario_id, expira_em) VALUES (?, ?, ?)", (sha256(token), usuario_id, expira))
    return token


@router.post("/login", summary="Entrar com e-mail e senha")
def login(dados: Login, request: Request, db: sqlite3.Connection = Depends(get_db)):
    email = dados.email.strip().lower()
    usuario = db.execute("SELECT * FROM usuarios WHERE email = ?", (email,)).fetchone()
    # Mesma mensagem para e-mail inexistente e senha errada: não revela quais e-mails existem.
    if not usuario or not conferir_senha(dados.senha, usuario["senha_hash"]) or (dados.papel and usuario["papel"] != dados.papel):
        registrar_auditoria(db, request, "login_falhou", usuario["id"] if usuario else None, detalhe=email)
        raise HTTPException(401, "E-mail ou senha incorretos.")
    registrar_auditoria(db, request, "login", usuario["id"])
    return {"token": criar_sessao(db, usuario["id"]), "usuario": dados_publicos(usuario)}


@router.post("/ativar", status_code=201, summary="Primeiro acesso do paciente com o código de convite")
def ativar(dados: Ativacao, request: Request, db: sqlite3.Connection = Depends(get_db)):
    codigo = dados.codigo.strip().upper()
    email = dados.email.strip().lower()
    paciente = db.execute(
        "SELECT * FROM usuarios WHERE codigo_convite = ? AND papel = 'paciente'", (codigo,)
    ).fetchone()
    if not paciente:
        raise HTTPException(400, "Código de convite inválido ou já utilizado.")
    if db.execute("SELECT 1 FROM usuarios WHERE email = ?", (email,)).fetchone():
        raise HTTPException(409, "Este e-mail já está em uso.")

    db.execute(
        "UPDATE usuarios SET email = ?, senha_hash = ?, codigo_convite = NULL WHERE id = ?",
        (email, gerar_hash_senha(dados.senha), paciente["id"]),
    )
    registrar_auditoria(db, request, "conta_ativada", paciente["id"])
    atualizado = db.execute("SELECT * FROM usuarios WHERE id = ?", (paciente["id"],)).fetchone()
    return {"token": criar_sessao(db, paciente["id"]), "usuario": dados_publicos(atualizado)}


@router.get("/eu", summary="Quem está logado")
def eu(usuario=Depends(usuario_logado)):
    return {"usuario": dados_publicos(usuario)}


@router.post("/logout", status_code=204, summary="Encerrar a sessão")
def logout(request: Request, usuario=Depends(usuario_logado), db: sqlite3.Connection = Depends(get_db)):
    token = request.headers["authorization"].split(" ", 1)[1]
    db.execute("DELETE FROM sessoes WHERE token = ?", (sha256(token),))
    registrar_auditoria(db, request, "logout", usuario["id"])
