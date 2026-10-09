"""Leitura e preenchimento controlado dos prompts versionados do projeto."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from backend.errors import ServiceError

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"


@lru_cache(maxsize=16)
def load_prompt(name: str) -> str:
    """Carrega apenas arquivos Markdown diretamente da pasta de prompts."""
    if not name.endswith(".md") or "/" in name or "\\" in name:
        raise ServiceError("Prompt inválido na configuração interna.", 500, code="PROMPT_INVALIDO")
    path = PROMPTS_DIR / name
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ServiceError("Arquivo de prompt não encontrado.", 500, code="PROMPT_AUSENTE") from exc
    if not text.strip():
        raise ServiceError("Arquivo de prompt vazio.", 500, code="PROMPT_VAZIO")
    return text.strip()


def render_prompt(name: str, **values: object) -> str:
    """Substitui somente marcadores conhecidos, preservando chaves JSON literais.

    ``str.format`` não é usado porque os próprios prompts contêm exemplos JSON com
    ``{`` e ``}``. A substituição literal reduz o risco de um exemplo estrutural
    ser interpretado como variável de template.
    """
    text = load_prompt(name)
    for key, value in values.items():
        marker = "{" + key + "}"
        if marker not in text:
            raise ServiceError(f"Marcador {marker} não existe no prompt {name}.", 500, code="PROMPT_INCOMPATIVEL")
        text = text.replace(marker, str(value))
    return text
