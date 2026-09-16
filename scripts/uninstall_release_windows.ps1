$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
python (Join-Path $Root "scripts\install.py") uninstall @args
