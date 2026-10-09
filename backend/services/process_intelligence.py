"""Orquestra a análise processual dos PDFs usando o text_generator corporativo."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import UploadFile
from pydantic import ValidationError

from backend.config import Settings
from backend.contracts import (
    DocumentSummary,
    Party,
    ProcessOverview,
    ProcessWorkspaceResponse,
    TimelineEvent,
)
from backend.errors import ServiceError
from backend.services.bradesco_bridge import BradescoBridgeClient
from backend.services.pdf_text_extractor import PdfTextDocument, PdfTextExtractor
from backend.services.prompt_loader import render_prompt
from backend.services.workspace_store import WorkspaceContext, WorkspaceStore


class ProcessIntelligenceService:
    """Mantém a regra de negócio da jornada AI Ready em um único ponto."""

    def __init__(self, settings: Settings, bridge: BradescoBridgeClient, store: WorkspaceStore):
        self.settings = settings
        self.bridge = bridge
        self.store = store
        self.pdf_extractor = PdfTextExtractor(settings)

    async def analyze_uploads(self, files: list[UploadFile]) -> ProcessWorkspaceResponse:
        """Valida PDFs, extrai texto localmente e consolida fatos com IA generativa."""
        if not 1 <= len(files) <= self.settings.max_upload_files:
            raise ServiceError(
                f"Envie entre 1 e {self.settings.max_upload_files} PDFs por análise.",
                422,
                code="QUANTIDADE_ARQUIVOS_INVALIDA",
            )
        if not self.bridge.configured:
            raise ServiceError(
                "O deployment de geração de texto não está configurado no backend.",
                503,
                code="IA_NAO_CONFIGURADA",
                retryable=False,
            )

        documents: list[PdfTextDocument] = []
        total_bytes = 0
        for file in files:
            name = Path(file.filename or "documento.pdf").name
            if name != (file.filename or name) or not name.lower().endswith(".pdf"):
                raise ServiceError("Envie apenas arquivos PDF com nome válido.", 422, code="ARQUIVO_INVALIDO")
            if file.content_type not in {"application/pdf", "application/octet-stream", None}:
                raise ServiceError("Envie apenas arquivos PDF.", 422, code="TIPO_ARQUIVO_INVALIDO")
            content = await file.read(self.settings.max_upload_bytes + 1)
            if len(content) > self.settings.max_upload_bytes:
                raise ServiceError(
                    f"O arquivo {name} excede o limite de {self.settings.max_upload_bytes // (1024 * 1024)} MB.",
                    413,
                    code="ARQUIVO_MUITO_GRANDE",
                )
            total_bytes += len(content)
            if total_bytes > self.settings.max_total_upload_bytes:
                raise ServiceError(
                    f"O conjunto de PDFs excede o limite total de {self.settings.max_total_upload_bytes // (1024 * 1024)} MB.",
                    413,
                    code="CONJUNTO_MUITO_GRANDE",
                )
            if not content.startswith(b"%PDF-"):
                raise ServiceError(f"{name} não possui assinatura válida de PDF.", 422, code="PDF_INVALIDO")
            documents.append(self.pdf_extractor.read(identifier=uuid4().hex, name=name, content=content))

        if not any(document.paginas_utilizaveis for document in documents):
            raise ServiceError(
                "Os PDFs não possuem camada textual suficiente para análise. Envie versões pesquisáveis dos documentos.",
                422,
                code="TEXTO_INSUFICIENTE",
            )

        raw_analysis = self._analyze_documents(documents)
        overview, timeline = self._normalize_analysis(raw_analysis, documents)
        workspace_id = uuid4().hex
        created_at = datetime.now(timezone.utc)
        self.store.put(WorkspaceContext(workspace_id, created_at, overview, tuple(timeline), tuple(documents)))
        return ProcessWorkspaceResponse(
            workspace_id=workspace_id,
            gerado_em=created_at,
            processo=overview,
            linha_tempo=timeline,
            documentos=[self._document_summary(document) for document in documents],
            aviso="Conteúdo gerado por IA a partir dos PDFs enviados. Confirme fatos, datas e referências diretamente nos autos antes de uso profissional.",
        )

    def discard(self, workspace_id: str) -> None:
        """Apaga imediatamente o texto temporário do workspace da memória do processo."""
        self.store.remove(workspace_id)

    def _analyze_documents(self, documents: list[PdfTextDocument]) -> dict[str, Any]:
        """Executa análise hierárquica para não depender de um PDF caber inteiro no prompt."""
        chunks = self._chunks(documents)
        if len(chunks) > self.settings.max_analysis_chunks:
            raise ServiceError(
                f"O conjunto possui {len(chunks)} trechos de análise e excede o limite operacional de {self.settings.max_analysis_chunks}. Divida os documentos em um conjunto menor para preservar a qualidade da análise.",
                422,
                code="CONTEXTO_MUITO_EXTENSO",
            )
        partials: list[str] = []
        for index, chunk in enumerate(chunks, start=1):
            prompt = render_prompt(
                "analise_trecho.md",
                chunk_number=index,
                chunk_total=len(chunks),
                document_context=chunk,
            )
            partials.append(self.bridge.generate_text(prompt, max_tokens=min(6000, self.settings.bradesco_analysis_max_tokens)))

        final_text = self._consolidate_partials(partials)
        return self._parse_json(final_text)


    def _consolidate_partials(self, partials: list[str]) -> str:
        """Reduz análises em lotes quando a consolidação ultrapassaria o contexto.

        A redução usa o mesmo prompt de consolidação e nunca corta silenciosamente
        uma análise parcial. O processo se repete até que reste um único JSON.
        """
        budget = max(8000, self.settings.bradesco_prompt_max_chars - 7000)
        current = partials
        rounds = 0
        while len(current) > 1:
            rounds += 1
            if rounds > 6:
                raise ServiceError(
                    "Não foi possível reduzir as análises parciais ao limite de contexto configurado.",
                    502,
                    code="CONSOLIDACAO_EXCEDE_CONTEXTO",
                    retryable=True,
                )
            groups: list[list[str]] = []
            group: list[str] = []
            group_size = 0
            for item in current:
                item_size = len(item) + 40
                if item_size > budget:
                    raise ServiceError(
                        "Uma análise parcial excedeu o limite de contexto configurado. Revise o deployment ou reduza o conjunto de documentos.",
                        502,
                        code="RESPOSTA_IA_MUITO_EXTENSA",
                        retryable=True,
                    )
                if group and group_size + item_size > budget:
                    groups.append(group)
                    group = []
                    group_size = 0
                group.append(item)
                group_size += item_size
            if group:
                groups.append(group)

            # Se tudo cabe em um único grupo, essa chamada já é a consolidação final.
            next_round: list[str] = []
            for items in groups:
                prompt = render_prompt(
                    "consolidacao_processo.md",
                    partial_analyses="\n\n--- ANALISE PARCIAL ---\n".join(items),
                )
                next_round.append(self.bridge.generate_text(prompt, max_tokens=self.settings.bradesco_analysis_max_tokens))
            if len(next_round) >= len(current) and sum(map(len, next_round)) >= sum(map(len, current)):
                raise ServiceError(
                    "A consolidação não conseguiu reduzir o conteúdo ao limite de contexto. Divida os documentos em um conjunto menor.",
                    422,
                    code="CONTEXTO_MUITO_EXTENSO",
                )
            current = next_round

        if not current:
            raise ServiceError("Nenhuma análise parcial foi produzida.", 502, code="RESPOSTA_IA_VAZIA", retryable=True)
        # Mesmo uma única análise passa pelo prompt final para uniformizar o contrato.
        prompt = render_prompt("consolidacao_processo.md", partial_analyses=current[0])
        return self.bridge.generate_text(prompt, max_tokens=self.settings.bradesco_analysis_max_tokens)

    def _chunks(self, documents: list[PdfTextDocument]) -> list[str]:
        """Agrupa páginas preservando marcadores de documento e página."""
        budget = max(8000, self.settings.bradesco_prompt_max_chars - 9000)
        chunks: list[str] = []
        current: list[str] = []
        current_size = 0
        for document in documents:
            for page in document.paginas_utilizaveis:
                block = f"## DOCUMENTO: {document.nome}\n### PAGINA {page.numero}\n{page.texto}\n"
                if len(block) > budget:
                    block = block[:budget] + "\n[TEXTO DA PAGINA TRUNCADO POR LIMITE TECNICO]"
                if current and current_size + len(block) > budget:
                    chunks.append("\n".join(current))
                    current = []
                    current_size = 0
                current.append(block)
                current_size += len(block)
        if current:
            chunks.append("\n".join(current))
        return chunks or ["Nenhum texto utilizável foi extraído."]

    @staticmethod
    def _parse_json(text: str) -> dict[str, Any]:
        """Aceita JSON puro ou cercado por bloco Markdown e rejeita saídas ambíguas."""
        candidate = text.strip()
        fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", candidate, re.DOTALL | re.IGNORECASE)
        if fenced:
            candidate = fenced.group(1)
        else:
            start = candidate.find("{")
            end = candidate.rfind("}")
            if start >= 0 and end > start:
                candidate = candidate[start : end + 1]
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError as exc:
            raise ServiceError(
                "A IA respondeu em formato inesperado. Repita a análise; se persistir, valide o deployment configurado.",
                502,
                code="RESPOSTA_IA_INVALIDA",
                retryable=True,
            ) from exc
        if not isinstance(value, dict):
            raise ServiceError("A análise da IA não retornou um objeto estruturado.", 502, code="RESPOSTA_IA_INVALIDA", retryable=True)
        return value

    def _normalize_analysis(self, payload: dict[str, Any], documents: list[PdfTextDocument]) -> tuple[ProcessOverview, list[TimelineEvent]]:
        """Valida a estrutura gerada e aplica apenas defaults neutros, sem inventar fatos."""
        process_data = payload.get("processo") if isinstance(payload.get("processo"), dict) else payload
        timeline_data = payload.get("linha_tempo", [])
        if not isinstance(timeline_data, list):
            timeline_data = []

        def optional_text(value: Any) -> str | None:
            return value.strip() if isinstance(value, str) and value.strip() else None

        def string_list(value: Any, limit: int = 12) -> list[str]:
            if not isinstance(value, list):
                return []
            result: list[str] = []
            for item in value:
                if isinstance(item, str) and item.strip():
                    result.append(item.strip()[:1200])
            return result[:limit]

        parties: list[Party] = []
        for item in process_data.get("partes", []) if isinstance(process_data, dict) else []:
            if isinstance(item, dict) and optional_text(item.get("nome")) and optional_text(item.get("papel")):
                try:
                    parties.append(Party(nome=optional_text(item.get("nome")) or "", papel=optional_text(item.get("papel")) or ""))
                except ValidationError:
                    continue

        overview = ProcessOverview(
            numero_processo=optional_text(process_data.get("numero_processo")),
            classe_processual=optional_text(process_data.get("classe_processual")),
            tribunal=optional_text(process_data.get("tribunal")),
            unidade_judicial=optional_text(process_data.get("unidade_judicial")),
            fase_processual=optional_text(process_data.get("fase_processual")),
            assunto_principal=optional_text(process_data.get("assunto_principal")),
            valor_causa=optional_text(process_data.get("valor_causa")),
            ultima_data_relevante=optional_text(process_data.get("ultima_data_relevante")),
            partes=parties[:20],
            resumo=optional_text(process_data.get("resumo")) or "Não foi possível produzir um resumo confiável com o conteúdo disponível.",
            pedidos=string_list(process_data.get("pedidos")),
            fatos_controvertidos=string_list(process_data.get("fatos_controvertidos")),
            pontos_atencao=string_list(process_data.get("pontos_atencao")),
            proximas_acoes_sugeridas=string_list(process_data.get("proximas_acoes_sugeridas")),
        )

        known_documents = {document.nome for document in documents}
        events: list[TimelineEvent] = []
        allowed_categories = {"ajuizamento", "citacao", "manifestacao", "prova", "audiencia", "decisao", "recurso", "cumprimento", "outro"}
        for item in timeline_data[:80]:
            if not isinstance(item, dict):
                continue
            title = optional_text(item.get("titulo"))
            description = optional_text(item.get("descricao"))
            document = optional_text(item.get("documento"))
            if not title or not description or not document:
                continue
            if document not in known_documents:
                document = next((name for name in known_documents if name.lower() == document.lower()), document)
            category = item.get("categoria") if item.get("categoria") in allowed_categories else "outro"
            confidence = item.get("confianca") if item.get("confianca") in {"alta", "media", "baixa"} else "media"
            page = item.get("pagina") if isinstance(item.get("pagina"), int) and item.get("pagina") > 0 else None
            try:
                events.append(
                    TimelineEvent(
                        data=optional_text(item.get("data")),
                        titulo=title,
                        descricao=description,
                        categoria=category,
                        documento=document,
                        pagina=page,
                        confianca=confidence,
                    )
                )
            except ValidationError:
                continue
        events.sort(key=lambda event: (event.data is None, event.data or "9999-99-99", event.documento, event.pagina or 0))
        return overview, events

    @staticmethod
    def _document_summary(document: PdfTextDocument) -> DocumentSummary:
        return DocumentSummary(
            identificador=document.identificador,
            nome=document.nome,
            paginas=len(document.paginas),
            paginas_utilizaveis=len(document.paginas_utilizaveis),
            tamanho_bytes=document.tamanho_bytes,
            qualidade_textual=document.qualidade_geral,
            alertas=list(document.alertas[:8]),
        )
