@echo off
chcp 65001 >nul 2>&1
title Meeting TV Launcher

cd /d "%~dp0"

echo ========================================
echo   Meeting TV Launcher
echo ========================================
echo.

:: 1. Stop existing services
echo [1/4] Stopping existing services...
taskkill /f /im scrcpy.exe >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING 2^>nul') do (
    taskkill /f /pid %%a >nul 2>&1
)
timeout /t 2 /nobreak >nul

:: 2. Find Python
echo [2/4] Finding Python...
set "PY="
for %%c in (python python3 py) do (
    %%c --version >nul 2>&1
    if not errorlevel 1 if not defined PY set "PY=%%c"
)
if not defined PY (
    echo [ERROR] Python not found. Install Python 3.9-3.13
    echo         https://www.python.org/downloads/
    pause
    exit /b 1
)
%PY% --version

:: 3. Create venv if missing
if not exist "venv\Scripts\python.exe" (
    echo [3/4] Creating venv...
    %PY% -m venv venv
    if not exist "venv\Scripts\python.exe" (
        echo [ERROR] Failed to create venv
        pause
        exit /b 1
    )
) else (
    echo [3/4] venv OK
)
call venv\Scripts\activate.bat

:: 4. Install deps (only if needed)
echo [4/4] Checking dependencies...
pip install -r requirements.txt --timeout 15 -i https://pypi.tuna.tsinghua.edu.cn/simple -q 2>nul
if errorlevel 1 (
    echo   Tsinghua mirror failed, trying default...
    pip install -r requirements.txt --timeout 15 -q 2>nul
    if errorlevel 1 (
        echo   Retrying with verbose output...
        pip install -r requirements.txt --timeout 15
        if errorlevel 1 (
            echo [ERROR] Failed to install dependencies
            pause
            exit /b 1
        )
    )
)

echo.
echo ========================================
echo   Dashboard: http://localhost:8000
echo   Press Ctrl+C to stop
echo ========================================
echo.

:: Auto-open browser
start "" /b cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:8000"

:: Start server
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

pause
