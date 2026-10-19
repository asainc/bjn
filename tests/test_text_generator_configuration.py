"""Cobertura de configuração da Bridge usando somente credenciais fictícias."""
from pathlib import Path
from tempfile import TemporaryDirectory
from fastapi.testclient import TestClient
from backend.config import Settings, load_settings
from backend.principal import create_app
from backend.services.bradesco_bridge import BradescoBridgeClient


def test_diagnostico_distingue_deployment_e_credenciais():
    """Nunca confunde workflow Q&A e credenciais com deployment de texto."""
    base = {"bradesco_identificador": "fake-id", "bradesco_senha": "fake-password", "bradesco_qa_workflow_code": "workflow-ficticio"}
    bridge = BradescoBridgeClient(Settings(**base))
    assert not bridge.configured
    assert bridge.text_generator_status()["code"] == "TEXT_MODEL_MISSING"
    assert "fake-password" not in str(bridge.text_generator_status())
    only_model = BradescoBridgeClient(Settings(bradesco_text_model="deployment-ficticio"))
    assert not only_model.configured
    assert only_model.text_generator_status()["code"] == "BRIDGE_CREDENTIALS_MISSING"
    ready = BradescoBridgeClient(Settings(bradesco_text_model="deployment-ficticio", **base))
    assert ready.configured
    assert ready.text_generator_status()["code"] == "CONFIGURED_NOT_TESTED"
    assert "ficticio" not in str(ready.text_generator_status())


def test_configuracao_expoe_apenas_estado_e_nao_credenciais():
    """A UI recebe orientação verificável sem qualquer segredo no JSON."""
    with TemporaryDirectory() as temporary:
        path = Path(temporary)
        app = create_app(Settings(bjn_database_path=path / "db.sqlite", bjn_upload_directory=path / "uploads",
                                  bradesco_identificador="fake-id", bradesco_senha="fake-password"))
        with TestClient(app) as client:
            response = client.get('/api/v3/bjn/demandas/configuracao')
        assert response.status_code == 200
        data = response.json()
        assert not data["ai_available"]
        assert data["ai_configuration"]["code"] == "TEXT_MODEL_MISSING"
        assert 'fake-password' not in response.text
        assert 'fake-id' not in response.text


def test_env_da_raiz_prevalece_sobre_json_e_gera_estado_pronto(monkeypatch):
    """O backend consome as variáveis padronizadas em vez de configuração de Q&A."""
    with TemporaryDirectory() as temporary:
        path = Path(temporary)
        env = path / '.env'
        env.write_text('BRADESCO_IDENTIFICADOR=fake-id\nBRADESCO_SENHA=fake-password\nBRADESCO_TEXT_MODEL=deployment-ficticio\n', encoding='utf-8')
        config = path / 'settings.json'
        config.write_text('{"bradesco_text_model": ""}', encoding='utf-8')
        monkeypatch.setenv('APP_ENV_FILE', str(env))
        monkeypatch.setenv('APP_CONFIG_PATH', str(config))
        for name in ['BRADESCO_IDENTIFICADOR', 'BRADESCO_SENHA', 'BRADESCO_TEXT_MODEL']:
            monkeypatch.delenv(name, raising=False)
        settings = load_settings()
        assert BradescoBridgeClient(settings).configured
        assert settings.bradesco_text_model == 'deployment-ficticio'
