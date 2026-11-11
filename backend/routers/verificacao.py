"""7 — API de Verificação: pública, para a farmácia conferir se a receita é autêntica."""
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request

from ..database import get_db
from ..dependencias import registrar_auditoria
from ..receitas_servico import verificar

router = APIRouter(prefix="/api/verificar", tags=["7. Verificação"])


@router.get("/{codigo}", summary="Verificar autenticidade de uma receita (não expõe medicamentos nem paciente)")
def verificar_receita(codigo: str, request: Request, db: sqlite3.Connection = Depends(get_db)):
    resultado = verificar(db, codigo)
    if not resultado:
        raise HTTPException(404, "Receita não encontrada.")
    registrar_auditoria(db, request, "receita_verificada", receita_codigo=resultado["codigo"],
                        detalhe="válida" if resultado["valida"] else "INVÁLIDA")
    return resultado
