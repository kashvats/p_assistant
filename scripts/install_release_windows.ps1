$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Wheel = $args[0]
if (-not $Wheel) {
  $Wheel = Get-ChildItem (Join-Path $Root "dist\living_assistant-*.whl") | Sort-Object Name | Select-Object -Last 1 -ExpandProperty FullName
}
if (-not $Wheel -or -not (Test-Path $Wheel)) { throw "Living Assistant wheel not found." }
$Extras = if ($env:LIVING_ASSISTANT_EXTRAS) { $env:LIVING_ASSISTANT_EXTRAS } else { "desktop,browser,voice,wakeword,connectors,security" }
python (Join-Path $Root "scripts\install.py") install $Wheel --extras $Extras
$Bin = Join-Path $env:LOCALAPPDATA "LivingAssistant\Runtime\bin"
Write-Host ""
Write-Host "Installed versioned runtime. Add this directory to your user PATH if desired:"
Write-Host "  $Bin"
Write-Host "Then run: organism doctor"
