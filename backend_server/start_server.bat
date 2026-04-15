@echo off
chcp 65001 >nul
title Meeting TV Launcher Backend
color 0A

setlocal enabledelayedexpansion

echo ========================================
echo    Meeting TV Launcher 后台服务启动器
echo ========================================
echo.

:: Check for Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python，请先安装 Python 3.9 或更高版本。
    echo 访问 https://www.python.org/downloads/ 下载并安装。
    pause
    exit /b 1
)

:: Check for ADB
adb version >nul 2>&1
if %errorlevel% neq 0 (
    echo [警告] 未在系统 PATH 中找到 ADB (Android Debug Bridge)。
    echo 远程控制、截屏和安装功能将无法使用。
    echo 请在其他电脑上安装 Android SDK Platform-Tools 并添加到系统 PATH。
)

:: Change to backend directory
cd /d "%~dp0"

:: Create and activate virtual environment if it doesn't exist
if not exist "venv" (
    echo [1/3] 正在创建 Python 虚拟环境...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [错误] 创建虚拟环境失败。
        pause
        exit /b 1
    )
)

:: Activate venv
echo [2/3] 正在激活虚拟环境...
if not exist "venv\Scripts\activate.bat" (
    echo [错误] 虚拟环境文件损坏，正在重新创建...
    rmdir /s /q venv
    python -m venv venv
)
call venv\Scripts\activate
if %errorlevel% neq 0 (
    echo [错误] 激活虚拟环境失败。
    pause
    exit /b 1
)

:: Install/Update requirements
echo [3/3] 正在检查并安装依赖库 (首次启动可能较慢)...
python -m pip install --upgrade pip
pip install fastapi uvicorn[standard] sqlalchemy pydantic python-multipart
if %errorlevel% neq 0 (
    echo [错误] 依赖安装失败，请检查网络连接。
    pause
    exit /b 1
)

echo.
echo ========================================
echo    服务启动成功！
echo ========================================
echo.
echo 访问地址: http://localhost:8000
echo 后台管理: http://localhost:8000
echo.
echo 按 Ctrl+C 可停止服务
echo ========================================
echo.

:: Kill anything on port 8000
echo [清理] 正在清理 8000 端口...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do (
    taskkill /f /pid %%a >nul 2>&1
)
taskkill /f /im uvicorn.exe >nul 2>&1
timeout /t 1 >nul

:: Start the app
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

pause
