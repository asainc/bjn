"""Cobertura de configuração da Bridge usando somente credenciais fictícias."""
from pathlib import Path
from tempfile import TemporaryDirectory
from fastapi.testclient import TestClient
from backend.config import Settings, load_settings, text_model_configuration_diagnostic
from backend.principal import create_app
from backend.services.bradesco_bridge import BradescoBridgeClient


def test_diagnostico_distingue_deployment_e_credenciais():
    """Nunca confunde workflow Q&A e credenciais com deployment de texto."""
    base = {"bradesco_identificador": "fake-id", "bradesco_senha": "fake-password", "bradesco_qa_workflow_code": "workflow-ficticio"}
    # O caso sem deployment agora precisa ser explícito, pois existe um padrão.
    bridge = BradescoBridgeClient(Settings(bradesco_text_model="", **base))
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
                                  bradesco_identificador="fake-id", bradesco_senha="fake-password", bradesco_text_model=""))
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


def test_env_da_raiz_nao_e_apagado_por_variavel_corporativa_vazia(monkeypatch):
    """Reproduz o falso erro quando o Windows herda BRADESCO_TEXT_MODEL vazio."""
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        env = root / '.env'
        env.write_text(
            'BRADESCO_IDENTIFICADOR=identificador-de-teste\n'
            'BRADESCO_SENHA=senha-de-teste\n'
            'BRADESCO_TEXT_MODEL=deployment-de-teste\n',
            encoding='utf-8',
        )
        monkeypatch.setenv('APP_ENV_FILE', str(env))
        monkeypatch.setenv('BRADESCO_TEXT_MODEL', '')
        monkeypatch.setenv('BRADESCO_IDENTIFICADOR', '  ')
        monkeypatch.setenv('BRADESCO_SENHA', '')
        settings = load_settings()
        assert settings.bradesco_text_model == 'deployment-de-teste'
        assert BradescoBridgeClient(settings).configured
        source = text_model_configuration_diagnostic(settings)
        assert source['origem_modelo'] == 'arquivo_env'
        assert source['variavel_vazia_ignoravel'] is True
        assert source['modelo_carregado_pela_api'] is True
        assert 'deployment-de-teste' not in str(source)
        assert 'senha-de-teste' not in str(source)


def test_variavel_corporativa_nao_vazia_tem_precedencia(monkeypatch):
    """Mantém possibilidade de configuração via gerenciador de segredos externo."""
    with TemporaryDirectory() as temporary:
        env = Path(temporary) / '.env'
        env.write_text('BRADESCO_TEXT_MODEL=deployment-do-arquivo\n', encoding='utf-8')
        monkeypatch.setenv('APP_ENV_FILE', str(env))
        monkeypatch.setenv('BRADESCO_TEXT_MODEL', 'deployment-do-processo')
        settings = load_settings()
        assert settings.bradesco_text_model == 'deployment-do-processo'
        source = text_model_configuration_diagnostic(settings)
        assert source['origem_modelo'] == 'variavel_do_processo'
        assert 'deployment-do-processo' not in str(source)


def test_arquivo_env_relativo_independe_do_diretorio_atual(monkeypatch, tmp_path):
    """APP_ENV_FILE relativo resolve sempre a partir da raiz da aplicação."""
    import backend.config as config_module
    monkeypatch.setattr(config_module, 'ROOT', tmp_path)
    (tmp_path / 'settings.env').write_text('BRADESCO_TEXT_MODEL=deployment-sintetico\n', encoding='utf-8')
    monkeypatch.setenv('APP_ENV_FILE', 'settings.env')
    monkeypatch.delenv('BRADESCO_TEXT_MODEL', raising=False)
    monkeypatch.chdir(tmp_path.parent)
    settings = load_settings()
    assert settings.bradesco_text_model == 'deployment-sintetico'
    assert text_model_configuration_diagnostic(settings)['arquivo_env_encontrado'] is True


def test_diagnostico_aponta_env_em_pasta_incorreta(monkeypatch, tmp_path):
    """Aponta um .env em backend quando a raiz ainda não tem configuração."""
    import backend.config as config_module
    monkeypatch.setattr(config_module, 'ROOT', tmp_path)
    monkeypatch.delenv('APP_ENV_FILE', raising=False)
    monkeypatch.delenv('BRADESCO_TEXT_MODEL', raising=False)
    (tmp_path / 'backend').mkdir()
    (tmp_path / 'backend' / '.env').write_text('BRADESCO_TEXT_MODEL=nao-deve-ser-carregado\n', encoding='utf-8')
    settings = load_settings()
    diagnosis = text_model_configuration_diagnostic(settings)
    assert diagnosis['env_em_backend_em_vez_da_raiz'] is True
    assert diagnosis['modelo_carregado_pela_api'] is True
    assert diagnosis['origem_modelo'] == 'padrao'


def test_modelo_padrao_sem_configuracao_explicita():
    """O valor padrão mantém o gerador identificado mesmo sem variável externa."""
    from backend.config import DEFAULT_BRADESCO_TEXT_MODEL

    settings = Settings()
    assert settings.bradesco_text_model == DEFAULT_BRADESCO_TEXT_MODEL == "gpt-5.1"
    assert BradescoBridgeClient(settings).text_generator_status()["code"] == "BRIDGE_CREDENTIALS_MISSING"


def test_modelo_padrao_com_variaveis_vazias_e_json_vazio(monkeypatch, tmp_path):
    """Campos vazios não devem desativar o deployment padrão."""
    env = tmp_path / ".env"
    env.write_text("BRADESCO_TEXT_MODEL=   \n", encoding="utf-8")
    config = tmp_path / "app.settings.json"
    config.write_text('{"bradesco_text_model": ""}', encoding="utf-8")
    monkeypatch.setenv("APP_ENV_FILE", str(env))
    monkeypatch.setenv("APP_CONFIG_PATH", str(config))
    monkeypatch.setenv("BRADESCO_TEXT_MODEL", "")

    settings = load_settings()
    assert settings.bradesco_text_model == "gpt-5.1"
    assert text_model_configuration_diagnostic(settings)["modelo_carregado_pela_api"] is True


def test_modelo_customizado_substitui_padrao(monkeypatch, tmp_path):
    """Um deployment corporativo explícito continua tendo precedência."""
    env = tmp_path / ".env"
    env.write_text("BRADESCO_TEXT_MODEL=deployment-homologado\n", encoding="utf-8")
    monkeypatch.setenv("APP_ENV_FILE", str(env))
    monkeypatch.delenv("APP_CONFIG_PATH", raising=False)
    monkeypatch.delenv("BRADESCO_TEXT_MODEL", raising=False)

    assert load_settings().bradesco_text_model == "deployment-homologado"
