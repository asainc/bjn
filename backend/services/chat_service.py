"""Serviço do chatbot corporativo de perguntas e respostas."""
from __future__ import annotations

from backend.config import Settings
from backend.contracts import ChatResponse
from backend.errors import ServiceError
from backend.services.bradesco_bridge import BradescoBridgeClient


class ChatService:
    """Mantém o chat separado da análise local dos PDFs."""

    def __init__(self, settings: Settings, bridge: BradescoBridgeClient):
        self.settings = settings
        self.bridge = bridge

    def ask(self, question: str) -> ChatResponse:
        """Envia a pergunta sem reescrita ao workflow Q&A e devolve ``answer``."""
        if not self.bridge.qa_configured:
            raise ServiceError(
                "O workflow corporativo de perguntas e respostas não está configurado.",
                503,
                code="CHAT_QA_NAO_CONFIGURADO",
                retryable=False,
            )
        answer = self.bridge.answer_question(question)
        return ChatResponse(
            resposta=answer,
            aviso="Resposta retornada pela API corporativa de perguntas e respostas. Confirme informações críticas nas fontes oficiais antes do uso profissional.",
        )
