#!/usr/bin/env bash
set -euo pipefail
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e .
# crawl4ai without deps: it requires a litellm fork that would replace the project's litellm.
.venv/bin/python -m pip install --no-deps "crawl4ai==0.9.4"
.venv/bin/python -m playwright install chromium
echo
echo "Living Assistant installed."
echo "Next: install/start Ollama, then run: .venv/bin/organism doctor"
