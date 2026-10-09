"""Contratos compartilhados pela API jurídica do AI Ready."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Contract(BaseModel):
    """Base estrita para rejeitar campos inesperados nas fronteiras da aplicação."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, validate_default=True)
