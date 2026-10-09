from backend.config import Settings
from backend.services.chat_service import ChatService


class FakeBridge:
    qa_configured = True

    def __init__(self):
        self.questions = []

    def answer_question(self, question: str) -> str:
        self.questions.append(question)
        return "Resposta da API Q&A"


def test_chat_service_forwards_exact_question_and_returns_answer() -> None:
    bridge = FakeBridge()
    service = ChatService(Settings(), bridge)
    question = "Qual é o resumo do processo 123?"

    result = service.ask(question)

    assert bridge.questions == [question]
    assert result.resposta == "Resposta da API Q&A"
