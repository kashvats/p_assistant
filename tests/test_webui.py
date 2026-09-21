from __future__ import annotations

from importlib import resources
from pathlib import Path

from fastapi.testclient import TestClient


def _dashboard_source() -> str:
    return (
        resources.files("living_assistant")
        .joinpath("webui/index.html")
        .read_text(encoding="utf-8")
    )


def test_dashboard_webui_has_readable_markdown_and_highlighting_pipeline():
    page = _dashboard_source()
    assert "function renderMarkdown(target, markdown)" in page
    assert "function highlightCode(codeElement, source, language = '')" in page
    assert "function appendInlineMarkdown(parent, text)" in page
    assert "renderMarkdown(output, assistantText);" in page
    assert "out.textContent+=ev.text" not in page
    assert "target.replaceChildren();" in page
    # Markdown must be rendered through DOM/text nodes, not by injecting model HTML.
    assert "target.innerHTML = markdown" not in page
    assert "codeElement.innerHTML" not in page


def test_dashboard_webui_surfaces_request_errors_to_the_user():
    page = _dashboard_source()
    assert "function renderError(error, context = 'Request failed')" in page
    assert "toast(`${context}: ${message}`.slice(0, 500));" in page
    assert "Network request failed:" in page
    assert "Ignoring malformed activity stream event" in page


def test_dashboard_route_serves_hardened_local_ui(monkeypatch):
    import living_assistant.api as api

    monkeypatch.delenv("ASSISTANT_API_TOKEN", raising=False)
    response = TestClient(api.app).get("/dashboard")
    assert response.status_code == 200
    assert "function renderMarkdown" in response.text
    assert "function highlightCode" in response.text
    assert response.headers["x-frame-options"] == "DENY"
    csp = response.headers["content-security-policy"]
    assert "default-src 'self'" in csp
    assert "connect-src 'self'" in csp
    assert "https://" not in response.text.split("<script>", 1)[0]


def test_webui_is_declared_as_package_data():
    config = Path("pyproject.toml").read_text(encoding="utf-8")
    assert '"webui/*.html"' in config
