from __future__ import annotations

import importlib.util
import logging
import sys
import threading
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

_UNAVAILABLE = (
    "OpenMontage is enabled but the SDK is not installed or available at the configured path. "
    "Install it or clone to external-components/openmontage"
)

class OpenMontageAdapter:
    """Production boundary around OpenMontage media orchestration."""

    _import_lock = threading.RLock()

    def __init__(
        self,
        path: str | Path | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._timeout = timeout
        self._path = Path(path).expanduser().resolve() if path else None

    def _sdk(self):
        with self._import_lock:
            candidates: list[Path] = []
            if self._path:
                candidates.append(self._path)
            default_loc = Path("external-components/openmontage").resolve()
            if default_loc.is_dir():
                candidates.append(default_loc)

            for cand in candidates:
                cand_str = str(cand)
                if cand.is_dir() and cand_str not in sys.path:
                    sys.path.insert(0, cand_str)

            # We need to import pipeline_loader and tool_registry from openmontage
            try:
                import lib.pipeline_loader as pipeline_loader
                import tools.tool_registry as tool_registry
                # discover tools
                tool_registry.registry.discover()
                return pipeline_loader, tool_registry.registry
            except ImportError:
                raise RuntimeError(_UNAVAILABLE)

    def list_pipelines(self) -> dict[str, Any]:
        try:
            loader, _ = self._sdk()
            defs_dir = Path("external-components/openmontage/pipeline_defs").resolve()
            pipelines = loader.list_pipelines(defs_dir=defs_dir)
            return {"ok": True, "pipelines": pipelines}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def get_pipeline(self, name: str) -> dict[str, Any]:
        try:
            loader, _ = self._sdk()
            defs_dir = Path("external-components/openmontage/pipeline_defs").resolve()
            pipeline = loader.load_pipeline(name, defs_dir=defs_dir)
            return {"ok": True, "pipeline": pipeline}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def list_tools(self, capability: Optional[str] = None) -> dict[str, Any]:
        try:
            _, registry = self._sdk()
            if capability:
                tools = registry.find_by_capability(capability)
            else:
                tools = registry.get_available()

            tool_infos = [t.get_info() for t in tools]
            return {"ok": True, "tools": tool_infos}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def execute_tool(self, tool_name: str, inputs: dict[str, Any]) -> dict[str, Any]:
        try:
            _, registry = self._sdk()
            tool = registry.get(tool_name)
            if not tool:
                return {"ok": False, "error": f"Tool {tool_name} not found"}

            # Execute tool directly
            result = tool.execute(inputs)

            # Ensure it returns plain dict
            if hasattr(result, "to_dict"):
                return {"ok": True, "result": result.to_dict()}
            elif hasattr(result, "__dict__"):
                return {"ok": True, "result": result.__dict__}
            else:
                return {"ok": True, "result": str(result)}
        except Exception as e:
            return {"ok": False, "error": str(e)}
