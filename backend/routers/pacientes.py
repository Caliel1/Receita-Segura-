"""3 — API de Pacientes: o médico lista e cadastra seus pacientes."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ..database import Conexao, Linha, get_db
from ..dependencias import exigir_medico, registrar_auditoria
from ..seguranca import gerar_codigo_convite

router = APIRouter(prefix="/api/pacientes", tags=["3. Pacientes"])


class NovoPaciente(BaseModel):
    nome: str = Field(min_length=3, max_length=120)


def formatar(linha: Linha) -> dict:
    return {
        "id": linha["id"],
        "nome": linha["nome"],
        "ultimoAtendimento": linha["ultimo_atendimento"],
        "codigoConvite": linha["codigo_convite"],
        "contaAtiva": linha["senha_hash"] is not None,
        "dataNascimento": linha["data_nascimento"] or "",
        "cpf": linha["cpf"] or "",
        "telefone": linha["telefone"] or "",
    }


CONSULTA = """
    SELECT u.id, u.nome, u.codigo_convite, u.senha_hash, u.data_nascimento, u.cpf, u.telefone,
           mp.ultimo_atendimento
    FROM medico_pacientes mp JOIN usuarios u ON u.id = mp.paciente_id
    WHERE mp.medico_id = ?
"""


@router.get("", summary="Listar meus pacientes")
def listar(medico=Depends(exigir_medico), db: Conexao = Depends(get_db)):
    linhas = db.execute(
        CONSULTA + " ORDER BY mp.ultimo_atendimento IS NULL DESC, mp.ultimo_atendimento DESC, u.nome",
        (medico["id"],),
    ).fetchall()
    return {"pacientes": [formatar(l) for l in linhas]}


@router.post("", status_code=201, summary="Cadastrar paciente (gera código de primeiro acesso)")
def cadastrar(dados: NovoPaciente, request: Request, medico=Depends(exigir_medico),
              db: Conexao = Depends(get_db)):
    cursor = db.execute(
        "INSERT INTO usuarios (papel, nome, codigo_convite) VALUES ('paciente', ?, ?) RETURNING id",
        (dados.nome.strip(), gerar_codigo_convite()),
    ).fetchone()
    db.execute("INSERT INTO medico_pacientes (medico_id, paciente_id) VALUES (?, ?)", (medico["id"], cursor["id"]))
    registrar_auditoria(db, request, "paciente_cadastrado", medico["id"], detalhe=dados.nome.strip())
    linha = db.execute(CONSULTA + " AND u.id = ?", (medico["id"], cursor["id"])).fetchone()
    return {"paciente": formatar(linha)}


@router.get("/{paciente_id}", summary="Detalhe de um paciente meu")
def detalhe(paciente_id: int, medico=Depends(exigir_medico), db: Conexao = Depends(get_db)):
    linha = db.execute(CONSULTA + " AND u.id = ?", (medico["id"], paciente_id)).fetchone()
    if not linha:
        raise HTTPException(404, "Paciente não encontrado na sua lista.")
    return {"paciente": formatar(linha)}
