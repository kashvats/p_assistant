$ErrorActionPreference = "Stop"
if (-not (Test-Path ".venv")) {
  python -m venv .venv
}
& .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
Write-Host ""
Write-Host "Living Assistant installed."
Write-Host "Next: install/start Ollama, then run: organism doctor"
