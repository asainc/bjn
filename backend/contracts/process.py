"""Contratos HTTP da análise documental e do assistente processual."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from backend.contracts.base import Contract


Confidence = Literal["alta", "media", "baixa"]
TimelineCategory = Literal[
    "ajuizamento",
    "citacao",
    "manifestacao",
    "prova",
    "audiencia",
    "decisao",
    "recurso",
    "cumprimento",
    "outro",
]


class Party(Contract):
    """Parte ou participante expressamente identificado nos documentos."""

    nome: str = Field(min_length=1, max_length=300)
    papel: str = Field(min_length=1, max_length=120)


class TimelineEvent(Contract):
    """Fato processual com referência documental rastreável."""

    data: str | None = Field(default=None, max_length=20)
    titulo: str = Field(min_length=1, max_length=220)
    descricao: str = Field(min_length=1, max_length=1400)
    categoria: TimelineCategory = "outro"
    documento: str = Field(min_length=1, max_length=260)
    pagina: int | None = Field(default=None, ge=1, le=100000)
    confianca: Confidence = "media"


class DocumentSummary(Contract):
    """Metadados técnicos do PDF, sem persistir o conteúdo textual na resposta."""

    identificador: str
    nome: str
    paginas: int = Field(ge=1)
    paginas_utilizaveis: int = Field(ge=0)
    tamanho_bytes: int = Field(ge=1)
    qualidade_textual: Literal["boa", "parcial", "insuficiente"]
    alertas: list[str] = Field(default_factory=list)


class ProcessOverview(Contract):
    """Síntese factual do processo extraída dos documentos enviados."""

    numero_processo: str | None = None
    classe_processual: str | None = None
    tribunal: str | None = None
    unidade_judicial: str | None = None
    fase_processual: str | None = None
    assunto_principal: str | None = None
    valor_causa: str | None = None
    ultima_data_relevante: str | None = None
    partes: list[Party] = Field(default_factory=list)
    resumo: str
    pedidos: list[str] = Field(default_factory=list)
    fatos_controvertidos: list[str] = Field(default_factory=list)
    pontos_atencao: list[str] = Field(default_factory=list)
    proximas_acoes_sugeridas: list[str] = Field(default_factory=list)


class ProcessWorkspaceResponse(Contract):
    """Estado necessário para renderizar a tela principal do AI Ready."""

    workspace_id: str
    gerado_em: datetime
    processo: ProcessOverview
    linha_tempo: list[TimelineEvent]
    documentos: list[DocumentSummary]
    aviso: str


class ChatRequest(Contract):
    """Pergunta digitada pelo usuário na janela do chatbot."""

    pergunta: str = Field(min_length=2, max_length=8000)


class ChatResponse(Contract):
    """Resposta devolvida pelo campo ``answer`` da API corporativa Q&A."""

    resposta: str
    aviso: str


class AiReadyConfiguration(Contract):
    """Disponibilidade funcional sem expor credenciais ou configuração sensível."""

    provedor: Literal["bradesco_iagen"] = "bradesco_iagen"
    geracao_texto_configurada: bool
    chat_qa_configurado: bool
    limite_arquivos: int
    limite_mb_por_arquivo: int
    limite_total_mb: int
