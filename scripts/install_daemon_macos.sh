#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
EXE="$ROOT/.venv/bin/organism"
PY="$ROOT/.venv/bin/python"
if [ ! -x "$EXE" ] || [ ! -x "$PY" ]; then echo "Missing venv. Create/install the package first."; exit 1; fi
PLIST="$HOME/Library/LaunchAgents/com.livingassistant.daemon.plist"
LOGDIR="$HOME/Library/Logs"
mkdir -p "$HOME/Library/LaunchAgents" "$LOGDIR"
ROOT="$ROOT" EXE="$EXE" PLIST="$PLIST" LOGDIR="$LOGDIR" "$PY" - <<'PY'
import os, plistlib
payload={
    'Label':'com.livingassistant.daemon',
    'ProgramArguments':[os.environ['EXE'],'daemon'],
    'WorkingDirectory':os.environ['ROOT'],
    'RunAtLoad':True,
    'KeepAlive':{'SuccessfulExit':False},
    'ProcessType':'Background',
    'StandardOutPath':os.path.join(os.environ['LOGDIR'],'living-assistant.log'),
    'StandardErrorPath':os.path.join(os.environ['LOGDIR'],'living-assistant.err.log'),
}
with open(os.environ['PLIST'],'wb') as f: plistlib.dump(payload,f,sort_keys=False)
PY
plutil -lint "$PLIST" >/dev/null
DOMAIN="gui/$(id -u)"
launchctl bootout "$DOMAIN" "$PLIST" 2>/dev/null || true
launchctl bootstrap "$DOMAIN" "$PLIST"
launchctl kickstart -k "$DOMAIN/com.livingassistant.daemon"
echo "Installed and started LaunchAgent: com.livingassistant.daemon"
