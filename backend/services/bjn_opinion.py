"""Parecer preliminar pelo text_generator, com separação entre IA e ato jurídico humano."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from backend.errors import ServiceError
from backend.services.bradesco_bridge import BradescoBridgeClient

PROMPT = Path(__file__).resolve().parents[2] / "prompts" / "bjn" / "opinion_draft.system.md"


class OpinionAIService:
    """Não lê anexos nem dados pessoais estruturados do cliente para gerar rascunhos."""
    def __init__(self, bridge: BradescoBridgeClient):
        self.bridge = bridge

    def generate(self, nature: str, description: str) -> tuple[str, str]:
        """Propaga falhas da API sem publicar conteúdo parcial."""
        if not self.bridge.configured:
            raise ServiceError("Serviço text_generator não configurado.", 503, code="AI_NOT_CONFIGURED")
        template = PROMPT.read_text(encoding="utf-8")
        digest = hashlib.sha256(template.encode("utf-8")).hexdigest()
        payload = f"<system>\n{template}\n</system>\n<user_data_untrusted>\n" + json.dumps(
            {"natureza": nature, "descricao": description}, ensure_ascii=False
        ) + "\n</user_data_untrusted>"
        try:
            output = self.bridge.generate_text(payload, max_tokens=3200).strip()
        except ServiceError:
            raise
        except Exception as exc:
            raise ServiceError("Não foi possível gerar a proposta. O advogado pode elaborar o texto manualmente.", 503, code="AI_PROVIDER_UNAVAILABLE") from exc
        if len(output) < 30 or len(output) > 18000:
            raise ServiceError("Resposta da IA inválida; edite o parecer manualmente.", 502, code="AI_RESPONSE_INVALID")
        return output, digest
