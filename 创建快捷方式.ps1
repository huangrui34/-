$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$env:USERPROFILE\Desktop\MeetingTV后台服务.lnk")
$Shortcut.TargetPath = "%USERPROFILE%\Desktop\启动后台服务.bat"
$Shortcut.WorkingDirectory = "%USERPROFILE%\Desktop"
$Shortcut.Description = "一键启动 Meeting TV Launcher 后台管理服务"
$Shortcut.Save()
Write-Host "快捷方式已创建到桌面: MeetingTV后台服务.lnk"
