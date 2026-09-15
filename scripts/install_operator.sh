#!/usr/bin/env bash
set -euo pipefail
source .venv/bin/activate 2>/dev/null || true
python -m pip install -e '.[desktop,browser]'
python -m playwright install chromium
echo 'Desktop + browser operator extras installed.'
