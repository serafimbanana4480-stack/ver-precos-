@echo off
REM AutoDeal IA Hunter - Startup Script

echo ========================================
echo AutoDeal IA Hunter
echo ========================================
echo.

REM Check if virtual environment exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt

REM Check if .env file exists
if not exist ".env" (
    echo Creating .env file from example...
    copy .env.example .env
    echo.
    echo IMPORTANT: Please edit .env file with your configuration before running the application.
    echo.
    pause
    exit /b
)

REM Run the application
echo.
echo Starting application...
python main.py %*

pause
