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
