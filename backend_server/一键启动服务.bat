@echo off
chcp 65001 >nul
title Meeting TV Launcher - 一键启动服务
color 0A

setlocal enabledelayedexpansion

echo.
echo ========================================================
echo        Meeting TV Launcher - 一键启动所有服务
echo ========================================================
echo.

:: 设置路径
set "SCRIPT_DIR=%~dp0"
set "TV_IP=10.181.184.226"
set "TV_PORT=5555"
set "SERVER_PORT=8000"

:: 切换到后端目录
cd /d "%SCRIPT_DIR%"

:: 检查虚拟环境
if not exist "venv" (
    echo [创建] Python虚拟环境...
    python -m venv venv
)
echo [OK] 虚拟环境就绪

:: 安装依赖
echo [检查] 安装依赖库...
call venv\Scripts\activate.bat
pip install fastapi uvicorn sqlalchemy pydantic python-multipart websockets -q 2>nul
echo [OK] 依赖库已安装

:: 清理旧进程
echo [清理] 停止旧服务...
taskkill /f /im uvicorn.exe >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :%SERVER_PORT% ^| findstr LISTENING 2^>nul') do (
    taskkill /f /pid %%a >nul 2>&1
)

:: 等待端口释放
timeout /t 2 >nul

:: 启动后端服务
echo [启动] 后端API服务 (端口: %SERVER_PORT%)...
start "TV-Launcher-API" cmd /c "cd /d %SCRIPT_DIR% && call venv\Scripts\activate.bat && uvicorn app.main:app --host 0.0.0.0 --port %SERVER_PORT% --reload"

:: 等待服务启动
timeout /t 5 >nul

:: 检查服务是否启动成功
echo [检查] 服务状态...
curl -s http://localhost:%SERVER_PORT%/api/health >nul 2>&1
if errorlevel 1 (
    echo [警告] API服务可能还在启动中...
) else (
    echo [OK] API服务已启动
)

:: 连接ADB到电视
echo [连接] ADB连接电视 (%TV_IP%:%TV_PORT%)...
"D:\MyConfiguration\admin\AppData\Local\Android\Sdk\platform-tools\adb.exe" connect %TV_IP%:%TV_PORT% >nul 2>&1
timeout /t 2 >nul

echo.
echo ========================================================
echo                  服务已启动
echo ========================================================
echo   后台管理: http://localhost:%SERVER_PORT%
echo   电视IP:    %TV_IP%:%TV_PORT%
echo ========================================================
echo.

:: 自动打开浏览器
echo [提示] 正在打开管理页面...
start http://localhost:%SERVER_PORT%

echo.
echo 服务运行中，请勿关闭此窗口...
echo 按任意键停止所有服务...
echo.

pause >nul

echo.
echo [停止] 正在停止所有服务...
taskkill /f /im uvicorn.exe >nul 2>&1
taskkill /f /fi "WINDOWTITLE eq TV-Launcher-API*" >nul 2>&1
echo [OK] 服务已停止

pause
