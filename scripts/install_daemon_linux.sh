#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RELEASE_EXE="${XDG_DATA_HOME:-$HOME/.local/share}/LivingAssistantRuntime/bin/living-assistant-daemon"
DEV_EXE="$ROOT/.venv/bin/organism"
if [ -x "$RELEASE_EXE" ]; then
  EXE="$RELEASE_EXE"
  WORKDIR="$HOME"
elif [ -x "$DEV_EXE" ]; then
  EXE="$DEV_EXE"
  WORKDIR="$ROOT"
else
  echo "No installed Living Assistant runtime found. Run install_release_linux.sh or bootstrap.sh first." >&2; exit 1
fi
mkdir -p "$HOME/.config/systemd/user"
unit_quote() {
  local v="$1"
  if [[ "$v" == *$'\n'* || "$v" == *$'\r'* ]]; then echo "Paths containing newlines are unsupported." >&2; exit 2; fi
  v="${v//\\/\\\\}"; v="${v//\"/\\\"}"; v="${v//%/%%}"; printf '%s' "$v"
}
UNIT_WORKDIR="$(unit_quote "$WORKDIR")"; UNIT_EXE="$(unit_quote "$EXE")"
cat > "$HOME/.config/systemd/user/living-assistant.service" <<EOF
[Unit]
Description=Living Assistant nervous system
After=network-online.target

[Service]
Type=simple
WorkingDirectory="$UNIT_WORKDIR"
ExecStart="$UNIT_EXE"
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
