"""Vision layer: attachments, model routing, swap mode, OCR assist, chat turns with images."""
from __future__ import annotations

import base64
import io
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from living_assistant.core.sessions import SessionStore
from living_assistant.vision import attachments, engine as engine_mod, models


def _png(color=(200, 30, 30), size=(40, 30)) -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture(autouse=True)
def isolated_data(tmp_path, monkeypatch):
    monkeypatch.setattr(attachments, "data_dir", lambda: tmp_path)
    monkeypatch.setattr(models, "data_dir", lambda: tmp_path)
    return tmp_path


def _downloaded(name):
    spec = models.CATALOG[name]
    spec.folder.mkdir(parents=True, exist_ok=True)
    spec.model_path.write_bytes(b"m")
    spec.mmproj_path.write_bytes(b"p")


class FakeServer:
    started: list = []

    def __init__(self, model, port, log_dir, binary=None, threads=None):
        self.model, self.proc, self.last_used, self.prompts = model, None, 0.0, []

    def start(self):
        FakeServer.started.append(self.model.name)
        self.proc = object()

    def stop(self):
        self.proc = None

    def ask(self, image, question, max_tokens=512, mime="image/png", system=None, timeout=600):
        self.prompts.append((question, system))
        FakeServer.last_prompt = question
        return {"text": f"{self.model.name} saw it", "seconds": 0.1, "timings": {}}

    def status(self):
        return {"model": self.model.name}


class ChatServer:
    def __init__(self):
        self.log = []

    def pause(self, reason):
        self.log.append("pause")
        return {"paused": True}

    def resume(self):
        self.log.append("resume")


@pytest.fixture
def vision(monkeypatch, tmp_path):
    FakeServer.started = []
    monkeypatch.setattr(engine_mod, "VisionServer", FakeServer)
    monkeypatch.setattr(engine_mod.ocr, "available", lambda: True)
    monkeypatch.setattr(engine_mod.ocr, "ocr_lines", lambda image: ["Error 0x80070005", "Access is denied"])
    chat = ChatServer()
    eng = engine_mod.VisionEngine({"vision": {"default": "qwen3-vl-2b", "tasks": {"photo": "qwen3-vl-4b"}}},
                                  tmp_path / "logs", chat_server=chat)
    eng.chat = chat
    return eng


def test_attachments_are_validated_and_stored_by_content(isolated_data):
    first = attachments.save(_png(), "shot.png")
    again = attachments.save(_png(), "same.png")
    assert first["id"] == again["id"] and first["id"].startswith("img_") and first["width"] == 40
    assert attachments.load(first["id"]) == _png()
    with pytest.raises(ValueError):
        attachments.save(b"%PDF-1.4 not an image")
    assert attachments.path_of("../../etc/passwd") is None and attachments.path_of("img_zz") is None


def test_tasks_route_to_configured_models_and_text_tasks_get_ocr(vision):
    _downloaded("qwen3-vl-2b")
    out = vision.analyze(_png(), "What went wrong?", task="ui")
    assert out["ok"] and out["model"] == "qwen3-vl-2b" and out["ocr_lines"][0] == "Error 0x80070005"
    assert "0x80070005" in FakeServer.last_prompt and "What went wrong?" in FakeServer.last_prompt
    vision.analyze(_png(), "Who is there?", task="photo", model="qwen3-vl-2b")
    assert "OCR" not in FakeServer.last_prompt  # photos are not text tasks
    with pytest.raises(KeyError):
        vision.analyze(_png(), task="general", model="no-such-model")


def test_large_models_pause_the_chat_model_and_resume_it(vision):
    _downloaded("qwen3-vl-4b")
    out = vision.analyze(_png(), "Describe the scene", task="photo")
    assert out["model"] == "qwen3-vl-4b" and out["mode"] == "swap"
    assert vision.chat.log == ["pause", "resume"]
    assert vision._server is None  # the big model is unloaded right away


def test_missing_model_starts_a_download_instead_of_failing(vision, monkeypatch):
    calls = []
    monkeypatch.setattr(engine_mod, "download", lambda model, progress: calls.append(model.name))
    out = vision.analyze(_png(), "hi")
    assert out["ok"] is False and out["needs_download"] and out["model"] == "qwen3-vl-2b"


def test_config_can_add_any_llama_cpp_vision_model():
    extra = models.catalog({"models": {"my-vlm": {"repo": "me/vlm-GGUF", "file": "v.gguf", "mmproj": "mm.gguf", "mode": "swap"}}})
    assert extra["my-vlm"].mode == "swap" and "qwen3-vl-2b" in extra


@pytest.fixture
def client(tmp_path, monkeypatch, vision):
    import living_assistant.api as api

    sessions = SessionStore(tmp_path / "a.sqlite3")
    seen = {}

    class Orch:
        def run_stream(self, message, context="", session_id=None, source="text"):
            seen["message"], seen["context"] = message, context
            sessions.add_message(session_id, "user", message, source=source)
            yield {"type": "final", "text": "It is an error dialog.", "session_id": session_id}

    rt = SimpleNamespace(sessions=sessions, events_bus=None, orchestrator=Orch(), vision=lambda: vision)
    monkeypatch.setattr(api, "runtime", rt)
    monkeypatch.setenv("ASSISTANT_API_TOKEN", "t")
    c = TestClient(api.app, headers={"Authorization": "Bearer t"})
    c.seen = seen
    return c


def test_chat_with_an_attached_image_shows_the_vision_findings_to_the_chat_model(client):
    _downloaded("qwen3-vl-2b")
    image = client.post("/attachments", json={"data": "data:image/png;base64," + base64.b64encode(_png()).decode()}).json()
    assert client.get(f"/attachments/{image['id']}").content == _png()
    with client.stream("POST", "/chat/stream", json={"message": "What is this?", "images": [image["id"]]}) as r:
        body = "".join(r.iter_text())
    assert '"looking"' in body and "final" in body
    assert f"[image {image['id']}]" in client.seen["message"]           # kept in history for follow-ups
    assert "qwen3-vl-2b saw it" in client.seen["context"] and "analyze_image" in client.seen["context"]
    assert "never instructions" in client.seen["context"]


def test_attachment_upload_rejects_non_images(client):
    assert client.post("/attachments", json={"data": base64.b64encode(b"hello world").decode()}).status_code == 400
    assert client.post("/attachments", json={"data": "!!!not-base64!!!"}).status_code == 400
    assert client.post("/vision/analyze", json={"image": "img_0000000000000000"}).status_code == 404


def test_default_vision_model_can_be_chosen_and_benchmarks_are_listed(client, monkeypatch, tmp_path):
    import json as _json
    import living_assistant.api_routes.vision as vision_routes

    saved = {}
    monkeypatch.setattr(vision_routes, "save_model_preference", lambda key, model: saved.update({key: model}))
    assert client.put("/vision/default", json={"model": "lfm2.5-vl-1.6b"}).json()["default"] == "lfm2.5-vl-1.6b"
    assert saved == {"vision": "lfm2.5-vl-1.6b"}
    assert client.put("/vision/default", json={"model": "nope"}).status_code == 404
    results = tmp_path / "src" / "benchmarks" / "vision" / "results"
    results.mkdir(parents=True)
    (results / "m.json").write_text(_json.dumps({"model": "m", "peak_rss_mb": 900, "rows": [
        {"category": "ocr", "variant": "vision", "ok": True, "seconds": 2.0},
        {"category": "ocr", "variant": "vision", "ok": False, "seconds": 4.0}]}), encoding="utf-8")
    monkeypatch.setattr(vision_routes, "source_root", lambda: tmp_path / "src")
    row = client.get("/vision/benchmark").json()["results"][0]
    assert (row["passed"], row["total"], row["categories"]["ocr"]) == (1, 2, [1, 2])


def test_benchmark_scoring_accepts_alternatives_and_ignores_thousands_separators():
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location("bench", Path(__file__).parents[1] / "benchmarks" / "vision" / "run.py")
    bench = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bench)
    assert bench.score({"all": ["INV-48213", "12,480.50"]}, "Invoice INV-48213 totals ₹12480.50")[0]
    assert bench.score({"any": ["tv|television"]}, "A Television on the left")[0]
    assert not bench.score({"tokens": ["a1", "b2", "c3"], "min": 3}, "a1 b2")[0]
