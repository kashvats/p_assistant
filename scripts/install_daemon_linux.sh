#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
EXE="$ROOT/.venv/bin/organism"
if [ ! -x "$EXE" ]; then echo "Missing $EXE. Run scripts/bootstrap.sh first."; exit 1; fi
mkdir -p "$HOME/.config/systemd/user"
# systemd expands % specifiers even in paths; double literal percent signs.
unit_quote() {
  local v="$1"
  if [[ "$v" == *$'\n'* || "$v" == *$'\r'* ]]; then echo "Paths containing newlines are unsupported." >&2; exit 2; fi
  v="${v//\\/\\\\}"
  v="${v//\"/\\\"}"
  v="${v//%/%%}"
  printf '%s' "$v"
}
UNIT_ROOT="$(unit_quote "$ROOT")"
UNIT_EXE="$(unit_quote "$EXE")"
cat > "$HOME/.config/systemd/user/living-assistant.service" <<EOF
[Unit]
Description=Living Assistant nervous system
After=network-online.target

[Service]
Type=simple
WorkingDirectory="$UNIT_ROOT"
ExecStart="$UNIT_EXE" daemon
Restart=on-failure
RestartSec=5
TimeoutStopSec=20

[Install]
WantedBy=default.target
EOF
systemctl --user daemon-reload
systemctl --user enable --now living-assistant.service
systemctl --user --no-pager status living-assistant.service || true
echo "Enabled user service: living-assistant.service"
