$ErrorActionPreference = 'Stop'
if (Test-Path '.venv\Scripts\Activate.ps1') { & .\.venv\Scripts\Activate.ps1 }
python -m pip install -e '.[desktop,browser]'
python -m playwright install chromium
Write-Host 'Desktop + browser operator extras installed.'
