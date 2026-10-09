#!/usr/bin/env sh
set -eu
# Inicia o backend usando a configuração central de config/runtime.json.
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
if [ -n "${BACKEND_PYTHON:-}" ]; then PYTHON="$BACKEND_PYTHON"; elif [ -x "$ROOT/.venv/bin/python" ]; then PYTHON="$ROOT/.venv/bin/python"; else PYTHON=python; fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
exec "$PYTHON" scripts/run_backend.py
