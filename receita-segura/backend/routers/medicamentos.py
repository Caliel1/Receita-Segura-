"""5 — API de Medicamentos: catálogo para busca e autocompletar na prescrição."""
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query

from ..database import get_db
from ..dependencias import usuario_logado

router = APIRouter(prefix="/api/medicamentos", tags=["5. Medicamentos"])


def formatar(l: sqlite3.Row) -> dict:
    return {
        "id": l["id"], "nome": l["nome"], "classe": l["classe"],
        "posologiaSugerida": l["posologia_sugerida"], "controlado": bool(l["controlado"]),
    }


@router.get("", summary="Buscar medicamentos pelo nome ou classe")
def buscar(busca: str = Query(default="", max_length=60), limite: int = Query(default=20, ge=1, le=100),
           _=Depends(usuario_logado), db: sqlite3.Connection = Depends(get_db)):
    termo = f"%{busca.strip()}%"
    linhas = db.execute(
        "SELECT * FROM medicamentos WHERE nome LIKE ? OR classe LIKE ? ORDER BY nome LIMIT ?",
        (termo, termo, limite),
    ).fetchall()
    return {"medicamentos": [formatar(l) for l in linhas]}


@router.get("/{medicamento_id}", summary="Detalhe de um medicamento")
def detalhe(medicamento_id: int, _=Depends(usuario_logado), db: sqlite3.Connection = Depends(get_db)):
    linha = db.execute("SELECT * FROM medicamentos WHERE id = ?", (medicamento_id,)).fetchone()
    if not linha:
        raise HTTPException(404, "Medicamento não encontrado.")
    return {"medicamento": formatar(linha)}
