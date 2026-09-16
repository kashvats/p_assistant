# Desktop Intelligence — v0.14.0

Living Assistant v0.14 adds an accessibility-first local computer-use layer.

## Control order

1. Prefer application APIs/connectors when available.
2. Prefer semantic accessibility trees for native UI understanding.
3. Use browser DOM automation for webpages.
4. Use approved local screenshot + vision analysis only when semantic data is insufficient.
5. Use raw mouse/keyboard coordinates only as a final fallback.

## Platform backends

- **Windows:** built-in UI Automation through PowerShell/.NET for foreground semantic inspection. Elevated windows may be inaccessible from a non-elevated assistant process.
- **macOS:** System Events accessibility inspection. The user must grant Accessibility permission to the terminal/app running Living Assistant.
- **Linux:** AT-SPI when `pyatspi` and distro accessibility packages are available. `wmctrl` is used as a window-list fallback where present. Wayland may restrict synthetic input.

## Input control

Mouse/keyboard fallback uses `pyautogui` from the `desktop` optional dependency set. Every click, pointer move, hotkey and typed-text action goes through the existing approval manager. PyAutoGUI's fail-safe remains enabled.

## Multi-monitor

`mss` supplies monitor geometry and per-monitor screenshot capture. Monitor `0` means the combined virtual desktop; physical displays are numbered from `1`.

## Vision fallback

Vision is **disabled by default**:

```yaml
desktop:
  vision_enabled: false
  vision_model: null
  allow_remote_vision: false
```

When enabled, the screenshot is sent only to the configured Ollama vision model. Remote Ollama endpoints are refused for desktop screenshots unless `desktop.allow_remote_vision: true` is explicitly set.

The vision model is leased through the adaptive model manager, so it can stay unloaded until needed and remains subject to RAM/VRAM/concurrency controls.

## CLI

```bash
organism desktop status
organism desktop monitors
organism desktop windows
organism desktop accessibility
organism desktop click 400 300
organism desktop type "hello"
organism desktop hotkey "ctrl+s"
organism desktop analyze-screen
```

## Safety boundary

Reading accessibility text or screenshots is treated as a sensitive read. Input injection is treated as a desktop write. The assistant does not gain blanket permission to control the desktop just because Desktop Intelligence is enabled.
