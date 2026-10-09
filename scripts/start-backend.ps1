# Inicia o backend usando a configuração central de config/runtime.json.
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $Root
$Python = if ($env:BACKEND_PYTHON) { $env:BACKEND_PYTHON } elseif (Test-Path '.venv\Scripts\python.exe') { '.venv\Scripts\python.exe' } else { 'python' }
$env:PYTHONPATH = $Root
& $Python scripts/run_backend.py
exit $LASTEXITCODE
