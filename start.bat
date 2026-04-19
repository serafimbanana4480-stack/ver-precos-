@echo off
REM AutoDeal IA Hunter - Startup Script

echo ========================================
echo AutoDeal IA Hunter
echo ========================================
echo.

REM Detect Python version - prefer 3.12 or 3.13 over 3.14
set PYTHON_CMD=
for %%v in (3.12 3.13 3.14) do (
    py -%%v --version >nul 2>&1
    if not errorlevel 1 (
        set PYTHON_CMD=py -%%v
        echo Found Python %%v
        goto :python_found
    )
)

:python_found
if "%PYTHON_CMD%"=="" (
    echo ERROR: Python 3.12, 3.13, or 3.14 not found.
    echo Please install Python 3.12 or 3.13 from https://www.python.org/downloads/
    echo During installation, check "Add Python to PATH"
    pause
    exit /b 1
)

REM Check if virtual environment exists
if not exist "venv" (
    echo Creating virtual environment with %PYTHON_CMD%...
    %PYTHON_CMD% -m venv venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment.
        pause
        exit /b 1
    )
)

REM Activate virtual environment
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else (
    echo ERROR: Virtual environment activation script not found.
    echo Please delete the 'venv' folder and run this script again.
    pause
    exit /b 1
)

REM Install dependencies
echo Checking dependencies...
pip show parsera >nul 2>&1
if errorlevel 1 (
    echo Cleaning up broken pip installations...
    if exist "venv\Lib\site-packages\~*" FOR /D %%p IN ("venv\Lib\site-packages\~*") DO rmdir "%%p" /s /q
    
    echo Installing dependencies...
    echo Installing minimal dependencies first...
    pip install --prefer-binary -r requirements-minimal.txt
    if errorlevel 1 (
        echo ERROR: Failed to install minimal dependencies.
        pause
        exit /b 1
    )

    echo.
    echo Installing full dependencies ^(this may take 10-30 minutes^)...
    echo Press Ctrl+C to skip ML/AI dependencies if not needed.
    pip install --prefer-binary -r requirements.txt
    if errorlevel 1 (
        echo.
        echo WARNING: Some dependencies failed to install ^(likely due to Python 3.14 compatibility^).
        echo The project will run with minimal dependencies.
        echo ML/AI features may not work without full dependencies.
        echo Consider using Python 3.12 or 3.13 for full compatibility.
        echo.
    ) else (
        echo Installing Playwright browsers...
        python -m playwright install
    )
) else (
    echo Dependencies already installed. Skipping reinstall.
    echo To force reinstall, delete venv folder and run this script again.
)

REM Force UTF-8 encoding for Python on Windows console
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
chcp 65001 >nul 2>&1

REM Check if .env file exists
if not exist ".env" (
    echo.
    echo WARNING: .env file not found.
    echo Please create a .env file with your configuration.
    echo Example: DATABASE_URL=sqlite:///autodeal.db
    echo.
)

REM Check if arguments were passed (quick start mode)
if not "%1"=="" (
    echo Running with arguments: %*
    python main.py %*
    pause
    exit /b 0
)

REM Check if database exists
set DB_EXISTS=0
if exist "autodeal.db" set DB_EXISTS=1
if exist "*.db" set DB_EXISTS=1

REM Show interactive menu
echo.
echo ========================================
echo What would you like to do?
echo ========================================
echo.
if %DB_EXISTS%==0 (
    echo [RECOMMENDED] 1. Initialize database
) else (
    echo 1. Initialize database
)
echo 2. Start dashboard
echo 3. Run scrapers
echo 4. Find deals
echo 5. Open command prompt ^(manual control^)
echo.
set /p choice="Enter your choice (1-5): "

if "%choice%"=="1" (
    echo.
    echo Initializing database...
    python main.py init
) else if "%choice%"=="2" (
    echo.
    echo Starting dashboard...
    echo Dashboard will open at http://localhost:8501
    echo Press Ctrl+C to stop the dashboard.
    echo.
    python main.py dashboard
) else if "%choice%"=="3" (
    echo.
    echo Running scrapers...
    python main.py scrape --source all --vehicle-type all --max-listings 50
) else if "%choice%"=="4" (
    echo.
    echo Finding best deals...
    python main.py find-deals --limit 20
) else if "%choice%"=="5" (
    echo.
    echo Opening command prompt...
    echo You can now run commands manually:
    echo   python main.py init
    echo   python main.py scrape
    echo   python main.py dashboard
    echo.
    cmd /k
) else (
    echo Invalid choice. Please run the script again.
)

echo.
pause
