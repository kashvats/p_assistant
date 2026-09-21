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
        raw = sct.grab(sct.monitors[0])
        image = Image.frombytes('RGB', raw.size, raw.rgb)
        path.parent.mkdir(parents=True, exist_ok=True)
        image.save(path)
    return str(path)


def build_desktop_tools(workspace: Workspace, approval: ApprovalManager, controller=None) -> list[Tool]:
    def clipboard_read():
        req = approval.request('Read current clipboard contents','Clipboard may contain passwords, tokens or private text.', 'SENSITIVE_READ')
        if not req.get('allowed'): return {'ok': False, 'approval_required': True, **req}
        text = _clipboard_read_impl(); return {'ok': True, 'text': text[:20000], 'truncated': len(text) > 20000}

    def clipboard_write(text: str):
        req = approval.request(f'Write {len(text)} characters to clipboard','This replaces the current clipboard contents.', 'DESKTOP_WRITE')
        if not req.get('allowed'): return {'ok': False, 'approval_required': True, **req}
        _clipboard_write_impl(text); return {'ok': True, 'characters': len(text)}

    def take_screenshot(destination: str = 'artifacts/desktop-screenshot.png', monitor_id: int = 0):
        if controller: return controller.screenshot(destination, monitor_id)
        target = workspace.resolve(destination)
        req = approval.request(f'Capture desktop screenshot -> {target}','Desktop screenshots may contain sensitive information.', 'SENSITIVE_READ')
        if not req.get('allowed'): return {'ok': False, 'approval_required': True, **req}
        return {'ok': True, 'path': _screenshot_impl(target)}

    def open_url(url: str):
        if not (url.startswith('https://') or url.startswith('http://')): return {'ok': False, 'error': 'Only http/https URLs are allowed.'}
        req = approval.request(f'Open URL in default browser: {url}','This opens an external page on the desktop.', 'DESKTOP_WRITE')
        if not req.get('allowed'): return {'ok': False, 'approval_required': True, **req}
        return {'ok': bool(webbrowser.open(url)), 'url': url}

    tools=[
        Tool('clipboard_read','Read the current system clipboard. Always requires explicit approval because clipboard data may be sensitive.',{'type':'object','properties':{}},clipboard_read),
        Tool('clipboard_write','Replace the system clipboard contents. Requires approval.',{'type':'object','properties':{'text':{'type':'string'}},'required':['text']},clipboard_write),
        Tool('take_desktop_screenshot','Capture the desktop or one monitor into the approved workspace. Always requires approval.',{'type':'object','properties':{'destination':{'type':'string','default':'artifacts/desktop-screenshot.png'},'monitor_id':{'type':'integer','default':0}}},take_screenshot),
        Tool('open_url_desktop','Open an http/https URL in the default desktop browser. Requires approval.',{'type':'object','properties':{'url':{'type':'string'}},'required':['url']},open_url),
    ]
    if controller:
        tools += [
            Tool('desktop_status','Report desktop-control/accessibility capability without taking control.',{'type':'object','properties':{}},controller.status),
            Tool('desktop_monitors','List monitor geometry for multi-monitor reasoning.',{'type':'object','properties':{}},controller.monitors),
            Tool('desktop_windows','List visible native application windows. Window titles are omitted by default; requesting titles requires sensitive-read approval.',{'type':'object','properties':{'include_titles':{'type':'boolean','default':False}}},controller.windows),
            Tool('desktop_accessibility_tree','Read the active application accessibility tree. Requires sensitive-read approval.',{'type':'object','properties':{'max_nodes':{'type':'integer','default':250}}},controller.accessibility_tree),
            Tool('desktop_click','Click an approved screen coordinate. Prefer accessibility/semantic targets first.',{'type':'object','properties':{'x':{'type':'integer'},'y':{'type':'integer'},'button':{'type':'string','default':'left'}},'required':['x','y']},controller.click),
            Tool('desktop_type_text','Type text into the active application. Requires approval.',{'type':'object','properties':{'text':{'type':'string'},'interval':{'type':'number','default':0.01}},'required':['text']},controller.type_text),
            Tool('desktop_hotkey','Send a keyboard shortcut. Requires approval.',{'type':'object','properties':{'keys':{'type':'array','items':{'type':'string'}}},'required':['keys']},controller.hotkey),
            Tool('desktop_move_mouse','Move the pointer to a coordinate. Requires approval.',{'type':'object','properties':{'x':{'type':'integer'},'y':{'type':'integer'},'duration':{'type':'number','default':0.2}},'required':['x','y']},controller.move_mouse),
            Tool('desktop_analyze_screen','Use the configured sleeping local vision model when semantic UI data is insufficient. Requires sensitive-read approval.',{'type':'object','properties':{'prompt':{'type':'string','default':'Describe the visible UI and actionable controls.'},'monitor_id':{'type':'integer','default':0}}},controller.analyze_screen),
        ]
    return tools
