"""Inicialização FastAPI da aplicação AI Ready."""
from __future__ import annotations

import json
import logging
import os
import secrets
from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.access import require_access
from backend.config import Settings, load_settings
from backend.contracts.base import Contract
from backend.errors import ServiceError
from backend.routers import processes, bjn, bjn_demands
from backend.services.bradesco_bridge import BradescoBridgeClient
from backend.services.chat_service import ChatService
from backend.services.process_intelligence import ProcessIntelligenceService
from backend.services.workspace_store import WorkspaceStore
from backend.services.bjn_demand_store import DemandStore, DEMO_LAWYERS
from backend.services.bjn_demand_ai import BjnDemandAIService
from backend.services.bjn_opinion import OpinionAIService
from backend.services.bjn_document_opinion import BjnDocumentOpinionService
from backend.version import API_CONTRACT_VERSION, API_PREFIX, APP_VERSION


class Health(Contract):
    """Resposta mínima de disponibilidade da API."""

    status: str = "ok"
    versao_api: str = API_CONTRACT_VERSION


class StructuredFormatter(logging.Formatter):
    """Serializa somente metadados técnicos, nunca o texto dos documentos."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {"level": record.levelname, "event": record.getMessage()}
        for key in ("request_id", "status_code", "duration_ms", "error_type"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(payload, ensure_ascii=False)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Cria a API com dependências explícitas e workspace documental temporário."""
    configuration = settings or load_settings()
    bridge = BradescoBridgeClient(configuration)
    store = WorkspaceStore(configuration)
    process_intelligence = ProcessIntelligenceService(configuration, bridge, store)
    chat_service = ChatService(configuration, bridge)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield

    app = FastAPI(title="AI Ready - Assistente Processual Cível", version=APP_VERSION, lifespan=lifespan)
    app.state.settings = configuration
    app.state.bridge = bridge
    app.state.process_intelligence = process_intelligence
    app.state.chat_service = chat_service
    app.state.bjn_chat_service = ChatService(configuration, bridge)
    app.state.bjn_demand_ai = BjnDemandAIService(bridge)
    app.state.bjn_opinion_ai = OpinionAIService(bridge)
    app.state.bjn_document_opinion = BjnDocumentOpinionService(bridge)
    # A chave HMAC é fornecida externamente. Em desenvolvimento local, a chave
    # é criada uma única vez no diretório privado e não acompanha o código.
    cpf_key = configuration.bjn_document_hash_key.get_secret_value()
    if configuration.environment == "local" and not cpf_key:
        private_key_path = configuration.bjn_database_path.parent / ".bjn-cpf-local.key"
        private_key_path.parent.mkdir(parents=True, exist_ok=True)
        if not private_key_path.exists():
            try:
                descriptor = os.open(private_key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(descriptor, "w", encoding="ascii") as handle:
                    handle.write(secrets.token_hex(32))
            except FileExistsError:
                pass
        cpf_key = private_key_path.read_text(encoding="ascii").strip()
    # Equipe fictícia é habilitada apenas quando o modo de desenvolvimento é explícito.
    demo_lawyers = list(DEMO_LAWYERS) if configuration.environment == "local" and configuration.bjn_demo_lawyers_enabled else []
    app.state.bjn_demo_lawyers = demo_lawyers
    app.state.bjn_demand_store = DemandStore(
        configuration.bjn_database_path,
        configuration.bjn_upload_directory,
        [*configuration.bjn_allowed_lawyers, *demo_lawyers],
        document_key=cpf_key,
    )

    logger = logging.getLogger("ai_ready")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(StructuredFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False

    app.add_middleware(
        CORSMiddleware,
        allow_origins=configuration.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        # Cabeçalhos de perfis fictícios são aceitos apenas no desenvolvimento local.
        # Em produção, o gateway controla a identidade e não há simulação de perfil.
        allow_headers=(["Content-Type", "X-Request-ID", "X-Authenticated-Role", "X-Authenticated-User", "X-Authenticated-Name"]
                       if configuration.environment == "local" else ["Content-Type", "X-Request-ID"]),
    )

    @app.middleware("http")
    async def request_log(request: Request, call_next):
        """Registra duração e status sem gravar caminho, prompt ou conteúdo dos autos."""
        request_id = uuid4().hex
        request.state.request_id = request_id
        started = perf_counter()
        try:
            response = await call_next(request)
        except Exception as error:
            logger.error("request_failed", extra={"request_id": request_id, "error_type": type(error).__name__})
            response = JSONResponse(
                status_code=500,
                content={
                    "code": "INTERNAL_ERROR",
                    "message": "Falha interna. Informe o identificador da requisição ao suporte.",
                    "fields": [],
                    "retryable": False,
                    "request_id": request_id,
                },
            )
        response.headers["X-Request-ID"] = request_id
        response.headers["X-API-Version"] = API_CONTRACT_VERSION
        response.headers["Cache-Control"] = "no-store"
        logger.info(
            "request_completed",
            extra={"request_id": request_id, "status_code": response.status_code, "duration_ms": round((perf_counter() - started) * 1000, 2)},
        )
        return response

    @app.exception_handler(ServiceError)
    async def service_error(request: Request, error: ServiceError):
        return JSONResponse(status_code=error.status_code, content=error.payload(getattr(request.state, "request_id", None)))

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError):
        details = [
            {"field": ".".join(str(item) for item in problem["loc"]), "type": problem["type"], "message": problem["msg"]}
            for problem in error.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "code": "VALIDATION_ERROR",
                "message": "Revise os campos informados.",
                "fields": details,
                "retryable": False,
                "request_id": getattr(request.state, "request_id", None),
            },
        )

    api = APIRouter(dependencies=[Depends(require_access)])

    @api.get("/saude", response_model=Health, tags=["Saúde"])
    def health() -> Health:
        return Health()

    api.include_router(processes.router)
    api.include_router(bjn.router)
    api.include_router(bjn_demands.router)
    app.include_router(api, prefix=API_PREFIX)
    return app


aplicacao = create_app()
