from __future__ import annotations

from living_assistant.core.config import load_config
from living_assistant.core.workspace import Workspace
from living_assistant.tools.webtools import build_web_tools


def _tool_map(tools):
    return {tool.name: tool.handler for tool in tools}


class _Response:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = ""

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class _Browser:
    def __init__(self):
        self.web_calls = 0
        self.image_calls = 0

    def search_web(self, query, limit):
        self.web_calls += 1
        return {
            "ok": True,
            "provider": "browser",
            "results": [{"title": "Browser", "link": "https://b.example", "snippet": query}],
        }

    def search_images(self, query, limit):
        self.image_calls += 1
        return {
            "ok": True,
            "provider": "browser",
            "results": [{"title": "Browser image", "imageUrl": "https://b.example/a.png", "link": "https://b.example"}],
        }


def test_explicit_searxng_web_search_uses_json_api_without_api_key(tmp_path, monkeypatch):
    import living_assistant.tools.webtools as webtools

    calls = {}

    class Client:
        def __init__(self, **kwargs):
            calls["client"] = kwargs

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url, params=None):
            calls["url"] = url
            calls["params"] = params
            return _Response(
                {
                    "results": [
                        {
                            "title": "Local result",
                            "url": "https://example.com/result",
                            "content": "Private metasearch result",
                        }
                    ]
                }
            )

    monkeypatch.setattr(webtools.httpx, "Client", Client)
    monkeypatch.delenv("SERPER_API_KEY", raising=False)
    root = tmp_path / "workspace"
    root.mkdir()
    tools = _tool_map(
        build_web_tools(
            Workspace([root]),
            {
                "web_search": {
                    "provider": "searxng",
                    "searxng_url": "http://127.0.0.1:8080/searxng",
                    "max_calls_per_day": 0,
                }
            },
        )
    )

    result = tools["web_search"]("living assistant", 5)
    assert result["ok"] is True
    assert result["provider"] == "searxng"
    assert result["results"][0]["link"] == "https://example.com/result"
    assert calls["url"] == "http://127.0.0.1:8080/searxng/search"
    assert calls["params"] == {
        "q": "living assistant",
        "format": "json",
        "categories": "general",
    }
    assert calls["client"]["trust_env"] is False


def test_searxng_image_search_maps_image_fields(tmp_path, monkeypatch):
    import living_assistant.tools.webtools as webtools

    class Client:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url, params=None):
            assert params["categories"] == "images"
            return _Response(
                {
                    "results": [
                        {
                            "title": "Image result",
                            "img_src": "https://img.example/photo.webp",
                            "url": "https://example.com/page",
                            "engine": "local-engine",
                        }
                    ]
                }
            )

    monkeypatch.setattr(webtools.httpx, "Client", Client)
    monkeypatch.delenv("SERPER_API_KEY", raising=False)
    root = tmp_path / "workspace"
    root.mkdir()
    tools = _tool_map(
        build_web_tools(
            Workspace([root]),
            {
                "web_search": {
                    "provider": "searxng",
                    "searxng_url": "http://localhost:8888",
                    "max_calls_per_day": 0,
                }
            },
        )
    )

    result = tools["image_search"]("shop camera", 3)
    assert result["ok"] is True
    assert result["provider"] == "searxng"
    assert len(result["results"]) == 1
    item = result["results"][0]
    assert "Image result" in item["title"]
    assert item["imageUrl"] == "https://img.example/photo.webp"
    assert item["link"] == "https://example.com/page"
    assert "local-engine" in item["source"]
    # SearXNG text is still external observation data and must stay wrapped/sanitized.
    assert "UNTRUSTED_EXTERNAL_OBSERVATION" in item["title"]


def test_auto_prefers_configured_searxng_before_browser(tmp_path, monkeypatch):
    import living_assistant.tools.webtools as webtools

    browser = _Browser()

    class Client:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url, params=None):
            return _Response({"results": [{"title": "S", "url": "https://s.example", "content": "ok"}]})

    monkeypatch.setattr(webtools.httpx, "Client", Client)
    monkeypatch.delenv("SERPER_API_KEY", raising=False)
    root = tmp_path / "workspace"
    root.mkdir()
    tools = _tool_map(
        build_web_tools(
            Workspace([root]),
            {
                "web_search": {
                    "provider": "auto",
                    "searxng_url": "http://localhost:8080",
                    "max_calls_per_day": 0,
                }
            },
            browser=browser,
        )
    )

    result = tools["web_search"]("query")
    assert result["provider"] == "searxng"
    assert browser.web_calls == 0


def test_auto_falls_back_to_browser_when_searxng_is_unavailable(tmp_path, monkeypatch):
    import living_assistant.tools.webtools as webtools

    browser = _Browser()

    class Client:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url, params=None):
            raise RuntimeError("service offline secret=should-not-escape")

    monkeypatch.setattr(webtools.httpx, "Client", Client)
    monkeypatch.delenv("SERPER_API_KEY", raising=False)
    root = tmp_path / "workspace"
    root.mkdir()
    tools = _tool_map(
        build_web_tools(
            Workspace([root]),
            {
                "web_search": {
                    "provider": "auto",
                    "searxng_url": "http://localhost:8080",
                    "max_calls_per_day": 0,
                }
            },
            browser=browser,
        )
    )

    result = tools["web_search"]("query")
    assert result["ok"] is True
    assert result["provider"] == "browser"
    assert browser.web_calls == 1


def test_explicit_searxng_rejects_missing_or_credential_bearing_url(tmp_path, monkeypatch):
    monkeypatch.delenv("SEARXNG_BASE_URL", raising=False)
    monkeypatch.delenv("SERPER_API_KEY", raising=False)
    root = tmp_path / "workspace"
    root.mkdir()

    missing = _tool_map(
        build_web_tools(
            Workspace([root]),
            {"web_search": {"provider": "searxng", "max_calls_per_day": 0}},
        )
    )["web_search"]("x")
    assert missing["ok"] is False
    assert "SEARXNG_BASE_URL" in missing["error"]

    unsafe = _tool_map(
        build_web_tools(
            Workspace([root]),
            {
                "web_search": {
                    "provider": "searxng",
                    "searxng_url": "http://user:password@localhost:8080",
                    "max_calls_per_day": 0,
                }
            },
        )
    )["web_search"]("x")
    assert unsafe["ok"] is False
    assert "embedded credentials" in unsafe["error"]
    assert "password" not in unsafe["error"]


def test_default_config_supports_searxng_environment_override(monkeypatch):
    monkeypatch.setenv("SEARXNG_BASE_URL", "http://127.0.0.1:8080")
    cfg = load_config()
    assert cfg["web_search"]["searxng_url"] == "http://127.0.0.1:8080"
    assert cfg["web_search"]["provider"] == "auto"
