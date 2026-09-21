#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WHEEL="${1:-}"
EXTRAS="${LIVING_ASSISTANT_EXTRAS:-desktop,browser,voice,wakeword,connectors,security}"
CHECKSUM_FILE="${LIVING_ASSISTANT_CHECKSUM_FILE:-$ROOT/SHA256SUMS.txt}"
if [ -z "$WHEEL" ]; then
  WHEEL="$(find "$ROOT/dist" -maxdepth 1 -name 'living_assistant-*.whl' -print | sort | tail -n1)"
fi
if [ -z "$WHEEL" ] || [ ! -f "$WHEEL" ]; then echo "Living Assistant wheel not found." >&2; exit 2; fi
if [ ! -f "$CHECKSUM_FILE" ]; then echo "Checksum manifest not found: $CHECKSUM_FILE" >&2; exit 3; fi
EXPECTED_SHA="$(python3 - "$CHECKSUM_FILE" "$WHEEL" <<'PY'
from pathlib import Path
import sys
manifest=Path(sys.argv[1]); wheel=Path(sys.argv[2]).resolve(); target=wheel.name
for line in manifest.read_text(encoding='utf-8').splitlines():
    parts=line.strip().split(None,1)
    if len(parts)==2 and Path(parts[1].lstrip('*')).name==target:
        print(parts[0]); raise SystemExit(0)
raise SystemExit(4)
PY
)" || { echo "No checksum entry found for $(basename "$WHEEL")" >&2; exit 4; }
python3 "$ROOT/scripts/install.py" install "$WHEEL" --extras "$EXTRAS" --sha256 "$EXPECTED_SHA"
echo
echo "Installed verified versioned runtime. Add to PATH if desired:"
echo "  $HOME/Library/Application Support/LivingAssistantRuntime/bin"
echo "Then run the organism shim from that directory and execute: organism doctor"
