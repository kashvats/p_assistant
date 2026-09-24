from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from typing import Any

from living_assistant.security.security_utils import redact_secrets

logger = logging.getLogger(__name__)

# Complete list of 41 diagram types supported by diagram-design
DIAGRAM_TYPES: list[dict[str, str]] = [
    {"type": "architecture", "name": "Architecture", "description": "Components + connections in a system", "reference": "type-architecture.md"},
    {"type": "it-state", "name": "IT current-state", "description": "Legacy IT landscape by phase or department; shows the before state", "reference": "type-it-state.md"},
    {"type": "flowchart", "name": "Flowchart", "description": "Decision logic with branches", "reference": "type-flowchart.md"},
    {"type": "sequence", "name": "Sequence", "description": "Time-ordered messages between actors", "reference": "type-sequence.md"},
    {"type": "state", "name": "State machine", "description": "States + transitions + guards", "reference": "type-state.md"},
    {"type": "er", "name": "ER / data model", "description": "Entities + fields + relationships", "reference": "type-er.md"},
    {"type": "timeline", "name": "Timeline", "description": "Events positioned in time", "reference": "type-timeline.md"},
    {"type": "swimlane", "name": "Swimlane", "description": "Cross-functional process with handoffs", "reference": "type-swimlane.md"},
    {"type": "quadrant", "name": "Quadrant", "description": "Two-axis positioning / prioritization", "reference": "type-quadrant.md"},
    {"type": "radar", "name": "Radar / Spider", "description": "Multiple entities scored across 3–5 quantitative criteria", "reference": "type-radar.md"},
    {"type": "polar", "name": "Polar chart", "description": "One quantitative series across cyclic categories; angle=category, radius=magnitude", "reference": "type-polar.md"},
    {"type": "loop", "name": "Loop", "description": "Reinforcing cycle; the last step feeds the first and a hub accumulates state", "reference": "type-loop.md"},
    {"type": "nested", "name": "Nested", "description": "Hierarchy through containment / scope", "reference": "type-nested.md"},
    {"type": "tree", "name": "Tree", "description": "Parent → children relationships", "reference": "type-tree.md"},
    {"type": "org-chart", "name": "Org chart", "description": "Human/agent/team ownership, reporting, routing, escalation", "reference": "type-org-chart.md"},
    {"type": "layers", "name": "Layer stack", "description": "Stacked abstraction levels", "reference": "type-layers.md"},
    {"type": "venn", "name": "Venn", "description": "Overlap between sets", "reference": "type-venn.md"},
    {"type": "pyramid", "name": "Pyramid / funnel", "description": "Ranked hierarchy or conversion drop-off", "reference": "type-pyramid.md"},
    {"type": "bar", "name": "Bar chart", "description": "Quantitative comparison across categories", "reference": "type-bar.md"},
    {"type": "waterfall", "name": "Waterfall", "description": "A start total bridged to an end total by signed contributions", "reference": "type-waterfall.md"},
    {"type": "treemap", "name": "Treemap", "description": "Part-of-whole where the relative sizes are the story", "reference": "type-treemap.md"},
    {"type": "heatmap", "name": "Heatmap", "description": "Cross-tabulated data; fill encodes value per cell", "reference": "type-heatmap.md"},
    {"type": "line", "name": "Line chart", "description": "Continuous trends over time, slopegraphs, ridgelines, bump charts", "reference": "type-line.md"},
    {"type": "gantt", "name": "Gantt", "description": "Tasks and phases on a timeline", "reference": "type-gantt.md"},
    {"type": "scatter", "name": "Scatter plot", "description": "Correlation or distribution of variables (bubble and beeswarm variants)", "reference": "type-scatter.md"},
    {"type": "high-level", "name": "High-Level", "description": "End-to-end data stack on a container cluster", "reference": "type-high-level.md"},
    {"type": "process", "name": "Process", "description": "Multi-actor sequential process with data handoffs", "reference": "type-process.md"},
    {"type": "medallion", "name": "Medallion", "description": "Multi-tier data storage with quality levels and access policies", "reference": "type-medallion.md"},
    {"type": "data-flow", "name": "Data flow", "description": "Role-scoped data flow: who does what at each pipeline step", "reference": "type-data-flow.md"},
    {"type": "dp-integration", "name": "DP integration", "description": "Integration topology of a data platform: sources → core → consumers", "reference": "type-dp-integration.md"},
    {"type": "dp-security-matrix", "name": "DP security matrix", "description": "Per-role / per-component access permissions matrix", "reference": "type-dp-security-matrix.md"},
    {"type": "sankey", "name": "Sankey", "description": "A quantity splitting and merging across stages, band width = amount", "reference": "type-sankey.md"},
    {"type": "fishbone", "name": "Fishbone", "description": "Causes of one observed effect, grouped by category (root-cause analysis)", "reference": "type-fishbone.md"},
    {"type": "wardley", "name": "Wardley map", "description": "Value chain against evolution: what to build, buy, and move", "reference": "type-wardley.md"},
    {"type": "kanban", "name": "Kanban", "description": "Work-in-progress by state, with WIP limits and blocked items", "reference": "type-kanban.md"},
    {"type": "journey", "name": "User journey", "description": "What a person does across stages of an experience, and how it feels", "reference": "type-journey.md"},
    {"type": "deployment", "name": "Deployment", "description": "Where software runs: zones, hosts, artifacts, replicas, ports", "reference": "type-deployment.md"},
    {"type": "dependency", "name": "Dependency graph", "description": "What depends on what, with fan-in and cycles a tree cannot express", "reference": "type-dependency.md"},
    {"type": "uml-class", "name": "UML class", "description": "Classes with operations, inheritance, and composition", "reference": "type-uml-class.md"},
    {"type": "story-map", "name": "Story map", "description": "Narrative backbone sliced into releases, with the cut line", "reference": "type-story-map.md"},
    {"type": "db-schema", "name": "Database schema", "description": "Physical tables: SQL types, constraints, indexes, column-level FKs", "reference": "type-db-schema.md"},
]


class DiagramDesignAdapter:
    """Production boundary around the diagram-design system.

    Provides deterministic IR extraction from Mermaid, draw.io, and Excalidraw,
    single-file HTML/SVG generation with an editorial design system,
    and automated accessibility/safety self-checks.
    """

    _lock = threading.RLock()

    def __init__(
        self,
        path: str | Path | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._path = Path(path).expanduser().resolve() if path else None
        self._timeout = float(timeout)
        self._scripts_dir: Path | None = None
        self._resolve_paths()

    def _resolve_paths(self) -> None:
        if self._path and self._path.is_dir():
            candidate = self._path / "skills" / "diagram-design" / "scripts"
            if candidate.is_dir():
                self._scripts_dir = candidate
                return
            candidate_direct = self._path / "scripts"
            if (candidate_direct / "mermaid_extract.py").is_file():
                self._scripts_dir = candidate_direct
                return
        # Default fallback to external-components
        default_candidate = Path("external-components/diagram-design/skills/diagram-design/scripts").resolve()
        if default_candidate.is_dir():
            self._scripts_dir = default_candidate

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    def available(self) -> bool:
        """Check if diagram-design scripts directory and tools are present."""
        if self._scripts_dir and (self._scripts_dir / "mermaid_extract.py").is_file():
            return True
        default_dir = Path("external-components/diagram-design/skills/diagram-design/scripts").resolve()
        return (default_dir / "mermaid_extract.py").is_file()

    def list_types(self) -> list[dict[str, str]]:
        """List all 41 supported diagram types, descriptions, and reference guides."""
        return list(DIAGRAM_TYPES)

    # ------------------------------------------------------------------
    # Extraction Operations
    # ------------------------------------------------------------------

    def extract_mermaid(self, source_or_path: str, as_json: bool = True) -> dict[str, Any]:
        """Extract a normalized IR from Mermaid text or a .mmd/.md file."""
        script = self._get_script("mermaid_extract.py")
        if not script:
            return {"ok": False, "error": "mermaid_extract.py script not found"}

        p = Path(source_or_path)
        is_existing_file = p.is_file()

        temp_path: Path | None = None
        try:
            if is_existing_file:
                target_file = str(p.resolve())
            else:
                # Write raw mermaid text to a temp file
                with tempfile.NamedTemporaryFile("w", suffix=".mmd", encoding="utf-8", delete=False) as f:
                    f.write(source_or_path)
                    temp_path = Path(f.name)
                target_file = str(temp_path)

            args = [sys.executable, str(script), target_file]
            if as_json:
                args.append("--json")

            res = self._run_proc(args)
            if not res["ok"]:
                return res

            if as_json:
                try:
                    data = json.loads(res["stdout"])
                    return {"ok": True, **data}
                except json.JSONDecodeError as exc:
                    return {"ok": False, "error": f"Failed to parse JSON IR: {exc}", "raw": res["stdout"]}
            return {"ok": True, "digest": res["stdout"]}
        finally:
            if temp_path and temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass

    def extract_drawio(self, file_path: str, page: str | None = None, as_json: bool = True) -> dict[str, Any]:
        """Extract a normalized IR from a draw.io diagram file."""
        script = self._get_script("drawio_extract.py")
        if not script:
            return {"ok": False, "error": "drawio_extract.py script not found"}

        p = Path(file_path).resolve()
        if not p.is_file():
            return {"ok": False, "error": f"File not found: {file_path}"}

        args = [sys.executable, str(script), str(p)]
        if page is not None:
            args.extend(["--page", str(page)])
        if as_json:
            args.append("--json")

        res = self._run_proc(args)
        if not res["ok"]:
            return res

        if as_json:
            try:
                data = json.loads(res["stdout"])
                return {"ok": True, **data}
            except json.JSONDecodeError as exc:
                return {"ok": False, "error": f"Failed to parse JSON IR: {exc}", "raw": res["stdout"]}
        return {"ok": True, "digest": res["stdout"]}

    def extract_excalidraw(self, file_path: str, as_json: bool = True) -> dict[str, Any]:
        """Extract a normalized IR from an Excalidraw diagram file."""
        script = self._get_script("excalidraw_extract.py")
        if not script:
            return {"ok": False, "error": "excalidraw_extract.py script not found"}

        p = Path(file_path).resolve()
        if not p.is_file():
            return {"ok": False, "error": f"File not found: {file_path}"}

        args = [sys.executable, str(script), str(p)]
        if as_json:
            args.append("--json")

        res = self._run_proc(args)
        if not res["ok"]:
            return res

        if as_json:
            try:
                data = json.loads(res["stdout"])
                return {"ok": True, **data}
            except json.JSONDecodeError as exc:
                return {"ok": False, "error": f"Failed to parse JSON IR: {exc}", "raw": res["stdout"]}
        return {"ok": True, "digest": res["stdout"]}

    # ------------------------------------------------------------------
    # Validation Operations
    # ------------------------------------------------------------------

    def validate_diagram(self, html_or_path: str) -> dict[str, Any]:
        """Validate diagram HTML against single-file safety and accessible SVG rules."""
        script = self._get_script("self_check.py")
        if not script:
            return {"ok": False, "error": "self_check.py script not found"}

        p = Path(html_or_path)
        is_existing_file = p.is_file()

        temp_path: Path | None = None
        try:
            if is_existing_file:
                target_file = str(p.resolve())
            else:
                with tempfile.NamedTemporaryFile("w", suffix=".html", encoding="utf-8", delete=False) as f:
                    f.write(html_or_path)
                    temp_path = Path(f.name)
                target_file = str(temp_path)

            args = [sys.executable, str(script), target_file]
            res = self._run_proc(args)
            output = (res.get("stdout", "") + "\n" + res.get("stderr", "")).strip()

            lines = [ln.strip() for ln in output.splitlines() if ln.strip()]
            errors: list[str] = []
            for ln in lines:
                if ln.startswith("- "):
                    errors.append(ln[2:])
                elif ln.startswith("FAIL"):
                    pass
                elif ln.startswith("OK"):
                    pass
                elif "usage:" in ln.lower() or "error" in ln.lower():
                    errors.append(ln)

            is_valid = (res.get("exit_code") == 0) and len(errors) == 0
            return {
                "ok": True,
                "valid": is_valid,
                "errors": errors,
                "details": output,
            }
        finally:
            if temp_path and temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass

    # ------------------------------------------------------------------
    # HTML & SVG Generation
    # ------------------------------------------------------------------

    def generate_html(
        self,
        title: str,
        svg_content: str,
        description: str = "",
        paper_color: str = "#f5f5f5",
        ink_color: str = "#2d3142",
        accent_color: str = "#eb6c36",
    ) -> dict[str, Any]:
        """Generate a compliant, standalone HTML diagram wrapping an accessible SVG."""
        safe_title = (title or "Architecture Diagram").strip()
        safe_desc = (description or f"Diagram illustrating {safe_title}").strip()

        clean_svg = svg_content.strip()
        # If the provided SVG doesn't include accessible title/desc and role, wrap or enhance it
        if "<svg" in clean_svg:
            # Check if role="img" is present
            if 'role="img"' not in clean_svg:
                clean_svg = re.sub(r"<svg\b", '<svg role="img"', clean_svg, count=1)
            # Check if aria-labelledby is present
            if 'aria-labelledby="' not in clean_svg:
                clean_svg = re.sub(
                    r"<svg\b([^>]*)>",
                    r'<svg\1 aria-labelledby="diag-title diag-desc">',
                    clean_svg,
                    count=1,
                )
            # Ensure <title id="diag-title"> and <desc id="diag-desc"> are the first children
            if '<title id="diag-title">' not in clean_svg:
                # Remove any existing bare <title> or <desc> tags to satisfy self_check
                clean_svg = re.sub(r"<title\b[^>]*>.*?</title>", "", clean_svg, flags=re.DOTALL)
                clean_svg = re.sub(r"<desc\b[^>]*>.*?</desc>", "", clean_svg, flags=re.DOTALL)
                accessible_header = (
                    f'\n  <title id="diag-title">{safe_title}</title>\n'
                    f'  <desc id="diag-desc">{safe_desc}</desc>\n'
                )
                clean_svg = re.sub(r"(<svg\b[^>]*>)", r"\1" + accessible_header, clean_svg, count=1)
        else:
            # Wrap content in a default SVG viewport
            clean_svg = (
                f'<svg role="img" aria-labelledby="diag-title diag-desc" '
                f'viewBox="0 0 960 540" width="960" height="540" xmlns="http://www.w3.org/2000/svg">\n'
                f'  <title id="diag-title">{safe_title}</title>\n'
                f'  <desc id="diag-desc">{safe_desc}</desc>\n'
                f'  {clean_svg}\n'
                f'</svg>'
            )

        html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{safe_title}</title>
<style>
:root {{
  --paper: {paper_color};
  --ink: {ink_color};
  --accent: {accent_color};
  --font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}}
body {{
  margin: 0;
  padding: 32px;
  background-color: var(--paper);
  color: var(--ink);
  font-family: var(--font-family);
  display: flex;
  flex-direction: column;
  align-items: center;
  box-sizing: border-box;
}}
.diagram-frame {{
  max-width: 100%;
  width: 100%;
  margin: 0 auto;
  display: flex;
  justify-content: center;
  overflow: auto;
}}
svg {{
  max-width: 100%;
  height: auto;
  display: block;
}}
</style>
</head>
<body>
<figure class="diagram-frame">
{clean_svg}
</figure>
</body>
</html>
"""
        validation = self.validate_diagram(html_template)
        return {
            "ok": True,
            "html": html_template,
            "svg": clean_svg,
            "valid": validation.get("valid", True),
            "errors": validation.get("errors", []),
        }

    def export_svg(self, html_or_path: str, output_path: str | None = None) -> dict[str, Any]:
        """Extract the standalone SVG element from a diagram HTML file or text."""
        p = Path(html_or_path)
        if p.is_file():
            content = p.read_text(encoding="utf-8")
        else:
            content = html_or_path

        match = re.search(r"(<svg\b.*?</svg>)", content, flags=re.DOTALL | re.IGNORECASE)
        if not match:
            return {"ok": False, "error": "No <svg> root element found in content"}

        svg_text = match.group(1).strip()
        if output_path:
            out_file = Path(output_path).resolve()
            out_file.parent.mkdir(parents=True, exist_ok=True)
            out_file.write_text(svg_text, encoding="utf-8")
            return {"ok": True, "path": str(out_file), "bytes": len(svg_text)}

        return {"ok": True, "svg": svg_text, "bytes": len(svg_text)}

    # ------------------------------------------------------------------
    # Subprocess Helper
    # ------------------------------------------------------------------

    def _get_script(self, script_name: str) -> Path | None:
        self._resolve_paths()
        if self._scripts_dir:
            target = self._scripts_dir / script_name
            if target.is_file():
                return target
        return None

    def _run_proc(self, args: list[str]) -> dict[str, Any]:
        with self._lock:
            try:
                proc = subprocess.run(
                    args,
                    capture_output=True,
                    text=True,
                    timeout=self._timeout,
                    check=False,
                )
                return {
                    "ok": proc.returncode == 0,
                    "exit_code": proc.returncode,
                    "stdout": redact_secrets(proc.stdout.strip()),
                    "stderr": redact_secrets(proc.stderr.strip()),
                }
            except subprocess.TimeoutExpired:
                return {"ok": False, "error": f"Command timed out after {self._timeout}s"}
            except Exception as exc:
                return {"ok": False, "error": str(exc)}
