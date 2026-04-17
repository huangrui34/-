@echo off
REM Scrcpy启动脚本
REM 自动安装并启动Scrcpy

setlocal enabledelayedexpansion

echo ========================================
echo Scrcpy自动启动脚本
echo ========================================

REM 检查参数
if "%1"=="" (
    echo 使用方法: start_scrcpy.bat [电视IP地址]
    echo 例如: start_scrcpy.bat 10.181.184.226
    pause
    exit /b 1
)

set TV_IP=%1
set TV_PORT=5555

echo 目标电视: %TV_IP%:%TV_PORT%

REM 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: Python未安装或未添加到PATH
    echo 请先安装Python 3.6或更高版本
    pause
    exit /b 1
)

REM 检查并安装Scrcpy
echo 检查Scrcpy安装状态...
python install_scrcpy.py

if errorlevel 1 (
    echo Scrcpy安装失败，请手动安装
    echo 1. 访问: https://github.com/Genymobile/scrcpy/releases
    echo 2. 下载最新版本
    echo 3. 解压到: %~dp0scrcpy\
    pause
    exit /b 1
)

echo Scrcpy安装检查完成

REM 检查ADB连接
echo 检查ADB连接...
adb connect %TV_IP%:%TV_PORT%

REM 启动Scrcpy
echo 启动Scrcpy...
if exist "scrcpy\scrcpy.exe" (
    scrcpy\scrcpy.exe --serial %TV_IP%:%TV_PORT% --no-audio --max-fps 30 --max-size 1280
) else (
    scrcpy --serial %TV_IP%:%TV_PORT% --no-audio --max-fps 30 --max-size 1280
)

echo Scrcpy已启动
pause