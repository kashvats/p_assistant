#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
EXE="$ROOT/.venv/bin/organism"
if [ ! -x "$EXE" ]; then echo "Missing $EXE. Create the venv/install package first."; exit 1; fi
PLIST="$HOME/Library/LaunchAgents/com.livingassistant.daemon.plist"
mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>com.livingassistant.daemon</string>
<key>ProgramArguments</key><array><string>$EXE</string><string>daemon</string></array>
<key>WorkingDirectory</key><string>$ROOT</string>
<key>RunAtLoad</key><true/><key>KeepAlive</key><true/>
<key>StandardOutPath</key><string>$HOME/Library/Logs/living-assistant.log</string>
<key>StandardErrorPath</key><string>$HOME/Library/Logs/living-assistant.err.log</string>
</dict></plist>
EOF
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
echo "Installed $PLIST"
