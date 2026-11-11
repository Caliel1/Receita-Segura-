"""6 — API de Assinatura/Integridade: expõe os dados criptográficos para conferência independente."""
import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from ..database import get_db
from ..dependencias import exigir_medico, usuario_logado
from ..receitas_servico import receita_do_usuario, verificar
from ..seguranca import conferir_assinatura, sha256

router = APIRouter(prefix="/api/assinatura", tags=["6. Assinatura / Integridade"])


@router.get("/chaves/{medico_id}", summary="Chave pública de um médico (pública)")
def chave_publica(medico_id: int, db: sqlite3.Connection = Depends(get_db)):
    medico = db.execute(
        "SELECT id, nome, crm, chave_publica FROM usuarios WHERE id = ? AND papel = 'medico'", (medico_id,)
    ).fetchone()
    if not medico:
        raise HTTPException(404, "Médico não encontrado.")
    return {"medicoId": medico["id"], "nome": medico["nome"], "crm": medico["crm"],
            "algoritmo": "Ed25519", "chavePublica": medico["chave_publica"]}


@router.get("/receitas/{codigo}", summary="Pacote de assinatura de uma receita (conteúdo exato, hash e assinatura)")
def pacote(codigo: str, usuario=Depends(usuario_logado), db: sqlite3.Connection = Depends(get_db)):
    """Com isso, qualquer ferramenta externa (OpenSSL, Python...) pode conferir a assinatura sem confiar no servidor."""
    linha = receita_do_usuario(db, codigo, usuario)
    return {
        "codigo": linha["codigo"],
        "algoritmoHash": "SHA-256",
        "algoritmoAssinatura": "Ed25519",
        "conteudoCanonico": linha["conteudo"],
        "hash": linha["hash"],
        "assinatura": linha["assinatura"],
        "chavePublicaUrl": f"/api/assinatura/chaves/{linha['medico_id']}",
    }


@router.get("/integridade", summary="Checa a integridade de todas as receitas que emiti")
def integridade(medico=Depends(exigir_medico), db: sqlite3.Connection = Depends(get_db)):
    codigos = [l["codigo"] for l in db.execute(
        "SELECT codigo FROM receitas WHERE medico_id = ? ORDER BY id", (medico["id"],)
    ).fetchall()]
    resultados = [verificar(db, c) for c in codigos]
    invalidas = [r["codigo"] for r in resultados if not r["valida"]]
    return {"total": len(resultados), "validas": len(resultados) - len(invalidas), "invalidas": invalidas}


@router.post("/conferir", summary="Confere um conteúdo + assinatura qualquer contra a chave de um médico")
def conferir(dados: dict, db: sqlite3.Connection = Depends(get_db)):
    """Recebe {medicoId, conteudo, assinatura}. Útil para demonstrar que mudar 1 caractere invalida tudo."""
    medico = db.execute("SELECT chave_publica FROM usuarios WHERE id = ? AND papel = 'medico'",
                        (dados.get("medicoId"),)).fetchone()
    conteudo, assinatura = dados.get("conteudo"), dados.get("assinatura")
    if not medico or not isinstance(conteudo, str) or not isinstance(assinatura, str):
        raise HTTPException(400, "Envie medicoId, conteudo e assinatura.")
    return {"hash": sha256(conteudo), "assinaturaConfere": conferir_assinatura(conteudo, assinatura, medico["chave_publica"])}
