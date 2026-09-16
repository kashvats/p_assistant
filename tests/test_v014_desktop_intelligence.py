from pathlib import Path
from types import SimpleNamespace
import pytest

from living_assistant.desktop_intelligence import DesktopController
from living_assistant.tools.desktop import build_desktop_tools


class Approval:
    def __init__(self, allowed=True): self.allowed=allowed; self.calls=[]
    def request(self, action, reason, kind='execute'):
        self.calls.append((action,reason,kind)); return {'allowed':self.allowed}

class Workspace:
    def __init__(self, root): self.root=Path(root)
    def resolve(self, value):
        p=(self.root/value).resolve()
        if self.root.resolve() not in p.parents and p != self.root.resolve(): raise ValueError('outside')
        return p

class Provider:
    base_url='http://127.0.0.1:11434'
    def chat(self,*a,**k): return {'message':{'content':'button: Save'}}

class Lease:
    def __enter__(self): return 30
    def __exit__(self,*a): return False
class MM:
    def lease(self,model): return Lease()


def controller(tmp_path, allowed=True, **desktop):
    cfg={'desktop':{'enabled':True,'vision_enabled':False,**desktop}}
    return DesktopController(Workspace(tmp_path),Approval(allowed),cfg,Provider(),MM())


def test_status_is_non_invasive(tmp_path):
    c=controller(tmp_path)
    s=c.status()
    assert 'semantic_backend' in s and 'platform' in s
    assert c.approval.calls == []


def test_accessibility_requires_approval(tmp_path):
    c=controller(tmp_path,allowed=False)
    r=c.accessibility_tree()
    assert r['approval_required'] is True
    assert c.approval.calls[-1][2]=='SENSITIVE_READ'


def test_click_denied_before_pyautogui_import(tmp_path):
    c=controller(tmp_path,allowed=False)
    r=c.click(5,6)
    assert not r['ok'] and r['approval_required']


def test_type_length_guard(tmp_path):
    c=controller(tmp_path)
    r=c.type_text('x'*10001)
    assert not r['ok']
    assert not c.approval.calls


def test_hotkey_empty_rejected(tmp_path):
    c=controller(tmp_path)
    assert not c.hotkey([])['ok']


def test_vision_disabled_by_default(tmp_path):
    c=controller(tmp_path)
    r=c.analyze_screen()
    assert not r['ok'] and 'disabled' in r['error'].lower()


def test_remote_vision_blocked(tmp_path):
    c=controller(tmp_path,vision_enabled=True,vision_model='vision')
    c.provider.base_url='https://example.com'
    r=c.analyze_screen()
    assert not r['ok'] and 'blocked' in r['error'].lower()


def test_remote_vision_can_be_explicitly_allowed_but_still_needs_approval(tmp_path):
    c=controller(tmp_path,allowed=False,vision_enabled=True,vision_model='vision',allow_remote_vision=True)
    c.provider.base_url='https://example.com'
    r=c.analyze_screen()
    assert r['approval_required'] is True


def test_desktop_tools_expose_semantic_first_controls(tmp_path):
    c=controller(tmp_path)
    names={x.name for x in build_desktop_tools(c.workspace,c.approval,c)}
    for name in {'desktop_status','desktop_monitors','desktop_windows','desktop_accessibility_tree','desktop_click','desktop_type_text','desktop_hotkey','desktop_analyze_screen'}:
        assert name in names


def test_monitor_ids_are_validated_without_capture(monkeypatch,tmp_path):
    # Exercise validation with a fake mss module.
    class FakeCtx:
        monitors=[{'left':0,'top':0,'width':100,'height':100},{'left':0,'top':0,'width':100,'height':100}]
        def __enter__(self): return self
        def __exit__(self,*a): pass
    import sys, types
    mm=types.ModuleType('mss'); mm.mss=lambda:FakeCtx(); monkeypatch.setitem(sys.modules,'mss',mm)
    pil=types.ModuleType('PIL'); pil.Image=object(); monkeypatch.setitem(sys.modules,'PIL',pil)
    c=controller(tmp_path)
    assert not c.screenshot('a.png',99)['ok']


def test_tool_order_documents_preference(tmp_path):
    c=controller(tmp_path)
    tools=build_desktop_tools(c.workspace,c.approval,c)
    click=next(x for x in tools if x.name=='desktop_click')
    assert 'Prefer accessibility' in click.description
