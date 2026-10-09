"""Testes de regressão da validação do ambiente Python.

O cenário principal reproduz as versões informadas durante a execução em uma
estação corporativa. A finalidade é garantir que patches diferentes do lock de
referência não voltem a bloquear a API quando forem funcionalmente compatíveis.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = ROOT / "scripts" / "check-python-environment.py"


def load_checker():
    """Carrega o script de validação como módulo sem executá-lo como programa."""
    spec = importlib.util.spec_from_file_location("ai_ready_environment_checker", CHECKER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_corporate_runtime_versions_are_accepted(capsys) -> None:
    """Aceita o conjunto compatível que anteriormente falhava por pins exatos."""
    checker = load_checker()
    versions = {
        "requests": "2.32.5",
        "pydantic": "2.13.4",
        "fastapi": "0.121.2",
        "uvicorn": "0.38.0",
        "python-multipart": "0.0.32",
        "pymupdf": "1.26.7",
        "starlette": "0.49.3",
        "charset-normalizer": "3.4.4",
        "chardet": "7.4.0.post2",
    }

    with (
        patch.object(checker, "installed_version", side_effect=lambda name: versions.get(name)),
        patch.object(
            checker,
            "fastapi_declared_starlette_range",
            return_value=((">=", "0.40.0"), ("<", "0.50.0")),
        ),
    ):
        result = checker.main()

    captured = capsys.readouterr()
    assert result == 0
    assert "Dependências Python compatíveis" in captured.out
    assert "chardet 7.4.0.post2" in captured.err
    assert "AVISO:" in captured.err


def test_incompatible_starlette_is_rejected(capsys) -> None:
    """Continua bloqueando uma combinação que o próprio FastAPI não aceita."""
    checker = load_checker()
    versions = {
        "requests": "2.32.5",
        "pydantic": "2.13.4",
        "fastapi": "0.121.2",
        "uvicorn": "0.38.0",
        "python-multipart": "0.0.32",
        "pymupdf": "1.26.7",
        "starlette": "1.6.0",
        "charset-normalizer": "3.4.4",
        "chardet": None,
    }

    with (
        patch.object(checker, "installed_version", side_effect=lambda name: versions.get(name)),
        patch.object(
            checker,
            "fastapi_declared_starlette_range",
            return_value=((">=", "0.40.0"), ("<", "0.50.0")),
        ),
    ):
        result = checker.main()

    captured = capsys.readouterr()
    assert result == 2
    assert "starlette: instalado 1.6.0" in captured.err
