from __future__ import annotations
from dataclasses import dataclass
from typing import Any
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
from .voice import VoiceEngine
from .routines import RoutineRegistry
from .improvements import ImprovementStore, ImprovementEngine
from .evaluation import EvaluationStore, EvaluationEngine
from .canary import CanaryEngine, CanaryStore
from .browser import BrowserController
from .groups import ProjectGroupRegistry, ProjectGroupController
from .personal_state import PersonalState
from .calendar_store import CalendarStore
from .sessions import SessionStore
from .connectors import ConnectorRegistry, ConnectorManager
from .connector_credentials import CredentialStore
from .briefing import BriefingEngine
from .security_guardian import SecurityGuardian
from .security_sensors import SecuritySensorPlatform
from .experience import ExperienceEngine
from .event_bus import EventBus
from .desktop_intelligence import DesktopController
from .task_graph import TaskGraphManager
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
from .tools.voicetools import build_voice_tools
from .tools.routinetools import build_routine_tools
from .tools.improvementtools import build_improvement_tools
from .tools.calendartools import build_calendar_tools
from .tools.personalstate import build_personal_state_tools
from .tools.briefingtools import build_briefing_tools
from .tools.sessiontools import build_session_tools
from .tools.experiencetools import build_experience_tools
from .tools.connectortools import build_connector_tools
from .tools.planning import build_planning_tools

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
    voice: VoiceEngine
    routines: RoutineRegistry
    improvements: ImprovementEngine
    evaluations: EvaluationEngine
    canaries: CanaryEngine
    browser: BrowserController
    personal: PersonalState
    calendar: CalendarStore
    sessions: SessionStore
    connectors: ConnectorRegistry
    connector_manager: ConnectorManager
    briefings: BriefingEngine
    guardian: SecurityGuardian
    security_sensors: SecuritySensorPlatform
    experiences: ExperienceEngine
    planner: TaskGraphManager
    events_bus: EventBus
    def dispatch(self, event_type: str, data: dict[str, Any] = None) -> Any:
        return self.orchestrator.dispatch(event_type, data)
    orchestrator: Orchestrator
    model_manager: ModelManager
    desktop_controller: DesktopController


import threading

_runtime_lock = threading.Lock()
_global_runtime = None

def get_runtime(interactive: bool = False) -> Runtime:
    global _global_runtime
    with _runtime_lock:
        if _global_runtime is None:
            _global_runtime = build_runtime(interactive=interactive)
        return _global_runtime

def build_runtime(interactive: bool = True) -> Runtime:
    load_dotenv()
    cfg = load_config(); hw = detect_hardware(); profile = choose_profile(cfg, hw); pcfg = cfg['profiles'][profile]

    roots=[]
    for r in cfg.get('workspace_roots',['./workspace']):
        p=Path(r)
        if not p.is_absolute(): p=project_root()/p
        roots.append(p)

    projects=ProjectRegistry()
    for item in projects.list().values():
        if isinstance(item,dict) and item.get('path'):
            rp=Path(item['path']).expanduser().resolve()
            if rp.exists(): roots.append(rp)

    ws=Workspace(roots)
    personal=PersonalState(timezone=str(cfg.get('personal',{}).get('timezone','local')), defaults=cfg.get('personal',{}))
    notifier=Notifier(quiet_provider=personal.is_quiet)
    approvals=ApprovalStore(); approval=ApprovalManager(interactive=interactive,store=approvals,notifier=notifier)
    memory=MemoryStore(); processes=ProcessRegistry(); watches=WatchRegistry(); skills=SkillRegistry()
    resources=ResourceManager(profile,cfg,hardware=hw); quarantine=QuarantineVault(); routines=RoutineRegistry()
    improvement_store=ImprovementStore(); improvements=ImprovementEngine(ws,approval,improvement_store)
    evaluation_store=EvaluationStore(); evaluations=EvaluationEngine(ws,approval,improvements,evaluation_store,cfg,profile=profile)
    canary_store=CanaryStore(); canaries=CanaryEngine(ws,approval,improvements,evaluations,canary_store,cfg,profile=profile); evaluations.canary_store=canary_store
    voice=VoiceEngine(ws,approval,cfg,profile); groups=ProjectGroupRegistry()
    group_controller=ProjectGroupController(groups,projects,processes,approval)
    calendar=CalendarStore()
    session_cfg=cfg.get('sessions',{})
    sessions=SessionStore(retention_days=int(session_cfg.get('retention_days',30)), redact_secrets=bool(session_cfg.get('redact_secrets',True)))
    connectors=ConnectorRegistry()
    connector_cfg=cfg.get('connectors',{})
    connector_manager=ConnectorManager(connectors, approval, credentials=CredentialStore(use_keyring=bool(connector_cfg.get('use_keyring',True))), max_external_chars=int(cfg.get('policy',{}).get('max_web_text_chars',120000)))
    briefings=BriefingEngine(cfg,personal,memory,calendar,projects,processes,approvals,notifier)
    guardian=SecurityGuardian(cfg,approval=approval)
    security_sensors=SecuritySensorPlatform(cfg,approval=approval,guardian=guardian)
    experiences=ExperienceEngine(config=cfg)
    planner=TaskGraphManager(approvals.path)
    events_bus=EventBus(max_events=int(cfg.get('ui',{}).get('activity_history',500)), path=approvals.path)

    ocfg=cfg.get('ollama',{})
    provider=OllamaProvider(base_url=ocfg['base_url'], allow_remote=bool(ocfg.get('allow_remote',False)), allow_insecure_remote=bool(ocfg.get('allow_insecure_remote',False))); mm=ModelManager(provider, resource_manager=resources, event_bus=events_bus)
    desktop_controller=DesktopController(ws, approval, cfg, provider=provider, model_manager=mm)
    keep_alive=int(cfg['ollama'].get('keep_alive_seconds',45)); context_tokens=int(pcfg.get('context_tokens',4096))
    browser_cfg=cfg.get('browser',{})
    browser_enabled=bool(browser_cfg.get('enabled',True)) and (profile!='lite' or bool(browser_cfg.get('lite_enabled',False)))
    browser=BrowserController(ws,approval,headless=bool(browser_cfg.get('headless',False)))

    tools=[]
    tools += build_filesystem_tools(ws,approval,bool(cfg.get('policy',{}).get('require_write_approval',False)))
    tools += build_shell_tools(ws,approval,cfg,processes)
    tools += build_project_tools(ws,projects)
    tools += build_group_tools(group_controller)
    tools += build_git_tools(ws,approval)
    tools += build_web_tools(ws,cfg,approval,quarantine,browser=browser)
    tools += build_browser_tools(browser,enabled=browser_enabled)
    tools += build_database_tools(cfg)
    tools += build_personal_tools(memory,notifier)
    tools += build_calendar_tools(calendar)
    tools += build_personal_state_tools(personal)
    tools += build_briefing_tools(briefings)
    tools += build_session_tools(sessions)
    tools += build_experience_tools(experiences)
    tools += build_planning_tools(planner)
    if bool(cfg.get('connectors',{}).get('enabled',True)): tools += build_connector_tools(connector_manager)
    tools += build_routine_tools(routines)
    tools += build_improvement_tools(improvements, evaluations, canaries)
    tools += build_voice_tools(voice)
    tools += build_security_tools(ws,approval,guardian,security_sensors)
    if bool(cfg.get('desktop',{}).get('enabled',True)): tools += build_desktop_tools(ws,approval,desktop_controller)

    specialists=SpecialistRouter(
        mm, pcfg['models'], keep_alive=keep_alive, max_handoffs=int(pcfg['max_handoffs']),
        context_tokens=context_tokens, resource_manager=resources,
        timeout_seconds=float(cfg.get('policy',{}).get('specialist_timeout_seconds',60)),
    )
    orchestrator=Orchestrator(mm,pcfg['models']['orchestrator'],tools,specialists,
                              keep_alive=keep_alive,max_steps=int(pcfg['max_tool_steps']),context_tokens=context_tokens,
                              skills=skills,resource_manager=resources,session_store=(sessions if bool(session_cfg.get('enabled',True)) else None),
                              max_session_messages=int(session_cfg.get('max_context_messages',24)), experiences=experiences, event_bus=events_bus)
    return Runtime(cfg,profile,hw,ws,memory,projects,groups,group_controller,processes,approvals,
                   approval,watches,skills,notifier,resources,quarantine,voice,routines,improvements,evaluations,canaries,browser,
                   personal,calendar,sessions,connectors,connector_manager,briefings,guardian,security_sensors,experiences,planner,events_bus,orchestrator,mm,desktop_controller)
