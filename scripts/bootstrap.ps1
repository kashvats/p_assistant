$ErrorActionPreference = "Stop"
if (-not (Test-Path ".venv\Scripts\python.exe")) {
  python -m venv .venv
}
$Py = (Resolve-Path ".venv\Scripts\python.exe").Path
& $Py -m pip install --upgrade pip
& $Py -m pip install -e .
Write-Host ""
Write-Host "Living Assistant installed."
Write-Host "Activation is optional; this bootstrap does not depend on PowerShell script execution policy."
Write-Host "Next: install/start Ollama, then run: .\.venv\Scripts\organism.exe doctor"
