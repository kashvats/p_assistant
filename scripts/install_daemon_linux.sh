#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
EXE="$ROOT/.venv/bin/organism"
if [ ! -x "$EXE" ]; then echo "Missing $EXE. Run scripts/bootstrap.sh first."; exit 1; fi
mkdir -p "$HOME/.config/systemd/user"
cat > "$HOME/.config/systemd/user/living-assistant.service" <<EOF
[Unit]
Description=Living Assistant nervous system
After=network-online.target

[Service]
Type=simple
WorkingDirectory=$ROOT
ExecStart=$EXE daemon
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF
systemctl --user daemon-reload
systemctl --user enable --now living-assistant.service
echo "Enabled user service: living-assistant.service"
