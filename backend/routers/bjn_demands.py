"""API de cadastro, andamento, distribuição e visualização de demandas BJN."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import ValidationError, Field
from backend.contracts.base import Contract
from backend.services.bjn_demand_ai import DemandGuidanceInput
from backend.services.bjn_journey import TriageInput, routing_decision, NATURES, CompetenceReview, OpinionPublish, validate_journey_fields, issue_triage_proof, verify_triage_proof
from backend.services.bjn_notifications import dispatch_notifications
from backend.services.bjn_demand_store import DEMO_LAWYERS

from backend.errors import ErrorField, ServiceError
from backend.services.bjn_demand_store import (
    Actor, Assignment, DemandCreate, DemandStore, MAX_DOCUMENTS_PER_DEMAND,
    StatusUpdate, SavedDocument, save_upload,
)

router = APIRouter(prefix="/bjn/demandas", tags=["BJN · Demandas"])


def actor_from(request: Request) -> Actor:
    """Aceita identidade do gateway; nunca utiliza um nome informado no formulário.

    O gateway deve remover cabeçalhos enviados pelo cliente e injetar os valores
    após autenticação. Modo local é explícito e não deve ser publicado externamente.
    """
    settings = request.app.state.settings
    if settings.environment == "local":
        user_id = request.headers.get("X-Authenticated-User", "local.admin@example.invalid").strip().lower()
        role = request.headers.get("X-Authenticated-Role", "admin").strip().lower()
        display_name = request.headers.get("X-Authenticated-Name", "Usuário local de desenvolvimento").strip()
    else:
        user_id = request.headers.get("X-Authenticated-User", "").strip().lower()
        role = request.headers.get("X-Authenticated-Role", "solicitante").strip().lower()
        display_name = request.headers.get("X-Authenticated-Name", "").strip()
    if not user_id or len(user_id) > 250 or role not in {"solicitante", "advogado", "admin"}:
        raise ServiceError("Identidade corporativa não validada.", 401, code="MISSING_IDENTITY")
    return Actor(user_id, display_name[:150] or user_id, role)


def store_from(request: Request) -> DemandStore:
    """Recupera repositório injetado na inicialização da aplicação."""
    return request.app.state.bjn_demand_store


def _uploaded(request: Request, files: list[UploadFile], category: str) -> list[SavedDocument]:
    """Valida limites e conteúdo antes de criar qualquer demanda no banco."""
    if len(files) > MAX_DOCUMENTS_PER_DEMAND:
        raise ServiceError("Limite de documentos excedido.", 422, code="TOO_MANY_FILES")
    store = store_from(request)
    saved: list[SavedDocument] = []
    try:
        for file in files:
            if not file.filename:
                continue
            saved.append(save_upload(file.file, file.filename, file.content_type or "", store.uploads, category))
        return saved
    except Exception:
        for item in saved:
            item.temp_path.unlink(missing_ok=True)
        raise


def _cleanup(documents: list[SavedDocument]) -> None:
    """Descarta arquivos temporários caso o banco rejeite o cadastro."""
    for item in documents:
        item.temp_path.unlink(missing_ok=True)


@router.get("/configuracao")
def demand_configuration(request: Request) -> dict:
    """Publica apenas dados de controle necessários à interface."""
    actor = actor_from(request)
    return {
        "actor": {"name": actor.display_name, "role": actor.role, "email": actor.user_id if "@" in actor.user_id else ""},
        "allowed_lawyers": store_from(request).allowed_lawyers if actor.role == "admin" else [],
        "lawyer_options": [{"email": e, "name": DEMO_LAWYERS.get(e, e) if e in request.app.state.bjn_demo_lawyers else e, "demo": e in request.app.state.bjn_demo_lawyers} for e in store_from(request).allowed_lawyers] if actor.role == "admin" else [],
        "ai_available": request.app.state.bjn_demand_ai.available,
        "opinion_ai_available": request.app.state.bjn_opinion_ai.bridge.configured,
        # Disponível somente na máquina de desenvolvimento e com perfis fictícios habilitados.
        "demo_session_available": request.app.state.settings.environment == "local" and bool(request.app.state.bjn_demo_lawyers),
        "available_natures": list(NATURES),
        "max_file_size_mb": 15,
        "max_files": MAX_DOCUMENTS_PER_DEMAND,
        "accepted_formats": ["PDF", "PNG", "JPEG"],
    }


@router.get("")
def list_demands(request: Request, status: str = "", search: str = "", limit: int = Query(50, ge=1, le=50),
                 branch: str = "", registered_email: str = "", from_date: str = "", client_cpf: str = "") -> dict:
    """Filtros adicionais preservam restrições de visibilidade por usuário."""
    return {"items": store_from(request).list_demands(actor_from(request), status, search, limit,
               branch=branch, registered_email=registered_email, from_date=from_date, client_cpf=client_cpf)}


def _public_validation_fields(error: ValidationError) -> list[ErrorField]:
    """Traduz os campos rejeitados sem repetir valores nem metadados sensíveis do formulário."""
    known_fields = {
        "legal_department": "Departamento jurídico",
        "consult_area": "Área de consulta",
        "service_nature": "Natureza do serviço",
        "title": "Título da demanda",
        "description": "Descrição da consulta",
        "type": "Tipo do envolvido",
        "name": "Nome do envolvido",
        "document": "Documento do envolvido",
        "period": "Período do envolvido",
    }
    fields: list[ErrorField] = []
    for problem in error.errors():
        parts = problem.get("loc", ())
        name = next((part for part in reversed(parts) if isinstance(part, str) and part in known_fields), None)
        if name is None:
            fields.append(ErrorField(field="formulario", message="Verifique a estrutura do formulário."))
            continue
        prefix = ""
        if parts and parts[0] == "involved":
            index = next((part for part in parts if isinstance(part, int)), None)
            prefix = f"Envolvido {index + 1}: " if index is not None else "Envolvidos: "
        fields.append(ErrorField(field=name, message=f"{prefix}revise {known_fields[name].lower()}."))
    return fields


class DemandSearch(Contract):
    """Consulta com filtros no corpo da requisição para não expor CPF na URL."""
    search: str = Field(default="", max_length=120)
    status: str = Field(default="", max_length=40)
    branch: str = Field(default="", max_length=40)
    registered_email: str = Field(default="", max_length=120)
    from_date: str = Field(default="", max_length=10)
    client_cpf: str = Field(default="", max_length=14)


@router.post("/consulta")
def search_demands(body: DemandSearch, request: Request) -> dict:
    """Pesquisa demandas autorizadas sem vazar documento pessoal em query string."""
    return {"items": store_from(request).list_demands(actor_from(request), body.status, body.search, 50,
        branch=body.branch, registered_email=body.registered_email,
        from_date=body.from_date, client_cpf=body.client_cpf)}


@router.post("/{demand_id}/notificacoes/reprocessar")
def retry_notification(demand_id: str, request: Request) -> dict:
    """Somente administração pode reenviar notificações pendentes de publicação."""
    actor = actor_from(request)
    if actor.role != "admin":
        raise ServiceError("Reenvio restrito à administração.", 403, code="FORBIDDEN")
    store_from(request).get_demand(demand_id, actor)
    return dispatch_notifications(store_from(request), request.app.state.settings, demand_id)


@router.post("/triagem")
def triage_demand(body: TriageInput, request: Request) -> dict:
    """Aplica a triagem sem criar demanda nem executar encaminhamento externo."""
    actor = actor_from(request)
    result = routing_decision(body)
    if result["requires_registration"]:
        result["proof"] = issue_triage_proof(actor.user_id, store_from(request).document_key)
    return result


@router.post("/fluxo", status_code=201)
def create_journey_demand(request: Request, payload: Annotated[str, Form()], files: Annotated[list[UploadFile] | None, File()] = None) -> dict:
    """Cadastro com validações obrigatórias por natureza e protocolo gerado no servidor."""
    try:
        data = DemandCreate.model_validate_json(payload)
    except ValidationError as exc:
        raise ServiceError("Revise os dados do cadastro.", 422, code="INVALID_FORM", fields=_public_validation_fields(exc)) from exc
    if not store_from(request).document_key:
        raise ServiceError("A configuração de proteção do CPF está ausente.", 503, code="DOCUMENT_KEY_MISSING")
    actor = actor_from(request)
    if not verify_triage_proof(data.triage_proof, actor.user_id, store_from(request).document_key):
        raise ServiceError("Triagem ausente ou expirada. Retorne à primeira etapa.", 409, code="TRIAGE_EXPIRED")
    validate_journey_fields(data, len(files or []))
    uploaded = _uploaded(request, files or [], "ANEXO")
    try:
        return store_from(request).create(data, actor_from(request), uploaded)
    finally:
        _cleanup(uploaded)


@router.post("", status_code=201)
def create_demand(request: Request, payload: Annotated[str, Form()], files: Annotated[list[UploadFile] | None, File()] = None) -> dict:
    """Recebe formulário e arquivos via multipart, de modo atômico."""
    try:
        data = DemandCreate.model_validate_json(payload)
    except ValidationError as exc:
        raise ServiceError(
            "Há campos inválidos na demanda.", 422, code="INVALID_FORM",
            fields=_public_validation_fields(exc),
        ) from exc
    except ValueError as exc:
        raise ServiceError("Não foi possível ler o formulário enviado.", 422, code="INVALID_FORM") from exc
    if request.app.state.settings.environment != "local":
        raise ServiceError("Use o cadastro de demandas com triagem obrigatória.", 409, code="JOURNEY_REQUIRED")
    uploaded = _uploaded(request, files or [], "ANEXO")
    try:
        return store_from(request).create(data, actor_from(request), uploaded)
    finally:
        _cleanup(uploaded)


@router.post("/assistente/analisar")
def analyze_draft(body: DemandGuidanceInput, request: Request) -> dict:
    """Antes do cadastro, orienta sem criar demanda nem convocar advogado."""
    actor_from(request)
    guidance, prompt_hash, _ = request.app.state.bjn_demand_ai.analyze(body.description)
    return {**guidance.model_dump(), "prompt_version": prompt_hash[:12], "aviso": "Sugestão gerada por IA. Não constitui parecer jurídico; o usuário decide se precisa de atendimento humano."}


@router.post("/{demand_id}/assistente/analisar")
def analyze_existing(demand_id: str, request: Request) -> dict:
    """Análise explícita com auditoria na demanda e documentos fora do contexto do modelo."""
    actor = actor_from(request)
    store = store_from(request)
    demand = store.get_demand(demand_id, actor)
    guidance, prompt_hash, description_hash = request.app.state.bjn_demand_ai.analyze(demand["description"])
    return store.save_ai_guidance(demand_id, actor, guidance, prompt_hash, description_hash)


@router.patch("/{demand_id}/assistente/resolver")
def resolve_existing(demand_id: str, request: Request) -> dict:
    """Confirmar autoatendimento depende de clique do solicitante e de regras no banco."""
    return store_from(request).resolve_with_ai(demand_id, actor_from(request))


@router.patch("/{demand_id}/competencia")
def review_competence(demand_id: str, body: CompetenceReview, request: Request) -> dict:
    """Triagem administrativa manual para a natureza Pareceres em geral."""
    return store_from(request).review_competence(demand_id, actor_from(request), body.is_team_competence, body.destination_area)


@router.post("/{demand_id}/parecer/rascunho")
def generate_opinion(demand_id: str, request: Request) -> dict:
    """Somente advogado designado pode solicitar proposta de IA para revisão."""
    actor = actor_from(request)
    store = store_from(request)
    demand = store.demand_for_opinion(demand_id, actor)
    text, digest = request.app.state.bjn_opinion_ai.generate(demand["service_nature"], demand["description"])
    return store.save_opinion_draft(demand_id, actor, text, digest)


@router.post("/{demand_id}/parecer/publicar")
def publish_opinion(demand_id: str, body: OpinionPublish, request: Request) -> dict:
    """O clique de revisão do advogado é condição obrigatória para publicação."""
    if not body.human_review_confirmed:
        raise ServiceError("O advogado deve confirmar a revisão humana.", 422, code="REVIEW_REQUIRED")
    actor = actor_from(request)
    store = store_from(request)
    published = store.publish_opinion(demand_id, actor, body.final_text)
    # Envio é posterior ao commit da publicação e não bloqueia o retorno jurídico.
    # Protocolos antigos podem não ter destinatário: publicação não depende do SMTP.
    notification = (dispatch_notifications(store, request.app.state.settings, demand_id)
                    if published.get("registration") and published["registration"].get("requester_email")
                    else {"status": "SEM_EMAIL_CADASTRADO", "count": 0})
    return {**published, "notification_dispatch": notification}


@router.get("/{demand_id}")
def demand_details(demand_id: str, request: Request) -> dict:
    """Agrega detalhes, documentos e histórico para a tela de acompanhamento."""
    return store_from(request).get_demand(demand_id, actor_from(request))


@router.post("/{demand_id}/documentos")
def attach_documents(demand_id: str, request: Request, files: Annotated[list[UploadFile], File()]) -> dict:
    """Adiciona novos documentos enviados, preservando os originais."""
    if not files:
        raise ServiceError("Selecione ao menos um documento.", 422, code="MISSING_FILES")
    store = store_from(request)
    store.get_demand(demand_id, actor_from(request))
    uploaded = _uploaded(request, files, "DOCUMENTO_ENVIADO")
    if not uploaded:
        raise ServiceError("Selecione ao menos um documento.", 422, code="MISSING_FILES")
    try:
        return store.add_documents(demand_id, actor_from(request), uploaded)
    finally:
        _cleanup(uploaded)


@router.get("/{demand_id}/documentos/{document_id}/arquivo")
def view_document(demand_id: str, document_id: str, request: Request) -> FileResponse:
    """Entrega documento autenticado para prévia inline sem expor o diretório privado."""
    path, document = store_from(request).document(demand_id, document_id, actor_from(request))
    return FileResponse(
        path,
        media_type=document["media_type"],
        filename=document["original_name"],
        content_disposition_type="inline",
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"},
    )


@router.patch("/{demand_id}/atribuicao")
def assign_demand(demand_id: str, body: Assignment, request: Request) -> dict:
    """Atribui advogado autorizado por ação explícita de administrador."""
    return store_from(request).assign(demand_id, actor_from(request), body.lawyer_email)


@router.patch("/{demand_id}/status")
def change_status(demand_id: str, body: StatusUpdate, request: Request) -> dict:
    """Atualiza o andamento somente por pessoa autorizada."""
    return store_from(request).update_status(demand_id, actor_from(request), body)
