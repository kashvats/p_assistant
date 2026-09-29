$ErrorActionPreference = "Stop"
if (-not (Test-Path ".venv\Scripts\python.exe")) {
  python -m venv .venv
}
$Py = (Resolve-Path ".venv\Scripts\python.exe").Path
& $Py -m pip install --upgrade pip
& $Py -m pip install -e .
# crawl4ai without deps: it requires a litellm fork that would replace the project's litellm.
& $Py -m pip install --no-deps "crawl4ai==0.9.4"
& $Py -m playwright install chromium
Write-Host ""
Write-Host "Living Assistant installed."
Write-Host "Activation is optional; this bootstrap does not depend on PowerShell script execution policy."
Write-Host "Next: install/start Ollama, then run: .\.venv\Scripts\organism.exe doctor"
