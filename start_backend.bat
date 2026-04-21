@echo off
chcp 65001 >nul
title Meeting TV Launcher Backend
color 0A

echo.
echo ========================================================
echo        Meeting TV Launcher Backend Server
echo ========================================================
echo.

:: Change to backend directory
cd /d "%~dp0backend_server"
if not exist "app" (
    echo [ERROR] Backend app folder not found!
    echo Please run this script from the project root directory.
    echo.
    pause
    exit /b 1
)

echo [1/4] Checking Python...
python --version
if %errorlevel% neq 0 (
    echo [ERROR] Python not found! Please install Python 3.9+
    pause
    exit /b 1
)

echo [2/4] Setting up virtual environment...
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create venv
        pause
        exit /b 1
    )
)

echo [3/4] Activating virtual environment...
call venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo [ERROR] Failed to activate venv
    pause
    exit /b 1
)

echo [4/4] Installing dependencies...
pip install fastapi uvicorn sqlalchemy pydantic python-multipart websockets -q

echo.
echo ========================================================
echo Server starting on http://localhost:8000
echo Press Ctrl+C to stop
echo ========================================================
echo.

:: Kill existing processes on port 8000
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING 2^>nul') do (
    taskkill /f /pid %%a >nul 2>&1
)
timeout /t 1 >nul

:: Start server
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

pause
