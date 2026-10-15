"""Regressões da publicação de parecer, com identidades e dados sintéticos."""
from pathlib import Path
from tempfile import TemporaryDirectory
from fastapi.testclient import TestClient
from pydantic import SecretStr

from backend.config import Settings
from backend.principal import create_app
from backend.services.bjn_demand_store import DEMO_LAWYERS
from tests.test_bjn_journey import BASE, identity, send


FINAL = ("Parecer de teste revisado integralmente pela pessoa designada. "
         "Nenhuma decisão jurídica foi produzida automaticamente.")


def test_demo_lawyer_can_review_and_publish_after_admin_assignment():
    """Simula a mudança de perfil que faltava na interface, sem liberar administração."""
    with TemporaryDirectory() as root:
        lawyer = next(iter(DEMO_LAWYERS))
        app = create_app(Settings(environment="local", bjn_database_path=Path(root)/"db.sqlite3",
                                  bjn_upload_directory=Path(root)/"uploads", bjn_demo_lawyers_enabled=True))
        client = TestClient(app)
        created = send(client)
        assert created.status_code == 201
        uid = created.json()["id"]
        admin_config = client.get(f"{BASE}/configuracao", headers=identity("admin")).json()
        assert admin_config["demo_session_available"]
        assert lawyer in admin_config["allowed_lawyers"]
        assert client.patch(f"{BASE}/{uid}/atribuicao", headers=identity("admin"),
                            json={"lawyer_email": lawyer}).status_code == 200
        request = {"final_text": FINAL, "human_review_confirmed": True}
        forbidden = client.post(f"{BASE}/{uid}/parecer/publicar", headers=identity("admin"), json=request)
        assert forbidden.status_code == 403
        assert client.get(f"{BASE}/{uid}", headers=identity("admin")).json()["can_review_opinion"] is False
        reviewer = {"X-Authenticated-User": lawyer, "X-Authenticated-Role": "advogado",
                    "X-Authenticated-Name": "Advogado sintetico de testes"}
        detail = client.get(f"{BASE}/{uid}", headers=reviewer)
        assert detail.status_code == 200
        assert detail.json()["can_review_opinion"] is True
        published = client.post(f"{BASE}/{uid}/parecer/publicar", headers=reviewer, json=request)
        assert published.status_code == 200, published.text
        assert published.json()["status"] == "CONCLUIDA"
        assert published.json()["opinion"]["reviewer_id"] == lawyer
        assert published.json()["notification_dispatch"]["status"] == "PENDENTE_CONFIGURACAO"
        assert client.get(f"{BASE}/{uid}", headers=identity("solicitante")).json()["opinion"]["final_text"] == FINAL
        assert client.post(f"{BASE}/{uid}/parecer/publicar", headers=reviewer, json=request).status_code == 409


def test_legacy_demand_publishes_without_notification_email():
    """Não impede parecer manual de demanda pré-existente sem tabela de cadastro."""
    from backend.services.bjn_demand_store import DemandCreate
    with TemporaryDirectory() as root:
        app = create_app(Settings(environment="local", bjn_database_path=Path(root)/"db.sqlite3",
                                  bjn_upload_directory=Path(root)/"uploads", bjn_allowed_lawyers=["advogado@example.invalid"]))
        store = app.state.bjn_demand_store
        from backend.services.bjn_demand_store import Actor
        requester = Actor("solicitante@example.invalid", "Solicitante sintético", "solicitante")
        created = store.create(DemandCreate(legal_department="Jurídico", consult_area="Agências",
                  service_nature="Pareceres em geral", title="Parecer legado",
                  description="Consulta antiga com dados de teste e nenhum e-mail de cadastro."), requester, [])
        client = TestClient(app)
        uid = created["id"]
        assert client.patch(f"{BASE}/{uid}/atribuicao", headers=identity("admin"),
                     json={"lawyer_email":"advogado@example.invalid"}).status_code == 200
        published = client.post(f"{BASE}/{uid}/parecer/publicar", headers=identity("advogado"),
                                json={"final_text":FINAL,"human_review_confirmed":True})
        assert published.status_code == 200, published.text
        assert published.json()["notification_dispatch"] == {"status":"SEM_EMAIL_CADASTRADO","count":0}
        assert client.get(f"{BASE}/{uid}", headers=identity()).json()["opinion"]["final_text"] == FINAL
        assert store.pending_notifications(uid) == []


def test_demo_reviewer_disabled_in_published_environment():
    """Uma configuração de demo indevida nunca ativa perfis fictícios em produção."""
    with TemporaryDirectory() as root:
        settings = Settings(environment="prod", gateway_token=SecretStr("x"*40),
                            bjn_database_path=Path(root)/"db.sqlite3",
                            bjn_upload_directory=Path(root)/"uploads", bjn_demo_lawyers_enabled=True)
        app = create_app(settings)
        client = TestClient(app)
        response = client.get(f"{BASE}/configuracao", headers={"X-Gateway-Token":"x"*40,**identity("admin")})
        assert response.status_code == 200
        assert not response.json()["demo_session_available"]
        assert not response.json()["lawyer_options"]
        preflight = client.options(f"{BASE}/configuracao", headers={
            "Origin": "http://localhost:4200", "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-Authenticated-User"})
        assert "x-authenticated-user" not in preflight.headers.get("access-control-allow-headers", "").lower()
