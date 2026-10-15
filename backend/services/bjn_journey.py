"""Regras explícitas de triagem e cadastro fornecidas nas cinco imagens de referência.

Não envia e-mails ou solicitações a sistemas externos. A definição dos destinos é
operacional e exige validação do Jurídico antes de habilitar integrações.
"""
from __future__ import annotations

import re
import hmac
import hashlib
import time
from typing import Literal
from pydantic import Field, model_validator
from backend.contracts.base import Contract
from backend.errors import ServiceError

NATURES = ("Inventário", "Alvará", "Curatela", "Procuração", "Pareceres em geral")
REQUIRED_ATTACHMENTS = frozenset(NATURES[:4])
TRIAGE_OPTIONS = {
    "PROCESSO_COM_BANCO": {"label": "Processo judicial com o Banco como parte", "destination": "Consultar GCPJ e a caixa institucional correspondente"},
    "OFICIO_DELEGACIA": {"label": "Ofício de Delegacia de Polícia", "destination": "Cadastrar no WCPS"},
    "INTIMACAO_DELEGACIA": {"label": "Intimação de Delegacia de Polícia", "destination": "Encaminhar à caixa jurídica responsável e à Consultoria Criminal"},
    "OFICIO_SEM_BANCO": {"label": "Ofício judicial sem o Banco como parte", "destination": "Atendimento operacional (ON)"},
    "OUTRAS": {"label": "Nenhuma das opções anteriores", "destination": "Cadastrar demanda para atendimento da equipe"},
}


class TriageInput(Contract):
    """Resposta reproduzida do primeiro desvio do fluxo apresentado."""
    category: Literal["PROCESSO_COM_BANCO", "OFICIO_DELEGACIA", "INTIMACAO_DELEGACIA", "OFICIO_SEM_BANCO", "OUTRAS"]
    bank_role: Literal["AUTOR", "REU"] | None = None
    has_gcpj: bool | None = None

    @model_validator(mode="after")
    def validate_branch(self):
        """Evita rotas ambíguas para processos judiciais com o Banco como parte."""
        if self.category == "PROCESSO_COM_BANCO" and (not self.bank_role or self.has_gcpj is None):
            raise ValueError("Informe a posição do Banco e a existência de GCPJ.")
        if self.category != "PROCESSO_COM_BANCO" and (self.bank_role is not None or self.has_gcpj is not None):
            raise ValueError("A posição do Banco e o GCPJ só são válidos em processo com o Banco como parte.")
        return self


def routing_decision(data: TriageInput) -> dict:
    """Produz orientação para revisão e nunca aciona sistemas externos por conta própria."""
    route = TRIAGE_OPTIONS[data.category]
    details = route["destination"]
    if data.category == "PROCESSO_COM_BANCO":
        if data.bank_role == "AUTOR":
            details = "Banco autor: consultar GCPJ; se não houver, encaminhar à caixa de advogados responsável."
        elif data.has_gcpj:
            details = "Banco réu com GCPJ: encaminhar às caixas de operacional e expediente responsáveis."
        else:
            details = "Banco réu sem GCPJ: encaminhar à caixa de expediente responsável."
    return {
        "category": data.category,
        "label": route["label"],
        "destination": details,
        "requires_registration": data.category == "OUTRAS",
        "external_action_performed": False,
        "notice": "O BJN não enviou e-mails nem cadastrou demandas em sistemas externos. Confirme o procedimento com a área responsável.",
    }


def validate_journey_fields(data, attachments: int) -> None:
    """Impõe no servidor as regras obrigatórias para o novo fluxo (independente do Angular)."""
    if data.triage_type != "OUTRAS":
        raise ServiceError("Conclua a triagem inicial antes do cadastro.", 422, code="TRIAGE_REQUIRED")
    if data.service_nature not in NATURES:
        raise ServiceError("Selecione uma das cinco naturezas previstas.", 422, code="INVALID_NATURE")
    if not 2 <= len(data.branch.strip()) <= 40:
        raise ServiceError("Informe a agência responsável.", 422, code="BRANCH_REQUIRED")
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", data.requester_email.strip()):
        raise ServiceError("Informe o e-mail do demandante.", 422, code="EMAIL_REQUIRED")
    if not 2 <= len(data.client_name.strip()) <= 180:
        raise ServiceError("Informe o nome do cliente.", 422, code="CLIENT_NAME_REQUIRED")
    doc = re.sub(r"\D", "", data.client_document)
    if len(doc) != 11 or len(set(doc)) == 1 or not _valid_cpf(doc):
        raise ServiceError("Informe um CPF de cliente válido.", 422, code="CLIENT_DOCUMENT_INVALID")
    if data.service_nature in REQUIRED_ATTACHMENTS and attachments < 1:
        raise ServiceError("Esta natureza exige ao menos um documento anexo.", 422, code="ATTACHMENT_REQUIRED")


def _valid_cpf(digits: str) -> bool:
    """Verifica dígitos de controle, sem consultar bases externas nem registrar CPF."""
    for size in (9, 10):
        weight = size + 1
        check = (sum(int(char) * (weight - pos) for pos, char in enumerate(digits[:size])) * 10) % 11
        if (0 if check == 10 else check) != int(digits[size]):
            return False
    return True


def issue_triage_proof(actor_id: str, secret: bytes) -> str:
    """Concede comprovante temporário só depois da decisão OUTRAS validada."""
    expiry = int(time.time()) + 30 * 60
    signature = hmac.new(secret, f"OUTRAS|{actor_id}|{expiry}".encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{expiry}.{signature}"


def verify_triage_proof(proof: str, actor_id: str, secret: bytes) -> bool:
    """Vincula triagem ao usuário, à opção e a uma janela de validade de 30 minutos."""
    if not secret or not proof or "." not in proof:
        return False
    try:
        expiry_str, signature = proof.split(".", 1)
        expiry = int(expiry_str)
        if expiry <= time.time() or expiry > time.time() + 30 * 60 + 5:
            return False
        expected = hmac.new(secret, f"OUTRAS|{actor_id}|{expiry}".encode("utf-8"), hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, expected)
    except (ValueError, OverflowError):
        return False


class CompetenceReview(Contract):
    """Decisão humana de triagem para Pareceres em geral."""
    is_team_competence: bool
    destination_area: str = Field(default="", max_length=120)

    @model_validator(mode="after")
    def check_destination(self):
        if not self.is_team_competence and len(self.destination_area.strip()) < 3:
            raise ValueError("Informe a área competente para encaminhamento.")
        return self


class OpinionPublish(Contract):
    """Publicação só acontece depois da revisão expressa do advogado."""
    final_text: str = Field(min_length=40, max_length=18000)
    human_review_confirmed: bool


class OpinionDraft(Contract):
    """Parecer preliminar gerado pela IA; nunca é uma decisão final."""
    text: str = Field(min_length=30, max_length=18000)
