"""The Electron desktop shell: one floating-agent window with the guarantees the product relies on."""
from __future__ import annotations

import json
import re
from pathlib import Path

SHELL = Path("electron-assistant")


def test_single_floating_agent_window_and_old_companion_removed():
    for old in ("index.html", "renderer.js", "style.css", "preload.js"):
        assert not (SHELL / old).exists(), old  # the duplicate chat UI (and its token-in-URL requests) is gone
    main = (SHELL / "main.js").read_text(encoding="utf-8")
    assert main.count("new BrowserWindow(") == 1
    assert "loadURL(`${API_URL}/agent`)" in main
    assert "token=" not in main


def test_shell_keeps_the_agent_available():
    main = (SHELL / "main.js").read_text(encoding="utf-8")
    assert "requestSingleInstanceLock()" in main            # one copy; a second launch opens the chat
    assert "setAlwaysOnTop(true, 'screen-saver')" in main   # above fullscreen apps
    assert "setLoginItemSettings" in main                   # optional start with the OS
    assert "superviseBackend" in main and "startBackend" in main  # restarts the backend when it is down
    assert "agent-settings.json" in main and "rememberPosition" in main
    assert "globalShortcut.register('CommandOrControl+Shift+Space'" in main
    assert "sandbox: true" in main and "contextIsolation: true" in main and "nodeIntegration: false" in main


def test_preload_exposes_only_the_agent_bridge():
    preload = (SHELL / "agent-preload.js").read_text(encoding="utf-8")
    exposed = re.findall(r"^\s{2}(\w+):", preload, re.M)
    assert exposed == ["moveBy", "dragStart", "dragMove", "dragEnd", "savePosition", "setClickThrough", "setExpanded", "openDashboard", "captureScreen", "quitApp", "menu",
                       "onCursor", "onMenuAction"]
    assert "require('fs')" not in preload and "shell" not in preload


def test_run_bat_no_longer_starts_the_desktop_companion():
    # Removed 2026-10-12 at the user's request: the orb used ~370 MB the local model needs.
    run_bat = Path("run.bat").read_text(encoding="utf-8")
    assert "ELECTRON_EXE" not in run_bat and "npm.cmd install" not in run_bat
