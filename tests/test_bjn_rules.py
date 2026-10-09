"""Garante bloqueio jurídico e seleção determinística dos temas."""
from backend.services.bjn_rules import Answers, assess


def test_blocks_document_until_clause_homologation():
    values = {field: "nao" for field in (
        "personal_data", "confidential_information", "cloud", "software", "outsourced_staff",
        "international_transfer", "information_security", "critical_service", "business_continuity", "supplier_equipment")}
    answers = Answers(contract_type="servicos", contracting_entity="banco", contract_duration_months=12,
                      **{**values, "personal_data": "sim"})
    result = assess(answers)
    assert result.human_review_required
    assert "Proteção de dados pessoais de terceiros ou clientes" in result.suggested_clause_topics
    assert all("homologad" in reason or "validado" in reason for reason in result.reasons)


def test_escalates_uncertainty_and_international_transfer():
    values = {field: "nao" for field in (
        "personal_data", "confidential_information", "cloud", "software", "outsourced_staff",
        "international_transfer", "information_security", "critical_service", "business_continuity", "supplier_equipment")}
    answers = Answers(contract_type="servicos", contracting_entity="banco", contract_duration_months=24,
                      **{**values, "cloud": "nao_sei", "international_transfer": "sim"})
    assert len(assess(answers).reasons) == 3
