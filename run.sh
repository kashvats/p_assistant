#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv}"

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

PYTHON="$VENV_DIR/bin/python"
"$PYTHON" -m pip install --disable-pip-version-check --quiet --upgrade pip
"$PYTHON" -m pip install --disable-pip-version-check --quiet -e .

export PYTHONPATH="$ROOT_DIR/src${PYTHONPATH:+:$PYTHONPATH}"
HOST="${ASSISTANT_HOST:-127.0.0.1}"
PORT="${ASSISTANT_PORT:-8787}"

echo "Starting Living Assistant at http://${HOST}:${PORT}"
exec "$PYTHON" -m uvicorn living_assistant.api:app --host "$HOST" --port "$PORT"
