"""4 — API de Receitas: emitir (já assinada), listar e ver detalhe."""
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ..database import get_db
from ..dependencias import exigir_medico, registrar_auditoria, usuario_logado
from ..receitas_servico import emitir_receita, formatar, receita_do_usuario

router = APIRouter(prefix="/api/receitas", tags=["4. Receitas"])


class ItemMedicamento(BaseModel):
    nome: str = Field(min_length=1, max_length=200)
    posologia: str = Field(min_length=1, max_length=200)


class NovaReceita(BaseModel):
    pacienteId: int
    medicamentos: list[ItemMedicamento] = Field(min_length=1, max_length=20)
    orientacoes: str = Field(default="", max_length=1000)


@router.get("", summary="Minhas receitas (emitidas, se médico; recebidas, se paciente)")
def listar(usuario=Depends(usuario_logado), db: sqlite3.Connection = Depends(get_db)):
    coluna = "medico_id" if usuario["papel"] == "medico" else "paciente_id"
    linhas = db.execute(f"SELECT * FROM receitas WHERE {coluna} = ? ORDER BY id DESC", (usuario["id"],)).fetchall()
    return {"receitas": [formatar(l) for l in linhas]}


@router.post("", status_code=201, summary="Emitir e assinar digitalmente uma receita")
def emitir(dados: NovaReceita, request: Request, medico=Depends(exigir_medico),
           db: sqlite3.Connection = Depends(get_db)):
    vinculado = db.execute(
        "SELECT 1 FROM medico_pacientes WHERE medico_id = ? AND paciente_id = ?", (medico["id"], dados.pacienteId)
    ).fetchone()
    if not vinculado:
        raise HTTPException(400, "Selecione um paciente da sua lista.")

    medicamentos = [{"nome": m.nome.strip(), "posologia": m.posologia.strip()} for m in dados.medicamentos]
    receita = emitir_receita(db, medico["id"], dados.pacienteId, medicamentos, dados.orientacoes.strip())
    registrar_auditoria(db, request, "receita_emitida", medico["id"], receita["id"])
    return {"receita": receita}


@router.get("/{codigo}", summary="Detalhe de uma receita (só médico emissor ou paciente)")
def detalhe(codigo: str, request: Request, usuario=Depends(usuario_logado), db: sqlite3.Connection = Depends(get_db)):
    linha = receita_do_usuario(db, codigo, usuario)
    registrar_auditoria(db, request, "receita_visualizada", usuario["id"], linha["codigo"])
    return {"receita": formatar(linha)}
