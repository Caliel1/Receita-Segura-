"""14 — API de Documentos: encaminhamento médico, relatório/laudo e atestado (assinados digitalmente)."""
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..database import Conexao, get_db
from ..dependencias import agora_iso, exigir_medico, registrar_auditoria, usuario_logado
from ..documentos_servico import (TIPOS, buscar_linha, documento_do_usuario, emitir_documento,
                                  exigir_consentimento_cid, formatar)
from ..pdf_documentos import gerar_pdf_documento
from ..validacao import (normalizar_cid10, normalizar_cid11, normalizar_cpf, normalizar_data,
                         normalizar_telefone)
from .qrcode_api import url_verificacao

router = APIRouter(prefix="/api/documentos", tags=["14. Documentos"])


# ---------- Modelos de entrada ----------

class DadosPaciente(BaseModel):
    """Ficha do paciente para o documento. Tudo opcional: o que faltar usa o cadastro do paciente."""
    dataNascimento: str = ""
    cpf: str = ""
    telefone: str = ""

    @field_validator("dataNascimento", mode="before")
    @classmethod
    def _nascimento(cls, v):
        return normalizar_data(v)

    @field_validator("cpf", mode="before")
    @classmethod
    def _cpf(cls, v):
        return normalizar_cpf(v)

    @field_validator("telefone", mode="before")
    @classmethod
    def _telefone(cls, v):
        return normalizar_telefone(v)


class _Base(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    pacienteId: int
    paciente: DadosPaciente = DadosPaciente()


class _ComCid(BaseModel):
    """CID é opcional e só vale com a autorização do paciente (sigilo médico)."""
    cid10: str = Field(default="", max_length=12)
    cid11: str = Field(default="", max_length=12)
    consentimentoCid: bool = False

    @field_validator("cid10", mode="before")
    @classmethod
    def _cid10(cls, v):
        return normalizar_cid10(v)

    @field_validator("cid11", mode="before")
    @classmethod
    def _cid11(cls, v):
        return normalizar_cid11(v)


class NovoEncaminhamento(_Base, _ComCid):
    especialidadeDestino: str = Field(min_length=2, max_length=120)
    servicoDestino: str = Field(default="", max_length=200)
    urgencia: Literal["rotina", "prioritario", "urgente"] = "rotina"
    hipoteseDiagnostica: str = Field(default="", max_length=500)
    motivo: str = Field(min_length=3, max_length=1000)
    resumoClinico: str = Field(min_length=3, max_length=3000)


class NovoRelatorio(_Base, _ComCid):
    finalidade: str = Field(default="", max_length=300)
    descricaoClinica: str = Field(min_length=3, max_length=4000)
    diagnostico: str = Field(min_length=2, max_length=500)
    limitacoes: str = Field(default="", max_length=2000)
    recomendacoes: str = Field(default="", max_length=2000)


class NovoAtestado(_Base, _ComCid):
    finalidade: Literal["afastamento", "comparecimento"]
    dataAtendimento: str = Field(default_factory=lambda: date.today().isoformat())
    diasAfastamento: int | None = Field(default=None, ge=1, le=365)
    inicioAfastamento: str = ""
    horarioAtendimento: str = Field(default="", max_length=60)
    observacoes: str = Field(default="", max_length=500)

    @field_validator("dataAtendimento", mode="before")
    @classmethod
    def _data_atendimento(cls, v):
        return normalizar_data(v) or date.today().isoformat()

    @field_validator("inicioAfastamento", mode="before")
    @classmethod
    def _inicio(cls, v):
        return normalizar_data(v, permitir_futuro=True)

    @model_validator(mode="after")
    def _coerencia(self):
        if self.finalidade == "afastamento":
            if not self.diasAfastamento:
                raise ValueError("Informe por quantos dias o paciente deve ficar afastado.")
            if self.inicioAfastamento and self.inicioAfastamento < self.dataAtendimento:
                raise ValueError("O afastamento não pode começar antes da data do atendimento.")
        else:  # comparecimento: campos de afastamento não se aplicam
            self.diasAfastamento = None
            self.inicioAfastamento = ""
        return self


# ---------- Emissão ----------

def _emitir(tipo: str, dados: _Base, campos: dict, request: Request, medico, db: Conexao) -> dict:
    vinculado = db.execute(
        "SELECT 1 FROM medico_pacientes WHERE medico_id = ? AND paciente_id = ?", (medico["id"], dados.pacienteId)
    ).fetchone()
    if not vinculado:
        raise HTTPException(400, "Selecione um paciente da sua lista.")

    # Campos vazios não entram no documento assinado.
    campos = {k: v for k, v in campos.items() if v not in ("", None)}
    documento = emitir_documento(db, tipo, medico["id"], dados.pacienteId, dados.paciente.model_dump(), campos)

    com_cid = bool(campos.get("cid10") or campos.get("cid11"))
    detalhe = TIPOS[tipo][1] + (" · CID incluído com autorização do paciente" if com_cid else "")
    registrar_auditoria(db, request, "documento_emitido", medico["id"], documento["id"], detalhe)
    return {"documento": documento}


@router.post("/encaminhamentos", status_code=201, summary="Emitir encaminhamento médico (guia de referência)")
def emitir_encaminhamento(dados: NovoEncaminhamento, request: Request, medico=Depends(exigir_medico),
                          db: Conexao = Depends(get_db)):
    exigir_consentimento_cid(dados.consentimentoCid, hipoteseDiagnostica=dados.hipoteseDiagnostica,
                             cid10=dados.cid10, cid11=dados.cid11)
    campos = dados.model_dump(exclude={"pacienteId", "paciente"})
    return _emitir("encaminhamento", dados, campos, request, medico, db)


@router.post("/relatorios", status_code=201, summary="Emitir relatório médico / laudo de atendimento")
def emitir_relatorio(dados: NovoRelatorio, request: Request, medico=Depends(exigir_medico),
                     db: Conexao = Depends(get_db)):
    # O diagnóstico é o centro do laudo; o CID, esse sim, depende da autorização do paciente.
    exigir_consentimento_cid(dados.consentimentoCid, cid10=dados.cid10, cid11=dados.cid11)
    campos = dados.model_dump(exclude={"pacienteId", "paciente"})
    return _emitir("relatorio", dados, campos, request, medico, db)


@router.post("/atestados", status_code=201, summary="Emitir atestado médico simples")
def emitir_atestado(dados: NovoAtestado, request: Request, medico=Depends(exigir_medico),
                    db: Conexao = Depends(get_db)):
    exigir_consentimento_cid(dados.consentimentoCid, cid10=dados.cid10, cid11=dados.cid11)
    campos = dados.model_dump(exclude={"pacienteId", "paciente"})
    return _emitir("atestado", dados, campos, request, medico, db)


# ---------- Consulta ----------

@router.get("", summary="Meus documentos (emitidos, se médico; recebidos, se paciente)")
def listar(tipo: Literal["encaminhamento", "relatorio", "atestado"] | None = Query(default=None),
           usuario=Depends(usuario_logado), db: Conexao = Depends(get_db)):
    coluna = "medico_id" if usuario["papel"] == "medico" else "paciente_id"
    sql, params = f"SELECT * FROM documentos WHERE {coluna} = ?", [usuario["id"]]
    if tipo:
        sql += " AND tipo = ?"
        params.append(tipo)
    linhas = db.execute(sql + " ORDER BY id DESC", params).fetchall()
    return {"documentos": [formatar(l) for l in linhas]}


@router.get("/{codigo}", summary="Detalhe de um documento (só médico emissor ou paciente)")
def detalhe(codigo: str, request: Request, usuario=Depends(usuario_logado),
            db: Conexao = Depends(get_db)):
    linha = documento_do_usuario(db, codigo, usuario)
    registrar_auditoria(db, request, "documento_visualizado", usuario["id"], linha["codigo"])
    return {"documento": formatar(linha)}


@router.get("/{codigo}/pdf", summary="Baixar o documento em PDF (com carimbo, assinatura e QR Code)",
            response_class=Response, responses={200: {"content": {"application/pdf": {}}}})
def baixar_pdf(codigo: str, request: Request, usuario=Depends(usuario_logado),
               db: Conexao = Depends(get_db)):
    linha = documento_do_usuario(db, codigo, usuario)
    registrar_auditoria(db, request, "documento_pdf_gerado", usuario["id"], linha["codigo"])
    pdf = gerar_pdf_documento(formatar(linha), linha["assinatura"], url_verificacao(request, linha["codigo"]))
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="documento-{linha["codigo"]}.pdf"'})


# ---------- Cancelamento ----------

class Cancelamento(BaseModel):
    motivo: str = Field(min_length=3, max_length=300)


@router.post("/{codigo}/cancelar", summary="Médico cancela um documento que emitiu")
def cancelar(codigo: str, dados: Cancelamento, request: Request, medico=Depends(exigir_medico),
             db: Conexao = Depends(get_db)):
    # O status fica fora do conteúdo assinado: cancelar não "quebra" a assinatura, só marca o documento como sem efeito.
    linha = buscar_linha(db, codigo)
    if not linha or linha["medico_id"] != medico["id"]:
        raise HTTPException(404, "Documento não encontrado.")
    if linha["status"] != "ativo":
        raise HTTPException(409, "Este documento já está cancelado.")
    db.execute("UPDATE documentos SET status = 'cancelado', status_motivo = ?, status_em = ? WHERE id = ?",
               (dados.motivo.strip(), agora_iso(), linha["id"]))
    registrar_auditoria(db, request, "documento_cancelado", medico["id"], linha["codigo"], dados.motivo.strip())
    return {"documento": formatar(buscar_linha(db, codigo))}
