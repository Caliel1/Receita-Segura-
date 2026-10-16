"""2 — API de Usuários: cadastro de médicos, perfil e troca de senha."""
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ..database import get_db
from ..dependencias import dados_publicos, registrar_auditoria, usuario_logado
from ..seguranca import conferir_senha, gerar_hash_senha, gerar_par_de_chaves
from .autenticacao import EMAIL_REGEX, criar_sessao

router = APIRouter(prefix="/api/usuarios", tags=["2. Usuários"])


class CadastroMedico(BaseModel):
    nome: str = Field(min_length=3, max_length=120)
    email: str = Field(max_length=200, pattern=EMAIL_REGEX)
    senha: str = Field(min_length=6, max_length=200)
    crm: str = Field(pattern=r"^\d{4,6}-[A-Z]{2}$", description="Formato 12345-AM")
    especialidade: str = Field(default="Clínica Geral", max_length=80)


class AtualizarPerfil(BaseModel):
    nome: str | None = Field(default=None, min_length=3, max_length=120)
    especialidade: str | None = Field(default=None, max_length=80)


class TrocarSenha(BaseModel):
    senhaAtual: str = Field(max_length=200)
    novaSenha: str = Field(min_length=6, max_length=200)


@router.post("/medicos", status_code=201, summary="Cadastrar um novo médico (gera o par de chaves de assinatura)")
def cadastrar_medico(dados: CadastroMedico, request: Request, db: sqlite3.Connection = Depends(get_db)):
    email = dados.email.strip().lower()
    if db.execute("SELECT 1 FROM usuarios WHERE email = ?", (email,)).fetchone():
        raise HTTPException(409, "Este e-mail já está em uso.")
    publica, privada = gerar_par_de_chaves()
    cursor = db.execute(
        """INSERT INTO usuarios (papel, nome, email, senha_hash, crm, especialidade, chave_publica, chave_privada)
           VALUES ('medico', ?, ?, ?, ?, ?, ?, ?)""",
        (dados.nome.strip(), email, gerar_hash_senha(dados.senha), dados.crm, dados.especialidade.strip(), publica, privada),
    )
    registrar_auditoria(db, request, "medico_cadastrado", cursor.lastrowid)
    medico = db.execute("SELECT * FROM usuarios WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return {"token": criar_sessao(db, medico["id"]), "usuario": dados_publicos(medico)}


@router.get("/eu", summary="Ver meu perfil")
def meu_perfil(usuario=Depends(usuario_logado)):
    return {"usuario": dados_publicos(usuario)}


@router.put("/eu", summary="Atualizar meu perfil")
def atualizar_perfil(dados: AtualizarPerfil, request: Request, usuario=Depends(usuario_logado),
                     db: sqlite3.Connection = Depends(get_db)):
    # Receitas já emitidas não mudam: o nome antigo continua dentro do conteúdo assinado.
    if dados.nome:
        db.execute("UPDATE usuarios SET nome = ? WHERE id = ?", (dados.nome.strip(), usuario["id"]))
    if dados.especialidade and usuario["papel"] == "medico":
        db.execute("UPDATE usuarios SET especialidade = ? WHERE id = ?", (dados.especialidade.strip(), usuario["id"]))
    registrar_auditoria(db, request, "perfil_atualizado", usuario["id"])
    return {"usuario": dados_publicos(db.execute("SELECT * FROM usuarios WHERE id = ?", (usuario["id"],)).fetchone())}


@router.put("/eu/senha", status_code=204, summary="Trocar minha senha (encerra as outras sessões)")
def trocar_senha(dados: TrocarSenha, request: Request, usuario=Depends(usuario_logado),
                 db: sqlite3.Connection = Depends(get_db)):
    if not conferir_senha(dados.senhaAtual, usuario["senha_hash"]):
        raise HTTPException(400, "Senha atual incorreta.")
    db.execute("UPDATE usuarios SET senha_hash = ? WHERE id = ?", (gerar_hash_senha(dados.novaSenha), usuario["id"]))
    db.execute("DELETE FROM sessoes WHERE usuario_id = ?", (usuario["id"],))
    registrar_auditoria(db, request, "senha_alterada", usuario["id"])
