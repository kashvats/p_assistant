from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from living_assistant.overlay import FloatingOverlay


class _FakeLabel:
    def __init__(self):
        self.calls = []

    def configure(self, **kwargs):
        self.calls.append(kwargs)


def test_overlay_query_error_uses_customtkinter_text_color():
    overlay = FloatingOverlay.__new__(FloatingOverlay)
    overlay.lbl_dot = _FakeLabel()
    messages = []
    overlay._append_message = lambda *args: messages.append(args)

    overlay._on_query_error("offline")

    assert overlay.lbl_dot.calls == [{"text_color": "#ff5555"}]
    assert messages[-1][0] == "System"
    assert "offline" in messages[-1][1]


def test_overlay_source_has_no_commented_out_import_stubs():
    from pathlib import Path

    source = Path("src/living_assistant/overlay.py").read_text(encoding="utf-8")
    assert "# import " not in source
    assert "# from " not in source
    assert "customtkinter>=5.2,<6" in Path("pyproject.toml").read_text(encoding="utf-8")


def test_overlay_screen_analysis_route_uses_existing_desktop_controller(monkeypatch):
    import living_assistant.api as api

    calls = []
    controller = SimpleNamespace(
        analyze_screen=lambda prompt, monitor_id: calls.append((prompt, monitor_id)) or {
            "ok": True, "analysis": "screen result", "monitor_id": monitor_id
        }
    )
    monkeypatch.setattr(api, "get_runtime", lambda: SimpleNamespace(desktop_controller=controller))
    monkeypatch.setattr(api, "get_api_token", lambda: "test-token")

    response = TestClient(api.app).post(
        "/desktop/analyze-screen",
        headers={"Authorization": "Bearer test-token"},
        json={"prompt": "Inspect the current screen", "monitor_id": 1},
    )

    assert response.status_code == 200
    assert response.json()["analysis"] == "screen result"
    assert calls == [("Inspect the current screen", 1)]


def test_overlay_screen_analysis_route_requires_auth(monkeypatch):
    import living_assistant.api as api

    monkeypatch.setattr(api, "get_api_token", lambda: "test-token")
    response = TestClient(api.app).post(
        "/desktop/analyze-screen", json={"prompt": "x", "monitor_id": 0}
    )
    assert response.status_code == 401


def test_overlay_registers_ctrl_space_global_hotkey_without_extra_dependency(monkeypatch):
    import living_assistant.desktop.overlay as module

    calls = []

    class User32:
        def RegisterHotKey(self, hwnd, hotkey_id, modifiers, key):
            calls.append((hwnd, hotkey_id, modifiers, key))
            return 1

    class Root:
        def __init__(self):
            self.scheduled = []
        def after(self, delay, callback):
            self.scheduled.append((delay, callback))

    overlay = FloatingOverlay.__new__(FloatingOverlay)
    overlay.root = Root()
    overlay._hotkey_registered = False
    monkeypatch.setattr(module.ctypes, 'windll', SimpleNamespace(user32=User32()), raising=False)

    assert overlay._register_global_hotkey() is True
    assert calls == [(None, overlay.HOTKEY_ID, overlay.MOD_CONTROL, overlay.VK_SPACE)]
    assert overlay.root.scheduled[0][0] == 75


def test_overlay_command_palette_reuses_existing_composer_and_centers_window():
    calls = []

    class Root:
        def winfo_screenwidth(self): return 1200
        def winfo_screenheight(self): return 800
        def geometry(self, value): calls.append(('geometry', value))
        def deiconify(self): calls.append(('deiconify',))
        def lift(self): calls.append(('lift',))
        def focus_force(self): calls.append(('focus_force',))

    class Input:
        def focus_set(self): calls.append(('input_focus',))

    overlay = FloatingOverlay.__new__(FloatingOverlay)
    overlay.root = Root()
    overlay.input_text = Input()
    overlay.is_expanded = True
    overlay.hud_w = 420
    overlay.hud_h = 580
    overlay.pos_x = 0
    overlay.pos_y = 0

    overlay._show_command_palette()

    assert overlay.pos_x == 390
    assert overlay.pos_y == 80
    assert ('input_focus',) in calls
    assert calls[0] == ('geometry', '420x580+390+80')


def test_overlay_ui10_has_scrollable_conversation_history_sidebar():
    from pathlib import Path
    source = Path('src/living_assistant/desktop/overlay.py').read_text(encoding='utf-8')
    assert 'CTkScrollableFrame' in source
    assert 'self.history_sidebar' in source
    assert 'self._history_items' in source
    assert 'if len(self._history_items) > 100' in source
    assert 'before=self.conversation_frame' in source


def test_overlay_ui11_expand_collapse_uses_smooth_geometry_animation():
    from pathlib import Path
    source = Path('src/living_assistant/desktop/overlay.py').read_text(encoding='utf-8')
    assert 'def _animate_overlay_geometry(' in source
    assert 'steps = 9' in source
    assert 'eased = 1.0 - (1.0 - progress) ** 3' in source
    assert 'self.root.after(18' in source
    assert 'on_complete=(None if expanded else self.body_frame.pack_forget)' in source


def test_overlay_ui12_has_model_voice_and_focus_settings_controls():
    from pathlib import Path
    source = Path('src/living_assistant/desktop/overlay.py').read_text(encoding='utf-8')
    assert 'self.settings_card' in source
    assert 'self.settings_model' in source
    assert 'self.settings_voice' in source
    assert 'self.settings_focus_minutes' in source
    assert '"/models/select"' in source
    assert '"/voice/enabled"' in source
    assert '"/personal/focus"' in source


def test_overlay_ui12_runtime_settings_endpoints_reuse_existing_runtime(monkeypatch):
    import living_assistant.api as api

    class MM:
        def status(self, refresh=False):
            return {'refresh': refresh, 'active_model': 'old:7b'}
        def preload(self, model):
            return {'ok': True, 'model': model, 'runtime': {'active_model': model}}

    class Voice:
        def __init__(self): self.slept = False
        def enabled(self): return True
        def status(self): return {'enabled': bool(rt.config['voice']['enabled'])}
        def sleep(self): self.slept = True

    events = []
    rt = SimpleNamespace(
        model_manager=MM(),
        orchestrator=SimpleNamespace(model='old:7b'),
        config={'profiles': {'balanced': {'models': {'orchestrator': 'old:7b'}}}, 'voice': {'enabled': True}},
        profile='balanced',
        events_bus=SimpleNamespace(publish=lambda kind, **data: events.append((kind, data))),
    )
    rt.voice = Voice()
    monkeypatch.setattr(api, 'get_runtime', lambda: rt)
    monkeypatch.setattr(api, 'get_api_token', lambda: 'test-token')
    client = TestClient(api.app, headers={'Authorization': 'Bearer test-token'})

    status = client.get('/models/status').json()
    assert status['selected_model'] == 'old:7b'

    selected = client.post('/models/select', json={'model': 'qwen2.5:7b'})
    assert selected.status_code == 200
    assert rt.orchestrator.model == 'qwen2.5:7b'
    assert rt.config['profiles']['balanced']['models']['orchestrator'] == 'qwen2.5:7b'

    voice = client.post('/voice/enabled', json={'enabled': False})
    assert voice.status_code == 200
    assert rt.config['voice']['enabled'] is False
    assert rt.voice.slept is True


def test_overlay_ui13_has_drag_resize_grip_and_handlers():
    from pathlib import Path
    source = Path('src/living_assistant/desktop/overlay.py').read_text(encoding='utf-8')
    assert 'self.resize_grip' in source
    assert 'def _start_resize(' in source
    assert 'def _on_resize(' in source
    assert '"<B1-Motion>", self._on_resize' in source


def test_overlay_ui13_resize_updates_persistent_expanded_geometry_with_bounds():
    geometry_calls = []

    class Root:
        def winfo_screenwidth(self): return 1000
        def winfo_screenheight(self): return 800
        def geometry(self, value): geometry_calls.append(value)

    overlay = FloatingOverlay.__new__(FloatingOverlay)
    overlay.root = Root()
    overlay.is_expanded = True
    overlay.hud_w = 620
    overlay.hud_h = 580
    overlay.pos_x = 100
    overlay.pos_y = 50
    overlay._resize_start_x_root = 500
    overlay._resize_start_y_root = 400
    overlay._resize_start_w = 620
    overlay._resize_start_h = 580

    overlay._on_resize(SimpleNamespace(x_root=700, y_root=550))
    assert overlay.hud_w == 820
    assert overlay.hud_h == 730
    assert geometry_calls[-1] == '820x730+100+50'

    overlay._on_resize(SimpleNamespace(x_root=-500, y_root=-500))
    assert overlay.hud_w == 480
    assert overlay.hud_h == 420
    assert geometry_calls[-1] == '480x420+100+50'


def test_overlay_ui14_draws_pending_approval_badge_only_when_collapsed():
    class Canvas:
        def __init__(self): self.calls = []
        def delete(self, *args): self.calls.append(('delete', args))
        def create_polygon(self, *args, **kwargs): self.calls.append(('polygon', kwargs))
        def create_oval(self, *args, **kwargs): self.calls.append(('oval', kwargs))
        def create_line(self, *args, **kwargs): self.calls.append(('line', kwargs))
        def create_text(self, *args, **kwargs): self.calls.append(('text', kwargs))

    overlay = FloatingOverlay.__new__(FloatingOverlay)
    overlay.eye_canvas = Canvas()
    overlay.BG_CARD = '#141c2a'
    overlay.BORDER = '#223048'
    overlay.ACCENT = '#7c9cff'
    overlay.is_scanning = False
    overlay.scan_pos = 70
    overlay.pending_approval_count = 3
    overlay.active_inquiry_id = None
    overlay.is_expanded = False

    overlay._draw_eye()
    badge = [c for c in overlay.eye_canvas.calls if c[0] == 'text' and c[1].get('tags') == ('approval_badge',)]
    assert len(badge) == 1
    assert badge[0][1]['text'] == '3'

    overlay.eye_canvas.calls.clear()
    overlay.is_expanded = True
    overlay._draw_eye()
    assert not [c for c in overlay.eye_canvas.calls if c[0] in {'oval', 'text', 'line', 'polygon'} and isinstance(c[1], dict) and c[1].get('tags') == ('approval_badge',)]


def test_overlay_ui14_badge_count_is_bounded_and_redrawn():
    overlay = FloatingOverlay.__new__(FloatingOverlay)
    redraws = []
    overlay.pending_approval_count = 0
    overlay._draw_eye = lambda: redraws.append(True)

    overlay._set_pending_approval_count(-2)
    assert overlay.pending_approval_count == 0
    overlay._set_pending_approval_count(140)
    assert overlay.pending_approval_count == 140
    assert redraws == [True, True]


def test_overlay_ui14_polls_existing_authenticated_approvals_endpoint(monkeypatch):
    import living_assistant.desktop.overlay as module

    requests = []
    scheduled = []

    class Root:
        def after(self, delay, callback, *args):
            scheduled.append((delay, callback, args))
            if delay == 0:
                callback(*args)

    overlay = FloatingOverlay.__new__(FloatingOverlay)
    overlay.root = Root()
    overlay.pending_approval_count = 0
    overlay._draw_eye = lambda: None
    overlay._settings_request = lambda path, timeout=10.0: requests.append((path, timeout)) or [{"id":"1"}, {"id":"2"}]

    class ImmediateThread:
        def __init__(self, target, daemon=False): self.target = target
        def start(self): self.target()

    monkeypatch.setattr(module.threading, 'Thread', ImmediateThread)
    overlay._poll_approval_badge()

    assert requests == [('/approvals', 3.0)]
    assert overlay.pending_approval_count == 2
    assert any(delay == 3000 and cb == overlay._poll_approval_badge for delay, cb, _ in scheduled)
