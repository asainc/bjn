"""Seleciona trechos exclusivamente da planilha de cláusulas com origem verificável."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from zipfile import ZipFile
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / 'config' / 'catalogo_clausulas_bjn.xlsx'
MAPPING = ROOT / 'config' / 'bjn_book_image_mappings.json'
IMAGES = ROOT / 'backend' / 'bjn_book_images'
MAIN_NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'


def _sheet_rows(path: Path) -> list[dict]:
    """Lê a primeira aba XLSX sem acrescentar dependências ao backend corporativo."""
    with ZipFile(path) as archive:
        strings = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            root = ET.fromstring(archive.read('xl/sharedStrings.xml'))
            strings = [''.join(n.itertext()) for n in root.findall(f'{MAIN_NS}si')]
        sheet = ET.fromstring(archive.read('xl/worksheets/sheet1.xml'))
        matrix = []
        for row in sheet.findall(f'.//{MAIN_NS}sheetData/{MAIN_NS}row'):
            fields = {}
            for cell in row.findall(f'{MAIN_NS}c'):
                col = ''.join(ch for ch in cell.attrib['r'] if ch.isalpha())
                inline = cell.find(f'{MAIN_NS}is')
                value = cell.find(f'{MAIN_NS}v')
                if inline is not None:
                    fields[col] = ''.join(inline.itertext())
                elif value is not None:
                    fields[col] = strings[int(value.text)] if cell.get('t') == 's' else (value.text or '')
            matrix.append(fields)
    if not matrix:
        raise ValueError('Catálogo Excel vazio')
    headers = matrix[0]
    return [{name: row.get(col, '') for col, name in headers.items()} for row in matrix[1:]]


def catalog_records() -> list[dict]:
    """Lê o catálogo ordenado de quatro colunas e rejeita dados incompletos.

    A extração OCR é preliminar: registros carregados não são automaticamente
    considerados cláusulas aprovadas para emissão contratual.
    """
    try:
        records = _sheet_rows(CATALOG)
    except (OSError, ValueError, ET.ParseError, KeyError, IndexError) as exc:
        raise HTTPException(409, f'Catálogo de cláusulas indisponível: {exc}') from exc
    expected = {'ID', 'Tema', 'Número / título', 'Texto literal (OCR a conferir)'}
    if not records or not expected.issubset(records[0]):
        raise HTTPException(409, 'Cabeçalho do catálogo incompatível com as quatro colunas esperadas')
    ids = set()
    for record in records:
        identifier = record['ID'].strip()
        if not identifier or identifier in ids or not record['Texto literal (OCR a conferir)'].strip():
            raise HTTPException(409, 'ID duplicado, vazio ou texto ausente no catálogo')
        ids.add(identifier)
    return records


def selected_book_clauses(answers: dict) -> list[dict]:
    """Exibe somente registros expressamente vinculados a uma resposta do script.

    A matriz de vínculos é separada da planilha para preservar suas quatro colunas.
    Não são criadas regras com base em semelhança textual ou palavras-chave.
    """
    mapping = json.loads(MAPPING.read_text(encoding='utf-8'))
    records = {row['ID']: row for row in catalog_records()}
    selected = []
    for rule in mapping['rules']:
        if answers.get(rule['question_id']) != rule['value']:
            continue
        for reference in rule['book_pages']:
            original = IMAGES / reference['file']
            if not original.is_file() or hashlib.sha256(original.read_bytes()).hexdigest() != reference['sha256']:
                raise HTTPException(409, 'Imagem original alterada ou ausente')
        sections = []
        for clause_id in rule.get('catalog_ids', []):
            row = records.get(clause_id)
            if row is None:
                raise HTTPException(409, f'ID vinculado não existe no catálogo: {clause_id}')
            sections.append({'id': clause_id, 'heading':row['Número / título'],
                             'text':row['Texto literal (OCR a conferir)'],
                             'status':'OCR_PENDENTE_CONFERENCIA'})
        if not sections:
            raise HTTPException(409, f'Regra sem cláusulas explicitamente mapeadas: {rule["clause_id"]}')
        selected.append({'clause_id':rule['clause_id'], 'title':rule['title'],
                         'sections':sections, 'status':'OCR_PENDENTE_CONFERENCIA',
                         'source_page':rule['book_pages'][0]['page'],
                         'remaining_pages':len(rule['book_pages']) - 1})
    return selected

def book_image(filename: str) -> bytes:
    """Recupera evidência original, restrita às páginas cadastradas."""
    mapping = json.loads(MAPPING.read_text(encoding='utf-8'))
    allowed = {p['file']: p['sha256'] for r in mapping['rules'] for p in r['book_pages']}
    if filename not in allowed:
        raise HTTPException(404, 'Página não mapeada')
    path = IMAGES / filename
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != allowed[filename]:
        raise HTTPException(409, 'Integridade da página não confirmada')
    return path.read_bytes()
