"""Dependências compartilhadas: usuário logado, controle de papel e auditoria."""
import sqlite3
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .database import get_db
from .seguranca import sha256

bearer = HTTPBearer(auto_error=False)


def agora_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def usuario_logado(
    credenciais: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: sqlite3.Connection = Depends(get_db),
) -> sqlite3.Row:
    usuario = None
    if credenciais:
        usuario = db.execute(
            """SELECT u.* FROM sessoes s JOIN usuarios u ON u.id = s.usuario_id
               WHERE s.token = ? AND s.expira_em > ?""",
            (sha256(credenciais.credentials), agora_iso()),
        ).fetchone()
    if not usuario:
        raise HTTPException(401, "Sessão inválida ou expirada. Faça login novamente.")
    return usuario


def exigir_medico(usuario=Depends(usuario_logado)):
    if usuario["papel"] != "medico":
        raise HTTPException(403, "Acesso permitido apenas para médicos.")
    return usuario


def exigir_paciente(usuario=Depends(usuario_logado)):
    if usuario["papel"] != "paciente":
        raise HTTPException(403, "Acesso permitido apenas para pacientes.")
    return usuario


def dados_publicos(u: sqlite3.Row) -> dict:
    """Só o que pode ir para o navegador (nunca senha nem chave privada)."""
    return {
        "id": u["id"], "papel": u["papel"], "nome": u["nome"], "email": u["email"],
        "crm": u["crm"], "especialidade": u["especialidade"],
    }


def registrar_auditoria(db: sqlite3.Connection, request: Request | None, acao: str,
                        usuario_id: int | None = None, receita_codigo: str | None = None,
                        detalhe: str | None = None) -> None:
    ip = request.client.host if request and request.client else None
    db.execute(
        "INSERT INTO auditoria (quando, usuario_id, acao, receita_codigo, detalhe, ip) VALUES (?, ?, ?, ?, ?, ?)",
        (agora_iso(), usuario_id, acao, receita_codigo, detalhe, ip),
    )
