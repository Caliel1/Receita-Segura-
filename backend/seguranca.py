"""Criptografia: senhas, tokens, hash SHA-256 e assinatura digital Ed25519."""
import base64
import hashlib
import hmac
import json
import secrets

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


# ---------- Senhas (scrypt com sal aleatório) ----------

def gerar_hash_senha(senha: str) -> str:
    sal = secrets.token_hex(16)
    hash_ = hashlib.scrypt(senha.encode(), salt=sal.encode(), n=16384, r=8, p=1, dklen=64).hex()
    return f"scrypt${sal}${hash_}"


def conferir_senha(senha: str, guardado: str | None) -> bool:
    if not guardado:
        return False
    _, sal, hash_ = guardado.split("$")
    calculado = hashlib.scrypt(senha.encode(), salt=sal.encode(), n=16384, r=8, p=1, dklen=64).hex()
    return hmac.compare_digest(calculado, hash_)  # comparação em tempo constante


# ---------- Tokens ----------

def gerar_token() -> str:
    return secrets.token_hex(32)


def gerar_codigo_convite() -> str:
    """Código curto e legível (sem 0/O/1/I para evitar confusão). Ex.: ABCD-EF23"""
    alfabeto = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    codigo = "".join(secrets.choice(alfabeto) for _ in range(8))
    return f"{codigo[:4]}-{codigo[4:]}"


# ---------- Hash e assinatura ----------

def sha256(texto: str) -> str:
    return hashlib.sha256(texto.encode()).hexdigest()


def json_canonico(valor) -> str:
    """JSON com chaves em ordem alfabética e sem espaços:
    o mesmo conteúdo sempre gera o mesmo texto — e portanto o mesmo hash."""
    return json.dumps(valor, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def gerar_par_de_chaves() -> tuple[str, str]:
    privada = Ed25519PrivateKey.generate()
    privada_pem = privada.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    publica_pem = privada.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()
    return publica_pem, privada_pem


def assinar(texto: str, chave_privada_pem: str) -> str:
    privada = serialization.load_pem_private_key(chave_privada_pem.encode(), password=None)
    return base64.b64encode(privada.sign(texto.encode())).decode()


def conferir_assinatura(texto: str, assinatura_b64: str, chave_publica_pem: str) -> bool:
    publica = serialization.load_pem_public_key(chave_publica_pem.encode())
    try:
        publica.verify(base64.b64decode(assinatura_b64), texto.encode())
        return True
    except (InvalidSignature, ValueError):
        return False
