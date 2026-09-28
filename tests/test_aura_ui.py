from __future__ import annotations

from pathlib import Path
from fastapi.testclient import TestClient

import living_assistant.api as api

_WEBUI = Path("src/living_assistant/webui")


def test_aura_endpoint_serves_html_with_security_headers():
    client = TestClient(api.app)
    response = client.get("/aura")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert response.headers.get("x-frame-options") == "DENY"
    assert response.headers.get("x-content-type-options") == "nosniff"

    csp = response.headers.get("content-security-policy", "")
    assert "default-src 'self'" in csp
    assert "script-src 'self'" in csp
    assert "cdn.tailwindcss.com" not in csp


def test_aura_html_has_no_external_cdn_dependencies():
    content = (_WEBUI / "aura.html").read_text(encoding="utf-8")
    assert "cdn.tailwindcss.com" not in content
    assert "images.unsplash.com" not in content
    assert "Assistant OS" in content
    assert "AURA" in content
    assert "VISION PANEL" in content
    assert "Privacy Approval Required" in content
    assert "TOOL EXECUTION LOGS" in content
    assert "VOICE INPUT" in content


def test_aura_assets_exist_and_are_served():
    assert (_WEBUI / "src/aura.css").is_file()
    assert (_WEBUI / "src/aura.js").is_file()

    client = TestClient(api.app)
    css_res = client.get("/dashboard-assets/src/aura.css")
    assert css_res.status_code == 200
    assert "text/css" in css_res.headers["content-type"]

    js_res = client.get("/dashboard-assets/src/aura.js")
    assert js_res.status_code == 200
    assert ("javascript" in js_res.headers["content-type"] or "text/plain" in js_res.headers["content-type"])
