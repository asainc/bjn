from types import SimpleNamespace

from backend.config import Settings
from backend.services.bradesco_bridge import BradescoBridgeClient


def test_generate_text_uses_text_generator(monkeypatch) -> None:
    calls = []

    def text_generator(payload, parameters):
        calls.append((payload, parameters))
        return "resposta"

    module = SimpleNamespace(text_generator=text_generator)
    client = BradescoBridgeClient(Settings(bradesco_text_model="deployment-teste"))
    monkeypatch.setattr(client, "_module", module)

    result = client.generate_text("pergunta", max_tokens=2000)

    assert result == "resposta"
    assert calls[0][0] == "pergunta"
    assert calls[0][1]["deployment_name"] == "deployment-teste"
    assert calls[0][1]["async_mode"] is False
    assert calls[0][1]["stream"] is False


def test_answer_question_uses_agente_informacional_without_rewriting(monkeypatch) -> None:
    calls = []

    def text_generator(payload, parameters):
        return "nao usado"

    def agente_informacional(payload):
        calls.append(payload)
        return {"answer": "Resposta corporativa\ncom duas linhas."}

    module = SimpleNamespace(
        text_generator=text_generator,
        agente_informacional=agente_informacional,
    )
    settings = Settings(
        bradesco_text_model="deployment-teste",
        bradesco_qa_workflow_code="CD_WRFL_QA_778_LEITURA_SENTENCA_PIAUI_AAJR_SYNC",
    )
    client = BradescoBridgeClient(settings)
    monkeypatch.setattr(client, "_module", module)

    question = "faça um resumo da petição inicial do gcpj 2000039753"
    result = client.answer_question(question)

    assert result == "Resposta corporativa\ncom duas linhas."
    assert calls == [{
        "workflow_code": "CD_WRFL_QA_778_LEITURA_SENTENCA_PIAUI_AAJR_SYNC",
        "question": question,
        "async_mode": False,
    }]
