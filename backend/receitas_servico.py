"""Regras de negócio das receitas, usadas por várias APIs (receitas, verificação, PDF, QR...)."""
import json
import sqlite3

from fastapi import HTTPException

from .database import transacao
from .dependencias import agora_iso
from .seguranca import assinar, conferir_assinatura, json_canonico, sha256

PRIMEIRO_NUMERO = 2298  # continua a numeração que o protótipo já exibia


def emitir_receita(db: sqlite3.Connection, medico_id: int, paciente_id: int,
                   medicamentos: list[dict], orientacoes: str = "", emitida_em: str | None = None) -> dict:
    emitida_em = emitida_em or agora_iso()
    medico = db.execute("SELECT * FROM usuarios WHERE id = ? AND papel = 'medico'", (medico_id,)).fetchone()
    paciente = db.execute("SELECT id, nome FROM usuarios WHERE id = ? AND papel = 'paciente'", (paciente_id,)).fetchone()
    if not medico or not paciente:
        raise HTTPException(400, "Médico ou paciente inexistente.")

    with transacao(db):
        proximo = db.execute("SELECT COALESCE(MAX(id), 0) + ? FROM receitas", (PRIMEIRO_NUMERO,)).fetchone()[0]
        codigo = f"RS-{proximo}"

        # Tudo o que estiver aqui dentro fica protegido pela assinatura.
        conteudo = json_canonico({
            "codigo": codigo,
            "emitidaEm": emitida_em,
            "medico": {"id": medico["id"], "nome": medico["nome"], "crm": medico["crm"],
                       "especialidade": medico["especialidade"]},
            "paciente": {"id": paciente["id"], "nome": paciente["nome"]},
            "medicamentos": [{"nome": m["nome"], "posologia": m["posologia"]} for m in medicamentos],
            "orientacoes": orientacoes,
        })
        hash_ = sha256(conteudo)
        assinatura = assinar(conteudo, medico["chave_privada"])

        db.execute(
            """INSERT INTO receitas (codigo, medico_id, paciente_id, conteudo, hash, assinatura, emitida_em)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (codigo, medico["id"], paciente["id"], conteudo, hash_, assinatura, emitida_em),
        )
        db.execute(
            """UPDATE medico_pacientes SET ultimo_atendimento = MAX(COALESCE(ultimo_atendimento, ''), ?)
               WHERE medico_id = ? AND paciente_id = ?""",
            (emitida_em[:10], medico["id"], paciente["id"]),
        )
    return buscar_por_codigo(db, codigo)


def formatar(linha: sqlite3.Row | None) -> dict | None:
    """Converte a linha do banco no formato que o front-end usa."""
    if not linha:
        return None
    c = json.loads(linha["conteudo"])
    return {
        "id": c["codigo"],
        "medico": c["medico"]["nome"],
        "crm": c["medico"]["crm"],
        "especialidade": c["medico"].get("especialidade"),
        "paciente": c["paciente"]["nome"],
        "pacienteId": c["paciente"]["id"],
        "medicamentos": c["medicamentos"],
        "orientacoes": c["orientacoes"],
        "emitidaEm": c["emitidaEm"],
        "hash": linha["hash"],
        "medicoId": linha["medico_id"],
        "status": linha["status"],
        "statusMotivo": linha["status_motivo"],
        "statusEm": linha["status_em"],
    }


def buscar_linha(db: sqlite3.Connection, codigo: str) -> sqlite3.Row | None:
    return db.execute("SELECT * FROM receitas WHERE codigo = ?", (codigo.upper(),)).fetchone()


def buscar_por_codigo(db: sqlite3.Connection, codigo: str) -> dict | None:
    return formatar(buscar_linha(db, codigo))


def receita_do_usuario(db: sqlite3.Connection, codigo: str, usuario: sqlite3.Row) -> sqlite3.Row:
    """Devolve a receita só se o usuário for o médico que emitiu ou o paciente.
    Responde 404 também quando ela é de outra pessoa, para não revelar que existe."""
    linha = buscar_linha(db, codigo)
    if not linha or usuario["id"] not in (linha["medico_id"], linha["paciente_id"]):
        raise HTTPException(404, "Receita não encontrada.")
    return linha


def verificar(db: sqlite3.Connection, codigo: str) -> dict | None:
    """Recalcula o hash e confere a assinatura com a chave pública do médico."""
    linha = db.execute(
        """SELECT r.*, u.chave_publica FROM receitas r JOIN usuarios u ON u.id = r.medico_id
           WHERE r.codigo = ?""",
        (codigo.upper(),),
    ).fetchone()
    if not linha:
        return None
    hash_confere = sha256(linha["conteudo"]) == linha["hash"]
    assinatura_confere = conferir_assinatura(linha["conteudo"], linha["assinatura"], linha["chave_publica"])
    c = json.loads(linha["conteudo"])
    return {
        "valida": hash_confere and assinatura_confere,
        "hashConfere": hash_confere,
        "assinaturaConfere": assinatura_confere,
        "status": linha["status"],
        "podeSerDispensada": hash_confere and assinatura_confere and linha["status"] == "ativa",
        "codigo": c["codigo"],
        "medico": c["medico"]["nome"],
        "crm": c["medico"]["crm"],
        "emitidaEm": c["emitidaEm"],
        "hash": linha["hash"],
    }
