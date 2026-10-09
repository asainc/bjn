"""Testes de segurança da emissão de contratos."""
import hashlib
from pathlib import Path
import json
import pytest
from fastapi import HTTPException
from backend.services import bjn_pdf

def test_missing_catalog_blocks_pdf(monkeypatch, tmp_path):
    monkeypatch.setattr(bjn_pdf, "CATALOG_PATH", tmp_path / "missing.json")
    with pytest.raises(HTTPException) as failure:
        bjn_pdf.generate_pdf(["CLAUSE-001"])
    assert failure.value.status_code == 409

def test_changed_clause_text_blocks_pdf(monkeypatch, tmp_path):
    path = tmp_path / "approved.json"
    path.write_text(json.dumps({"approval_status":"approved","approved_by":"Juridico",
        "source_book_sha256":"a"*64,"clauses":[{"id":"CLAUSE-001", "source_image":"page1.jpg",
        "text":"texto alterado", "text_sha256":hashlib.sha256(b"texto original").hexdigest()}]}))
    monkeypatch.setattr(bjn_pdf, "CATALOG_PATH", path)
    with pytest.raises(HTTPException) as failure:
        bjn_pdf.generate_pdf(["CLAUSE-001"])
    assert failure.value.status_code == 409

def test_validated_clauses_generate_pdf(monkeypatch, tmp_path):
    path = tmp_path / "approved.json"
    text = "CLAUSULA DEMONSTRATIVA PARA TESTE, NAO EXTRAIDA DO BOOK."
    path.write_text(json.dumps({"approval_status":"approved","approved_by":"Fixture de teste",
        "source_book_sha256":hashlib.sha256((Path(bjn_pdf.__file__).resolve().parents[2] / "docs/bjn_evidencias/book_clausulas.zip").read_bytes()).hexdigest(),"clauses":[{"id":"TEST-001", "source_image":"fixture.jpg",
        "text":text, "text_sha256":hashlib.sha256(text.encode()).hexdigest()}]}))
    monkeypatch.setattr(bjn_pdf, "CATALOG_PATH", path)
    assert bjn_pdf.generate_pdf(["TEST-001"]).startswith(b"%PDF-")
