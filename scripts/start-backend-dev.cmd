@echo off
setlocal
REM Inicia o backend em desenvolvimento sem observar frontend\node_modules.
cd /d "%~dp0\.."
if defined BACKEND_PYTHON (set "PYTHON=%BACKEND_PYTHON%") else if exist ".venv\Scripts\python.exe" (set "PYTHON=.venv\Scripts\python.exe") else (set "PYTHON=python")
set "PYTHONPATH=%CD%"
"%PYTHON%" scripts\run_backend.py --reload
exit /b %ERRORLEVEL%
