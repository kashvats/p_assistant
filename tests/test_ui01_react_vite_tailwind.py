from __future__ import annotations

import json
from pathlib import Path


ROOT = Path("src/living_assistant/webui")


def test_ui01_has_react_vite_tailwind_project_structure():
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    assert "vite --host 127.0.0.1" in package["scripts"]["dev"]
    assert package["scripts"]["build"].endswith("vite build")
    assert "react" in package["dependencies"]
    assert "react-dom" in package["dependencies"]
    assert "vite" in package["devDependencies"]
    assert "tailwindcss" in package["devDependencies"]
    assert (ROOT / "vite.config.js").is_file()
    assert '@import "tailwindcss";' in (ROOT / "src/styles.css").read_text(encoding="utf-8")


def test_ui01_react_app_has_multiple_pages_and_hash_navigation():
    app = (ROOT / "src/main.js").read_text(encoding="utf-8")
    for page in ["overview", "models", "chat", "approvals", "organize", "security", "activity"]:
        assert f"['{page}'," in app
    assert "location.hash = `/${page}`" in app
    assert "ReactDOM.render" in app
    assert "document.querySelectorAll('.nav button')" not in app


def test_ui01_production_assets_are_local_only():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    assert "https://" not in html
    assert "http://" not in html
    assert "/vendor/react.production.min.js" in html
    assert "/src/main.js" in html
    assert (ROOT / "dist/app.css").stat().st_size > 1000


def test_ui01_vendored_react_versions_match_declared_runtime():
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    react = (ROOT / "vendor/react.production.min.js").read_text(encoding="utf-8")
    react_dom = (ROOT / "vendor/react-dom.production.min.js").read_text(encoding="utf-8")
    assert f'version:"{package["dependencies"]["react"]}"' in react
    assert f'version:"{package["dependencies"]["react-dom"]}"' in react_dom
