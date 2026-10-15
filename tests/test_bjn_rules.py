"""Regressão do questionário oficial do script_bjn, sem campos legados inventados."""
from backend.services.bjn_rules import Answers, assess, is_visible, workflow


def complete_answers(overrides: dict[str, object] | None = None) -> Answers:
    """Preenche o script atual com valores sintéticos, respeitando condições visíveis."""
    values: dict[str, object] = {}
    for question in workflow()["questions"]:
        if not is_visible(question, values):
            continue
        key = question["id"]
        if overrides and key in overrides:
            values[key] = overrides[key]
        elif question.get("options"):
            selected = question["options"][0]["value"]
            values[key] = [selected] if question["type"] == "multi" else selected
        elif question["type"] == "number":
            values[key] = 1
        else:
            values[key] = "Valor sintético para teste"
    return Answers(answers=values)


def test_blocks_document_until_clause_homologation():
    """Mesmo com resposta LGPD, a API não permite documento sem homologação."""
    result = assess(complete_answers({"personal_data": "sim"}))
    assert result.human_review_required is True
    assert result.status == "encaminhar_atendimento_humano"
    assert any("homologad" in reason for reason in result.reasons)
    assert result.suggested_clause_topics == []


def test_escalates_uncertainty_and_out_of_standard_fine():
    """Encaminhamentos expressos no script geram razões rastreáveis."""
    result = assess(complete_answers({"instrument": "Outros, especificar", "fine": "fora_padrao", "fine_approved": "nao"}))
    assert result.human_review_required is True
    assert any("página 1" in reason for reason in result.reasons)
    assert any("página 2" in reason for reason in result.reasons)


def test_unknown_question_is_rejected():
    """Proíbe incorporar campos antigos ou não presentes no script."""
    import pytest
    with pytest.raises(ValueError, match="Campos ausentes"):
        assess(Answers(answers={"unlisted_question": "sim"}))
