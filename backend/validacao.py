"""Validações e normalizações usadas pelos documentos médicos (CPF, telefone, datas, CID)."""
import re
from datetime import date

# CID-10: letra + 2 dígitos, com subcategoria opcional (ex.: F90, F90.0, J45.9)
_CID10 = re.compile(r"^[A-Z]\d{2}(\.\d{1,2})?$")
# CID-11: 4 caracteres alfanuméricos, com extensão opcional (ex.: 6A05, 6A05.0, CA40.Z)
_CID11 = re.compile(r"^[0-9A-Z][A-Z0-9]{3}(\.[0-9A-Z]{1,2})?$")


def so_digitos(texto: str) -> str:
    return re.sub(r"\D", "", texto or "")


def normalizar_cpf(valor: str | None) -> str:
    """Devolve só os 11 dígitos ou '' (vazio). Levanta ValueError se for inválido."""
    digitos = so_digitos(valor or "")
    if not digitos:
        return ""
    if len(digitos) != 11 or digitos == digitos[0] * 11:
        raise ValueError("CPF inválido.")
    for tamanho in (9, 10):
        soma = sum(int(d) * peso for d, peso in zip(digitos[:tamanho], range(tamanho + 1, 1, -1)))
        digito = (soma * 10 % 11) % 10
        if digito != int(digitos[tamanho]):
            raise ValueError("CPF inválido.")
    return digitos


def normalizar_telefone(valor: str | None) -> str:
    digitos = so_digitos(valor or "")
    if not digitos:
        return ""
    if len(digitos) not in (10, 11):
        raise ValueError("Telefone inválido: informe o DDD e o número.")
    return digitos


def normalizar_data(valor: str | None, *, permitir_futuro: bool = False) -> str:
    """Aceita AAAA-MM-DD. Devolve a própria string ou '' (vazio)."""
    if not valor:
        return ""
    try:
        data = date.fromisoformat(valor)
    except ValueError:
        raise ValueError("Data inválida (use AAAA-MM-DD).") from None
    if not permitir_futuro and data > date.today():
        raise ValueError("A data não pode estar no futuro.")
    return data.isoformat()


def normalizar_cid10(valor: str | None) -> str:
    codigo = (valor or "").strip().upper().replace(" ", "")
    if codigo and not _CID10.match(codigo):
        raise ValueError("CID-10 inválido (exemplo: F90.0).")
    return codigo


def normalizar_cid11(valor: str | None) -> str:
    codigo = (valor or "").strip().upper().replace(" ", "")
    if codigo and not _CID11.match(codigo):
        raise ValueError("CID-11 inválido (exemplo: 6A05.0).")
    return codigo


# ---------- Formatação para exibição (texto dos PDFs e dos documentos) ----------

def formatar_cpf(cpf: str) -> str:
    return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}" if len(cpf) == 11 else cpf


def formatar_telefone(tel: str) -> str:
    if len(tel) == 11:
        return f"({tel[:2]}) {tel[2:7]}-{tel[7:]}"
    if len(tel) == 10:
        return f"({tel[:2]}) {tel[2:6]}-{tel[6:]}"
    return tel


def formatar_data(iso: str) -> str:
    return "/".join(reversed(iso[:10].split("-"))) if iso else ""


# ---------- Número por extenso (usado no atestado: "3 (três) dias") ----------

_UNIDADES = ["zero", "um", "dois", "três", "quatro", "cinco", "seis", "sete", "oito", "nove", "dez", "onze",
             "doze", "treze", "quatorze", "quinze", "dezesseis", "dezessete", "dezoito", "dezenove"]
_DEZENAS = ["", "", "vinte", "trinta", "quarenta", "cinquenta", "sessenta", "setenta", "oitenta", "noventa"]
_CENTENAS = ["", "cento", "duzentos", "trezentos", "quatrocentos", "quinhentos", "seiscentos", "setecentos",
             "oitocentos", "novecentos"]


def por_extenso(n: int) -> str:
    """0 a 999, em português."""
    if not 0 <= n <= 999:
        return str(n)
    if n == 100:
        return "cem"
    partes = []
    centenas, resto = divmod(n, 100)
    if centenas:
        partes.append(_CENTENAS[centenas])
    if resto:
        if resto < 20:
            partes.append(_UNIDADES[resto])
        else:
            dezena, unidade = divmod(resto, 10)
            partes.append(_DEZENAS[dezena] + (f" e {_UNIDADES[unidade]}" if unidade else ""))
    return " e ".join(partes) if partes else _UNIDADES[0]
