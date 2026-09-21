from __future__ import annotations

import base64
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path("src/living_assistant/webui")
PLOTLY_VERSION = "3.3.1"
PLOTLY_SIZE = 4_838_938
PLOTLY_SHA384 = "SsOMajmLeeY81sOzGCn88NjTdDwa+nz3Lb1ZNouSdXAz5TBsvD+Pwgf1Iqtxns6c"


def test_ui06_uses_real_plotly_component_not_hand_drawn_svg_or_canvas():
    app = (ROOT / "src/main.js").read_text(encoding="utf-8")
    assert "class ResourceChart extends React.Component" in app
    assert "loadPlotly()" in app
    assert "Plotly.react(this.plot.current" in app
    assert "h('polyline'" not in app
    assert "resource-line" not in app
    assert "h('canvas'" not in app
    assert "trace('CPU'" in app
    assert "trace('RAM'" in app
    assert "trace('VRAM'" in app


def test_ui06_plotly_version_is_exact_and_loader_is_same_origin_only():
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    loader = (ROOT / "src/chart_loader.js").read_text(encoding="utf-8")
    assert package["dependencies"]["plotly.js-dist-min"] == PLOTLY_VERSION
    assert 'PLOTLY_VENDOR_PATH = "../vendor/plotly.min.js"' in loader
    assert "new URL(PLOTLY_VENDOR_PATH, import.meta.url).href" in loader
    assert "loadScript(PLOTLY_LOCAL_URL)" in loader
    assert "cdn.jsdelivr.net" not in loader
    assert "unpkg.com" not in loader
    assert 'script.referrerPolicy = "no-referrer"' in loader
    assert "Plotly.version" in loader


def test_ui06_dashboard_csp_is_local_only(monkeypatch):
    import living_assistant.api as api

    monkeypatch.delenv("ASSISTANT_API_TOKEN", raising=False)
    response = TestClient(api.app).get("/dashboard")
    assert response.status_code == 200
    csp = response.headers["content-security-policy"]
    assert "script-src 'self'" in csp
    assert "cdn.jsdelivr.net" not in csp
    assert "unpkg.com" not in csp
    assert "'unsafe-inline'" not in csp
    assert "'unsafe-eval'" not in csp


def test_ui06_resource_samples_handle_cpu_ram_vram_and_partial_metrics():
    if shutil.which("node") is None:
        return
    script = r"""
import {makeResourceSample, resourceSeries, resourceSampleLabel} from './src/resource_chart_data.js';
const gpu = makeResourceSample(
  {cpu_percent: 27.4, ram_percent: 61.2, gpu_free_vram_gb: 8},
  {gpu_vram_gb: 16},
);
const noGpu = makeResourceSample({cpu_percent: 'bad', ram_percent: null}, {});
const clamped = makeResourceSample(
  {cpu_percent: 125, ram_percent: -5, gpu_free_vram_gb: 32},
  {gpu_vram_gb: 16},
);
console.log(JSON.stringify({
  gpu,
  noGpu,
  clamped,
  gpuSeries: resourceSeries([gpu, noGpu]),
  noGpuSeries: resourceSeries([noGpu]),
  gpuLabel: resourceSampleLabel(gpu),
  noGpuLabel: resourceSampleLabel(noGpu),
}));
"""
    completed = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    data = json.loads(completed.stdout)
    assert data["gpu"]["cpu_percent"] == 27.4
    assert data["gpu"]["ram_percent"] == 61.2
    assert data["gpu"]["vram_percent"] == 50
    assert data["gpuSeries"]["hasVram"] is True
    assert data["noGpu"]["cpu_percent"] is None
    assert data["noGpu"]["ram_percent"] is None
    assert data["noGpu"]["vram_percent"] is None
    assert data["noGpuSeries"]["hasVram"] is False
    assert data["clamped"]["cpu_percent"] == 100
    assert data["clamped"]["ram_percent"] == 0
    assert data["clamped"]["vram_percent"] == 0
    assert data["gpuLabel"] == "CPU 27% · RAM 61% · VRAM 50%"
    assert data["noGpuLabel"] == "CPU -- · RAM --"


def test_ui06_chart_render_errors_are_contained():
    app = (ROOT / "src/main.js").read_text(encoding="utf-8")
    assert "try { this.plotly.purge(this.plot.current); } catch (_) {}" in app
    assert "catch (error)" in app
    assert "this.setState({chartError:" in app
    assert "Chart unavailable." in app
    assert "dangerouslySetInnerHTML" not in app


def test_ui06_chart_loader_and_vendor_build_are_packaged_source_assets():
    config = Path("pyproject.toml").read_text(encoding="utf-8")
    assert '"webui/src/*.js"' in config
    assert '"webui/*.cjs"' in config
    assert '"webui/vendor/*.js"' in config
    assert '"webui/vendor/*.md"' in config
    assert (ROOT / "src/chart_loader.js").is_file()
    assert (ROOT / "src/resource_chart_data.js").is_file()
    assert (ROOT / "vendor_chart.cjs").is_file()


def test_ui06_vendor_build_copies_exact_pinned_plotly_and_license(tmp_path):
    if shutil.which("node") is None:
        return

    root = tmp_path / "webui"
    package_root = root / "node_modules" / "plotly.js-dist-min"
    package_root.mkdir(parents=True)
    (root / "vendor").mkdir(parents=True)
    shutil.copy2(ROOT / "vendor_chart.cjs", root / "vendor_chart.cjs")
    (root / "package.json").write_text(
        json.dumps({"dependencies": {"plotly.js-dist-min": PLOTLY_VERSION}}), encoding="utf-8"
    )
    (package_root / "package.json").write_text(
        json.dumps({"version": PLOTLY_VERSION}), encoding="utf-8"
    )
    shutil.copy2(ROOT / "vendor/plotly.min.js", package_root / "plotly.min.js")
    shutil.copy2(ROOT / "vendor/plotly-LICENSE.md", package_root / "LICENSE")

    completed = subprocess.run(
        ["node", "vendor_chart.cjs"], cwd=root, text=True, capture_output=True, check=False
    )
    assert completed.returncode == 0, completed.stderr
    assert (root / "vendor" / "plotly.min.js").read_bytes() == (ROOT / "vendor/plotly.min.js").read_bytes()
    assert (root / "vendor" / "plotly-LICENSE.md").read_bytes() == (ROOT / "vendor/plotly-LICENSE.md").read_bytes()
    assert (root / "public/vendor/plotly.min.js").is_file()


def test_ui06_committed_plotly_runtime_is_verified():
    chart = ROOT / "vendor/plotly.min.js"
    assert chart.is_file(), "The genuine Plotly.js 3.3.1 runtime must be committed for offline packaging"
    payload = chart.read_bytes()
    digest = base64.b64encode(hashlib.sha384(payload).digest()).decode("ascii")
    assert len(payload) == PLOTLY_SIZE
    assert digest == PLOTLY_SHA384
    assert b"plotly.js v3.3.1" in payload[:500]
    assert (ROOT / "vendor/plotly-LICENSE.md").is_file()


def test_ui06_packaged_dashboard_serves_plotly(monkeypatch):
    import living_assistant.api as api

    monkeypatch.delenv("ASSISTANT_API_TOKEN", raising=False)
    response = TestClient(api.app).get("/dashboard-assets/vendor/plotly.min.js")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(("text/javascript", "application/javascript"))
    assert b"plotly.js v3.3.1" in response.content[:500]


def test_ui06_production_build_runs_vendor_and_css_before_vite():
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    assert package["scripts"]["vendor:chart"] == "node vendor_chart.cjs"
    assert package["scripts"]["build"] == "npm run vendor:chart && npm run build:css && vite build"
    assert package["scripts"]["dev"].startswith("npm run vendor:chart &&")
