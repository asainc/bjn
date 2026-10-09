"""Testes do iniciador do backend independentes do diretório atual."""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run_backend.py"


def load_runner_module():
    """Carrega o script como módulo sem iniciar o servidor HTTP."""
    spec = importlib.util.spec_from_file_location("ai_ready_run_backend_test", RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_runner_adds_project_root_to_python_import_path(tmp_path, monkeypatch):
    """O backend deve ser importável mesmo quando o comando parte de outra pasta."""
    runner = load_runner_module()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PYTHONPATH", "")

    runner.ensure_project_import_path()

    assert Path.cwd() == ROOT
    assert str(ROOT) in sys.path
    assert str(ROOT) in os.environ["PYTHONPATH"].split(os.pathsep)

    import backend.principal  # noqa: F401
