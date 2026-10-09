"""Controle de acesso da API atrás do gateway corporativo."""
import secrets

from fastapi import Request

from backend.errors import ServiceError


def require_access(request: Request) -> None:
    """Em ambiente publicado, aceita apenas chamadas validadas pelo gateway."""
    settings = request.app.state.settings
    if settings.environment == "local":
        return
    supplied = request.headers.get("X-Gateway-Token", "")
    if not secrets.compare_digest(supplied, settings.gateway_token.get_secret_value()):
        raise ServiceError("Acesso permitido somente pelo gateway autenticado.", 403, code="ACESSO_NEGADO")
