@echo off
REM ============================================================
REM  VER PRECOS - inicia Backend (FastAPI) + Frontend (Streamlit)
REM  Backend  : http://127.0.0.1:8000/api/docs
REM  Frontend : http://127.0.0.1:8501
REM  Os dois arrancam EM PARALELO - o frontend nao espera pelo backend.
REM ============================================================
setlocal
cd /d "%~dp0.."
set "ROOT=%CD%"
set "PY=%ROOT%\.venv\Scripts\python.exe"

if not exist "%PY%" (
  echo [ERRO] venv nao encontrado em %ROOT%\.venv
  echo        Cria com: python -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt
  pause
  exit /b 1
)

if not exist "%ROOT%\data\autodeal.db" echo [aviso] data\autodeal.db nao existe - dashboard vai abrir vazio.

REM evita o prompt de email do Streamlit no primeiro arranque
if not exist "%ROOT%\.streamlit" mkdir "%ROOT%\.streamlit"
if not exist "%ROOT%\.streamlit\credentials.toml" (
  > "%ROOT%\.streamlit\credentials.toml" echo [general]
  >>"%ROOT%\.streamlit\credentials.toml" echo email = ""
)

echo.
echo ============================================================
echo   VER PRECOS - a iniciar servicos
echo   Raiz: %ROOT%
echo ============================================================
echo.

REM --- Lancar os DOIS de imediato ---------------------------------------
echo [1/2] Frontend Streamlit -^> http://127.0.0.1:8501
start "VERPRECOS-frontend" cmd /k ""%PY%" -m streamlit run dashboard/app.py --server.port 8501 --server.address 127.0.0.1 --server.headless true --browser.gatherUsageStats false"

echo [2/2] Backend FastAPI    -^> http://127.0.0.1:8000/api/docs
echo       (o backend importa modelos ML - pode levar 30-90s)
start "VERPRECOS-backend" cmd /k ""%PY%" -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000"
echo.

REM --- Esperar pelo frontend --------------------------------------------
echo A aguardar o frontend...
set /a _t=0
:waitui
timeout /t 2 /nobreak >nul
set /a _t+=2
"%PY%" -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health',timeout=2)" >nul 2>nul
if not errorlevel 1 goto uiok
echo    ... %_t%s
if %_t% GEQ 90 (
  echo.
  echo [ERRO] Frontend nao respondeu em 90s.
  echo        Ve a janela "VERPRECOS-frontend" - o erro esta la.
  echo        Teste manual:
  echo          cd /d "%ROOT%"
  echo          .venv\Scripts\python.exe -m streamlit run dashboard/app.py
  pause
  exit /b 1
)
goto waitui
:uiok
echo    frontend OK em %_t%s
start "" http://127.0.0.1:8501

REM --- Esperar pelo backend (nao bloqueia o frontend) --------------------
echo A aguardar o backend...
set /a _t=0
:waitapi
timeout /t 3 /nobreak >nul
set /a _t+=3
"%PY%" -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health',timeout=2)" >nul 2>nul
if not errorlevel 1 goto apiok
echo    ... %_t%s
if %_t% GEQ 120 (
  echo    [aviso] backend nao respondeu em 120s - ve a janela "VERPRECOS-backend".
  echo            O dashboard funciona na mesma ^(le direto do SQLite^).
  goto fim
)
goto waitapi
:apiok
echo    backend OK em %_t%s
start "" http://127.0.0.1:8000/api/docs

:fim
echo.
echo ============================================================
echo   Frontend : http://127.0.0.1:8501
echo   API docs : http://127.0.0.1:8000/api/docs
echo   Fecha as janelas VERPRECOS-* para parar.
echo ============================================================
echo.
pause
endlocal
