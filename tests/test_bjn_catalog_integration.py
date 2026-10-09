"""Testes sintéticos de integração do catálogo ordenado com a prévia BJN."""
from backend.services.bjn_book_preview import catalog_records, selected_book_clauses


def test_catalog_preserves_152_unique_records():
    records = catalog_records()
    assert len(records) == 152
    assert len({item['ID'] for item in records}) == 152
    assert all(item['Texto literal (OCR a conferir)'] for item in records)


def test_lgpd_yes_uses_only_explicit_catalog_identifiers():
    clauses = selected_book_clauses({'personal_data': 'sim'})
    assert [section['id'] for clause in clauses for section in clause['sections']] == [
        'BOOK-P02-T004', 'BOOK-P02-T005', 'BOOK-P02-T006'
    ]
    assert all(clause['status'] == 'OCR_PENDENTE_CONFERENCIA' for clause in clauses)


def test_lgpd_no_does_not_add_lgpd_text():
    assert selected_book_clauses({'personal_data': 'nao'}) == []
