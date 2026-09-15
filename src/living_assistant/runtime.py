from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv
from .config import load_config, project_root
from .hardware import detect_hardware, choose_profile
from .workspace import Workspace
from .approval import ApprovalManager
from .memory import MemoryStore
from .model_provider import OllamaProvider, ModelManager
from .agents import SpecialistRouter
from .orchestrator import Orchestrator
from .tools.filesystem import build_filesystem_tools
from .tools.shell import build_shell_tools, ProcessRegistry
from .tools.projects import build_project_tools, ProjectRegistry
from .tools.webtools import build_web_tools
from .tools.database import build_database_tools
from .tools.personal import build_personal_tools
from .tools.security import build_security_tools

@dataclass
class Runtime:
    config: dict
    profile: str
    hardware: object
    workspace: Workspace
    memory: MemoryStore
    projects: ProjectRegistry
    processes: ProcessRegistry
    orchestrator: Orchestrator
    model_manager: ModelManager

def build_runtime(interactive: bool = True) -> Runtime:
    load_dotenv()
    cfg = load_config()
    hw = detect_hardware()
    profile = choose_profile(cfg, hw)
    pcfg = cfg["profiles"][profile]

    roots = []
    for r in cfg.get("workspace_roots", ["./workspace"]):
        p = Path(r)
        if not p.is_absolute():
            p = project_root() / p
        roots.append(p)

    # Explicitly registered projects become approved workspace roots on future runs.
    projects = ProjectRegistry()
    for registered_path in projects.list().values():
        rp = Path(registered_path).expanduser().resolve()
        if rp.exists():
            roots.append(rp)

    ws = Workspace(roots)
    approval = ApprovalManager(interactive=interactive)
    memory = MemoryStore()
    processes = ProcessRegistry()

    provider = OllamaProvider(base_url=cfg["ollama"]["base_url"])
    mm = ModelManager(provider)
    keep_alive = int(cfg["ollama"].get("keep_alive_seconds",45))

    tools = []
    tools += build_filesystem_tools(ws)
    tools += build_shell_tools(ws, approval, cfg, processes)
    tools += build_project_tools(ws, projects)
    tools += build_web_tools(ws, cfg)
    tools += build_database_tools(cfg)
    tools += build_personal_tools(memory)
    tools += build_security_tools(ws, approval)

    specialists = SpecialistRouter(mm, pcfg["models"], keep_alive=keep_alive, max_handoffs=int(pcfg["max_handoffs"]))
    orchestrator = Orchestrator(mm, pcfg["models"]["orchestrator"], tools, specialists,
                                keep_alive=keep_alive, max_steps=int(pcfg["max_tool_steps"]))
    return Runtime(cfg, profile, hw, ws, memory, projects, processes, orchestrator, mm)
