"""Configuração central do AI Ready, sem parâmetros financeiros ou de cálculo."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, ValidationError, field_validator, model_validator
from starlette.config import Config

from backend.contracts.base import Contract

ROOT = Path(__file__).resolve().parents[1]


class Settings(Contract):
    """Parâmetros de execução e integração corporativa.

    Decisão técnica:
        O projeto mantém apenas configurações necessárias para upload de PDFs,
        extração textual e geração de linguagem. Não existem índices, taxas,
        regras financeiras do produto anterior.
    """

    environment: str = "local"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:4200", "http://127.0.0.1:4200"])
    max_upload_bytes: int = Field(default=25 * 1024 * 1024, ge=1024, le=100 * 1024 * 1024)
    max_upload_files: int = Field(default=12, ge=1, le=50)
    max_total_upload_bytes: int = Field(default=80 * 1024 * 1024, ge=1024 * 1024, le=500 * 1024 * 1024)
    max_pdf_pages: int = Field(default=2500, ge=1, le=10000)
    workspace_ttl_minutes: int = Field(default=120, ge=10, le=1440)
    max_workspaces_in_memory: int = Field(default=30, ge=1, le=500)

    bradesco_environment: Literal["dev", "homol", "prod"] = "dev"
    bradesco_identificador: SecretStr = SecretStr("")
    bradesco_senha: SecretStr = SecretStr("")
    bradesco_authorization_token: SecretStr = SecretStr("")
    bradesco_ca_bundle: Path | None = None
    bradesco_text_url: str = ""
    bradesco_identity_url: str = ""
    bradesco_qa_url: str = ""
    bradesco_qa_workflow_code: str = Field(default="CD_WRFL_QA_778_LEITURA_SENTENCA_PIAUI_AAJR_SYNC", min_length=1, max_length=180)
    bradesco_timeout_seconds: int = Field(default=600, ge=10, le=1800)
    bradesco_text_model: str = Field(default="", max_length=100)
    bradesco_text_temperature: float = Field(default=0.2, ge=0, le=2)
    bradesco_text_max_tokens: int = Field(default=12000, ge=1024, le=65536)
    bradesco_prompt_max_chars: int = Field(default=52000, ge=12000, le=250000)
    bradesco_analysis_max_tokens: int = Field(default=9000, ge=1024, le=30000)
    max_analysis_chunks: int = Field(default=24, ge=1, le=100)

    gateway_token: SecretStr = SecretStr("")

    @field_validator("cors_origins")
    @classmethod
    def validate_origins(cls, values: list[str]) -> list[str]:
        """Aceita somente origens HTTP/HTTPS explícitas."""
        from urllib.parse import urlsplit

        for value in values:
            parsed = urlsplit(value)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc or "*" in value or parsed.path or parsed.query or parsed.fragment:
                raise ValueError("CORS exige origens HTTP/HTTPS explícitas, sem caminho.")
        return values

    @model_validator(mode="after")
    def require_gateway(self) -> "Settings":
        """Fora do modo local, a API deve estar protegida pelo gateway corporativo."""
        if self.environment != "local" and len(self.gateway_token.get_secret_value()) < 32:
            raise ValueError("Defina GATEWAY_TOKEN com ao menos 32 caracteres para ambientes publicados.")
        return self


def load_settings() -> Settings:
    """Carrega JSON, .env e variáveis de ambiente, nessa ordem de precedência."""
    env_path = Path(os.environ.get("APP_ENV_FILE", ROOT / ".env"))
    if "APP_ENV_FILE" in os.environ and not env_path.is_file():
        raise ValueError("APP_ENV_FILE aponta para um arquivo inexistente.")
    file_values = Config(env_path if env_path.is_file() else None, environ={}, encoding="utf-8-sig").file_values
    variables = {**file_values, **os.environ}
    path = Path(variables.get("APP_CONFIG_PATH", ROOT / "config/app.settings.json"))
    if "APP_CONFIG_PATH" in variables and not path.is_file():
        raise ValueError("APP_CONFIG_PATH aponta para um arquivo inexistente.")
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else {}
    except (OSError, ValueError):
        raise ValueError("Não foi possível ler o JSON de configuração do backend.") from None
    if not isinstance(data, dict):
        raise ValueError("A configuração do backend deve ser um objeto JSON.")

    mapping = {
        "APP_ENV": "environment",
        "BRADESCO_AMBIENTE": "bradesco_environment",
        "BRADESCO_IAGEN_AMBIENTE": "bradesco_environment",
        "BRADESCO_IDENTIFICADOR": "bradesco_identificador",
        "BRADESCO_SENHA": "bradesco_senha",
        "BRADESCO_AUTHORIZATION_TOKEN": "bradesco_authorization_token",
        "BRADESCO_CA_BUNDLE": "bradesco_ca_bundle",
        "BRADESCO_TIMEOUT_SECONDS": "bradesco_timeout_seconds",
        "BRADESCO_TEXT_URL": "bradesco_text_url",
        "BRADESCO_IDENTITY_URL": "bradesco_identity_url",
        "BRADESCO_QA_URL": "bradesco_qa_url",
        "BRADESCO_QA_WORKFLOW_CODE": "bradesco_qa_workflow_code",
        "BRADESCO_TEXT_MODEL": "bradesco_text_model",
        "BRADESCO_TEXT_TEMPERATURE": "bradesco_text_temperature",
        "BRADESCO_TEXT_MAX_TOKENS": "bradesco_text_max_tokens",
        "BRADESCO_PROMPT_MAX_CHARS": "bradesco_prompt_max_chars",
        "BRADESCO_ANALYSIS_MAX_TOKENS": "bradesco_analysis_max_tokens",
        "MAX_ANALYSIS_CHUNKS": "max_analysis_chunks",
        "MAX_UPLOAD_BYTES": "max_upload_bytes",
        "MAX_UPLOAD_FILES": "max_upload_files",
        "MAX_TOTAL_UPLOAD_BYTES": "max_total_upload_bytes",
        "MAX_PDF_PAGES": "max_pdf_pages",
        "WORKSPACE_TTL_MINUTES": "workspace_ttl_minutes",
        "MAX_WORKSPACES_IN_MEMORY": "max_workspaces_in_memory",
        "GATEWAY_TOKEN": "gateway_token",
    }
    for layer in (file_values, os.environ):
        for variable, field in mapping.items():
            if variable in layer:
                value = layer[variable].strip()
                data[field] = value or None if field == "bradesco_ca_bundle" else value
        if "CORS_ORIGINS" in layer:
            data["cors_origins"] = [item.strip() for item in layer["CORS_ORIGINS"].split(",") if item.strip()]
    try:
        return Settings.model_validate(data)
    except ValidationError as error:
        fields = ", ".join(".".join(map(str, item["loc"])) or "configuração" for item in error.errors(include_input=False))
        raise ValueError(f"Configuração inválida no backend. Revise: {fields}.") from None
