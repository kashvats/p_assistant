from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from living_assistant.api_routes import models as model_routes
from living_assistant.api_routes.schemas import ModelDeleteRequest, ModelRequest
from living_assistant.core.model_provider import ModelError, ModelManager, OllamaProvider


class _Resources:
    def __init__(self):
        self.hardware = SimpleNamespace(
            gpu_name="Test GPU",
            gpu_vram_gb=4.0,
            gpu_vram_free_gb=3.25,
            unified_memory=False,
        )
        self.model_policy = SimpleNamespace(
            max_resident_models=1,
            max_concurrent_generations=1,
            max_parallel_per_model=1,
            resident_keep_alive_seconds=45,
            admission_timeout_seconds=5,
        )

    def snapshot(self):
        return {"gpu_free_vram_gb": 3.0}


@pytest.fixture
def provider(monkeypatch):
    p = OllamaProvider()
    inventory = {
        "qwen:latest": {
            "name": "qwen:latest",
            "size": 1_000,
            "digest": "abc",
            "modified_at": "2026-09-21T00:00:00Z",
            "details": {"parameter_size": "7B"},
        },
        "tiny:latest": {
            "name": "tiny:latest",
            "size": 200,
            "digest": "def",
            "details": {},
        },
    }
    monkeypatch.setattr(p, "model_inventory", lambda: inventory)
    monkeypatch.setattr(
        p,
        "running_models",
        lambda: [{"name": "tiny:latest", "size": 200, "size_vram": 80}],
    )
    return p


def test_local_catalog_reports_disk_and_labeled_vram(provider):
    manager = ModelManager(provider, resource_manager=_Resources())
    result = manager.local_model_catalog()

    assert result["ok"] is True
    assert result["count"] == 2
    assert result["total_disk_bytes"] == 1_200
    assert result["gpu"]["total_vram_gb"] == 4.0
    assert result["gpu"]["free_vram_gb"] == 3.0

    by_name = {row["name"]: row for row in result["models"]}
    assert by_name["qwen:latest"]["vram_kind"] == "estimated_from_disk"
    assert by_name["qwen:latest"]["estimated_vram_bytes"] == 1_150
    assert by_name["qwen:latest"]["vram_bytes"] == 1_150
    assert by_name["tiny:latest"]["loaded"] is True
    assert by_name["tiny:latest"]["vram_kind"] == "actual_loaded"
    assert by_name["tiny:latest"]["actual_vram_bytes"] == 80
    assert by_name["tiny:latest"]["vram_bytes"] == 80


def test_saved_ollama_alias_resolves_to_installed_tag(provider):
    manager = ModelManager(provider, resource_manager=_Resources())
    provider.model_inventory = lambda: {
        "qwen2.5:7b-instruct-q4_K_M": {"name": "qwen2.5:7b-instruct-q4_K_M"}
    }

    assert manager.resolve_local_model("qwen2.5:7b") == "qwen2.5:7b-instruct-q4_K_M"
    assert manager.resolve_local_model("missing:1b") == "missing:1b"


def test_local_model_pull_uses_existing_ollama_provider(provider, monkeypatch):
    pulled = []
    monkeypatch.setattr(provider, "pull", lambda model: pulled.append(model) or {"status": "success"})
    manager = ModelManager(provider, resource_manager=_Resources())

    result = manager.pull_local_model("qwen2.5:7b")

    assert result["ok"] is True
    assert pulled == ["qwen2.5:7b"]


@pytest.mark.parametrize("bad", ["", "https://evil.invalid/model", "bad model", "../model", "model\nname"])
def test_local_model_management_rejects_invalid_names(provider, bad):
    manager = ModelManager(provider, resource_manager=_Resources())
    with pytest.raises(ModelError):
        manager.pull_local_model(bad)


def test_local_model_delete_requires_confirmation_and_refuses_in_use(provider, monkeypatch):
    deleted = []
    unloaded = []
    monkeypatch.setattr(provider, "delete", lambda model: deleted.append(model) or {"status": "success"})
    monkeypatch.setattr(provider, "unload", lambda model: unloaded.append(model))
    manager = ModelManager(provider, resource_manager=_Resources())

    assert manager.delete_local_model("qwen:latest")["ok"] is False
    assert deleted == []

    manager._resident["qwen:latest"] = {"model": "qwen:latest"}
    manager._in_use["qwen:latest"] = 1
    blocked = manager.delete_local_model("qwen:latest", confirmed=True)
    assert blocked["ok"] is False
    assert "in use" in blocked["error"].lower()
    assert deleted == []
    assert unloaded == []

    manager._in_use.clear()
    result = manager.delete_local_model("qwen:latest", confirmed=True)
    assert result["ok"] is True
    assert unloaded == ["qwen:latest"]
    assert deleted == ["qwen:latest"]


def test_model_router_exposes_local_pull_and_delete(monkeypatch):
    calls = []

    class MM:
        def local_model_catalog(self):
            calls.append(("catalog",))
            return {"ok": True, "models": []}

        def pull_local_model(self, model):
            calls.append(("pull", model))
            return {"ok": True, "model": model}

        def delete_local_model(self, model, *, confirmed=False):
            calls.append(("delete", model, confirmed))
            return {"ok": confirmed, "model": model}

    monkeypatch.setattr(model_routes, "authorize", lambda _authorization: None)
    monkeypatch.setattr(model_routes, "runtime", lambda: SimpleNamespace(model_manager=MM()))

    assert model_routes.model_local_catalog()["ok"] is True
    assert model_routes.model_pull(ModelRequest(model="qwen:latest"))["ok"] is True
    result = model_routes.model_delete(ModelDeleteRequest(model="qwen:latest", confirm=True))
    assert result["ok"] is True
    assert calls == [
        ("catalog",),
        ("pull", "qwen:latest"),
        ("delete", "qwen:latest", True),
    ]

    route_pairs = {(route.path, tuple(sorted(route.methods or []))) for route in model_routes.router.routes}
    assert ("/models/local", ("GET",)) in route_pairs
    assert ("/models/pull", ("POST",)) in route_pairs
    assert ("/models/delete", ("POST",)) in route_pairs


def test_webui_contains_local_model_manager_without_unsafe_model_html():
    app = Path("src/living_assistant/webui/src/main.js").read_text(encoding="utf-8")
    assert "['models', 'Models']" in app
    assert "this.api('/models/local')" in app
    assert "this.api('/models/pull'" in app
    assert "this.api('/models/delete'" in app
    assert "confirm:true" in app or "confirm: true" in app
    assert "estimated requirement" in app
    # Model names are React text children; model-controlled HTML is never injected.
    assert "dangerouslySetInnerHTML" not in app
    assert ".innerHTML" not in app


def test_ollama_provider_management_calls_expected_http_endpoints(monkeypatch):
    calls = []

    class Response:
        def __init__(self, payload=None):
            self.status_code = 200
            self.text = ""
            self.content = b"{}"
            self._payload = payload or {"status": "success"}

        def json(self):
            return self._payload

    class Client:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def post(self, path, *, json, timeout=None):
            calls.append(("POST", path, json, timeout))
            return Response()

        def request(self, method, path, *, json):
            calls.append((method, path, json, None))
            return Response()

    p = OllamaProvider(timeout_seconds=5)
    monkeypatch.setattr(p, "_client", lambda: Client())

    assert p.pull("qwen2.5:7b")["status"] == "success"
    assert p.delete("qwen2.5:7b")["status"] == "success"
    assert calls[0] == (
        "POST",
        "/api/pull",
        {"model": "qwen2.5:7b", "stream": False},
        3600.0,
    )
    assert calls[1] == (
        "DELETE",
        "/api/delete",
        {"model": "qwen2.5:7b"},
        None,
    )
