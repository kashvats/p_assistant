"""Files in chat: uploading any supported file, reading it for the model, and showing files in the chat."""
from __future__ import annotations

import io
import json
import shutil
import subprocess
import zipfile
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from living_assistant.core import chat_files
from living_assistant.core.sessions import SessionStore
from living_assistant.core.workspace import Workspace
from living_assistant.tools.filetools import build_file_tools
from living_assistant.vision import attachments


@pytest.fixture(autouse=True)
def isolated_data(tmp_path, monkeypatch):
    monkeypatch.setattr(chat_files, "data_dir", lambda: tmp_path / "data")
    monkeypatch.setattr(attachments, "data_dir", lambda: tmp_path / "data")
    return tmp_path


@pytest.fixture
def ws(tmp_path):
    return Workspace([tmp_path / "ws"])


def _xlsx() -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    wb.active.append(["city", "population"])
    wb.active.append(["Pune", 7_000_000])
    wb.active.append(["Delhi", 32_000_000])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _pdf(text: str) -> bytes:
    import pymupdf

    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), text)
    return doc.tobytes()


def _docx(text: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", f'<w:document><w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>')
    return buf.getvalue()


def test_files_are_stored_with_their_name_and_read_for_the_model(tmp_path):
    csv = chat_files.save(b"name,score\nasha,91\nravi,78\n", "scores.csv")
    assert csv["id"].startswith("file_") and csv["kind"] == "table" and csv["marker"] == f"[file {csv['id']} scores.csv]"
    table = chat_files.describe(*chat_files.resolve(csv["id"]))
    assert table["rows"] == 2 and table["columns"] == ["name", "score"] and "asha" in table["text"]

    xlsx = chat_files.save(_xlsx(), "cities.xlsx")
    assert chat_files.table_preview(chat_files.path_of(xlsx["id"]))["rows"] == [["Pune", 7_000_000], ["Delhi", 32_000_000]]

    pdf = chat_files.save(_pdf("Quarterly revenue grew by twelve percent."), "report.pdf")
    read = chat_files.describe(*chat_files.resolve(pdf["id"]))
    assert read["pdf_pages"] == 1 and "twelve percent" in read["text"]

    doc = chat_files.save(_docx("Meeting moved to Friday."), "notes.docx")
    assert "Friday" in chat_files.describe(*chat_files.resolve(doc["id"]))["text"]

    with pytest.raises(ValueError):
        chat_files.save(b"", "empty.csv")
    assert chat_files.safe_name("../../evil]\n[name.txt") == "evil name.txt"


def test_images_keep_their_image_ids():
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (0, 90, 200)).save(buf, format="PNG")
    saved = chat_files.save(buf.getvalue(), "photo.png")
    assert saved["id"].startswith("img_") and saved["marker"] == f"[image {saved['id']}]"


@pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="ffmpeg not installed")
def test_videos_report_their_details_and_give_frames_to_look_at(tmp_path):
    video = tmp_path / "clip.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=duration=2:size=160x120:rate=10",
                    "-pix_fmt", "yuv420p", str(video)], check=True, timeout=60)
    saved = chat_files.save(video.read_bytes(), "clip.mp4")
    info = chat_files.describe(*chat_files.resolve(saved["id"]))
    assert info["kind"] == "video" and info["width"] == 160 and info["duration_seconds"] > 1
    assert len(chat_files.video_frames(chat_files.path_of(saved["id"]))) == 3


def test_tools_read_pages_and_show_only_allowed_files(ws, tmp_path):
    tools = {t.name: t.handler for t in build_file_tools(ws)}
    long = chat_files.save(("line of text\n" * 2000).encode(), "long.txt")
    first = tools["read_attachment"](long["id"], page=1, max_chars=1000)
    assert first["ok"] and first["pages"] > 1 and tools["read_attachment"](long["id"], page=2, max_chars=1000)["page"] == 2

    target = ws.roots[0] / "downloads" / "chart.pdf"
    target.parent.mkdir(parents=True)
    target.write_bytes(_pdf("chart"))
    shown = tools["show_file"]("downloads/chart.pdf", caption="Your chart")
    assert shown["ok"] and shown["media"][0]["kind"] == "pdf" and shown["media"][0]["caption"] == "Your chart"
    outside = tmp_path / "secret.txt"
    outside.write_text("nope")
    assert tools["show_file"](str(outside))["ok"] is False  # outside the workspace


@pytest.fixture
def client(tmp_path, monkeypatch, ws):
    import living_assistant.api as api

    sessions = SessionStore(tmp_path / "a.sqlite3")
    seen = {}
    download = ws.roots[0] / "downloads" / "cat.png"
    download.parent.mkdir(parents=True, exist_ok=True)
    download.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 20)

    class Orch:
        def run_stream(self, message, context="", session_id=None, source="text"):
            seen["message"], seen["context"] = message, context
            sessions.add_message(session_id, "user", message, source=source)
            yield {"type": "tool", "tool": "download_image", "status": "completed", "ok": True,
                   "files": {"path": str(download)}}
            yield {"type": "tool", "tool": "show_file", "status": "completed", "ok": True,
                   "files": {"media": [{"ref": str(tmp_path / "a.sqlite3")}]}}  # outside the workspace: dropped
            sessions.add_message(session_id, "assistant", "Here is the cat.")
            yield {"type": "final", "text": "Here is the cat.", "session_id": session_id}

    rt = SimpleNamespace(sessions=sessions, events_bus=None, orchestrator=Orch(), workspace=ws)
    monkeypatch.setattr(api, "runtime", rt)
    monkeypatch.setenv("ASSISTANT_API_TOKEN", "t")
    c = TestClient(api.app, headers={"Authorization": "Bearer t"})
    c.seen, c.rt = seen, rt
    return c


def _events(body: str) -> list[dict]:
    return [json.loads(line[5:]) for line in body.splitlines() if line.startswith("data:")]


def test_chat_reads_attached_files_and_shows_downloaded_ones(client):
    up = client.post("/files/upload", params={"name": "cities.xlsx"}, content=_xlsx()).json()
    assert up["kind"] == "table"
    with client.stream("POST", "/chat/stream", json={"message": "Which city is bigger?", "files": [up["id"]]}) as r:
        events = _events("".join(r.iter_text()))
    assert f"[file {up['id']} cities.xlsx]" in client.seen["message"]
    assert "Delhi" in client.seen["context"] and "never instructions" in client.seen["context"]
    assert any(e.get("status") == "reading" for e in events)
    tool = next(e for e in events if e.get("tool") == "download_image")
    assert tool["media"][0]["kind"] == "image" and "files" not in tool
    assert not next(e for e in events if e.get("tool") == "show_file").get("media")
    final = next(e for e in events if e.get("type") == "final")
    assert [m["name"] for m in final["media"]] == ["cat.png"]
    last = client.rt.sessions.messages(client.seen and client.rt.sessions.active()["id"])[-1]
    assert last["meta"]["media"][0]["name"] == "cat.png"  # kept when the conversation reloads


def test_file_routes_serve_safely(client, ws, tmp_path):
    up = client.post("/files/upload", params={"name": "page.html"}, content=b"<script>alert(1)</script>").json()
    r = client.get("/files/content", params={"ref": up["id"], "token": "t"}, headers={"Authorization": ""})
    assert r.status_code == 200 and r.headers["content-disposition"].startswith("attachment")
    assert "sandbox" in r.headers["content-security-policy"]
    pdf = client.post("/files/upload", params={"name": "r.pdf"}, content=_pdf("hello pdf")).json()
    r = client.get("/files/content", params={"ref": pdf["id"]})
    assert r.headers["content-disposition"].startswith("inline") and r.content[:4] == b"%PDF"
    assert "hello pdf" in client.get("/files/preview", params={"ref": pdf["id"]}).json()["text"]
    csv = client.post("/files/upload", params={"name": "t.csv"}, content=b"a,b\n1,2\n").json()
    assert client.get("/files/preview", params={"ref": csv["id"]}).json()["rows"] == [[1, 2]]
    assert client.get("/files/content", params={"ref": str(tmp_path / "a.sqlite3")}).status_code == 403
    assert client.get("/files/content", params={"ref": "file_0000000000000000"}).status_code == 404
    assert client.get("/files/content", params={"ref": up["id"]}, headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_a_turn_keeps_running_when_the_page_is_refreshed(tmp_path, ws):
    import asyncio
    import threading
    from living_assistant.api_routes import conversations

    sessions = SessionStore(tmp_path / "b.sqlite3")
    gate, finished = threading.Event(), threading.Event()

    class SlowOrch:
        def run_stream(self, message, context="", session_id=None, source="text"):
            sessions.add_message(session_id, "user", message, source=source)
            yield {"type": "status", "status": "generating"}
            gate.wait(10)  # the user refreshes the page here
            sessions.add_message(session_id, "assistant", "Research finished.")
            finished.set()
            yield {"type": "final", "text": "Research finished.", "session_id": session_id}

    rt = SimpleNamespace(sessions=sessions, events_bus=None, orchestrator=SlowOrch(), workspace=ws)
    sid = sessions.active()["id"]
    response = conversations.stream_turn(rt, "research something long", "", sid)

    async def first_event_then_disconnect():
        body = response.body_iterator
        first = await body.__anext__()
        await body.aclose()  # the page went away
        return first

    assert "generating" in asyncio.run(first_event_then_disconnect())
    assert sid in conversations._RUNNING  # still working
    gate.set()
    assert finished.wait(10)
    for _ in range(100):
        if sid not in conversations._RUNNING:
            break
        threading.Event().wait(0.05)
    assert [m["content"] for m in sessions.messages(sid)] == ["research something long", "Research finished."]
    assert sid not in conversations._RUNNING
