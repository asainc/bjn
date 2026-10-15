"""Análise orientativa BJN via text_generator, sem decisões jurídicas automatizadas."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationError

from backend.contracts.base import Contract
from backend.errors import ServiceError
from backend.services.bradesco_bridge import BradescoBridgeClient

ROOT = Path(__file__).resolve().parents[2]
PROMPT_FILE = ROOT / "prompts" / "bjn" / "demand_guidance.system.md"


class DemandGuidanceInput(Contract):
    """Somente a descrição, validada antes de chegar ao modelo."""

    description: str = Field(min_length=15, max_length=8000)


class DemandGuidance(Contract):
    """Resposta estruturada para exibição e registro controlado."""

    resumo: str = Field(min_length=10, max_length=400)
    orientacao: str = Field(min_length=20, max_length=1600)
    passos_sugeridos: list[str] = Field(default_factory=list, max_length=4)
    encaminhamento: Literal["POSSIVEL_AUTOATENDIMENTO", "ATENDIMENTO_HUMANO"]


class BjnDemandAIService:
    """Carrega prompt versionado e usa o bridge corporativo já existente."""

    def __init__(self, bridge: BradescoBridgeClient, prompt_file: Path = PROMPT_FILE):
        self.bridge = bridge
        self.prompt_file = prompt_file

    @property
    def available(self) -> bool:
        """Evita mostrar como funcional um serviço não configurado."""
        return self.bridge.configured

    def analyze(self, description: str) -> tuple[DemandGuidance, str, str]:
        """Retorna orientação, versão do prompt e hash da descrição analisada.

        O texto é transmitido ao serviço corporativo exclusivamente nesta ação explícita.
        Não são transmitidos anexos, dados dos envolvidos ou outros campos da demanda.
        """
        try:
            validated = DemandGuidanceInput(description=description.strip())
        except ValidationError as exc:
            raise ServiceError("Informe uma descrição entre 15 e 8.000 caracteres antes da análise.", 422, code="INVALID_AI_DESCRIPTION") from exc
        if not self.available:
            raise ServiceError("A análise assistida não está configurada neste ambiente.", 503, code="AI_NOT_CONFIGURED")
        try:
            system_prompt = self.prompt_file.read_text(encoding="utf-8")
        except OSError as exc:
            raise ServiceError("O prompt de análise BJN não está disponível.", 503, code="AI_PROMPT_MISSING") from exc
        prompt_hash = hashlib.sha256(system_prompt.encode("utf-8")).hexdigest()
        description_hash = hashlib.sha256(validated.description.encode("utf-8")).hexdigest()
        # Delimitadores e JSON impedem interpolação de instruções do solicitante no prompt de sistema.
        payload = (
            f"<system>\n{system_prompt}\n</system>\n"
            "<user_data_untrusted>\n"
            + json.dumps({"descricao_da_consulta": validated.description}, ensure_ascii=False)
            + "\n</user_data_untrusted>\nResponda somente com o objeto JSON solicitado."
        )
        try:
            response = self.bridge.generate_text(payload, max_tokens=1500)
        except ServiceError:
            raise
        except Exception as exc:
            # Não registra prompts, descrição nem conteúdo gerado em mensagens de erro.
            raise ServiceError("O serviço corporativo de IA está indisponível. Você pode continuar o cadastro normalmente.", 503, code="AI_PROVIDER_UNAVAILABLE") from exc
        raw = response.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.IGNORECASE).strip()
        try:
            result = DemandGuidance.model_validate(json.loads(raw))
            if any(not isinstance(step, str) or not (5 <= len(step) <= 250) for step in result.passos_sugeridos):
                raise ValueError("Passos inválidos")
        except (ValueError, ValidationError) as exc:
            raise ServiceError("A IA não retornou uma orientação válida. Tente novamente ou siga para o atendimento jurídico.", 502, code="AI_RESPONSE_INVALID") from exc
        return result, prompt_hash, description_hash
