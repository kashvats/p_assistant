#!/usr/bin/env bash
set -euo pipefail
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e .
echo
echo "Living Assistant installed."
echo "Next: install/start Ollama, then run: .venv/bin/organism doctor"
