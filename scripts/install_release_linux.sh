#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WHEEL="${1:-}"
EXTRAS="${LIVING_ASSISTANT_EXTRAS:-desktop,browser,voice,wakeword,connectors,security}"
if [ -z "$WHEEL" ]; then
  WHEEL="$(find "$ROOT/dist" -maxdepth 1 -name 'living_assistant-*.whl' -print | sort | tail -n1)"
fi
if [ -z "$WHEEL" ] || [ ! -f "$WHEEL" ]; then echo "Living Assistant wheel not found." >&2; exit 2; fi
python3 "$ROOT/scripts/install.py" install "$WHEEL" --extras "$EXTRAS"
echo
echo "Installed versioned runtime. Add this directory to PATH if desired:"
echo "  ${XDG_DATA_HOME:-$HOME/.local/share}/LivingAssistantRuntime/bin"
echo "Then run: organism doctor"
