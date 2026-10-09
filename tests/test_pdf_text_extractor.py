import pymupdf

from backend.config import Settings
from backend.services.pdf_text_extractor import PdfTextExtractor


def make_pdf(text: str) -> bytes:
    pdf = pymupdf.open()
    page = pdf.new_page()
    page.insert_text((72, 72), text)
    data = pdf.tobytes()
    pdf.close()
    return data


def test_extracts_searchable_pdf_text() -> None:
    extractor = PdfTextExtractor(Settings())
    document = extractor.read(identifier="doc1", name="peticao.pdf", content=make_pdf("Processo civel com conteudo textual suficiente para leitura automatica."))
    assert len(document.paginas) == 1
    assert document.paginas_utilizaveis
    assert "Processo civel" in document.paginas[0].texto
