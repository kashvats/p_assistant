from __future__ import annotations
from pathlib import Path
import webbrowser
from .base import Tool
from ..workspace import Workspace
from ..approval import ApprovalManager


def _clipboard_read_impl() -> str:
    try:
        import pyperclip
        return pyperclip.paste()
    except ImportError as e:
        raise RuntimeError('Clipboard support is optional. Install with: pip install -e ".[desktop]"') from e


def _clipboard_write_impl(text: str):
    try:
        import pyperclip
        pyperclip.copy(text)
    except ImportError as e:
        raise RuntimeError('Clipboard support is optional. Install with: pip install -e ".[desktop]"') from e


def _screenshot_impl(path: Path) -> str:
    try:
        import mss
        from PIL import Image
    except ImportError as e:
        raise RuntimeError('Screenshot support is optional. Install with: pip install -e ".[desktop]"') from e
    with mss.mss() as sct:
        monitor = sct.monitors[0]
        raw = sct.grab(monitor)
        image = Image.frombytes('RGB', raw.size, raw.rgb)
        path.parent.mkdir(parents=True, exist_ok=True)
        image.save(path)
    return str(path)


def build_desktop_tools(workspace: Workspace, approval: ApprovalManager) -> list[Tool]:
    def clipboard_read():
        req = approval.request('Read current clipboard contents',
                               'Clipboard may contain passwords, tokens or private text.', 'SENSITIVE_READ')
        if not req.get('allowed'):
            return {'ok': False, 'approval_required': True, **req}
        text = _clipboard_read_impl()
        return {'ok': True, 'text': text[:20000], 'truncated': len(text) > 20000}

    def clipboard_write(text: str):
        req = approval.request(f'Write {len(text)} characters to clipboard',
                               'This replaces the current clipboard contents.', 'DESKTOP_WRITE')
        if not req.get('allowed'):
            return {'ok': False, 'approval_required': True, **req}
        _clipboard_write_impl(text)
        return {'ok': True, 'characters': len(text)}

    def take_screenshot(destination: str = 'artifacts/desktop-screenshot.png'):
        target = workspace.resolve(destination)
        req = approval.request(f'Capture desktop screenshot -> {target}',
                               'Desktop screenshots may contain sensitive information.', 'SENSITIVE_READ')
        if not req.get('allowed'):
            return {'ok': False, 'approval_required': True, **req}
        return {'ok': True, 'path': _screenshot_impl(target)}

    def open_url(url: str):
        if not (url.startswith('https://') or url.startswith('http://')):
            return {'ok': False, 'error': 'Only http/https URLs are allowed.'}
        req = approval.request(f'Open URL in default browser: {url}',
                               'This opens an external page on the desktop.', 'DESKTOP_WRITE')
        if not req.get('allowed'):
            return {'ok': False, 'approval_required': True, **req}
        return {'ok': bool(webbrowser.open(url)), 'url': url}

    return [
        Tool('clipboard_read', 'Read the current system clipboard. Always requires explicit approval because clipboard data may be sensitive.',
             {'type':'object','properties':{}}, clipboard_read),
        Tool('clipboard_write', 'Replace the system clipboard contents. Requires approval.',
             {'type':'object','properties':{'text':{'type':'string'}},'required':['text']}, clipboard_write),
        Tool('take_desktop_screenshot', 'Capture the full desktop into the approved workspace. Always requires approval.',
             {'type':'object','properties':{'destination':{'type':'string','default':'artifacts/desktop-screenshot.png'}}}, take_screenshot),
        Tool('open_url_desktop', 'Open an http/https URL in the default desktop browser. Requires approval.',
             {'type':'object','properties':{'url':{'type':'string'}},'required':['url']}, open_url),
    ]
