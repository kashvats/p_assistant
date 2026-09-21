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


def _app_source() -> str:
    return (
        resources.files("living_assistant")
        .joinpath("webui/src/main.js")
        .read_text(encoding="utf-8")
    )


def test_dashboard_webui_has_safe_markdown_and_prism_pipeline():
    page = _dashboard_source()
    app = _app_source()
    assert "/vendor/prism.js" in page
    assert "function Markdown({text})" in app
    assert "function CodeBlock({language, source})" in app
    assert "Prism.tokenize" in app
    assert "dangerouslySetInnerHTML" not in app
    assert ".innerHTML" not in app


def test_dashboard_webui_surfaces_request_errors_to_the_user():
    app = _app_source()
    assert "Network request failed:" in app
    assert "this.notify(`Chat failed:" in app
    assert "this.notify(`Unable to load models:" in app


def test_dashboard_route_serves_hardened_local_ui(monkeypatch):
    import living_assistant.api as api

    monkeypatch.delenv("ASSISTANT_API_TOKEN", raising=False)
    client = TestClient(api.app)
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert 'id="root"' in response.text
    assert "/dashboard-assets/src/main.js" in response.text
    assert response.headers["x-frame-options"] == "DENY"
    csp = response.headers["content-security-policy"]
    assert "default-src 'self'" in csp
    assert "connect-src 'self'" in csp
    assert "script-src 'self'" in csp
    assert "'unsafe-inline'" not in csp

    js = client.get("/dashboard-assets/src/main.js")
    assert js.status_code == 200
    assert "ReactDOM.render" in js.text
    assert js.headers["x-content-type-options"] == "nosniff"

    css = client.get("/dashboard-assets/dist/app.css")
    assert css.status_code == 200
    assert "tailwindcss" in css.text

    assert client.get("/dashboard-assets/../default_config.yaml").status_code == 404
    assert client.get("/dashboard-assets/src/../../default_config.yaml").status_code == 404


def test_webui_is_declared_as_package_data():
    config = Path("pyproject.toml").read_text(encoding="utf-8")
    assert '"webui/*.html"' in config
    assert '"webui/src/*.js"' in config
    assert '"webui/dist/*.css"' in config
    assert '"webui/vendor/*.js"' in config
