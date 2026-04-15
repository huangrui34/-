@echo off
chcp 65001 >nul
title Meeting TV Launcher Backend
color 0A

echo ========================================
echo    Meeting TV Launcher 后台服务启动器
echo ========================================
echo.

cd /d "%~dp0backend_server"
powershell -ExecutionPolicy Bypass -File start_server.ps1

pause
