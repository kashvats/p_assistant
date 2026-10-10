from __future__ import annotations

import json
import threading
from types import SimpleNamespace

from fastapi.testclient import TestClient


def test_kill_switch_stops_everything_and_can_shut_down(tmp_path, monkeypatch):
    import living_assistant.api as api
    import living_assistant.api_routes.system as system_routes
    from living_assistant.api_routes import conversations
    from living_assistant.core.runtime import Runtime

    rt = SimpleNamespace(events_bus=None, goals=None, shutdown=lambda: {"shutdown_clean": True})
    rt.halt = lambda reason: Runtime.halt(rt, reason)
    monkeypatch.setattr(api, "runtime", rt)
    monkeypatch.setenv("ASSISTANT_API_TOKEN", "t")
    client = TestClient(api.app, headers={"Authorization": "Bearer t"})
    turn = threading.Event()
    conversations._RUNNING["s1"] = turn
    exits = []
    monkeypatch.setattr(system_routes.threading, "Timer", lambda delay, fn: SimpleNamespace(start=lambda: exits.append((delay, fn))))
    marker = tmp_path / "killed.json"
    monkeypatch.setattr(system_routes, "kill_marker", lambda: marker)
    try:
        r = client.post("/system/kill", json={"mode": "stop"}).json()
        assert r["ok"] and r["chat_turns_stopped"] >= 1 and turn.is_set() and r["shutdown_clean"]
        assert exits == []  # stop keeps the server up
        assert client.post("/system/kill", json={"mode": "shutdown"}).json()["mode"] == "shutdown"
        assert exits[0][0] == 1.5 and exits[0][1] is system_routes._exit_now
        assert json.loads(marker.read_text())["reason"] == "kill switch"  # the desktop app quits on this
        assert system_routes.KillRequest().mode == "shutdown"  # the kill switch shuts down by default
        assert client.post("/system/kill", json={"mode": "explode"}).status_code == 422
        assert client.post("/system/kill", json={"mode": "stop"}, headers={"Authorization": "Bearer wrong"}).status_code == 401
    finally:
        conversations._RUNNING.pop("s1", None)
