"""11 — API de Histórico: linha do tempo e resumo das receitas."""
import json
import sqlite3
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException

from ..database import get_db
from ..dependencias import exigir_medico, usuario_logado
from ..receitas_servico import formatar

router = APIRouter(prefix="/api/historico", tags=["11. Histórico"])


def montar_historico(linhas: list[sqlite3.Row]) -> dict:
    receitas = [formatar(l) for l in linhas]
    contagem = Counter(m["nome"] for r in receitas for m in r["medicamentos"])
    por_mes: dict[str, list] = {}
    for r in receitas:
        por_mes.setdefault(r["emitidaEm"][:7], []).append(
            {"codigo": r["id"], "emitidaEm": r["emitidaEm"], "medico": r["medico"], "paciente": r["paciente"],
             "status": r["status"], "medicamentos": [m["nome"] for m in r["medicamentos"]]}
        )
    return {
        "resumo": {
            "total": len(receitas),
            "ativas": sum(r["status"] == "ativa" for r in receitas),
            "dispensadas": sum(r["status"] == "dispensada" for r in receitas),
            "canceladas": sum(r["status"] == "cancelada" for r in receitas),
            "primeira": receitas[-1]["emitidaEm"] if receitas else None,
            "ultima": receitas[0]["emitidaEm"] if receitas else None,
        },
        "medicamentosMaisFrequentes": [{"nome": n, "vezes": v} for n, v in contagem.most_common(5)],
        "linhaDoTempo": [{"mes": mes, "receitas": itens} for mes, itens in por_mes.items()],
    }


@router.get("", summary="Meu histórico (médico: o que emiti; paciente: o que recebi)")
def meu_historico(usuario=Depends(usuario_logado), db: sqlite3.Connection = Depends(get_db)):
    coluna = "medico_id" if usuario["papel"] == "medico" else "paciente_id"
    linhas = db.execute(f"SELECT * FROM receitas WHERE {coluna} = ? ORDER BY emitida_em DESC", (usuario["id"],)).fetchall()
    return montar_historico(linhas)


@router.get("/pacientes/{paciente_id}", summary="Histórico de um paciente meu (receitas que eu emiti para ele)")
def historico_paciente(paciente_id: int, medico=Depends(exigir_medico), db: sqlite3.Connection = Depends(get_db)):
    if not db.execute("SELECT 1 FROM medico_pacientes WHERE medico_id = ? AND paciente_id = ?",
                      (medico["id"], paciente_id)).fetchone():
        raise HTTPException(404, "Paciente não encontrado na sua lista.")
    linhas = db.execute(
        "SELECT * FROM receitas WHERE medico_id = ? AND paciente_id = ? ORDER BY emitida_em DESC",
        (medico["id"], paciente_id),
    ).fetchall()
    return montar_historico(linhas)
