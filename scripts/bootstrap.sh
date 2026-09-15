#!/usr/bin/env bash
set -euo pipefail
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .
echo
echo "Living Assistant installed."
echo "Next: install/start Ollama, then run: organism doctor"
