# Inicia o backend em desenvolvimento. A recarga ignora completamente o frontend/node_modules.
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $Root
$Python = if ($env:BACKEND_PYTHON) { $env:BACKEND_PYTHON } elseif (Test-Path '.venv\Scripts\python.exe') { '.venv\Scripts\python.exe' } else { 'python' }
$env:PYTHONPATH = $Root
& $Python scripts/run_backend.py --reload
exit $LASTEXITCODE
