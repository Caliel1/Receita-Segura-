"""Regras de negócio dos documentos médicos (encaminhamento, relatório/laudo e atestado).

Mesmo princípio das receitas: o conteúdo é montado num JSON canônico, e é esse texto exato que recebe
o hash SHA-256 e a assinatura Ed25519 do médico. Mudar qualquer campo invalida a assinatura.
O status (ativo/cancelado) fica FORA do conteúdo assinado — cancelar não "quebra" a assinatura.
"""
import json
from datetime import date, timedelta

from fastapi import HTTPException

from .database import Conexao, Linha, transacao
from .dependencias import agora_iso
from .seguranca import assinar, conferir_assinatura, json_canonico, sha256
from .validacao import formatar_cpf, formatar_data, formatar_telefone, por_extenso

PRIMEIRO_NUMERO = 1001

TIPOS = {
    # tipo: (prefixo do código, rótulo curto, título completo do documento)
    "encaminhamento": ("EN", "Encaminhamento", "Encaminhamento Médico (Guia de Referência)"),
    "relatorio": ("LM", "Relatório / Laudo", "Relatório Médico / Laudo de Atendimento"),
    "atestado": ("AT", "Atestado", "Atestado Médico"),
}
URGENCIAS = {"rotina": "Rotina (eletivo)", "prioritario": "Prioritário", "urgente": "Urgente"}


# ---------- Emissão ----------

def exigir_consentimento_cid(consentimento: bool, **campos: str) -> None:
    """Sigilo médico: hipótese diagnóstica e CID só entram no documento com autorização do paciente."""
    preenchidos = [nome for nome, valor in campos.items() if valor]
    if preenchidos and not consentimento:
        raise HTTPException(400, "Para incluir diagnóstico/CID no documento é preciso marcar que o paciente "
                                 "autorizou (sigilo médico). Marque a autorização ou deixe esses campos vazios.")


def emitir_documento(db: Conexao, tipo: str, medico_id: int, paciente_id: int,
                     paciente_dados: dict, dados: dict, emitido_em: str | None = None) -> dict:
    if tipo not in TIPOS:
        raise HTTPException(400, "Tipo de documento inválido.")
    emitido_em = emitido_em or agora_iso()
    medico = db.execute("SELECT * FROM usuarios WHERE id = ? AND papel = 'medico'", (medico_id,)).fetchone()
    paciente = db.execute("SELECT * FROM usuarios WHERE id = ? AND papel = 'paciente'", (paciente_id,)).fetchone()
    if not medico or not paciente:
        raise HTTPException(400, "Médico ou paciente inexistente.")

    # Dados cadastrais: o que o médico informou no formulário vale para este documento; campos em
    # branco usam o que já está no cadastro do paciente (que ele mesmo cadastrou).
    ficha = {
        "dataNascimento": paciente_dados.get("dataNascimento") or paciente["data_nascimento"] or "",
        "cpf": paciente_dados.get("cpf") or paciente["cpf"] or "",
        "telefone": paciente_dados.get("telefone") or paciente["telefone"] or "",
    }

    with transacao(db):
        proximo = db.execute("SELECT COALESCE(MAX(id), 0) + ? FROM documentos", (PRIMEIRO_NUMERO,)).fetchone()[0]
        codigo = f"{TIPOS[tipo][0]}-{proximo}"

        conteudo = json_canonico({
            "codigo": codigo,
            "tipo": tipo,
            "emitidoEm": emitido_em,
            "medico": {"id": medico["id"], "nome": medico["nome"], "crm": medico["crm"],
                       "especialidade": medico["especialidade"]},
            "paciente": {"id": paciente["id"], "nome": paciente["nome"], **ficha},
            "dados": dados,
        })
        hash_ = sha256(conteudo)
        assinatura = assinar(conteudo, medico["chave_privada"])

        db.execute(
            """INSERT INTO documentos (codigo, tipo, medico_id, paciente_id, conteudo, hash, assinatura, emitido_em)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (codigo, tipo, medico["id"], paciente["id"], conteudo, hash_, assinatura, emitido_em),
        )
        # Guarda a ficha no cadastro para pré-preencher os próximos documentos.
        db.execute(
            "UPDATE usuarios SET data_nascimento = ?, cpf = ?, telefone = ? WHERE id = ?",
            (ficha["dataNascimento"] or None, ficha["cpf"] or None, ficha["telefone"] or None, paciente["id"]),
        )
        db.execute(
            """UPDATE medico_pacientes SET ultimo_atendimento = GREATEST(COALESCE(ultimo_atendimento, ''), ?)
               WHERE medico_id = ? AND paciente_id = ?""",
            (emitido_em[:10], medico["id"], paciente["id"]),
        )
    return buscar_por_codigo(db, codigo)


# ---------- Textos do documento (a mesma fonte alimenta a tela e o PDF) ----------

def _linha_cid(d: dict) -> str:
    partes = []
    if d.get("cid10"):
        partes.append(f"CID-10: {d['cid10']}")
    if d.get("cid11"):
        partes.append(f"CID-11: {d['cid11']}")
    return " · ".join(partes)


def _identificacao(c: dict) -> str:
    p = c["paciente"]
    texto = p["nome"]
    if p.get("cpf"):
        texto += f", CPF {formatar_cpf(p['cpf'])}"
    return texto


def texto_atestado(c: dict) -> str:
    d = c["dados"]
    quem = _identificacao(c)
    atendimento = formatar_data(d["dataAtendimento"])
    if d["finalidade"] == "afastamento":
        dias = d["diasAfastamento"]
        inicio = date.fromisoformat(d.get("inicioAfastamento") or d["dataAtendimento"])
        fim = inicio + timedelta(days=dias - 1)
        unidade = "dia" if dias == 1 else "dias"
        periodo = (f"no dia {formatar_data(inicio.isoformat())}" if dias == 1 else
                   f"de {formatar_data(inicio.isoformat())} a {formatar_data(fim.isoformat())}")
        return (f"Atesto, para os devidos fins, que {quem}, foi atendido(a) por mim em {atendimento} e, por "
                f"motivo de saúde, necessita de afastamento de suas atividades habituais por {dias} "
                f"({por_extenso(dias)}) {unidade}, {periodo}.")
    horario = f", no horário de {d['horarioAtendimento']}" if d.get("horarioAtendimento") else ""
    return (f"Atesto, para os devidos fins, que {quem}, compareceu a atendimento médico em "
            f"{atendimento}{horario}.")


def montar_secoes(c: dict) -> list[dict]:
    """Blocos de texto do documento, na ordem em que aparecem. Só entra o que foi preenchido."""
    d, tipo = c["dados"], c["tipo"]
    secoes: list[tuple[str, str]] = []

    if tipo == "encaminhamento":
        destino = d["especialidadeDestino"]
        if d.get("servicoDestino"):
            destino += f"\nServiço / profissional: {d['servicoDestino']}"
        destino += f"\nPrioridade: {URGENCIAS.get(d.get('urgencia'), 'Rotina (eletivo)')}"
        secoes.append(("Encaminhado para", destino))
        hipotese = "\n".join(x for x in (d.get("hipoteseDiagnostica"), _linha_cid(d)) if x)
        secoes.append(("Hipótese diagnóstica", hipotese))
        secoes.append(("Motivo do encaminhamento / avaliação solicitada", d["motivo"]))
        secoes.append(("Resumo da história clínica e condutas já realizadas", d["resumoClinico"]))

    elif tipo == "relatorio":
        secoes.append(("Finalidade", d.get("finalidade", "")))
        secoes.append(("Histórico e avaliação clínica", d["descricaoClinica"]))
        secoes.append(("Diagnóstico", "\n".join(x for x in (d["diagnostico"], _linha_cid(d)) if x)))
        secoes.append(("Limitações associadas", d.get("limitacoes", "")))
        secoes.append(("Recomendações de adaptação", d.get("recomendacoes", "")))

    else:  # atestado
        secoes.append(("", texto_atestado(c)))
        secoes.append(("Diagnóstico (informado com autorização do paciente)", _linha_cid(d)))
        secoes.append(("Observações", d.get("observacoes", "")))

    return [{"titulo": t, "texto": x} for t, x in secoes if x]


def formatar(linha: Linha | None) -> dict | None:
    """Converte a linha do banco no formato que o front-end e o PDF usam."""
    if not linha:
        return None
    c = json.loads(linha["conteudo"])
    p = c["paciente"]
    return {
        "id": c["codigo"],
        "tipo": c["tipo"],
        "tipoRotulo": TIPOS[c["tipo"]][1],
        "titulo": TIPOS[c["tipo"]][2],
        "medico": c["medico"]["nome"],
        "crm": c["medico"]["crm"],
        "especialidade": c["medico"].get("especialidade"),
        "medicoId": linha["medico_id"],
        "paciente": p["nome"],
        "pacienteId": p["id"],
        "pacienteDados": {"dataNascimento": p.get("dataNascimento", ""), "cpf": p.get("cpf", ""),
                          "telefone": p.get("telefone", "")},
        "emitidoEm": c["emitidoEm"],
        "secoes": montar_secoes(c),
        "hash": linha["hash"],
        "status": linha["status"],
        "statusMotivo": linha["status_motivo"],
        "statusEm": linha["status_em"],
    }


def paciente_formatado(doc: dict) -> str:
    """Linha de identificação do paciente para exibir no documento."""
    d = doc["pacienteDados"]
    partes = [doc["paciente"]]
    if d["dataNascimento"]:
        partes.append(f"nasc. {formatar_data(d['dataNascimento'])}")
    if d["cpf"]:
        partes.append(f"CPF {formatar_cpf(d['cpf'])}")
    if d["telefone"]:
        partes.append(f"tel. {formatar_telefone(d['telefone'])}")
    return " · ".join(partes)


# ---------- Consulta ----------

def buscar_linha(db: Conexao, codigo: str) -> Linha | None:
    return db.execute("SELECT * FROM documentos WHERE codigo = ?", (codigo.upper(),)).fetchone()


def buscar_por_codigo(db: Conexao, codigo: str) -> dict | None:
    return formatar(buscar_linha(db, codigo))


def documento_do_usuario(db: Conexao, codigo: str, usuario: Linha) -> Linha:
    """Só o médico emissor ou o paciente enxergam o documento (404 para os demais)."""
    linha = buscar_linha(db, codigo)
    if not linha or usuario["id"] not in (linha["medico_id"], linha["paciente_id"]):
        raise HTTPException(404, "Documento não encontrado.")
    return linha


def verificar(db: Conexao, codigo: str) -> dict | None:
    """Recalcula o hash e confere a assinatura. Não devolve nenhum dado do paciente."""
    linha = db.execute(
        """SELECT d.*, u.chave_publica FROM documentos d JOIN usuarios u ON u.id = d.medico_id
           WHERE d.codigo = ?""",
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
        "podeSerDispensada": False,
        "tipo": c["tipo"],
        "tipoRotulo": TIPOS[c["tipo"]][1],
        "codigo": c["codigo"],
        "medico": c["medico"]["nome"],
        "crm": c["medico"]["crm"],
        "emitidaEm": c["emitidoEm"],
        "hash": linha["hash"],
    }
