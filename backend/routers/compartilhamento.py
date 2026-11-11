"""10 — API de Compartilhamento: link temporário para a farmácia ver a receita completa."""
import sqlite3
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ..database import get_db, transacao
from ..dependencias import agora_iso, registrar_auditoria, usuario_logado
from ..receitas_servico import formatar, receita_do_usuario, verificar
from ..seguranca import gerar_token, sha256
from .pdf import resposta_pdf

router = APIRouter(prefix="/api/compartilhamentos", tags=["10. Compartilhamento"])


class NovoCompartilhamento(BaseModel):
    codigo: str = Field(max_length=20)
    horas: int = Field(default=24, ge=1, le=168)


def compartilhamento_valido(db: sqlite3.Connection, token: str) -> sqlite3.Row:
    linha = db.execute(
        """SELECT c.*, r.codigo FROM compartilhamentos c JOIN receitas r ON r.id = c.receita_id
           WHERE c.token_hash = ? AND c.revogado = 0 AND c.expira_em > ?""",
        (sha256(token), agora_iso()),
    ).fetchone()
    if not linha:
        raise HTTPException(404, "Link inválido, expirado ou revogado.")
    return linha


@router.post("", status_code=201, summary="Criar link de compartilhamento de uma receita")
def criar(dados: NovoCompartilhamento, request: Request, usuario=Depends(usuario_logado),
          db: sqlite3.Connection = Depends(get_db)):
    receita = receita_do_usuario(db, dados.codigo, usuario)
    if receita["status"] != "ativa":
        raise HTTPException(400, f"Esta receita está {receita['status']} e não pode ser compartilhada.")
    token = gerar_token()
    expira = (datetime.now(timezone.utc) + timedelta(hours=dados.horas)).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    cursor = db.execute(
        "INSERT INTO compartilhamentos (token_hash, receita_id, criado_por, criado_em, expira_em) VALUES (?, ?, ?, ?, ?)",
        (sha256(token), receita["id"], usuario["id"], agora_iso(), expira),
    )
    registrar_auditoria(db, request, "compartilhamento_criado", usuario["id"], receita["codigo"], f"{dados.horas}h")
    # O token só aparece aqui, uma vez. No banco fica só o hash dele.
    return {"id": cursor.lastrowid, "token": token, "url": f"{str(request.base_url).rstrip('/')}/?c={token}",
            "expiraEm": expira}


@router.get("", summary="Listar links que criei")
def listar(usuario=Depends(usuario_logado), db: sqlite3.Connection = Depends(get_db)):
    linhas = db.execute(
        """SELECT c.id, r.codigo, c.criado_em, c.expira_em, c.acessos, c.revogado
           FROM compartilhamentos c JOIN receitas r ON r.id = c.receita_id
           WHERE c.criado_por = ? ORDER BY c.id DESC""",
        (usuario["id"],),
    ).fetchall()
    agora = agora_iso()
    return {"compartilhamentos": [{
        "id": l["id"], "codigo": l["codigo"], "criadoEm": l["criado_em"], "expiraEm": l["expira_em"],
        "acessos": l["acessos"], "ativo": not l["revogado"] and l["expira_em"] > agora,
    } for l in linhas]}


@router.delete("/{compartilhamento_id}", status_code=204, summary="Revogar um link")
def revogar(compartilhamento_id: int, request: Request, usuario=Depends(usuario_logado),
            db: sqlite3.Connection = Depends(get_db)):
    linha = db.execute(
        """SELECT c.id, r.codigo FROM compartilhamentos c JOIN receitas r ON r.id = c.receita_id
           WHERE c.id = ? AND c.criado_por = ?""",
        (compartilhamento_id, usuario["id"]),
    ).fetchone()
    if not linha:
        raise HTTPException(404, "Compartilhamento não encontrado.")
    db.execute("UPDATE compartilhamentos SET revogado = 1 WHERE id = ?", (linha["id"],))
    registrar_auditoria(db, request, "compartilhamento_revogado", usuario["id"], linha["codigo"])


@router.get("/acesso/{token}", summary="Abrir receita compartilhada (público, com o token do link)")
def acessar(token: str, request: Request, db: sqlite3.Connection = Depends(get_db)):
    comp = compartilhamento_valido(db, token)
    db.execute("UPDATE compartilhamentos SET acessos = acessos + 1 WHERE id = ?", (comp["id"],))
    registrar_auditoria(db, request, "compartilhamento_acessado", receita_codigo=comp["codigo"])
    linha = db.execute("SELECT * FROM receitas WHERE id = ?", (comp["receita_id"],)).fetchone()
    return {"receita": formatar(linha), "verificacao": verificar(db, comp["codigo"]), "expiraEm": comp["expira_em"]}


@router.get("/acesso/{token}/pdf", summary="PDF da receita compartilhada", response_class=Response)
def acessar_pdf(token: str, request: Request, db: sqlite3.Connection = Depends(get_db)):
    comp = compartilhamento_valido(db, token)
    linha = db.execute("SELECT * FROM receitas WHERE id = ?", (comp["receita_id"],)).fetchone()
    registrar_auditoria(db, request, "pdf_gerado", receita_codigo=comp["codigo"], detalhe="via link compartilhado")
    return resposta_pdf(formatar(linha), linha["assinatura"], request)


@router.post("/acesso/{token}/dispensar", summary="Farmácia registra que entregou os medicamentos")
def dispensar(token: str, request: Request, db: sqlite3.Connection = Depends(get_db)):
    """Marca a receita como dispensada: evita que a mesma receita seja usada duas vezes."""
    comp = compartilhamento_valido(db, token)
    with transacao(db):
        linha = db.execute("SELECT * FROM receitas WHERE id = ?", (comp["receita_id"],)).fetchone()
        if linha["status"] != "ativa":
            raise HTTPException(409, f"Esta receita já está {linha['status']}.")
        if not verificar(db, linha["codigo"])["valida"]:
            raise HTTPException(409, "Assinatura inválida — não dispense esta receita.")
        db.execute(
            "UPDATE receitas SET status = 'dispensada', status_motivo = 'Dispensada pela farmácia', status_em = ? WHERE id = ?",
            (agora_iso(), linha["id"]),
        )
        db.execute("UPDATE compartilhamentos SET revogado = 1 WHERE receita_id = ?", (linha["id"],))
    registrar_auditoria(db, request, "receita_dispensada", receita_codigo=linha["codigo"])
    return {"receita": formatar(db.execute("SELECT * FROM receitas WHERE id = ?", (linha["id"],)).fetchone())}
