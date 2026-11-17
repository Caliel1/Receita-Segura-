"""7 — API de Verificação: pública, para a farmácia conferir se a receita é autêntica."""

from fastapi import APIRouter, Depends, HTTPException, Request

from ..database import Conexao, get_db
from ..dependencias import registrar_auditoria
from ..documentos_servico import verificar as verificar_documento
from ..receitas_servico import verificar

router = APIRouter(prefix="/api/verificar", tags=["7. Verificação"])


@router.get("/{codigo}", summary="Verificar autenticidade de uma receita ou documento (não expõe dados clínicos nem do paciente)")
def verificar_receita(codigo: str, request: Request, db: Conexao = Depends(get_db)):
    resultado = verificar(db, codigo) or verificar_documento(db, codigo)
    if not resultado:
        raise HTTPException(404, "Documento não encontrado.")
    acao = "receita_verificada" if resultado["tipo"] == "receita" else "documento_verificado"
    registrar_auditoria(db, request, acao, receita_codigo=resultado["codigo"],
                        detalhe="válida" if resultado["valida"] else "INVÁLIDA")
    return resultado
