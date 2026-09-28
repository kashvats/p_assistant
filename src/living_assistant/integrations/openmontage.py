from __future__ import annotations

import logging
import json
from pathlib import Path
from typing import Any, Optional

from living_assistant.core.isolated_executor import run_isolated_tool

logger = logging.getLogger(__name__)

class OpenMontageAdapter:
    """Production boundary around OpenMontage media orchestration.
    Uses subprocess isolation to prevent sys.path namespace collisions (e.g., 'lib', 'tools').
    """

    def __init__(
        self,
        path: str | Path | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._timeout = timeout
        self._path = str(Path(path).expanduser().resolve()) if path else ""

    def _build_preamble(self) -> str:
        return f"""
import sys
import json
path = {repr(self._path)}
if path:
    sys.path.insert(0, path)
sys.path.insert(0, 'external-components/openmontage')

import lib.pipeline_loader as pipeline_loader
import tools.tool_registry as tool_registry
tool_registry.registry.discover()
"""

    def list_pipelines(self) -> dict[str, Any]:
        script = self._build_preamble() + """
try:
    defs_dir = "external-components/openmontage/pipeline_defs"
    pipelines = pipeline_loader.list_pipelines(defs_dir=defs_dir)
    print(json.dumps({"ok": True, "pipelines": pipelines}))
except Exception as e:
    print(json.dumps({"ok": False, "error": str(e)}))
"""
        return run_isolated_tool(script, timeout=self._timeout)

    def get_pipeline(self, name: str) -> dict[str, Any]:
        script = self._build_preamble() + f"""
try:
    defs_dir = "external-components/openmontage/pipeline_defs"
    pipeline = pipeline_loader.load_pipeline({repr(name)}, defs_dir=defs_dir)
    print(json.dumps({{"ok": True, "pipeline": pipeline}}))
except Exception as e:
    print(json.dumps({{"ok": False, "error": str(e)}}))
"""
        return run_isolated_tool(script, timeout=self._timeout)

    def list_tools(self, capability: Optional[str] = None) -> dict[str, Any]:
        script = self._build_preamble() + f"""
try:
    capability = {repr(capability)}
    if capability:
        tools = tool_registry.registry.find_by_capability(capability)
    else:
        tools = tool_registry.registry.get_available()
    
    tool_infos = [t.get_info() for t in tools]
    print(json.dumps({{"ok": True, "tools": tool_infos}}))
except Exception as e:
    print(json.dumps({{"ok": False, "error": str(e)}}))
"""
        return run_isolated_tool(script, timeout=self._timeout)

    def download_video(
        self,
        url: str,
        output_dir: str,
        fmt: str = "video",
        max_resolution: str = "720p",
        max_duration_seconds: int = 1800,
        timeout: float = 900.0,
    ) -> dict[str, Any]:
        """Run OpenMontage's yt-dlp based VideoDownloader without loading the whole registry."""
        inputs = {
            "url": url,
            "output_dir": output_dir,
            "format": fmt,
            "max_resolution": max_resolution,
            "max_duration_seconds": int(max_duration_seconds),
        }
        script = f"""
import sys, json
sys.path.insert(0, {self._path!r})
try:
    from tools.analysis.video_downloader import VideoDownloader
    result = VideoDownloader().execute(json.loads({json.dumps(inputs)!r}))
    print(json.dumps({{"ok": bool(result.success), "error": result.error, "data": result.data,
                      "duration_seconds": result.duration_seconds}}, default=str))
except Exception as e:
    print(json.dumps({{"ok": False, "error": f"{{type(e).__name__}}: {{e}}"}}))
"""
        return run_isolated_tool(script, timeout=timeout)

    def execute_tool(self, tool_name: str, inputs: dict[str, Any]) -> dict[str, Any]:
        # Inputs travel as a JSON string literal; embedding json.dumps output directly
        # as Python source breaks on true/false/null.
        script = self._build_preamble() + f"""
try:
    tool = tool_registry.registry.get({repr(tool_name)})
    if not tool:
        print(json.dumps({{"ok": False, "error": f"Tool {repr(tool_name)} not found"}}))
    else:
        result = tool.execute(json.loads({json.dumps(inputs)!r}))
        if hasattr(result, "to_dict"):
            res_dict = result.to_dict()
        elif hasattr(result, "__dict__"):
            res_dict = result.__dict__
        else:
            res_dict = str(result)
        print(json.dumps({{"ok": True, "result": res_dict}}))
except Exception as e:
    print(json.dumps({{"ok": False, "error": str(e)}}))
"""
        return run_isolated_tool(script, timeout=self._timeout)
