@echo off
chcp 65001 >nul
title Meeting TV Launcher - Start Service
color 0A

setlocal enabledelayedexpansion

echo.
echo ========================================================
echo        Meeting TV Launcher - Start All Services
echo ========================================================
echo.

:: Set paths
set "SCRIPT_DIR=%~dp0"
set "BACKEND_DIR=%SCRIPT_DIR%backend_server"
set "TV_IP=10.181.184.226"
set "TV_PORT=5555"
set "SERVER_PORT=8000"

:: Check Python
echo [Check] Python environment...
python --version
if errorlevel 1 (
    echo [ERROR] Python not found, please install Python 3.9+
    pause
    exit /b 1
)
echo [OK] Python installed

:: Change to backend directory
cd /d "%BACKEND_DIR%"
if not exist "app" (
    echo [ERROR] Backend app folder not found!
    echo Current directory: %CD%
    pause
    exit /b 1
)

:: Create virtual environment
if not exist "venv" (
    echo [Create] Python virtual environment...
    python -m venv venv
)
echo [OK] Virtual environment ready

:: Install dependencies
echo [Check] Installing dependencies...
call venv\Scripts\activate.bat
pip install fastapi uvicorn sqlalchemy pydantic python-multipart websockets -q 2>nul
echo [OK] Dependencies installed

:: Kill old processes
echo [Clean] Stopping old services...
taskkill /f /im uvicorn.exe >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :%SERVER_PORT% ^| findstr LISTENING 2^>nul') do (
    taskkill /f /pid %%a >nul 2>&1
)

:: Wait for port release
timeout /t 2 >nul

:: Start backend service
echo [Start] Backend API service (port: %SERVER_PORT%)...
start "TV-Launcher-API" cmd /c "cd /d %BACKEND_DIR% && call venv\Scripts\activate.bat && python -m uvicorn app.main:app --host 0.0.0.0 --port %SERVER_PORT% --reload"

:: Wait for service to start
timeout /t 5 >nul

:: Check service status
echo [Check] Service status...
curl -s http://localhost:%SERVER_PORT%/health >nul 2>&1
if errorlevel 1 (
    echo [Warning] API service may still be starting...
) else (
    echo [OK] API service started
)

:: Connect ADB to TV
echo [Connect] ADB connect TV (%TV_IP%:%TV_PORT%)...
"D:\MyConfiguration\admin\AppData\Local\Android\Sdk\platform-tools\adb.exe" connect %TV_IP%:%TV_PORT% >nul 2>&1
timeout /t 2 >nul

echo.
echo ========================================================
echo                  Services Started
echo ========================================================
echo   Dashboard: http://localhost:%SERVER_PORT%
echo   TV IP:     %TV_IP%:%TV_PORT%
echo ========================================================
echo.

:: Auto open browser
echo [Info] Opening dashboard page...
start http://localhost:%SERVER_PORT%

echo.
echo Services running, do not close this window...
echo Press any key to stop all services...
echo.

pause >nul

echo.
echo [Stop] Stopping all services...
taskkill /f /im uvicorn.exe >nul 2>&1
taskkill /f /fi "WINDOWTITLE eq TV-Launcher-API*" >nul 2>&1
echo [OK] Services stopped

pause
