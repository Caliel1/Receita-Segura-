"""PDF dos documentos médicos: cabeçalho, identificação, seções, carimbo/assinatura digital e QR Code."""
import io
from datetime import datetime
from xml.sax.saxutils import escape

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)

from .database import RAIZ
from .documentos_servico import paciente_formatado
from .routers.qrcode_api import gerar_png

AZUL = HexColor("#12314f")  # cores do site (css/styles.css)
VERDE = HexColor("#2f8f5b")
CINZA = HexColor("#4b5563")
CINZA_CLARO = HexColor("#d9dee4")
VERMELHO = HexColor("#b42318")
TINTA = HexColor("#111111")
LOGO = RAIZ / "assets" / "icone-192.png"

MARGEM = 2 * cm
LARGURA_UTIL = A4[0] - 2 * MARGEM

ESTILOS = {
    "titulo": ParagraphStyle("titulo", fontName="Helvetica-Bold", fontSize=15, leading=19, textColor=AZUL,
                             spaceAfter=10),
    "medico": ParagraphStyle("medico", fontName="Helvetica", fontSize=9.5, leading=13, textColor=CINZA),
    "rotulo": ParagraphStyle("rotulo", fontName="Helvetica-Bold", fontSize=8.5, leading=11, textColor=AZUL,
                             spaceBefore=12, spaceAfter=3),
    "corpo": ParagraphStyle("corpo", fontName="Helvetica", fontSize=10, leading=14.5, textColor=TINTA,
                            alignment=TA_LEFT),
    "atestado": ParagraphStyle("atestado", fontName="Helvetica", fontSize=11.5, leading=19, textColor=TINTA,
                               spaceBefore=18, spaceAfter=6),
    "carimbo": ParagraphStyle("carimbo", fontName="Helvetica", fontSize=9, leading=12.5, textColor=TINTA),
    "mono": ParagraphStyle("mono", fontName="Courier", fontSize=6.8, leading=8.6, textColor=CINZA,
                           wordWrap="CJK"),  # CJK = quebra em qualquer caractere (hash/assinatura não têm espaços)
    "nota": ParagraphStyle("nota", fontName="Helvetica", fontSize=8, leading=10.5, textColor=CINZA),
}


def _data_hora(iso: str) -> str:
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone().strftime("%d/%m/%Y %H:%M")


def _texto(valor: str) -> str:
    """Escapa o texto digitado (evita que vire marcação do reportlab) e preserva as quebras de linha."""
    return escape(valor).replace("\n", "<br/>")


def _bloco_assinatura(doc: dict, assinatura: str, url_qr: str) -> KeepTogether:
    ativo = doc["status"] == "ativo"
    selo = "ASSINADO DIGITALMENTE (Ed25519)" if ativo else "DOCUMENTO CANCELADO"
    cor_selo = "#2f8f5b" if ativo else "#b42318"

    carimbo = [
        Paragraph(f'<font color="{cor_selo}"><b>{selo}</b></font>', ESTILOS["carimbo"]),
        Spacer(1, 4),
        Paragraph(f"<b>{_texto(doc['medico'])}</b>", ESTILOS["carimbo"]),
        Paragraph(_texto(f"CRM {doc['crm']}" + (f" · {doc['especialidade']}" if doc.get("especialidade") else "")),
                  ESTILOS["carimbo"]),
        Paragraph(f"Assinado em {_data_hora(doc['emitidoEm'])}", ESTILOS["carimbo"]),
        Spacer(1, 5),
        Paragraph(f"SHA-256: {doc['hash']}", ESTILOS["mono"]),
        Paragraph(f"Assinatura: {assinatura}", ESTILOS["mono"]),
    ]
    qr = [
        Image(io.BytesIO(gerar_png(url_qr)), width=3.2 * cm, height=3.2 * cm),
        Paragraph("Aponte a câmera para verificar a autenticidade.", ESTILOS["nota"]),
    ]
    tabela = Table([[carimbo, qr]], colWidths=[LARGURA_UTIL - 4.2 * cm, 4.2 * cm])
    tabela.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (0, 0), (0, 0), 0.8, AZUL),            # a "moldura" do carimbo
        ("LEFTPADDING", (0, 0), (0, 0), 10), ("RIGHTPADDING", (0, 0), (0, 0), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (1, 0), (1, 0), 10),
    ]))
    return KeepTogether([Spacer(1, 26), tabela])


def gerar_pdf_documento(doc: dict, assinatura: str, url_qr: str) -> bytes:
    buffer = io.BytesIO()

    def moldura(canvas, _):
        """Cabeçalho e rodapé de todas as páginas."""
        largura, altura = A4
        canvas.saveState()
        topo = altura - MARGEM
        if LOGO.exists():
            canvas.drawImage(ImageReader(str(LOGO)), MARGEM, topo - 1.2 * cm, 1.2 * cm, 1.2 * cm, mask="auto")
        canvas.setFillColor(AZUL)
        canvas.setFont("Helvetica-Bold", 15)
        canvas.drawString(MARGEM + 1.5 * cm, topo - 0.55 * cm, "Receita Segura")
        canvas.setFillColor(CINZA)
        canvas.setFont("Helvetica", 8.5)
        canvas.drawString(MARGEM + 1.5 * cm, topo - 1.05 * cm, "documento médico digital")
        canvas.setFillColor(TINTA)
        canvas.setFont("Helvetica-Bold", 10.5)
        canvas.drawRightString(largura - MARGEM, topo - 0.55 * cm, f"{doc['tipoRotulo']} #{doc['id']}")
        canvas.setFont("Helvetica", 8.5)
        canvas.drawRightString(largura - MARGEM, topo - 1.05 * cm, _data_hora(doc["emitidoEm"]))
        canvas.setStrokeColor(AZUL)
        canvas.line(MARGEM, topo - 1.6 * cm, largura - MARGEM, topo - 1.6 * cm)

        canvas.setStrokeColor(CINZA_CLARO)
        canvas.line(MARGEM, 1.7 * cm, largura - MARGEM, 1.7 * cm)
        canvas.setFillColor(CINZA)
        canvas.setFont("Helvetica", 7.5)
        canvas.drawString(MARGEM, 1.25 * cm, f"Documento {doc['id']} · verificável pelo QR Code · "
                                              "Protótipo acadêmico — não possui validade legal.")
        canvas.drawRightString(largura - MARGEM, 1.25 * cm, f"Página {canvas.getPageNumber()}")
        canvas.restoreState()

    modelo = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=MARGEM, rightMargin=MARGEM,
        topMargin=MARGEM + 2.1 * cm, bottomMargin=2.4 * cm,
        title=f"{doc['titulo']} {doc['id']}", author=doc["medico"],
    )

    historia = [Paragraph(_texto(doc["titulo"]), ESTILOS["titulo"])]

    if doc["status"] != "ativo":
        motivo = f" — {doc['statusMotivo']}" if doc.get("statusMotivo") else ""
        historia.append(Paragraph(f'<font color="#b42318"><b>DOCUMENTO CANCELADO{_texto(motivo)}</b></font>',
                                  ESTILOS["corpo"]))

    historia.append(Paragraph(f"<b>{_texto(doc['medico'])}</b> · CRM {_texto(doc['crm'])}"
                              + (f" · {_texto(doc['especialidade'])}" if doc.get("especialidade") else ""),
                              ESTILOS["medico"]))
    historia.append(Paragraph("PACIENTE", ESTILOS["rotulo"]))
    historia.append(Paragraph(_texto(paciente_formatado(doc)), ESTILOS["corpo"]))

    for secao in doc["secoes"]:
        if secao["titulo"]:
            historia.append(Paragraph(_texto(secao["titulo"]).upper(), ESTILOS["rotulo"]))
            historia.append(Paragraph(_texto(secao["texto"]), ESTILOS["corpo"]))
        else:  # texto corrido do atestado
            historia.append(Paragraph(_texto(secao["texto"]), ESTILOS["atestado"]))

    historia.append(_bloco_assinatura(doc, assinatura, url_qr))

    modelo.build(historia, onFirstPage=moldura, onLaterPages=moldura)
    return buffer.getvalue()
