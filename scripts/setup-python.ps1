# Cria um runtime Python isolado e reproduzível a partir do lock do projeto.
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $Root

if (-not (Test-Path '.venv\Scripts\python.exe')) {
    py -3.12 -m venv .venv
}

$Python = Join-Path $Root '.venv\Scripts\python.exe'
& $Python -m pip install --upgrade pip
& $Python -m pip install --upgrade --force-reinstall -r requirements.lock
& $Python -m pip install --no-deps -e .
& $Python scripts/check-python-environment.py
Write-Host 'Ambiente Python pronto.'
