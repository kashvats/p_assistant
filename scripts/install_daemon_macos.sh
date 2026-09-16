#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RELEASE_EXE="$HOME/Library/Application Support/LivingAssistantRuntime/bin/living-assistant-daemon"
DEV_EXE="$ROOT/.venv/bin/organism"
if [ -x "$RELEASE_EXE" ]; then EXE="$RELEASE_EXE"; WORKDIR="$HOME"; PY="$(command -v python3)"
elif [ -x "$DEV_EXE" ]; then EXE="$DEV_EXE"; WORKDIR="$ROOT"; PY="$ROOT/.venv/bin/python"
else echo "No installed Living Assistant runtime found. Run install_release_macos.sh or bootstrap.sh first." >&2; exit 1; fi
PLIST="$HOME/Library/LaunchAgents/com.livingassistant.daemon.plist"; LOGDIR="$HOME/Library/Logs"
mkdir -p "$HOME/Library/LaunchAgents" "$LOGDIR"
WORKDIR="$WORKDIR" EXE="$EXE" PLIST="$PLIST" LOGDIR="$LOGDIR" "$PY" - <<'PY'
import os, plistlib
payload={
    'Label':'com.livingassistant.daemon','ProgramArguments':[os.environ['EXE']],
    'WorkingDirectory':os.environ['WORKDIR'],'RunAtLoad':True,'KeepAlive':{'SuccessfulExit':False},
    'ProcessType':'Background','StandardOutPath':os.path.join(os.environ['LOGDIR'],'living-assistant.log'),
    'StandardErrorPath':os.path.join(os.environ['LOGDIR'],'living-assistant.err.log'),
}
with open(os.environ['PLIST'],'wb') as f: plistlib.dump(payload,f,sort_keys=False)
PY
plutil -lint "$PLIST" >/dev/null
DOMAIN="gui/$(id -u)"; launchctl bootout "$DOMAIN" "$PLIST" 2>/dev/null || true
launchctl bootstrap "$DOMAIN" "$PLIST"; launchctl kickstart -k "$DOMAIN/com.livingassistant.daemon"
echo "Installed and started LaunchAgent: com.livingassistant.daemon"
