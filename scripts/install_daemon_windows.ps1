$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ReleaseDaemon = Join-Path $env:LOCALAPPDATA "LivingAssistant\Runtime\bin\living-assistant-daemon.cmd"
$DevExe = Join-Path $Root ".venv\Scripts\organism.exe"
if (Test-Path $ReleaseDaemon) {
  $Action = New-ScheduledTaskAction -Execute $env:ComSpec -Argument "/d /s /c `"`"$ReleaseDaemon`"`"" -WorkingDirectory $env:USERPROFILE
} elseif (Test-Path $DevExe) {
  $Action = New-ScheduledTaskAction -Execute $DevExe -Argument "daemon" -WorkingDirectory $Root
} else { throw "No installed Living Assistant runtime found. Run install_release_windows.ps1 or bootstrap.ps1 first." }
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Seconds 0) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName "LivingAssistant" -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings -Force | Out-Null
Start-ScheduledTask -TaskName "LivingAssistant"
Get-ScheduledTask -TaskName "LivingAssistant" | Select-Object TaskName,State
Write-Host "Installed and started limited-privilege Scheduled Task: LivingAssistant"
