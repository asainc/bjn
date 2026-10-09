"""Erros públicos estruturados, estáveis e sem conteúdo sensível."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class ErrorField:
    """Erro associado a um campo sem repetir o valor recebido."""

    field: str
    message: str
    type: str | None = None


class ServiceError(Exception):
    """Falha esperada com código de máquina e mensagem segura para a interface.

    A assinatura também aceita o código HTTP como segundo argumento posicional, como em ``ServiceError(msg, 409)``.
    Novos pontos devem informar ``code=`` para que o frontend não dependa do texto.
    """

    def __init__(
        self,
        message: str,
        status_code: int = 422,
        *,
        code: str = "DOMAIN_ERROR",
        fields: Iterable[ErrorField] | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.fields = tuple(fields or ())
        self.retryable = retryable

    def payload(self, request_id: str | None = None) -> dict[str, object]:
        """Serializa somente metadados públicos previamente controlados."""
        fields = [
            {"field": item.field, "message": item.message, "type": item.type}
            for item in self.fields
        ]
        return {
            "code": self.code,
            "message": self.message,
            "fields": fields,
            "retryable": self.retryable,
            "request_id": request_id,
            # Alias temporário para consumidores v1; novos clientes usam message/fields.
            "detail": self.message,
        }
