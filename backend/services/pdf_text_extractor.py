"""Extração local da camada textual de PDFs enviados ao AI Ready."""
from __future__ import annotations

import math
from dataclasses import dataclass

import pymupdf

from backend.config import Settings
from backend.errors import ServiceError


@dataclass(frozen=True)
class PdfPageQuality:
    """Indicadores simples de legibilidade; não contêm interpretação jurídica."""

    caracteres: int
    proporcao_imprimivel: float
    proporcao_alfanumerica: float
    score: float
    status: str


@dataclass(frozen=True)
class PdfTextPage:
    """Texto de uma página com sua qualidade observada."""

    numero: int
    texto: str
    qualidade: PdfPageQuality


@dataclass(frozen=True)
class PdfTextDocument:
    """Conteúdo textual temporário usado somente durante o workspace ativo."""

    identificador: str
    nome: str
    tamanho_bytes: int
    paginas: tuple[PdfTextPage, ...]
    alertas: tuple[str, ...]

    @property
    def paginas_utilizaveis(self) -> tuple[PdfTextPage, ...]:
        return tuple(page for page in self.paginas if page.texto and page.qualidade.status != "inutilizavel")

    @property
    def qualidade_geral(self) -> str:
        if not self.paginas_utilizaveis:
            return "insuficiente"
        if len(self.paginas_utilizaveis) == len(self.paginas) and all(page.qualidade.status == "boa" for page in self.paginas):
            return "boa"
        return "parcial"

    def texto_prompt(self) -> str:
        """Inclui nome e página para permitir referências auditáveis nas respostas."""
        blocks = [f"## DOCUMENTO: {self.nome}"]
        for page in self.paginas_utilizaveis:
            blocks.append(f"### PAGINA {page.numero}\n{page.texto}")
        return "\n\n".join(blocks)


class PdfTextExtractor:
    """Valida os bytes do PDF e lê texto com PyMuPDF, sem OCR oculto."""

    def __init__(self, settings: Settings):
        self.settings = settings

    @staticmethod
    def _quality(text: str) -> PdfPageQuality:
        cleaned = text.replace("\x00", "").strip()
        total = len(cleaned)
        if not total:
            return PdfPageQuality(0, 0.0, 0.0, 0.0, "inutilizavel")
        printable = sum(1 for char in cleaned if char.isprintable() or char in "\n\t")
        alnum = sum(1 for char in cleaned if char.isalnum())
        printable_ratio = printable / total
        alnum_ratio = alnum / total
        length_component = min(1.0, math.log10(max(total, 1)) / 3.0)
        score = max(0.0, min(1.0, 0.40 * printable_ratio + 0.40 * min(1.0, alnum_ratio / 0.55) + 0.20 * length_component))
        if total < 20 or printable_ratio < 0.75 or alnum_ratio < 0.10:
            status = "inutilizavel"
        elif total < 80 or score < 0.56:
            status = "baixa"
        else:
            status = "boa"
        return PdfPageQuality(total, round(printable_ratio, 4), round(alnum_ratio, 4), round(score, 4), status)

    def read(self, *, identifier: str, name: str, content: bytes) -> PdfTextDocument:
        """Abre um PDF já validado em tamanho e retorna suas páginas em memória."""
        try:
            pdf = pymupdf.open(stream=content, filetype="pdf")
        except Exception as exc:
            raise ServiceError("Não foi possível abrir um dos PDFs. Reenvie um arquivo válido.", 400, code="PDF_INVALIDO") from exc
        try:
            if pdf.needs_pass:
                raise ServiceError("PDF protegido por senha não é suportado.", 422, code="PDF_PROTEGIDO")
            if not 1 <= pdf.page_count <= self.settings.max_pdf_pages:
                raise ServiceError(
                    f"Cada PDF deve ter entre 1 e {self.settings.max_pdf_pages} páginas.",
                    422,
                    code="PAGINAS_FORA_LIMITE",
                )
            pages: list[PdfTextPage] = []
            warnings: list[str] = []
            for page_number, page in enumerate(pdf, start=1):
                text = page.get_text("text", sort=True).replace("\x00", "").strip()
                quality = self._quality(text)
                pages.append(PdfTextPage(page_number, text, quality))
                if quality.status == "inutilizavel":
                    warnings.append(f"Página {page_number} sem camada textual confiável.")
                elif quality.status == "baixa":
                    warnings.append(f"Página {page_number} com camada textual de baixa qualidade.")
            return PdfTextDocument(identifier, name, len(content), tuple(pages), tuple(warnings))
        finally:
            pdf.close()
