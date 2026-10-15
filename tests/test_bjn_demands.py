"""Fluxo de demanda com documentos sintéticos e validação de permissões."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from backend.config import Settings
from backend.principal import create_app

BASE = "/api/v3/bjn/demandas"  # Adequar ao prefixo publicado na versão do projeto.


def create_client(root: Path) -> TestClient:
    """Instancia banco isolado por teste, sem arquivos reais de pessoas."""
    settings = Settings(
        environment="local", bjn_database_path=root / "demandas.sqlite3",
        bjn_upload_directory=root / "uploads",
        bjn_allowed_lawyers=["lawyer@example.invalid"],
    )
    return TestClient(create_app(settings))


def actor(email: str, role: str = "solicitante") -> dict[str, str]:
    """No modo local, simula headers que um gateway corporativo confiável atribuiria."""
    return {"X-Authenticated-User": email, "X-Authenticated-Role": role, "X-Authenticated-Name": "Usuario sintetico"}


def payload() -> dict:
    """Cria um cadastro completamente fictício, sem informação bancária ou pessoal."""
    return {
        "legal_department": "Jurídico de testes", "consult_area": "Consultas",
        "service_nature": "Orientação contratual", "title": "Solicitação sintética",
        "description": "Descrição sintética suficientemente longa para validação.",
        "involved": [{"type": "Pessoa jurídica", "name": "Organização fictícia", "document": "", "period": ""}],
    }


def test_create_list_detail_and_preview_access():
    """Valida persistência, acesso a anexo e isolamento entre solicitantes."""
    with TemporaryDirectory() as directory:
        client = create_client(Path(directory))
        original = b"%PDF-1.4\n1 0 obj<<>>endobj\n%%EOF\n"
        response = client.post(BASE, headers=actor("requester@example.invalid"), data={"payload": json.dumps(payload())}, files=[("files", ("evidencia.pdf", original, "application/pdf"))])
        assert response.status_code == 201, response.text
        item = response.json()
        assert item["status"] == "RECEBIDA"
        assert item["lawyer_email"] is None
        assert item["requester_id"] == "requester@example.invalid"
        assert item["involved"][0]["name"] == "Organização fictícia"
        document = item["documents"][0]
        assert document["category"] == "ANEXO"
        assert len(item["events"]) == 1
        route = f"{BASE}/{item['id']}/documentos/{document['id']}/arquivo"
        assert client.get(route, headers=actor("requester@example.invalid")).content == original
        assert client.get(f"{BASE}/{item['id']}", headers=actor("other@example.invalid")).status_code == 404
        assert client.get(route, headers=actor("other@example.invalid")).status_code == 404
        assert client.get(BASE, headers=actor("other@example.invalid")).json()["items"] == []
        assert len(client.get(BASE, headers=actor("requester@example.invalid")).json()["items"]) == 1


def test_admin_distribution_status_timeline_and_later_documents():
    """Somente administração distribui e somente responsável atualiza andamento."""
    with TemporaryDirectory() as directory:
        client = create_client(Path(directory))
        created = client.post(BASE,headers=actor("requester@example.invalid"),data={"payload":json.dumps(payload())}).json()
        item_id = created["id"]
        assert client.patch(f"{BASE}/{item_id}/atribuicao",headers=actor("requester@example.invalid"),json={"lawyer_email":"lawyer@example.invalid"}).status_code == 403
        assert client.patch(f"{BASE}/{item_id}/atribuicao",headers=actor("admin@example.invalid","admin"),json={"lawyer_email":"unknown@example.invalid"}).status_code == 422
        assigned = client.patch(f"{BASE}/{item_id}/atribuicao",headers=actor("admin@example.invalid","admin"),json={"lawyer_email":"lawyer@example.invalid"})
        assert assigned.status_code == 200, assigned.text
        assert assigned.json()["lawyer_email"] == "lawyer@example.invalid"
        assert assigned.json()["status"] == "EM_ANALISE"
        assert client.get(f"{BASE}/{item_id}",headers=actor("lawyer@example.invalid","advogado")).status_code == 200
        assert client.patch(f"{BASE}/{item_id}/status",headers=actor("requester@example.invalid"),json={"status":"CONCLUIDA"}).status_code == 403
        updated = client.patch(f"{BASE}/{item_id}/status",headers=actor("lawyer@example.invalid","advogado"),json={"status":"AGUARDANDO_INFORMACOES"})
        assert updated.status_code == 200
        assert len(updated.json()["events"]) == 3
        extra = client.post(f"{BASE}/{item_id}/documentos",headers=actor("requester@example.invalid"),files=[("files",("imagem.png",b"\x89PNG\r\n\x1a\n"+b"\x00"*25,"image/png"))])
        assert extra.status_code == 200, extra.text
        assert extra.json()["documents"][0]["category"] == "DOCUMENTO_ENVIADO"
        assert len(extra.json()["events"]) == 4


def test_reject_non_pdf_and_invalid_form():
    """Não aceita arquivo com MIME falso nem cadastro incompleto."""
    with TemporaryDirectory() as directory:
        client = create_client(Path(directory))
        bad = client.post(BASE, data={"payload":json.dumps(payload())},files=[("files",("fake.pdf",b"Hello, world!","application/pdf"))])
        assert bad.status_code == 415
        assert client.get(BASE).json()["items"] == []
        invalid = client.post(BASE, data={"payload":json.dumps({"title":"X"})})
        assert invalid.status_code == 422


def test_config_has_no_fake_lawyer_and_status_transition_is_enforced():
    """Nunca atribui advogado sem ação e rejeita transições inválidas."""
    with TemporaryDirectory() as directory:
        client = create_client(Path(directory))
        item=client.post(BASE,data={"payload":json.dumps(payload())}).json()
        demand_id=item["id"]
        assert client.patch(f"{BASE}/{demand_id}/status",json={"status":"CONCLUIDA"}).status_code == 409
        config=client.get(f"{BASE}/configuracao").json()
        assert config["allowed_lawyers"]==["lawyer@example.invalid"]
        assert config["actor"]["role"]=="admin"


def test_optional_involved_and_no_attachments_can_be_registered():
    """Confirma que a API não exige envolvidos nem anexos para cadastrar uma demanda."""
    with TemporaryDirectory() as directory:
        client = create_client(Path(directory))
        request_payload = payload()
        request_payload["involved"] = []
        response = client.post(BASE, data={"payload": json.dumps(request_payload)})
        assert response.status_code == 201, response.text
        saved = response.json()
        assert saved["involved"] == []
        assert saved["documents"] == []
        assert saved["status"] == "RECEBIDA"
        assert client.get(f"{BASE}/{saved['id']}").status_code == 200


def test_invalid_form_returns_field_without_echoing_input():
    """Aponta o campo inconsistente sem copiar dados contratuais ao erro público."""
    with TemporaryDirectory() as directory:
        client = create_client(Path(directory))
        request_payload = payload()
        request_payload["description"] = "TEST-PRIVATE"
        response = client.post(BASE, data={"payload": json.dumps(request_payload)})
        assert response.status_code == 422
        failure = response.json()
        assert failure["code"] == "INVALID_FORM"
        assert any(field["field"] == "description" for field in failure["fields"])
        assert request_payload["description"] not in str(failure)
