"""9 — API de PDF: gera a receita assinada em PDF, com QR Code de verificação."""
import io
import sqlite3
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfgen import canvas

from ..database import RAIZ, get_db
from ..dependencias import registrar_auditoria, usuario_logado
from ..receitas_servico import formatar, receita_do_usuario
from .qrcode_api import gerar_png, url_verificacao

router = APIRouter(prefix="/api/pdf", tags=["9. PDF"])

AZUL = HexColor("#12314f")  # cores do site (css/styles.css)
VERDE = HexColor("#2f8f5b")
CINZA = HexColor("#4b5563")
VERMELHO = HexColor("#b42318")
LOGO = RAIZ / "assets" / "icone-192.png"


def _data_hora(iso: str) -> str:
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone().strftime("%d/%m/%Y %H:%M")


def gerar_pdf(receita: dict, assinatura: str, url_qr: str) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    c.setTitle(f"Receita {receita['id']}")
    largura, altura = A4
    margem = 2 * cm
    y = altura - margem

    # Cabeçalho
    if LOGO.exists():
        c.drawImage(ImageReader(str(LOGO)), margem, y - 1.4 * cm, 1.4 * cm, 1.4 * cm)
    c.setFillColor(AZUL)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(margem + 1.7 * cm, y - 0.6 * cm, "Receita Segura")
    c.setFont("Helvetica", 9)
    c.setFillColor(CINZA)
    c.drawString(margem + 1.7 * cm, y - 1.1 * cm, "receita médica digital")
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(HexColor("#111111"))
    c.drawRightString(largura - margem, y - 0.6 * cm, f"Receita #{receita['id']}")
    c.setFont("Helvetica", 9)
    c.drawRightString(largura - margem, y - 1.1 * cm, _data_hora(receita["emitidaEm"]))
    y -= 2 * cm
    c.setStrokeColor(AZUL)
    c.line(margem, y, largura - margem, y)

    # Médico e paciente
    y -= 0.8 * cm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(margem, y, receita["medico"])
    c.setFont("Helvetica", 9)
    c.drawString(margem, y - 0.45 * cm, f"CRM {receita['crm']} · {receita.get('especialidade') or ''}")
    y -= 1.3 * cm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(margem, y, "Paciente:")
    c.setFont("Helvetica", 10)
    c.drawString(margem + 1.8 * cm, y, receita["paciente"])

    # Medicamentos
    y -= 1.1 * cm
    c.setFillColor(AZUL)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(margem, y, "MEDICAMENTOS")
    c.setFillColor(HexColor("#111111"))
    for i, m in enumerate(receita["medicamentos"], 1):
        y -= 0.7 * cm
        c.setFont("Helvetica-Bold", 10)
        c.drawString(margem, y, f"{i}. {m['nome']}")
        c.setFont("Helvetica", 9)
        for linha in simpleSplit(m["posologia"], "Helvetica", 9, largura - 2 * margem - 0.5 * cm):
            y -= 0.45 * cm
            c.drawString(margem + 0.5 * cm, y, linha)

    # Orientações
    if receita["orientacoes"]:
        y -= 1 * cm
        c.setFillColor(AZUL)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(margem, y, "RECOMENDAÇÕES")
        c.setFillColor(HexColor("#111111"))
        c.setFont("Helvetica", 9)
        for linha in simpleSplit(receita["orientacoes"], "Helvetica", 9, largura - 2 * margem):
            y -= 0.45 * cm
            c.drawString(margem, y, linha)

    # Bloco de assinatura com QR Code
    base = 2.5 * cm
    c.setStrokeColor(HexColor("#d9dee4"))
    c.line(margem, base + 4.2 * cm, largura - margem, base + 4.2 * cm)
    c.drawImage(ImageReader(io.BytesIO(gerar_png(url_qr))), largura - margem - 3.6 * cm, base, 3.6 * cm, 3.6 * cm)
    if receita["status"] == "ativa":
        c.setFillColor(VERDE)
        selo = "ASSINADO DIGITALMENTE (Ed25519)"
    else:
        c.setFillColor(VERMELHO)
        selo = f"RECEITA {receita['status'].upper()}"
    c.setFont("Helvetica-Bold", 11)
    c.drawString(margem, base + 3.2 * cm, selo)
    c.setFillColor(CINZA)
    c.setFont("Courier", 7)
    c.drawString(margem, base + 2.5 * cm, f"SHA-256: {receita['hash']}")
    for i, trecho in enumerate(simpleSplit(f"Assinatura: {assinatura}", "Courier", 7, largura - 2 * margem - 4 * cm)):
        c.drawString(margem, base + 2.1 * cm - i * 0.35 * cm, trecho)
    c.setFont("Helvetica", 8)
    c.drawString(margem, base + 0.4 * cm, "Aponte a câmera para o QR Code para verificar a autenticidade.")
    c.drawString(margem, base, "Protótipo acadêmico — não possui validade legal.")

    c.showPage()
    c.save()
    return buffer.getvalue()


def resposta_pdf(receita: dict, assinatura: str, request: Request) -> Response:
    pdf = gerar_pdf(receita, assinatura, url_verificacao(request, receita["id"]))
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="receita-{receita["id"]}.pdf"'})


@router.get("/{codigo}", summary="Baixar a receita em PDF", response_class=Response,
            responses={200: {"content": {"application/pdf": {}}}})
def baixar_pdf(codigo: str, request: Request, usuario=Depends(usuario_logado), db: sqlite3.Connection = Depends(get_db)):
    linha = receita_do_usuario(db, codigo, usuario)
    registrar_auditoria(db, request, "pdf_gerado", usuario["id"], linha["codigo"])
    return resposta_pdf(formatar(linha), linha["assinatura"], request)
