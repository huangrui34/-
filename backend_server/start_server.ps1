# Simple startup script
Set-Location $PSScriptRoot

Write-Host "[1/2] 清理 8000 端口..." -ForegroundColor Gray
try {
    $conns = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
    if ($conns) {
        foreach ($c in $conns) {
            Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
            Write-Host "已关闭 PID: $($c.OwningProcess)" -ForegroundColor Gray
        }
    }
} catch {
    # Ignore errors
}

Write-Host "[2/2] 启动 Uvicorn..." -ForegroundColor Green
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
