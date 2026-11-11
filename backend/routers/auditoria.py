"""12 — API de Auditoria: registro de quem fez o quê e quando (logins, emissões, acessos...)."""
import sqlite3

from fastapi import APIRouter, Depends, Query

from ..database import get_db
from ..dependencias import usuario_logado

router = APIRouter(prefix="/api/auditoria", tags=["12. Auditoria"])

DESCRICOES = {
    "login": "Login realizado",
    "login_falhou": "Tentativa de login com senha errada",
    "logout": "Saiu da conta",
    "conta_ativada": "Conta de paciente ativada",
    "medico_cadastrado": "Médico cadastrado",
    "perfil_atualizado": "Perfil atualizado",
    "senha_alterada": "Senha alterada",
    "paciente_cadastrado": "Paciente cadastrado",
    "receita_emitida": "Receita emitida e assinada",
    "receita_visualizada": "Receita visualizada",
    "receita_verificada": "Autenticidade verificada",
    "pdf_gerado": "PDF gerado",
    "compartilhamento_criado": "Link de compartilhamento criado",
    "compartilhamento_acessado": "Link compartilhado acessado",
    "compartilhamento_revogado": "Link de compartilhamento revogado",
    "receita_dispensada": "Receita dispensada pela farmácia",
    "receita_cancelada": "Receita cancelada",
}


@router.get("", summary="Eventos da minha conta e das minhas receitas")
def listar(limite: int = Query(default=30, ge=1, le=200), acao: str | None = None,
           usuario=Depends(usuario_logado), db: sqlite3.Connection = Depends(get_db)):
    coluna = "medico_id" if usuario["papel"] == "medico" else "paciente_id"
    # Tudo o que eu fiz + tudo o que aconteceu com receitas minhas (ex.: farmácia verificou).
    sql = f"""
        SELECT a.*, u.nome AS usuario_nome FROM auditoria a LEFT JOIN usuarios u ON u.id = a.usuario_id
        WHERE (a.usuario_id = ? OR a.receita_codigo IN (SELECT codigo FROM receitas WHERE {coluna} = ?))
    """
    params: list = [usuario["id"], usuario["id"]]
    if acao:
        sql += " AND a.acao = ?"
        params.append(acao)
    sql += " ORDER BY a.id DESC LIMIT ?"
    params.append(limite)
    return {"eventos": [{
        "id": l["id"], "quando": l["quando"], "acao": l["acao"],
        "descricao": DESCRICOES.get(l["acao"], l["acao"]),
        "usuario": l["usuario_nome"] or "Acesso público",
        "receita": l["receita_codigo"], "detalhe": l["detalhe"], "ip": l["ip"],
    } for l in db.execute(sql, params).fetchall()]}
