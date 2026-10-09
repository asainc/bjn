"""Geração em PDF limitada a cláusulas integralmente aprovadas do book."""
from __future__ import annotations
import hashlib
import io
import json
import os
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, KeepTogether
from fastapi import HTTPException

CATALOG_PATH = Path(os.environ.get("BJN_CLAUSE_CATALOG", str(Path(__file__).resolve().parents[2] / "config" / "bjn_clauses_approved.json")))


def _load_approved_catalog() -> dict:
    """Recusa catálogos não homologados, vazios ou inconsistentes."""
    if not CATALOG_PATH.is_file():
        raise HTTPException(409, "Book não homologado: catálogo de cláusulas inexistente; contrato PDF bloqueado.")
    try:
        catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise HTTPException(409, "Catálogo jurídico inválido ou inacessível.") from exc
    if catalog.get("approval_status") != "approved" or not catalog.get("approved_by") or not catalog.get("source_book_sha256"):
        raise HTTPException(409, "Catálogo sem aprovação jurídica ou vínculo verificável ao book.")
    # A origem declarada deve corresponder ao ZIP do book fornecido, sem substituições.
    source_archive = Path(__file__).resolve().parents[2] / "docs" / "bjn_evidencias" / "book_clausulas.zip"
    if not source_archive.is_file() or hashlib.sha256(source_archive.read_bytes()).hexdigest() != catalog["source_book_sha256"]:
        raise HTTPException(409, "O hash do book não corresponde ao arquivo-fonte anexado.")
    clauses = catalog.get("clauses")
    if not isinstance(clauses, list) or not clauses:
        raise HTTPException(409, "Catálogo jurídico sem cláusulas homologadas.")
    for item in clauses:
        if not isinstance(item, dict) or not all(item.get(k) for k in ("id", "source_image", "text", "text_sha256")):
            raise HTTPException(409, "Cláusula sem identificação, fonte, texto ou hash.")
        digest = hashlib.sha256(item["text"].encode("utf-8")).hexdigest()
        if digest != item["text_sha256"]:
            raise HTTPException(409, f"Integridade textual não verificada: {item['id']}.")
    return catalog


def generate_pdf(clause_ids: list[str]) -> bytes:
    """Produz PDF exclusivamente com textos literais do catálogo homologado.

    Nenhum LLM, paráfrase, preenchimento automático ou trecho externo participa da composição.
    """
    catalog = _load_approved_catalog()
    index = {item["id"]: item for item in catalog["clauses"]}
    if not clause_ids or len(clause_ids) != len(set(clause_ids)) or any(i not in index for i in clause_ids):
        raise HTTPException(422, "Seleção contém cláusula inexistente, duplicada ou vazia.")
    output = io.BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4, leftMargin=56, rightMargin=56, topMargin=54, bottomMargin=54,
                            title="Minuta contratual BJN", author="BJN")
    style = ParagraphStyle("clause", fontName="Helvetica", fontSize=10, leading=15,
                           spaceAfter=14, alignment=TA_JUSTIFY, textColor=colors.HexColor("#24272D"))
    story = []
    for clause_id in clause_ids:
        item = index[clause_id]
        # Preserve quebras de linha e caracteres literais; escape apenas marcação de PDF/ReportLab.
        paragraphs = [Paragraph(escape(line), style) for line in item["text"].split("\n") if line.strip()]
        if not paragraphs:
            raise HTTPException(409, f"Cláusula vazia: {clause_id}.")
        story.extend(paragraphs)
        story.append(Spacer(1, 6))
    doc.build(story)
    return output.getvalue()
