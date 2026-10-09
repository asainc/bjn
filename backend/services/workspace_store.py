"""Armazenamento temporário e limitado dos workspaces processuais em memória."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import RLock

from backend.config import Settings
from backend.contracts import ProcessOverview, TimelineEvent
from backend.errors import ServiceError
from backend.services.pdf_text_extractor import PdfTextDocument


@dataclass(frozen=True)
class WorkspaceContext:
    """Dados temporários necessários para responder perguntas sobre um conjunto de PDFs."""

    workspace_id: str
    created_at: datetime
    overview: ProcessOverview
    timeline: tuple[TimelineEvent, ...]
    documents: tuple[PdfTextDocument, ...]


class WorkspaceStore:
    """Cache com TTL para evitar persistência desnecessária do texto dos autos."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._items: dict[str, WorkspaceContext] = {}
        self._lock = RLock()

    def _purge_expired(self) -> None:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=self.settings.workspace_ttl_minutes)
        expired = [key for key, value in self._items.items() if value.created_at < cutoff]
        for key in expired:
            self._items.pop(key, None)

    def put(self, context: WorkspaceContext) -> None:
        """Inclui um workspace e remove o mais antigo se o limite for atingido."""
        with self._lock:
            self._purge_expired()
            if len(self._items) >= self.settings.max_workspaces_in_memory:
                oldest = min(self._items.values(), key=lambda item: item.created_at)
                self._items.pop(oldest.workspace_id, None)
            self._items[context.workspace_id] = context

    def get(self, workspace_id: str) -> WorkspaceContext:
        """Retorna contexto ativo ou orienta novo upload após expiração."""
        with self._lock:
            self._purge_expired()
            context = self._items.get(workspace_id)
            if context is None:
                raise ServiceError(
                    "A sessão documental expirou ou não existe. Envie os PDFs novamente.",
                    404,
                    code="WORKSPACE_INDISPONIVEL",
                )
            return context

    def remove(self, workspace_id: str) -> None:
        with self._lock:
            self._items.pop(workspace_id, None)
