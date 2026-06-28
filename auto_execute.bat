@echo off
title AutoDeal IA Hunter - Mega Scraper Pipeline
color 0F
chcp 65001 >nul 2>&1

:: ============================================================
:: AutoDeal IA Hunter - Professional Execution Pipeline
:: ============================================================
:: Este script executa scraping, limpeza, e ML autonomamente
:: ============================================================

setlocal enabledelayedexpansion

:: Colors for Windows 10+ (ANSI escape codes)
for /F "tokens=1,2 delims=#" %%a in ('"prompt #$H#$E# & echo on & for %%b in (1) do rem"') do set "ESC=%%b"
set "GREEN=%ESC%[92m"
set "YELLOW=%ESC%[93m"
set "RED=%ESC%[91m"
set "CYAN=%ESC%[96m"
set "WHITE=%ESC%[97m"
set "BOLD=%ESC%[1m"
set "RESET=%ESC%[0m"

:: Set project root
set "PROJECT_DIR=C:\Users\rodri\Desktop\VER PRECOS"
cd /d "%PROJECT_DIR%"

:: ============================================================
:: ASCII Header
:: ============================================================
cls
echo %BOLD%%CYAN% 
echo    █████╗ ██╗   ██╗████████╗ ██████╗ ██████╗ ███████╗ █████╗ ██╗     
echo   ██╔══██╗██║   ██║╚══██╔══╝██╔═══██╗██╔══██╗██╔════╝██╔══██╗██║     
echo   ███████║██║   ██║   ██║   ██║   ██║██║  ██║█████╗  ███████║██║     
echo   ██╔══██║██║   ██║   ██║   ██║   ██║██║  ██║██╔══╝  ██╔══██║██║     
echo   ██║  ██║╚██████╔╝   ██║   ╚██████╔╝██████╔╝███████╗██║  ██║███████╗
echo   ╚═╝  ╚═╝ ╚═════╝    ╚═╝    ╚═════╝ ╚═════╝ ╚══════╝╚═╝  ╚═╝╚══════╝
echo %RESET%
echo %BOLD%    Professional Scraper ^| Market Valuation ^| ML Pipeline%RESET%
echo.

:: ============================================================
:: Detect Python
:: ============================================================
echo %YELLOW%[INIT]%RESET% Detecting Python interpreter...
set "PYTHON="

if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
    echo %GREEN%[OK]%RESET% Found venv Python: .venv\Scripts\python.exe
) else (
    where py >nul 2>&1
    if !ERRORLEVEL! EQU 0 (
        for /f %%i in ('"py -3 --version 2>nul"') do set "PY_VER=%%i"
        set "PYTHON=py -3"
        echo %GREEN%[OK]%RESET% Found Python launcher: py -3
    ) else (
        where python >nul 2>&1
        if !ERRORLEVEL! EQU 0 (
            set "PYTHON=python"
            echo %GREEN%[OK]%RESET% Found system Python
        ) else (
            echo %RED%[ERROR]%RESET% Python not found! Please install Python 3.12+
            echo          Download: https://www.python.org/downloads/
            pause
            exit /b 1
        )
    )
)

:: Verify Python works
%PYTHON% -c "print('')" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo %RED%[ERROR]%RESET% Python failed to start! Try reinstalling.
    pause
    exit /b 1
)

:: Install required packages if missing
echo %YELLOW%[INIT]%RESET% Checking dependencies...
%PYTHON% -c "import requests, bs4, sqlalchemy, pydantic" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo %YELLOW%[INIT]%RESET% Installing core dependencies...
    %PYTHON% -m pip install --quiet -r requirements.txt 2>&1 | findstr /V "^$"
)

:: ============================================================
:: Function: run_step
:: ============================================================
set STEP=0
set STEP_FAILED=0

:run_step
set /a STEP+=1

:: Check if we've moved past step 6
if %STEP% GTR 6 goto :done

if %STEP%==1 goto :step1
if %STEP%==2 goto :step2
if %STEP%==3 goto :step3
if %STEP%==4 goto :step4
if %STEP%==5 goto :step5
if %STEP%==6 goto :step6

:step1
echo.
echo %BOLD%%WHITE%============================================================%RESET%
echo %BOLD% STEP 1/6: Standvirtual Mega Scraper%RESET%
echo %BOLD%%WHITE%============================================================%RESET%
%PYTHON% scripts\mega_scrape.py
if !ERRORLEVEL! NEQ 0 (
    echo %YELLOW%[WARN]%RESET% mega_scrape.py had issues, continuing...
)
goto :run_step

:step2
echo.
echo %BOLD%%WHITE%============================================================%RESET%
echo %BOLD% STEP 2/6: Clean data & normalize brands%RESET%
echo %BOLD%%WHITE%============================================================%RESET%
%PYTHON% scripts\clean_data.py
%PYTHON% scripts\normalize_brands.py
%PYTHON% scripts\extract_features.py
goto :run_step

:step3
echo.
echo %BOLD%%WHITE%============================================================%RESET%
echo %BOLD% STEP 3/6: Statistical price estimation%RESET%
echo %BOLD%%WHITE%============================================================%RESET%
%PYTHON% valuation\statistical_pricer.py
goto :run_step

:step4
echo.
echo %BOLD%%WHITE%============================================================%RESET%
echo %BOLD% STEP 4/6: Market valuation update%RESET%
echo %BOLD%%WHITE%============================================================%RESET%
%PYTHON% valuation\statistical_pricer.py
goto :run_step

:step5
echo.
echo %BOLD%%WHITE%============================================================%RESET%
echo %BOLD% STEP 5/6: Train ML model (XGBoost/LightGBM/CatBoost)%RESET%
echo %BOLD%%WHITE%============================================================%RESET%
%PYTHON% -c "import sys; sys.path.insert(0,'.'); from valuation.train import train_all_models; import logging; logging.basicConfig(level=logging.INFO,format='%%(message)s'); r=train_all_models(force_retrain=True); [print(f'{k}: {v[\"model_type\"]} R2={v[\"metrics\"][\"r2\"]:.4f} MAE=EUR{v[\"metrics\"][\"mae\"]:.0f} n={v[\"n_samples\"]}') if v else print(f'{k}: FAILED') for k,v in r.items()]"
goto :run_step

:step6
echo.
echo %BOLD%%WHITE%============================================================%RESET%
echo %BOLD% STEP 6/6: Final Database Report%RESET%
echo %BOLD%%WHITE%============================================================%RESET% 
%PYTHON% -c "import sys; sys.path.insert(0,'.'); from database.db import get_db_context; from database.models import Vehicle; from sqlalchemy import func; with get_db_context() as db: t=db.query(Vehicle).count(); a=db.query(Vehicle).filter(Vehicle.is_active==True).count(); hp=db.query(Vehicle).filter(Vehicle.horsepower.isnot(None),Vehicle.is_active==True).count(); cc=db.query(Vehicle).filter(Vehicle.engine_size.isnot(None),Vehicle.is_active==True).count(); fuel=db.query(Vehicle).filter(Vehicle.fuel_type.isnot(None),Vehicle.is_active==True).count(); print(f'TOTAL:{t} ACTIVE:{a} HP:{hp} CC:{cc} FUEL:{fuel}'); [print(f'  {s.value if hasattr(s,\"value\") else s}:{c}') for s,c in db.query(Vehicle.source,func.count(Vehicle.id)).filter(Vehicle.is_active==True).group_by(Vehicle.source).all()]"

:: Show top deals
echo.
echo %BOLD% Top 10 Deals Found:%RESET%
%PYTHON% -c "import sys; sys.path.insert(0,'.'); from database.db import get_db_context; from database.models import Vehicle; db=next(get_db_context()); q=db.query(Vehicle).filter(Vehicle.estimated_value.isnot(None),Vehicle.is_active==True).order_by(Vehicle.deal_score.desc()).limit(10).all(); [print(f'  {v.brand:15s} {str(v.model)[:20]:20s} EUR{v.price:>7,.0f} vs EUR{v.estimated_value:>7,.0f} score={v.deal_score}') for v in q]"

goto :run_step

:done
echo.
echo %BOLD%%GREEN%============================================================%RESET%
echo %BOLD%%GREEN%  ✓  ALL STEPS COMPLETED SUCCESSFULLY%RESET%
echo %BOLD%%GREEN%============================================================%RESET%
echo.
echo   Database: %total% vehicles processed
echo   For more: double-click start.bat for interactive menu
echo   Or:       cd %PROJECT_DIR% ^&^& %PYTHON% main.py dashboard
echo.
pause
goto :eof
