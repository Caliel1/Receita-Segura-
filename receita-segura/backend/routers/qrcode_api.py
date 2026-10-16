"""8 — API de QR Code: imagem que leva direto à página de verificação da receita."""
import io
import sqlite3

import qrcode
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from ..database import get_db
from ..receitas_servico import buscar_linha

router = APIRouter(prefix="/api/qrcode", tags=["8. QR Code"])


def url_verificacao(request: Request, codigo: str) -> str:
    return f"{str(request.base_url).rstrip('/')}/?verificar={codigo}"


def gerar_png(texto: str) -> bytes:
    imagem = qrcode.make(texto, box_size=8, border=2)
    buffer = io.BytesIO()
    imagem.save(buffer, format="PNG")
    return buffer.getvalue()


@router.get("/{codigo}.png", summary="QR Code (PNG) de verificação da receita",
            responses={200: {"content": {"image/png": {}}}}, response_class=Response)
def qrcode_png(codigo: str, request: Request, db: sqlite3.Connection = Depends(get_db)):
    # O QR só contém o link de verificação pública — nenhum dado de saúde.
    linha = buscar_linha(db, codigo)
    if not linha:
        raise HTTPException(404, "Receita não encontrada.")
    png = gerar_png(url_verificacao(request, linha["codigo"]))
    return Response(png, media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})
