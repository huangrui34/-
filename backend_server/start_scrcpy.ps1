# Scrcpy启动脚本 (PowerShell版本)
# 自动安装并启动Scrcpy

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Scrcpy自动启动脚本" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# 检查参数
if ($args.Count -eq 0) {
    Write-Host "使用方法: .\start_scrcpy.ps1 [电视IP地址]" -ForegroundColor Yellow
    Write-Host "例如: .\start_scrcpy.ps1 10.181.184.226" -ForegroundColor Yellow
    Write-Host "按任意键继续..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit 1
}

$TV_IP = $args[0]
$TV_PORT = 5555

Write-Host "目标电视: ${TV_IP}:${TV_PORT}" -ForegroundColor Green

# 检查Python是否安装
try {
    $pythonVersion = python --version 2>&1
    Write-Host "Python版本: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "错误: Python未安装或未添加到PATH" -ForegroundColor Red
    Write-Host "请先安装Python 3.6或更高版本" -ForegroundColor Yellow
    Write-Host "按任意键继续..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit 1
}

# 检查并安装Scrcpy
Write-Host "检查Scrcpy安装状态..." -ForegroundColor Cyan
$installResult = python install_scrcpy.py

if ($LASTEXITCODE -ne 0) {
    Write-Host "Scrcpy安装失败，请手动安装" -ForegroundColor Red
    Write-Host "1. 访问: https://github.com/Genymobile/scrcpy/releases" -ForegroundColor Yellow
    Write-Host "2. 下载最新版本" -ForegroundColor Yellow
    Write-Host "3. 解压到: $PSScriptRoot\scrcpy\" -ForegroundColor Yellow
    Write-Host "按任意键继续..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit 1
}

Write-Host "Scrcpy安装检查完成" -ForegroundColor Green

# 检查ADB连接
Write-Host "检查ADB连接..." -ForegroundColor Cyan
adb connect "${TV_IP}:${TV_PORT}"

# 启动Scrcpy
Write-Host "启动Scrcpy..." -ForegroundColor Cyan
$scrcpyExe = Join-Path $PSScriptRoot "scrcpy\scrcpy.exe"

if (Test-Path $scrcpyExe) {
    & $scrcpyExe --serial "${TV_IP}:${TV_PORT}" --no-audio --max-fps 30 --max-size 1280
} else {
    # 尝试使用系统PATH中的scrcpy
    scrcpy --serial "${TV_IP}:${TV_PORT}" --no-audio --max-fps 30 --max-size 1280
}

Write-Host "Scrcpy已启动" -ForegroundColor Green
Write-Host "按任意键退出..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")