$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Exe = Join-Path $Root ".venv\Scripts\organism.exe"
if (-not (Test-Path $Exe)) { throw "Missing $Exe. Run scripts\bootstrap.ps1 first." }
$Action = New-ScheduledTaskAction -Execute $Exe -Argument "daemon" -WorkingDirectory $Root
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Seconds 0) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName "LivingAssistant" -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings -Force | Out-Null
Start-ScheduledTask -TaskName "LivingAssistant"
Get-ScheduledTask -TaskName "LivingAssistant" | Select-Object TaskName,State
Write-Host "Installed and started limited-privilege Scheduled Task: LivingAssistant"
