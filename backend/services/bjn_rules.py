"""Regras de questionário exclusivamente provenientes de script_bjn.zip."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from pydantic import BaseModel, ConfigDict

WORKFLOW_PATH = Path(__file__).resolve().parents[2] / "config/bjn_script_workflow.json"

class Answers(BaseModel):
    """Respostas codificadas; nenhuma pergunta é criada pelo cliente."""
    model_config = ConfigDict(extra="forbid")
    answers: dict[str, Any]

class Assessment(BaseModel):
    """Decisão rastreável e conservadora."""
    status: str
    human_review_required: bool
    reasons: list[str]
    suggested_clause_topics: list[str]
    source_status: str

def workflow() -> dict:
    """Fonte única de perguntas e opções é o script transcrito."""
    return json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))

def is_visible(question: dict, values: dict) -> bool:
    """Só apresenta dependências expressamente indicadas no script."""
    condition = question.get("when", {})
    return all((expected in values.get(key, []) if isinstance(values.get(key), list) else values.get(key) == expected) for key, expected in condition.items())

def assess(body: Answers) -> Assessment:
    """Valida todas as respostas e aplica apenas encaminhamentos verificáveis."""
    schema = workflow()
    questions = schema["questions"]
    valid = {q["id"] for q in questions}
    unknown = set(body.answers) - valid
    if unknown:
        raise ValueError(f"Campos ausentes do script_bjn: {sorted(unknown)}")
    reasons = []
    for question in questions:
        if not is_visible(question, body.answers):
            if question["id"] in body.answers:
                raise ValueError(f"Campo não aplicável à seleção: {question['id']}")
            continue
        value = body.answers.get(question["id"])
        if value is None or value == "" or value == []:
            raise ValueError(f"Resposta obrigatória ausente: {question['id']}")
        options = {o["value"] for o in question.get("options", [])}
        if question["type"] == "multi":
            if not isinstance(value, list) or not value or any(v not in options for v in value):
                raise ValueError(f"Opção inválida: {question['id']}")
        elif options and value not in options:
            raise ValueError(f"Opção inválida: {question['id']}")
        if question["type"] == "number" and (isinstance(value, bool) or not str(value).isdigit() or int(value) < 1):
            raise ValueError(f"Número inválido: {question['id']}")
        action = question.get("action")
        if action and (action["value"] in value if isinstance(value, list) else value == action["value"]):
            reasons.append(f"Encaminhamento previsto no script_bjn, página {question['source_page']}: {question['label']}")
    # Bloquear documento até homologação completa da matriz e vínculo ao book.
    reasons.append("Mapeamento integral do script_bjn para as cláusulas literais do book ainda não homologado")
    return Assessment(status="encaminhar_atendimento_humano", human_review_required=True,
                      reasons=reasons, suggested_clause_topics=[],
                      source_status="Questionário baseado no script_bjn; minuta PDF bloqueada até homologação")
