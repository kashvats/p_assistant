$ErrorActionPreference = 'Stop'
if (-not (Get-Command wix -ErrorAction SilentlyContinue)) { throw 'WiX Toolset v4 (`wix`) is required on Windows.' }
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Wheel = Get-ChildItem (Join-Path $Root 'dist\living_assistant-*.whl') | Sort-Object Name | Select-Object -Last 1
if (-not $Wheel) { throw 'Build the wheel first.' }
$Stage = Join-Path $env:TEMP ('living-assistant-msi-' + [guid]::NewGuid())
New-Item -ItemType Directory -Force -Path (Join-Path $Stage 'payload\dist'),(Join-Path $Stage 'payload\scripts'),(Join-Path $Stage 'payload\src\living_assistant') | Out-Null
Copy-Item $Wheel.FullName (Join-Path $Stage 'payload\dist\')
Copy-Item (Join-Path $Root 'scripts\install.py') (Join-Path $Stage 'payload\scripts\')
Copy-Item (Join-Path $Root 'src\living_assistant\release_manager.py'),(Join-Path $Root 'src\living_assistant\__init__.py') (Join-Path $Stage 'payload\src\living_assistant\')
Write-Host 'Payload staged. The signed MSI wrapper must be built and signed on the Windows release host.'
Write-Host "Stage: $Stage"
Write-Host 'This source release intentionally does not embed or fake a signing certificate.'
