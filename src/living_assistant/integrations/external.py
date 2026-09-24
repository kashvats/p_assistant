from __future__ import annotations

from dataclasses import dataclass
import importlib.util
import os
from pathlib import Path
import shutil
from typing import Any


@dataclass(frozen=True)
class IntegrationSpec:
    name: str
    repository: str
    role: str
    package: str | None = None
    command: str | None = None
    path_key: str | None = None
    reference_only: bool = False
    hardware_note: str | None = None


INTEGRATIONS = (
    IntegrationSpec("browser_use", "https://github.com/browser-use/browser-use", "browser", package="browser_use"),
    IntegrationSpec("openviking", "https://github.com/volcengine/OpenViking", "memory", package="openviking"),
    IntegrationSpec("codebase_memory_mcp", "https://github.com/DeusData/codebase-memory-mcp", "code_intelligence", command="codebase-memory-mcp"),
    IntegrationSpec("diagram_design", "https://github.com/cathrynlavery/diagram-design", "diagram", path_key="diagram_design_path"),
    IntegrationSpec("cybersecurity_skills", "https://github.com/mukul975/Anthropic-Cybersecurity-Skills", "skills", path_key="cybersecurity_skills_path"),
    IntegrationSpec("agency_agents", "https://github.com/msitarzewski/agency-agents", "specialists", path_key="agency_agents_path"),
    IntegrationSpec("openmontage", "https://github.com/MrArtt/openmontage", "media", command="openmontage"),
    IntegrationSpec("graft", "https://github.com/AEndrix03/Graft", "memory", command="graft"),
    IntegrationSpec("agentmemory", "https://github.com/rohitg00/agentmemory", "memory", command="agentmemory"),
    IntegrationSpec(
        "edge0",
        "https://github.com/Edge0-AI/Edge0",
        "model",
        package="edge0",
        hardware_note="Edge0 currently supports Apple Silicon MLX, not dedicated NVIDIA CUDA.",
    ),
    IntegrationSpec(
        "awesome_harness_engineering",
        "https://github.com/harness-engineer/awesome-harness-engineering",
        "reference",
        reference_only=True,
    ),
    IntegrationSpec(
        "scientific_agent_skills",
        "https://github.com/K-Dense-AI/scientific-agent-skills",
        "skills",
        path_key="scientific_skills_path",
    ),
    IntegrationSpec(
        "awesome_ai_agent_tools",
        "https://github.com/michielhdoteth/awesome-ai-agent-tools",
        "reference",
        reference_only=True,
    ),
)


def _path_status(raw: Any) -> dict[str, Any]:
    if not raw:
        return {"configured": False, "available": False}
    path = Path(str(raw)).expanduser()
    return {"configured": True, "available": path.is_dir(), "path": str(path)}


class ExternalIntegrationRegistry:
    """Lazy, dependency-free registry for optional external engines.

    The core keeps its native implementations as fallbacks. External projects are
    never imported or started during a request unless explicitly enabled and
    their package/command/path is available.
    """

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self.external = self.config.get("external_integrations", {}) or {}

    def _enabled(self, name: str) -> bool:
        item = self.external.get(name, {}) or {}
        return bool(item.get("enabled", False))

    def status(self) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for spec in INTEGRATIONS:
            item = self.external.get(spec.name, {}) or {}
            info: dict[str, Any] = {
                "name": spec.name,
                "role": spec.role,
                "repository": spec.repository,
                "revision": item.get("revision"),
                "enabled": self._enabled(spec.name),
                "reference_only": spec.reference_only,
                "available": False,
                "activation": "disabled",
            }
            if spec.hardware_note:
                info["hardware_note"] = spec.hardware_note
            if spec.package:
                info["package_installed"] = importlib.util.find_spec(spec.package) is not None
                info["available"] = bool(info["package_installed"])
                info["activation"] = "python-package"
            if spec.command:
                command = str(item.get("command") or spec.command)
                info["command"] = command
                cmd_installed = shutil.which(command) is not None
                if not cmd_installed and spec.name == "agentmemory":
                    cmd_installed = Path("external-components/agentmemory/package.json").is_file()
                if not cmd_installed and spec.name == "codebase_memory_mcp":
                    cmd_installed = (
                        Path("external-components/codebase-memory-mcp/server.json").is_file()
                        or shutil.which("npx") is not None
                        or shutil.which("uvx") is not None
                    )
                if not cmd_installed and spec.name == "graft":
                    cmd_installed = (
                        Path("external-components/Graft/CMakeLists.txt").is_file()
                        or (Path.home() / ".graft" / "bin" / ("graft.exe" if os.name == "nt" else "graft")).is_file()
                        or (Path.home() / ".graft").is_dir()
                    )
                if not cmd_installed and spec.name == "openmontage":
                    cmd_installed = (
                        Path("external-components/openmontage/config.yaml").is_file()
                        or Path("external-components/openmontage/setup.py").is_file()
                    )
                info["command_installed"] = cmd_installed
                info["available"] = bool(info["command_installed"])
                info["activation"] = "subprocess"
            if spec.path_key:
                configured_path = item.get("path") or os.environ.get(spec.path_key.upper())
                if not configured_path and spec.name == "diagram_design":
                    default_checkout = Path("external-components/diagram-design")
                    if default_checkout.is_dir():
                        configured_path = str(default_checkout)
                elif not configured_path and spec.name == "cybersecurity_skills":
                    default_checkout = Path("external-components/Anthropic-Cybersecurity-Skills")
                    if default_checkout.is_dir():
                        configured_path = str(default_checkout)
                path_info = _path_status(configured_path)
                info.update(path_info)
                info["available"] = bool(path_info["available"])
                info["activation"] = "skill-directory"
            if spec.reference_only:
                info["available"] = False
                info["activation"] = "reference-only"
            if not info["enabled"] and not spec.reference_only:
                info["available"] = False
                info["activation"] = "disabled"
            if info["enabled"] and not info["available"] and not spec.reference_only:
                info["activation"] = "unavailable"
            result[spec.name] = info
        return result

    def role_status(self, role: str) -> list[dict[str, Any]]:
        return [item for item in self.status().values() if item["role"] == role]

    def environment_status(self) -> dict[str, Any]:
        from living_assistant.system.environment import get_environment_manager
        return get_environment_manager().status()

