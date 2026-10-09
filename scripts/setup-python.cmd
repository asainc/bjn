@echo off
setlocal
cd /d "%~dp0\.."

if not exist ".venv\Scripts\python.exe" (
    py -3.12 -m venv .venv || exit /b 1
)

set "PYTHON=.venv\Scripts\python.exe"
"%PYTHON%" -m pip install --upgrade pip || exit /b 1
"%PYTHON%" -m pip install --upgrade --force-reinstall -r requirements.lock || exit /b 1
"%PYTHON%" -m pip install --no-deps -e . || exit /b 1
"%PYTHON%" scripts\check-python-environment.py || exit /b 1

echo Ambiente Python pronto.
