"""Rotas do workspace processual AI Ready."""
from __future__ import annotations

from fastapi import APIRouter, File, Request, UploadFile

from backend.contracts import AiReadyConfiguration, ChatRequest, ChatResponse, ProcessWorkspaceResponse

router = APIRouter(prefix="/ai-ready", tags=["AI Ready"])


def _service(request: Request):
    return request.app.state.process_intelligence


def _chat_service(request: Request):
    return request.app.state.chat_service


@router.get("/configuracao", response_model=AiReadyConfiguration)
def configuration(request: Request) -> AiReadyConfiguration:
    """Informa limites da interface sem expor segredos ou endpoints corporativos."""
    settings = request.app.state.settings
    return AiReadyConfiguration(
        geracao_texto_configurada=request.app.state.bridge.configured,
        chat_qa_configurado=request.app.state.bridge.qa_configured,
        limite_arquivos=settings.max_upload_files,
        limite_mb_por_arquivo=settings.max_upload_bytes // (1024 * 1024),
        limite_total_mb=settings.max_total_upload_bytes // (1024 * 1024),
    )


@router.post("/analisar", response_model=ProcessWorkspaceResponse)
async def analyze(request: Request, files: list[UploadFile] = File(...)) -> ProcessWorkspaceResponse:
    """Cria um workspace temporário a partir de PDFs de um processo cível."""
    return await _service(request).analyze_uploads(files)


@router.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest, request: Request) -> ChatResponse:
    """Encaminha ao agente corporativo a pergunta digitada no chatbot."""
    return _chat_service(request).ask(body.pergunta)


@router.delete("/{workspace_id}", status_code=204)
def discard(workspace_id: str, request: Request) -> None:
    """Permite remover imediatamente o contexto documental mantido em memória."""
    _service(request).discard(workspace_id)
