"""Receita Segura — servidor FastAPI: as 13 APIs internas + os arquivos do site (PWA)."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from .database import RAIZ, criar_tabelas
from .routers import (assinatura, auditoria, autenticacao, compartilhamento, historico, medicamentos,
                      pacientes, pdf, qrcode_api, receitas, status, usuarios, verificacao)
from .seed import popular_se_vazio


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    criar_tabelas()
    popular_se_vazio()
    yield


app = FastAPI(
    title="Receita Segura — API",
    description="Receitas médicas assinadas digitalmente (Ed25519 + SHA-256). Projeto acadêmico — UNAMA.",
    version=status.VERSAO,
    lifespan=ciclo_de_vida,
)

for modulo in (autenticacao, usuarios, pacientes, receitas, medicamentos, assinatura, verificacao,
               qrcode_api, pdf, compartilhamento, historico, auditoria, status):
    app.include_router(modulo.router)


# ---------- Erros sempre no formato {"erro": "..."} que o front-end espera ----------

@app.exception_handler(StarletteHTTPException)
async def erro_http(request: Request, exc: StarletteHTTPException):
    mensagem = exc.detail if isinstance(exc.detail, str) else "Requisição inválida."
    if exc.status_code == 404 and mensagem == "Not Found":
        mensagem = "Rota não encontrada."
    return JSONResponse({"erro": mensagem}, status_code=exc.status_code, headers=getattr(exc, "headers", None))


@app.exception_handler(RequestValidationError)
async def erro_validacao(request: Request, exc: RequestValidationError):
    primeiro = exc.errors()[0] if exc.errors() else {}
    campo = ".".join(str(p) for p in primeiro.get("loc", [])[1:]) or "corpo"
    return JSONResponse({"erro": f"Dado inválido no campo '{campo}'.", "detalhes": jsonable(exc.errors())},
                        status_code=422)


def jsonable(erros):
    return [{"campo": ".".join(str(p) for p in e.get("loc", [])), "mensagem": e.get("msg")} for e in erros]


# ---------- Site estático (PWA) ----------
# Só as pastas públicas — nunca a raiz inteira, senão /data (banco) e /backend ficariam expostos.

for pasta in ("css", "js", "assets"):
    app.mount(f"/{pasta}", StaticFiles(directory=RAIZ / pasta), name=pasta)


@app.get("/", include_in_schema=False)
def pagina_inicial():
    return FileResponse(RAIZ / "index.html")


@app.get("/manifest.webmanifest", include_in_schema=False)
def manifesto():
    return FileResponse(RAIZ / "manifest.webmanifest", media_type="application/manifest+json")


@app.get("/service-worker.js", include_in_schema=False)
def service_worker():
    # Servido na raiz para poder controlar o site inteiro.
    return FileResponse(RAIZ / "service-worker.js", media_type="text/javascript",
                        headers={"Cache-Control": "no-cache"})
