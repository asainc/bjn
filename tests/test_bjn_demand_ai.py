"""Fluxo de IA com saída simulada, sem enviar dados a serviços externos."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend.config import Settings
from backend.principal import create_app
from backend.services.bjn_demand_ai import BjnDemandAIService

BASE = "/api/v3/bjn/demandas"
SYNTHETIC_DESCRIPTION = "Como localizar o canal interno de consulta e acompanhar uma solicitação de teste?"


def fake_app(directory: Path, ai_enabled: bool = True, demos: bool = False):
    """Simula API corporativa retornando JSON bem formado para testes reprodutíveis."""
    settings = Settings(
        environment="local", bjn_database_path=directory / "db.sqlite3",
        bjn_upload_directory=directory / "files", bjn_demo_lawyers_enabled=demos,
        bradesco_text_model="MODEL_TEST" if ai_enabled else "", bradesco_identificador="test-id", bradesco_senha="test-password",
    )
    app = create_app(settings)
    return app


def actor(name: str, role: str = "solicitante") -> dict:
    return {"X-Authenticated-User": name, "X-Authenticated-Role": role, "X-Authenticated-Name": "Pessoa de teste"}


def payload():
    return {"legal_department": "Jurídico", "consult_area": "Consultivo", "service_nature": "Suporte",
            "title": "Pesquisa interna", "description": SYNTHETIC_DESCRIPTION, "involved": []}


def response(kind: str = "POSSIVEL_AUTOATENDIMENTO") -> str:
    return json.dumps({"resumo": "Como acompanhar o registro da demanda",
                       "orientacao": "Consulte a página de acompanhamento para verificar o status da solicitação.",
                       "passos_sugeridos": ["Acesse a lista de demandas", "Selecione a demanda para ver o histórico"],
                       "encaminhamento": kind}, ensure_ascii=False)


def attach_fake(app, kind="POSSIVEL_AUTOATENDIMENTO"):
    """A substituição do adaptador testa a orquestração sem tráfego real."""
    app.state.bjn_demand_ai.bridge.generate_text = lambda prompt, max_tokens: response(kind)


def test_draft_ai_never_creates_demand_and_uses_only_description():
    with TemporaryDirectory() as path:
        app = fake_app(Path(path))
        seen = []
        def fake_generate(prompt, max_tokens):
            seen.append(prompt)
            return response()
        app.state.bjn_demand_ai.bridge.generate_text = fake_generate
        with TestClient(app) as client:
            result = client.post(f"{BASE}/assistente/analisar", json={"description": SYNTHETIC_DESCRIPTION}, headers=actor("a@example.invalid"))
            assert result.status_code == 200, result.text
            assert result.json()["encaminhamento"] == "POSSIVEL_AUTOATENDIMENTO"
            assert SYNTHETIC_DESCRIPTION in seen[0]
            assert "<system>" in seen[0]
            assert client.get(BASE).json()["items"] == []


def test_explicit_self_service_requires_owner_not_assigned_and_ai_suggestion():
    with TemporaryDirectory() as path:
        app = fake_app(Path(path))
        attach_fake(app)
        with TestClient(app) as client:
            owner = actor("owner@example.invalid")
            created = client.post(BASE, data={"payload": json.dumps(payload())}, headers=owner).json()
            demand_id = created["id"]
            assert client.patch(f"{BASE}/{demand_id}/assistente/resolver", headers=owner).status_code == 409
            assert client.post(f"{BASE}/{demand_id}/assistente/analisar", headers=actor("intruder@example.invalid")).status_code == 404
            suggestion = client.post(f"{BASE}/{demand_id}/assistente/analisar", headers=owner)
            assert suggestion.status_code == 200, suggestion.text
            assert suggestion.json()["ai_guidance"]["resumo"] == "Como acompanhar o registro da demanda"
            assert suggestion.json()["status"] == "RECEBIDA"
            assert suggestion.json()["lawyer_email"] is None
            assert client.patch(f"{BASE}/{demand_id}/assistente/resolver", headers=actor("intruder@example.invalid")).status_code == 404
            resolved = client.patch(f"{BASE}/{demand_id}/assistente/resolver", headers=owner)
            assert resolved.status_code == 200, resolved.text
            assert resolved.json()["status"] == "RESOLVIDA_IA"
            assert resolved.json()["lawyer_email"] is None
            assert any(event["event_type"] == "AUTOATENDIMENTO" for event in resolved.json()["events"])
            assert client.patch(f"{BASE}/{demand_id}/atribuicao", json={"lawyer_email":"lawyer@example.invalid"}).status_code in (409,422)


def test_human_recommendation_cannot_self_close():
    with TemporaryDirectory() as path:
        app = fake_app(Path(path))
        attach_fake(app, "ATENDIMENTO_HUMANO")
        with TestClient(app) as client:
            entry = client.post(BASE, data={"payload": json.dumps(payload())}).json()
            demand_id = entry["id"]
            checked = client.post(f"{BASE}/{demand_id}/assistente/analisar")
            assert checked.status_code == 200
            assert checked.json()["ai_guidance"]["encaminhamento"] == "ATENDIMENTO_HUMANO"
            assert client.patch(f"{BASE}/{demand_id}/assistente/resolver").status_code == 409


def test_demo_lawyers_local_only_and_manual_distribution():
    with TemporaryDirectory() as path:
        app = fake_app(Path(path), ai_enabled=False, demos=True)
        with TestClient(app) as client:
            config = client.get(f"{BASE}/configuracao").json()
            assert config["ai_available"] is False
            assert len(config["lawyer_options"]) == 4
            assert all(option["demo"] is True for option in config["lawyer_options"])
            demo_email = config["lawyer_options"][0]["email"]
            demand = client.post(BASE, data={"payload": json.dumps(payload())}).json()
            assigned = client.patch(f"{BASE}/{demand['id']}/atribuicao", json={"lawyer_email":demo_email})
            assert assigned.status_code == 200
            assert assigned.json()["lawyer_email"] == demo_email
            assert client.post(f"{BASE}/assistente/analisar", json={"description":SYNTHETIC_DESCRIPTION}).status_code == 503


def test_invalid_model_json_fails_closed_and_does_not_save_guidance():
    with TemporaryDirectory() as path:
        app = fake_app(Path(path))
        app.state.bjn_demand_ai.bridge.generate_text = lambda prompt, max_tokens: "Texto sem JSON"
        with TestClient(app) as client:
            entry = client.post(BASE,data={"payload":json.dumps(payload())}).json()
            failed = client.post(f"{BASE}/{entry['id']}/assistente/analisar")
            assert failed.status_code == 502
            assert client.get(f"{BASE}/{entry['id']}").json()["ai_guidance"] is None


def test_production_never_adds_demo_lawyers():
    # Ambiente publicado deve contar somente com lista explícita de advogados.
    with TemporaryDirectory() as path:
        app = create_app(Settings(environment="homol", gateway_token="t"*40,
                                  bjn_database_path=Path(path)/"db.sqlite3",
                                  bjn_upload_directory=Path(path)/"files",
                                  bjn_demo_lawyers_enabled=True))
        assert app.state.bjn_demand_store.allowed_lawyers == []


def test_assigned_demand_cannot_be_resolved_by_ai():
    """Distribuição humana prevalece mesmo após sugestão informacional favorável."""
    with TemporaryDirectory() as path:
        app = fake_app(Path(path), demos=True)
        attach_fake(app)
        with TestClient(app) as client:
            owner = actor("owner@example.invalid")
            created = client.post(BASE, data={"payload":json.dumps(payload())}, headers=owner).json()
            demand_id = created["id"]
            assert client.post(f"{BASE}/{demand_id}/assistente/analisar", headers=owner).status_code == 200
            demo_email = client.get(f"{BASE}/configuracao").json()["allowed_lawyers"][0]
            assert client.patch(f"{BASE}/{demand_id}/atribuicao", json={"lawyer_email":demo_email}).status_code == 200
            assert client.patch(f"{BASE}/{demand_id}/assistente/resolver", headers=owner).status_code == 409
            assert client.get(f"{BASE}/{demand_id}", headers=owner).json()["status"] == "EM_ANALISE"
