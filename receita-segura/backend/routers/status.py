"""13 — API de Status: saúde do sistema e status das receitas (ativa, dispensada, cancelada)."""
import sqlite3
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ..database import get_db
from ..dependencias import agora_iso, exigir_medico, registrar_auditoria
from ..receitas_servico import buscar_linha, formatar

router = APIRouter(prefix="/api/status", tags=["13. Status"])

INICIO = time.time()
VERSAO = "2.0.0"


class Cancelamento(BaseModel):
    motivo: str = Field(min_length=3, max_length=300)


@router.get("", summary="Saúde do sistema (servidor e banco)")
def status_sistema(db: sqlite3.Connection = Depends(get_db)):
    try:
        contagem = db.execute("""
            SELECT (SELECT COUNT(*) FROM usuarios WHERE papel = 'medico')   AS medicos,
                   (SELECT COUNT(*) FROM usuarios WHERE papel = 'paciente') AS pacientes,
                   (SELECT COUNT(*) FROM receitas)                          AS receitas
        """).fetchone()
        banco = "ok"
    except sqlite3.Error:
        contagem, banco = None, "erro"
    return {
        "status": "ok" if banco == "ok" else "degradado",
        "versao": VERSAO,
        "horaServidor": agora_iso(),
        "tempoOnlineSegundos": int(time.time() - INICIO),
        "banco": banco,
        "totais": dict(contagem) if contagem else None,
    }


@router.get("/receitas/{codigo}", summary="Status atual de uma receita (público)")
def status_receita(codigo: str, db: sqlite3.Connection = Depends(get_db)):
    linha = buscar_linha(db, codigo)
    if not linha:
        raise HTTPException(404, "Receita não encontrada.")
    return {"codigo": linha["codigo"], "status": linha["status"], "motivo": linha["status_motivo"], "desde": linha["status_em"]}


@router.post("/receitas/{codigo}/cancelar", summary="Médico cancela uma receita que emitiu")
def cancelar(codigo: str, dados: Cancelamento, request: Request, medico=Depends(exigir_medico),
             db: sqlite3.Connection = Depends(get_db)):
    # O status fica fora do conteúdo assinado: cancelar não "quebra" a assinatura, só marca a receita como inutilizável.
    linha = buscar_linha(db, codigo)
    if not linha or linha["medico_id"] != medico["id"]:
        raise HTTPException(404, "Receita não encontrada.")
    if linha["status"] != "ativa":
        raise HTTPException(409, f"Esta receita já está {linha['status']}.")
    db.execute("UPDATE receitas SET status = 'cancelada', status_motivo = ?, status_em = ? WHERE id = ?",
               (dados.motivo.strip(), agora_iso(), linha["id"]))
    db.execute("UPDATE compartilhamentos SET revogado = 1 WHERE receita_id = ?", (linha["id"],))
    registrar_auditoria(db, request, "receita_cancelada", medico["id"], linha["codigo"], dados.motivo.strip())
    return {"receita": formatar(buscar_linha(db, codigo))}
