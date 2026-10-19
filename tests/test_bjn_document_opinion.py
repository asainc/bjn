"""Verifica seleção por natureza, extração e gravação, usando exclusivamente dados sintéticos."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pymupdf
import pytest
from fastapi.testclient import TestClient

from backend.config import Settings
from backend.principal import create_app
from backend.errors import ServiceError
from backend.services.bjn_document_opinion import BjnDocumentOpinionService, PROMPTS

BASE = "/api/v3/bjn/demandas"
USER = {"X-Authenticated-User": "solicitante@example.invalid", "X-Authenticated-Role": "solicitante"}


class BridgeFake:
    """Simula retorno controlado sem sair do ambiente local."""
    configured = True
    def __init__(self) -> None:
        self.prompts: list[str] = []
    def generate_text(self, payload: str, *, max_tokens: int) -> str:
        self.prompts.append(payload)
        return "SUGESTÃO PRELIMINAR PARA REVISÃO. Documento de teste. " + ("Análise não conclusiva; validar informações e comprovações. " * 3)


def pdf_sintetico() -> bytes:
    """Gera PDF com camada de texto, sem dados pessoais nem terceiros reais."""
    pdf = pymupdf.open()
    page = pdf.new_page()
    page.insert_text((55, 70), "Documento de teste com poderes restritos para representacao. " * 3)
    result = pdf.tobytes()
    pdf.close()
    return result


@pytest.mark.parametrize("nature,filename", list(PROMPTS.items()))
def test_prompt_especifico_e_documento_validado(nature: str, filename: str) -> None:
    """Comprova que a natureza usa seu próprio .md e não o prompt de outra natureza."""
    bridge = BridgeFake()
    service = BjnDocumentOpinionService(bridge)
    suggestion = service.analyze(nature, "Dúvida de teste sintética", [("teste.pdf", "application/pdf", pdf_sintetico())])
    text = (Path(__file__).parents[1] / "prompts" / "bjn" / "naturezas" / filename).read_text(encoding="utf-8")
    assert text in bridge.prompts[-1]
    assert "Página 1" in bridge.prompts[-1]
    assert suggestion.nature == nature
    assert suggestion.prompt_hash and suggestion.source_hash
    assert suggestion.documents_analyzed == 1
    assert "SUGESTÃO PRELIMINAR" in suggestion.text


def test_imagens_e_pdf_digitalizado_nao_geram_inferencia() -> None:
    """Impede inventar conteúdo quando a camada textual não existe."""
    service = BjnDocumentOpinionService(BridgeFake())
    with pytest.raises(ServiceError) as photo:
        service.analyze("Inventário", "", [("imagem.jpg", "image/jpeg", b"\xff\xd8\xff" + b"a" * 100)])
    assert photo.value.code == "DOCUMENT_TEXT_UNAVAILABLE"
    blank = pymupdf.open(); blank.new_page(); content = blank.tobytes(); blank.close()
    with pytest.raises(ServiceError) as scanned:
        service.analyze("Alvará", "", [("digitalizado.pdf", "application/pdf", content)])
    assert scanned.value.code == "DOCUMENT_TEXT_UNAVAILABLE"


def test_upload_gera_sugestao_sem_publicar_e_usa_departamento_solicitante() -> None:
    """A prévia não cria protocolo; o registro grava sugestão, não parecer definitivo."""
    with TemporaryDirectory() as directory:
        root = Path(directory)
        app = create_app(Settings(environment="local", bradesco_text_model="fake-text-model", bradesco_identificador="test-id", bradesco_senha="test-password",
                bjn_database_path=root / "bjn.db", bjn_upload_directory=root / "uploads"))
        fake = BridgeFake()
        app.state.bjn_document_opinion = BjnDocumentOpinionService(fake)
        client = TestClient(app)
        document = pdf_sintetico()
        preview = client.post(BASE + "/assistente/analisar-documentos", headers=USER,
            data={"nature": "Procuração", "description": "Consulta de teste"},
            files=[("files", ("exemplo.pdf", document, "application/pdf"))])
        assert preview.status_code == 200, preview.text
        assert preview.json()["nature"] == "Procuração"
        assert client.get(BASE, headers=USER).json()["items"] == []
        data = {"requesting_department": "Negócios regionais", "consult_area": "Negócios regionais",
                "service_nature": "Procuração", "title": "Protocolo sintético", "description": "Consulta sintética de representação com documentos anexados."}
        created = client.post(BASE, headers=USER, data={"payload": json.dumps(data)},
            files=[("files", ("exemplo.pdf", document, "application/pdf"))])
        assert created.status_code == 201, created.text
        info = created.json()
        assert info["requesting_department"] == "Negócios regionais"
        assert "legal_department" not in info
        assert info["document_ai_suggestion"]["nature"] == "Procuração"
        assert info["opinion"] is None
        assert info["status"] == "RECEBIDA"
        assert client.get(BASE + "/" + info["id"], headers={"X-Authenticated-Role": "solicitante", "X-Authenticated-User": "outra@example.invalid"}).status_code == 404


def test_agent_workflow_is_not_a_duplicate_hardcoded_default() -> None:
    """O código do agente deve ser configurado pelo .env, e não no Settings."""
    assert Settings().bradesco_qa_workflow_code == ""
