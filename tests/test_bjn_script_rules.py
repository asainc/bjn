"""Testes com entradas sintéticas para assegurar fidelidade ao script."""
import pytest
from backend.services.bjn_rules import Answers, assess, workflow, is_visible

def test_workflow_only_uses_script_source():
    spec = workflow()
    assert spec['source'] == 'script_bjn.zip'
    assert spec['source_pages'] == 8
    assert all(1 <= q['source_page'] <= 8 for q in spec['questions'])
    assert len({q['id'] for q in spec['questions']}) == len(spec['questions'])

def test_conditional_cloud_fields():
    spec = workflow()
    target = next(q for q in spec['questions'] if q['id'] == 'cloud_type')
    assert not is_visible(target, {'cloud_storage':'nao'})
    assert is_visible(target, {'cloud_storage':'sim'})

def test_reject_unknown_fields():
    with pytest.raises(ValueError,match='ausentes do script_bjn'):
        assess(Answers(answers={'invented_question':'sim'}))

def test_unsupported_choice_rejected():
    with pytest.raises(ValueError,match='Opção inválida'):
        assess(Answers(answers={'instrument':'contrato_criado_pela_ia'}))
