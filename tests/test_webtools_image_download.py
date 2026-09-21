from __future__ import annotations

from pathlib import Path

import living_assistant.tools.webtools as webtools
from living_assistant.tools.webtools import build_web_tools
from living_assistant.workspace import Workspace


class _Response:
    status_code = 200
    url = "https://example.com/picture"
    encoding = "utf-8"

    def __init__(self, content_type: str, body: bytes):
        self.headers = {"content-type": content_type}
        self._body = body

    def raise_for_status(self):
        return None

    def iter_bytes(self):
        yield self._body

    def close(self):
        return None


class _Client:
    response = _Response("image/png", b"\x89PNG\r\n\x1a\nimage")

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def build_request(self, method, url):
        return (method, url)

    def send(self, request, stream=False):
        return self.response


def _tools(tmp_path, monkeypatch, content_type="image/png", body=b"data"):
    root = tmp_path / "workspace"
    root.mkdir()
    _Client.response = _Response(content_type, body)
    monkeypatch.setattr(webtools.httpx, "Client", _Client)
    # Keep production SSRF/DNS enforcement intact; this fixture isolates download
    # behavior from external DNS so the tests are deterministic/offline.
    monkeypatch.setattr(webtools, "url_network_scope", lambda url, resolve=True: ("public", ""))
    return {t.name: t.handler for t in build_web_tools(Workspace([root]), {})}, root


def test_download_image_infers_extension(tmp_path, monkeypatch):
    tools, root = _tools(tmp_path, monkeypatch, "image/png", b"png")
    result = tools["download_image"]("https://example.com/picture", "photo")
    assert result["ok"] is True and result["quarantined"] is False
    assert result["path"].endswith("photo.png")
    assert Path(result["path"]).read_bytes() == b"png"


def test_download_image_rejects_non_image_response(tmp_path, monkeypatch):
    tools, _ = _tools(tmp_path, monkeypatch, "text/html", b"<html>not an image</html>")
    result = tools["download_image"]("https://example.com/picture", "photo.png")
    assert result["ok"] is False
    assert "supported image" in result["error"]


def test_download_image_rejects_mismatched_extension(tmp_path, monkeypatch):
    tools, _ = _tools(tmp_path, monkeypatch, "image/jpeg", b"jpg")
    result = tools["download_image"]("https://example.com/picture", "photo.png")
    assert result["ok"] is False
    assert "does not match" in result["error"]


def test_download_image_quarantines_svg(tmp_path, monkeypatch):
    tools, _ = _tools(tmp_path, monkeypatch, "image/svg+xml", b"<svg></svg>")
    result = tools["download_image"]("https://example.com/picture.svg", "picture.svg")
    assert result["ok"] is True and result["quarantined"] is True
    assert "active_svg_image" in result["item"]["risk_reasons"]


def test_generic_download_url_remains_available(tmp_path, monkeypatch):
    tools, _ = _tools(tmp_path, monkeypatch, "application/octet-stream", b"blob")
    result = tools["download_url"]("https://example.com/file", "file.bin")
    assert result["ok"] is True
    assert result["content_type"] == "application/octet-stream"
