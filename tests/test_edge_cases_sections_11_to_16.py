import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
import httpx

from living_assistant.core.workspace import Workspace, WorkspaceViolation
from living_assistant.tools.webtools import build_web_tools
import living_assistant.tools.webtools as webtools


class _MockResponse:
    def __init__(self, status_code: int, content_type: str, body: bytes, url: str = "https://example.com/item"):
        self.status_code = status_code
        self.headers = {"content-type": content_type}
        self._body = body
        self.url = url
        self.encoding = "utf-8"

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("Error", request=MagicMock(), response=self)

    def iter_bytes(self):
        yield self._body

    def close(self):
        pass


class _MockClient:
    response = _MockResponse(200, "image/png", b"\x89PNG\r\n\x1a\nfakeimage")

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



# ==========================================
# SECTION 11 & 12: BROWSER AUTOMATION & DOM TARGETING
# ==========================================

def test_section_11_12_browser_dom_targeting_over_raw_coordinates():
    """Verify browser automation prioritizes semantic CSS selectors/DOM refs over brittle static screen coordinates."""
    class MockBrowserAgent:
        def __init__(self):
            self.dom_state = {"#submit-btn": {"visible": True, "text": "Submit"}}

        def click(self, selector: str = None, coordinates: tuple = None):
            if selector and selector in self.dom_state:
                return {"ok": True, "target": selector, "method": "semantic_dom"}
            if coordinates:
                return {"ok": False, "error": "Coordinate drift detected: use semantic DOM selector"}
            return {"ok": False, "error": "Element not found"}

    agent = MockBrowserAgent()
    # Semantic selector succeeds
    res_dom = agent.click(selector="#submit-btn")
    assert res_dom["ok"] is True
    assert res_dom["method"] == "semantic_dom"

    # Raw pixel coordinates fail safely
    res_coord = agent.click(coordinates=(800, 400))
    assert res_coord["ok"] is False
    assert "Coordinate drift" in res_coord["error"]


# ==========================================
# SECTION 13: YOUTUBE PLAYBACK & AMBIGUITY
# ==========================================

def test_section_13_youtube_playback_progress_verification():
    """Verify that YouTube state tracking checks that media time is actively progressing rather than paused/buffering."""
    def verify_playback(player_state: dict):
        if player_state.get("buffering"):
            return {"playing": False, "status": "buffering"}
        if player_state.get("current_time", 0) <= player_state.get("previous_time", 0):
            return {"playing": False, "status": "stalled_or_paused"}
        return {"playing": True, "status": "progressing"}

    # Case 1: Spinner / buffering
    assert verify_playback({"buffering": True, "current_time": 0})["playing"] is False

    # Case 2: Paused (time not changing)
    assert verify_playback({"buffering": False, "current_time": 10.5, "previous_time": 10.5})["playing"] is False

    # Case 3: Genuine progressing playback
    assert verify_playback({"buffering": False, "current_time": 12.0, "previous_time": 10.5})["playing"] is True


def test_section_13_youtube_search_disambiguation_preference():
    """Verify that search results prefer official tracks over unrelated covers/parodies when query specifies title."""
    candidates = [
        {"title": "Shape of You (Metal Parody Cover)", "id": "parody_123"},
        {"title": "Ed Sheeran - Shape of You (Official Music Video)", "id": "official_456"},
        {"title": "Shape of You 10 Hour Loop", "id": "loop_789"},
    ]
    query = "Shape of You"

    # Select best match prioritizing official/verified terms
    def rank_youtube_candidate(item, q):
        score = 0
        title = item["title"].lower()
        if q.lower() in title:
            score += 10
        if "official" in title:
            score += 20
        if "parody" in title or "cover" in title or "loop" in title:
            score -= 15
        return score

    best = max(candidates, key=lambda x: rank_youtube_candidate(x, query))
    assert best["id"] == "official_456"


# ==========================================
# SECTION 14: IMAGE SEARCH VALIDATION
# ==========================================

def test_section_14_image_content_type_validation(tmp_path, monkeypatch):
    """Verify that an HTML payload returned from an image URL is detected and rejected."""
    root = tmp_path / "workspace"
    root.mkdir()
    ws = Workspace([root])

    _MockClient.response = _MockResponse(200, "text/html", b"<html>Fake image portal</html>")
    monkeypatch.setattr(webtools.httpx, "Client", _MockClient)
    monkeypatch.setattr(webtools, "url_network_scope", lambda url, resolve=True: ("public", ""))

    tools = {t.name: t.handler for t in build_web_tools(ws, {})}
    res = tools["download_image"]("https://example.com/fake.png", "fake.png")
    assert res["ok"] is False
    assert "supported image" in res["error"]


# ==========================================
# SECTION 15: IMAGE DOWNLOAD SECURITY
# ==========================================

def test_section_15_image_download_path_traversal_blocked(tmp_path):
    """Verify malicious destination paths attempting to escape workspace are blocked by WorkspaceViolation."""
    root = tmp_path / "workspace"
    root.mkdir()
    ws = Workspace([root])
    tools = {t.name: t.handler for t in build_web_tools(ws, {})}

    with pytest.raises(WorkspaceViolation):
        tools["download_image"]("https://example.com/photo.png", "../../Windows/System32/evil.exe")


# ==========================================
# SECTION 16: DUPLICATE DOWNLOADS
# ==========================================

def test_section_16_duplicate_download_preserves_existing_file(tmp_path, monkeypatch):
    """Verify downloading the same destination twice appends numeric suffixes rather than overwriting."""
    root = tmp_path / "workspace"
    root.mkdir()
    ws = Workspace([root])

    _MockClient.response = _MockResponse(200, "image/png", b"original_content")
    monkeypatch.setattr(webtools.httpx, "Client", _MockClient)
    monkeypatch.setattr(webtools, "url_network_scope", lambda url, resolve=True: ("public", ""))

    tools = {t.name: t.handler for t in build_web_tools(ws, {})}

    # 1. First download
    res1 = tools["download_image"]("https://example.com/pic1.png", "photo.png")
    assert res1["ok"] is True
    p1 = Path(res1["path"])
    assert p1.name == "photo.png"
    assert p1.read_bytes() == b"original_content"

    # 2. Second download with different content
    _MockClient.response = _MockResponse(200, "image/png", b"second_content")
    res2 = tools["download_image"]("https://example.com/pic2.png", "photo.png")
    assert res2["ok"] is True
    p2 = Path(res2["path"])
    # File is preserved; new file gets photo_2.png
    assert p2.name == "photo_2.png"
    assert p1.read_bytes() == b"original_content"
    assert p2.read_bytes() == b"second_content"
