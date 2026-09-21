from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path("src/living_assistant/webui")


def test_ui06_uses_real_chartjs_component_not_hand_drawn_svg():
    app = (ROOT / "src/main.js").read_text(encoding="utf-8")
    assert "class ResourceChart extends React.Component" in app
    assert "loadChartJs()" in app
    assert "new Chart(this.canvas.current" in app
    assert "h('canvas'" in app
    assert "h('polyline'" not in app
    assert "resource-line" not in app


def test_ui06_chartjs_version_is_exact_and_loader_is_local_first_with_pinned_fallback():
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    loader = (ROOT / "src/chart_loader.js").read_text(encoding="utf-8")
    assert package["dependencies"]["chart.js"] == "4.5.1"
    assert 'CHART_JS_LOCAL_URL = "/vendor/chart.umd.min.js"' in loader
    assert "loadScript(CHART_JS_LOCAL_URL).catch" in loader
    assert "chart.js@${CHART_JS_VERSION}/dist/chart.umd.min.js" in loader
    assert "sha384-jb8JQMbMoBUzgWatfe6COACi2ljcDdZQ2OxczGA3bGNeWe+6DChMTBJemed7ZnvJ" in loader
    assert 'script.referrerPolicy = "no-referrer"' in loader
    assert 'crossOrigin: "anonymous"' in loader


def test_ui06_dashboard_csp_allows_only_pinned_chartjs_cdn_fallback(monkeypatch):
    import living_assistant.api as api

    monkeypatch.delenv("ASSISTANT_API_TOKEN", raising=False)
    response = TestClient(api.app).get("/dashboard")
    assert response.status_code == 200
    csp = response.headers["content-security-policy"]
    assert "script-src 'self' https://cdn.jsdelivr.net" in csp
    assert "'unsafe-inline'" not in csp
    assert "'unsafe-eval'" not in csp


def test_ui06_chart_loader_and_vendor_build_are_packaged_source_assets():
    config = Path("pyproject.toml").read_text(encoding="utf-8")
    assert '"webui/src/*.js"' in config
    assert '"webui/*.cjs"' in config
    assert '"webui/vendor/*.js"' in config
    assert '"webui/vendor/*.md"' in config
    assert (ROOT / "src/chart_loader.js").is_file()
    assert (ROOT / "vendor_chart.cjs").is_file()


def test_ui06_vendor_build_copies_exact_pinned_chart_and_license(tmp_path):
    if shutil.which("node") is None:
        return

    root = tmp_path / "webui"
    package_root = root / "node_modules" / "chart.js"
    (package_root / "dist").mkdir(parents=True)
    (root / "vendor").mkdir(parents=True)
    shutil.copy2(ROOT / "vendor_chart.cjs", root / "vendor_chart.cjs")
    (root / "package.json").write_text(
        json.dumps({"dependencies": {"chart.js": "4.5.1"}}), encoding="utf-8"
    )
    (package_root / "package.json").write_text(
        json.dumps({"version": "4.5.1"}), encoding="utf-8"
    )
    chart_bytes = b"/*! Chart.js v4.5.1 test fixture */"
    license_bytes = b"MIT fixture"
    (package_root / "dist" / "chart.umd.min.js").write_bytes(chart_bytes)
    (package_root / "LICENSE.md").write_bytes(license_bytes)

    completed = subprocess.run(
        ["node", "vendor_chart.cjs"], cwd=root, text=True, capture_output=True, check=False
    )
    assert completed.returncode == 0, completed.stderr
    assert (root / "vendor" / "chart.umd.min.js").read_bytes() == chart_bytes
    assert (root / "vendor" / "chart-LICENSE.md").read_bytes() == license_bytes


def test_ui06_production_build_runs_vendor_step_before_vite():
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    assert package["scripts"]["vendor:chart"] == "node vendor_chart.cjs"
    assert package["scripts"]["build"].startswith("npm run vendor:chart &&")
    assert package["scripts"]["dev"].startswith("npm run vendor:chart &&")
