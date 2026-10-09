import gpt_bradesco


def test_agente_informacional_posts_expected_payload(monkeypatch) -> None:
    captured = {}

    def fake_call(operation, method, url, **kwargs):
        captured.update({"operation": operation, "method": method, "url": url, **kwargs})
        return {"answer": "ok"}

    monkeypatch.setattr(gpt_bradesco, "_call", fake_call)
    payload = {
        "workflow_code": "CD_WRFL_QA_778_LEITURA_SENTENCA_PIAUI_AAJR_SYNC",
        "question": "pergunta teste",
        "async_mode": False,
    }

    result = gpt_bradesco.agente_informacional(payload, {"ambiente": "dev"})

    assert result == {"answer": "ok"}
    assert captured["operation"] == "qa.question"
    assert captured["method"] == "POST"
    assert captured["payload"] == payload
    assert captured["url"].endswith("/iagen-qa/v1/chats/questions")
