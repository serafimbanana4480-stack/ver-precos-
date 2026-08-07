@echo off
REM ============================================================
REM  VER PRECOS - so backend + dashboard (sem scraping)
REM ============================================================
setlocal
cd /d "%~dp0.."
set "PY=%CD%\.venv\Scripts\python.exe"

if not exist "%PY%" (
  echo [ERRO] venv nao encontrado. Corre: python -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt
  pause & exit /b 1
)

echo Backend  -> http://127.0.0.1:8000/api/docs
start "VERPRECOS-backend" cmd /k ""%PY%" -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000"

echo Dashboard -> http://127.0.0.1:8501
start "VERPRECOS-dashboard" cmd /k ""%PY%" -m streamlit run dashboard/app.py --server.port 8501 --server.headless true"

timeout /t 8 /nobreak >nul
start "" http://127.0.0.1:8501
start "" http://127.0.0.1:8000/api/docs
endlocal
