# 电视机全面测试脚本
# 测试IP: 10.181.184.226

param(
    [string]$TV_IP = "10.181.184.226",
    [int]$TV_PORT = 5555
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "电视机全面测试脚本" -ForegroundColor Cyan
Write-Host "测试目标: ${TV_IP}:${TV_PORT}" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan

# 函数：执行命令并检查结果
function Test-Command {
    param(
        [string]$Command,
        [string]$Description,
        [int]$Timeout = 30
    )
    
    Write-Host "`n测试: $Description" -ForegroundColor Yellow
    Write-Host "命令: $Command" -ForegroundColor Gray
    
    try {
        $startTime = Get-Date
        $result = Invoke-Expression $Command 2>&1
        $endTime = Get-Date
        $duration = ($endTime - $startTime).TotalSeconds
        
        Write-Host "结果: 成功 (${duration}秒)" -ForegroundColor Green
        if ($result) {
            Write-Host "输出: $result" -ForegroundColor Gray
        }
        return $true
    } catch {
        Write-Host "结果: 失败 - $($_.Exception.Message)" -ForegroundColor Red
        return $false
    }
}

# 1. 测试ADB连接
Write-Host "`n1. 测试ADB连接..." -ForegroundColor Cyan
$adbTest = Test-Command -Command "adb connect ${TV_IP}:${TV_PORT}" -Description "ADB连接测试"

if (-not $adbTest) {
    Write-Host "ADB连接失败，请检查:" -ForegroundColor Red
    Write-Host "1. 电视机是否开机" -ForegroundColor Yellow
    Write-Host "2. 电视机ADB调试是否开启" -ForegroundColor Yellow
    Write-Host "3. 网络是否连通" -ForegroundColor Yellow
    Write-Host "按任意键退出..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit 1
}

# 2. 测试设备信息获取
Write-Host "`n2. 测试设备信息获取..." -ForegroundColor Cyan
Test-Command -Command "adb -s ${TV_IP}:${TV_PORT} shell getprop ro.product.model" -Description "获取设备型号"
Test-Command -Command "adb -s ${TV_IP}:${TV_PORT} shell getprop ro.build.version.release" -Description "获取Android版本"
Test-Command -Command "adb -s ${TV_IP}:${TV_PORT} shell ifconfig wlan0 || ip addr show wlan0" -Description "获取网络信息"

# 3. 测试APK安装
Write-Host "`n3. 测试APK安装..." -ForegroundColor Cyan
$apkPath = Join-Path $PSScriptRoot "..\android_app\app\build\outputs\apk\debug\app-debug.apk"
if (Test-Path $apkPath) {
    Test-Command -Command "adb -s ${TV_IP}:${TV_PORT} install -r `"$apkPath`"" -Description "安装TV Launcher APK"
} else {
    Write-Host "APK文件未找到: $apkPath" -ForegroundColor Red
    Write-Host "请先编译Android项目" -ForegroundColor Yellow
}

# 4. 测试HDMI切换
Write-Host "`n4. 测试HDMI切换..." -ForegroundColor Cyan
Write-Host "注意: HDMI切换测试需要电视机有HDMI信号源连接" -ForegroundColor Yellow

# 测试切换到HDMI1
Test-Command -Command "adb -s ${TV_IP}:${TV_PORT} shell input keyevent --longpress 82" -Description "打开输入源菜单(长按菜单键)"
Start-Sleep -Seconds 2
Test-Command -Command "adb -s ${TV_IP}:${TV_PORT} shell input keyevent 20" -Description "向下选择(KEYCODE_DPAD_DOWN)"
Test-Command -Command "adb -s ${TV_IP}:${TV_PORT} shell input keyevent 20" -Description "向下选择(KEYCODE_DPAD_DOWN)"
Test-Command -Command "adb -s ${TV_IP}:${TV_PORT} shell input keyevent 23" -Description "确认选择(KEYCODE_DPAD_CENTER)"

# 5. 测试APP启动
Write-Host "`n5. 测试APP启动..." -ForegroundColor Cyan
$testApps = @(
    @{Name="设置"; Package="com.android.settings"},
    @{Name="Chrome浏览器"; Package="com.android.chrome"},
    @{Name="文件管理器"; Package="com.android.documentsui"}
)

foreach ($app in $testApps) {
    Test-Command -Command "adb -s ${TV_IP}:${TV_PORT} shell monkey -p $($app.Package) -c android.intent.category.LAUNCHER 1" -Description "启动$($app.Name)"
    Start-Sleep -Seconds 2
    # 返回主页
    Test-Command -Command "adb -s ${TV_IP}:${TV_PORT} shell input keyevent 3" -Description "返回主页(KEYCODE_HOME)"
    Start-Sleep -Seconds 1
}

# 6. 测试Scrcpy
Write-Host "`n6. 测试Scrcpy..." -ForegroundColor Cyan
$scrcpyExe = Join-Path $PSScriptRoot "scrcpy\scrcpy.exe"
if (Test-Path $scrcpyExe) {
    Write-Host "启动Scrcpy远程控制..." -ForegroundColor Yellow
    Write-Host "按Ctrl+C停止Scrcpy" -ForegroundColor Yellow
    
    $scrcpyProcess = Start-Process -FilePath $scrcpyExe -ArgumentList "--serial ${TV_IP}:${TV_PORT} --no-audio --max-fps 15 --max-size 800" -NoNewWindow -PassThru
    
    # 等待10秒让用户查看
    Start-Sleep -Seconds 10
    
    # 停止Scrcpy
    if ($scrcpyProcess -and (-not $scrcpyProcess.HasExited)) {
        Stop-Process -Id $scrcpyProcess.Id -Force
        Write-Host "Scrcpy已停止" -ForegroundColor Green
    }
} else {
    Write-Host "Scrcpy未安装，跳过测试" -ForegroundColor Yellow
    Write-Host "运行 .\install_scrcpy.py 安装Scrcpy" -ForegroundColor Yellow
}

# 7. 测试后台清理
Write-Host "`n7. 测试后台清理..." -ForegroundColor Cyan
Test-Command -Command "adb -s ${TV_IP}:${TV_PORT} shell am force-stop com.android.chrome" -Description "强制停止Chrome浏览器"
Test-Command -Command "adb -s ${TV_IP}:${TV_PORT} shell pm clear com.android.settings" -Description "清除设置数据"

# 8. 测试系统信息
Write-Host "`n8. 测试系统信息..." -ForegroundColor Cyan
Test-Command -Command "adb -s ${TV_IP}:${TV_PORT} shell dumpsys meminfo" -Description "内存信息" | Select-Object -First 20
Test-Command -Command "adb -s ${TV_IP}:${TV_PORT} shell df -h" -Description "磁盘空间"
Test-Command -Command "adb -s ${TV_IP}:${TV_PORT} shell cat /proc/cpuinfo" -Description "CPU信息" | Select-Object -First 10

# 测试总结
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "测试完成" -ForegroundColor Green
Write-Host "电视机IP: ${TV_IP}" -ForegroundColor Green
Write-Host "测试时间: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "`n下一步操作建议:" -ForegroundColor Yellow
Write-Host "1. 编译并安装TV Launcher APK" -ForegroundColor White
Write-Host "2. 在电视机上设置TV Launcher为默认桌面" -ForegroundColor White
Write-Host "3. 通过网页后台管理电视机策略" -ForegroundColor White
Write-Host "4. 使用Scrcpy进行远程控制" -ForegroundColor White

Write-Host "`n按任意键退出..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")