@echo off
REM ============================================================
REM  VER PRECOS - Arranque completo
REM  1) Scrapers (lightweight, 13 fontes em paralelo)
REM  2) Backend FastAPI  -> http://127.0.0.1:8000/api/docs
REM  3) Dashboard Streamlit -> http://127.0.0.1:8501
REM ============================================================
setlocal
cd /d "%~dp0.."
set "ROOT=%CD%"
set "PY=%ROOT%\.venv\Scripts\python.exe"

if not exist "%PY%" (
  echo [ERRO] venv nao encontrado em %ROOT%\.venv
  echo        Cria com:  python -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt
  pause
  exit /b 1
)

echo.
echo ============================================================
echo   VER PRECOS - arranque   %DATE% %TIME%
echo   Raiz: %ROOT%
echo ============================================================
echo.

REM --- 1. Scrapers -------------------------------------------------------
echo [1/3] Scrapers (13 fontes, 6 workers, 300 anuncios por fonte)...
echo       Isto pode levar 2-5 minutos.
"%PY%" main.py scrape --engine lightweight --source all --vehicle-type carros --max-listings 300
if errorlevel 1 echo       [aviso] scrape terminou com erros - ver logs\
echo.

REM --- 2. Backend --------------------------------------------------------
echo [2/3] Backend FastAPI em http://127.0.0.1:8000/api/docs
start "VERPRECOS-backend" cmd /k ""%PY%" -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000"

REM esperar o backend responder (max 30s)
set /a _t=0
:waitapi
timeout /t 2 /nobreak >nul
set /a _t+=2
"%PY%" -c "import urllib.request,sys; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health',timeout=2); print('backend OK')" 2>nul && goto apiok
if %_t% GEQ 30 (echo       [aviso] backend nao respondeu em 30s - ver a janela VERPRECOS-backend & goto apiok)
goto waitapi
:apiok
echo.

REM --- 3. Dashboard -----------------------------------------------------
echo [3/3] Dashboard Streamlit em http://127.0.0.1:8501
start "VERPRECOS-dashboard" cmd /k ""%PY%" -m streamlit run dashboard/app.py --server.port 8501 --server.headless true"

timeout /t 6 /nobreak >nul
start "" http://127.0.0.1:8501
start "" http://127.0.0.1:8000/api/docs

echo.
echo ============================================================
echo   Pronto.
echo     Dashboard : http://127.0.0.1:8501
echo     API docs  : http://127.0.0.1:8000/api/docs
echo   Fecha as janelas VERPRECOS-backend / VERPRECOS-dashboard
echo   para parar os servicos.
echo ============================================================
echo.
pause
endlocal
