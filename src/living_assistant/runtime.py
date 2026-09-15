from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv
from .config import load_config, project_root
from .hardware import detect_hardware, choose_profile
from .workspace import Workspace
from .approval import ApprovalManager, ApprovalStore
from .memory import MemoryStore
from .model_provider import OllamaProvider, ModelManager
from .agents import SpecialistRouter
from .orchestrator import Orchestrator
from .watchers import WatchRegistry
from .skills import SkillRegistry
from .notifications import Notifier
from .resource_manager import ResourceManager
from .quarantine import QuarantineVault
from .browser import BrowserController
from .groups import ProjectGroupRegistry, ProjectGroupController
from .tools.filesystem import build_filesystem_tools
from .tools.shell import build_shell_tools, ProcessRegistry
from .tools.projects import build_project_tools, ProjectRegistry
from .tools.webtools import build_web_tools
from .tools.database import build_database_tools
from .tools.personal import build_personal_tools
from .tools.security import build_security_tools
from .tools.desktop import build_desktop_tools
from .tools.gittools import build_git_tools
from .tools.browsertools import build_browser_tools
from .tools.grouptools import build_group_tools

@dataclass
class Runtime:
    config: dict
    profile: str
    hardware: object
    workspace: Workspace
    memory: MemoryStore
    projects: ProjectRegistry
    groups: ProjectGroupRegistry
    group_controller: ProjectGroupController
    processes: ProcessRegistry
    approvals: ApprovalStore
    approval_manager: ApprovalManager
    watches: WatchRegistry
    skills: SkillRegistry
    notifier: Notifier
    resources: ResourceManager
    quarantine: QuarantineVault
    browser: BrowserController
    orchestrator: Orchestrator
    model_manager: ModelManager


def build_runtime(interactive: bool = True) -> Runtime:
    load_dotenv()
    cfg = load_config()
    hw = detect_hardware()
    profile = choose_profile(cfg, hw)
    pcfg = cfg['profiles'][profile]

    roots = []
    for r in cfg.get('workspace_roots', ['./workspace']):
        p = Path(r)
        if not p.is_absolute(): p = project_root() / p
        roots.append(p)

    projects = ProjectRegistry()
    for item in projects.list().values():
        if isinstance(item, dict) and item.get('path'):
            rp = Path(item['path']).expanduser().resolve()
            if rp.exists(): roots.append(rp)

    ws = Workspace(roots)
    approvals = ApprovalStore()
    approval = ApprovalManager(interactive=interactive, store=approvals)
    memory = MemoryStore()
    processes = ProcessRegistry()
    watches = WatchRegistry()
    skills = SkillRegistry()
    notifier = Notifier()
    resources = ResourceManager(profile, cfg)
    quarantine = QuarantineVault()
    groups = ProjectGroupRegistry()
    group_controller = ProjectGroupController(groups, projects, processes, approval)

    provider = OllamaProvider(base_url=cfg['ollama']['base_url'])
    mm = ModelManager(provider)
    keep_alive = int(cfg['ollama'].get('keep_alive_seconds',45))
    context_tokens = int(pcfg.get('context_tokens',4096))

    browser_cfg = cfg.get('browser', {})
    browser_enabled = bool(browser_cfg.get('enabled', True)) and (profile != 'lite' or bool(browser_cfg.get('lite_enabled', False)))
    browser = BrowserController(ws, approval, headless=bool(browser_cfg.get('headless', False)))

    tools = []
    tools += build_filesystem_tools(ws, approval, bool(cfg.get('policy',{}).get('require_write_approval', False)))
    tools += build_shell_tools(ws, approval, cfg, processes)
    tools += build_project_tools(ws, projects)
    tools += build_group_tools(group_controller)
    tools += build_git_tools(ws, approval)
    tools += build_web_tools(ws, cfg, approval, quarantine)
    tools += build_browser_tools(browser, enabled=browser_enabled)
    tools += build_database_tools(cfg)
    tools += build_personal_tools(memory, notifier)
    tools += build_security_tools(ws, approval)
    if bool(cfg.get('desktop',{}).get('enabled', True)):
        tools += build_desktop_tools(ws, approval)

    specialists = SpecialistRouter(
        mm, pcfg['models'], keep_alive=keep_alive, max_handoffs=int(pcfg['max_handoffs']),
        context_tokens=context_tokens, resource_manager=resources,
    )
    orchestrator = Orchestrator(
        mm, pcfg['models']['orchestrator'], tools, specialists,
        keep_alive=keep_alive, max_steps=int(pcfg['max_tool_steps']), context_tokens=context_tokens,
        skills=skills, resource_manager=resources,
    )
    return Runtime(cfg, profile, hw, ws, memory, projects, groups, group_controller, processes, approvals,
                   approval, watches, skills, notifier, resources, quarantine, browser, orchestrator, mm)
