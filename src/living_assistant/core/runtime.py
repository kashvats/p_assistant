from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from pathlib import Path
from dotenv import load_dotenv
from living_assistant.core.config import load_config, project_root
from living_assistant.system.hardware import detect_hardware, choose_profile
from living_assistant.core.workspace import Workspace
from living_assistant.core.approval import ApprovalManager, ApprovalStore
from living_assistant.core.memory import MemoryStore
from living_assistant.core.model_provider import AirLLMProvider, CompositeModelProvider, OllamaProvider, ModelManager
from living_assistant.agents.agents import SpecialistRouter
from living_assistant.agents.orchestrator import Orchestrator
from living_assistant.system.watchers import WatchRegistry
from living_assistant.core.skills import SkillRegistry
from living_assistant.system.notifications import Notifier
from living_assistant.system.resource_manager import ResourceManager
from living_assistant.security.quarantine import QuarantineVault
from living_assistant.desktop.voice import VoiceEngine
from living_assistant.system.routines import RoutineRegistry
from living_assistant.learning.improvements import ImprovementStore, ImprovementEngine
from living_assistant.learning.evaluation import EvaluationStore, EvaluationEngine
from living_assistant.learning.canary import CanaryEngine, CanaryStore
from living_assistant.learning.repair_loop import AutonomousRepairLoop
from living_assistant.desktop.browser import BrowserController
from living_assistant.system.groups import ProjectGroupRegistry, ProjectGroupController
from living_assistant.core.personal_state import PersonalState
from living_assistant.core.calendar_store import CalendarStore
from living_assistant.core.sessions import SessionStore
from living_assistant.connectors.connectors import ConnectorRegistry, ConnectorManager
from living_assistant.connectors.connector_credentials import CredentialStore
from living_assistant.connectors.mobile_bridge import MobileBridge
from living_assistant.core.briefing import BriefingEngine
from living_assistant.security.security_guardian import SecurityGuardian
from living_assistant.security.security_sensors import SecuritySensorPlatform
from living_assistant.learning.experience import ExperienceEngine
from living_assistant.learning.run_history import RunHistoryStore
from living_assistant.learning.knowledge_gap_detection import KnowledgeGapDetector
from living_assistant.system.model_usage import ModelUsageStore
from living_assistant.core.event_bus import EventBus
from living_assistant.desktop.desktop_intelligence import DesktopController
from living_assistant.agents.task_graph import TaskGraphManager
from living_assistant.tools.filesystem import build_filesystem_tools
from living_assistant.tools.shell import build_shell_tools, ProcessRegistry
from living_assistant.tools.projects import build_project_tools, ProjectRegistry
from living_assistant.tools.webtools import build_web_tools
from living_assistant.tools.database import build_database_tools
from living_assistant.tools.personal import build_personal_tools
from living_assistant.tools.security import build_security_tools
from living_assistant.tools.desktop import build_desktop_tools
from living_assistant.tools.gittools import build_git_tools
from living_assistant.tools.browsertools import build_browser_tools
from living_assistant.tools.grouptools import build_group_tools
from living_assistant.tools.voicetools import build_voice_tools
from living_assistant.tools.routinetools import build_routine_tools
from living_assistant.tools.improvementtools import build_improvement_tools
from living_assistant.tools.calendartools import build_calendar_tools
from living_assistant.tools.personalstate import build_personal_state_tools
from living_assistant.tools.briefingtools import build_briefing_tools
from living_assistant.tools.sessiontools import build_session_tools
from living_assistant.tools.experiencetools import build_experience_tools
from living_assistant.tools.historytools import build_run_history_tools
from living_assistant.tools.connectortools import build_connector_tools
from living_assistant.tools.planning import build_planning_tools
from living_assistant.tools.registry import ToolRegistry
from living_assistant.tools.peertools import build_peer_tools
from living_assistant.system.codebase_index import CodebaseIndex
from living_assistant.system.workspace_snapshots import WorkspaceSnapshotManager
from living_assistant.system.peer_agents import PeerAgentManager

@dataclass
class Runtime:
    config: dict
    profile: str
    hardware: object
    workspace: Workspace
    snapshots: WorkspaceSnapshotManager
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
    repairs: AutonomousRepairLoop
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
    knowledge_gaps: KnowledgeGapDetector
    run_history: RunHistoryStore
    model_usage: ModelUsageStore
    code_index: CodebaseIndex
    planner: TaskGraphManager
    events_bus: EventBus
    def dispatch(self, event_type: str, data: dict[str, Any] = None) -> Any:
        return self.orchestrator.dispatch(event_type, data)
    orchestrator: Orchestrator
    mobile_bridge: MobileBridge
    peers: PeerAgentManager
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
    notifier=Notifier(quiet_provider=personal.is_quiet, approval_sound_enabled=bool(cfg.get('notifications',{}).get('approval_sound',True)))
    approvals=ApprovalStore(); approval=ApprovalManager(interactive=interactive,store=approvals,notifier=notifier)
    snapshot_cfg=cfg.get('workspace_snapshots',{})
    snapshots=WorkspaceSnapshotManager(
        ws, db_path=approvals.path,
        max_files=int(snapshot_cfg.get('max_files',50000)),
        max_total_bytes=int(snapshot_cfg.get('max_total_bytes',2000000000)),
        retention_per_root=int(snapshot_cfg.get('retention_per_root',30)),
    )
    memory=MemoryStore(); processes=ProcessRegistry(); watches=WatchRegistry(); skills=SkillRegistry()
    resources=ResourceManager(profile,cfg,hardware=hw); quarantine=QuarantineVault(); routines=RoutineRegistry()
    improvement_store=ImprovementStore(); improvements=ImprovementEngine(ws,approval,improvement_store,snapshot_manager=snapshots)
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
    guardian=SecurityGuardian(cfg,approval=approval)
    security_sensors=SecuritySensorPlatform(cfg,approval=approval,guardian=guardian)
    experiences=ExperienceEngine(config=cfg)
    knowledge_gaps=KnowledgeGapDetector(experiences,cfg)
    run_history=RunHistoryStore(approvals.path, retention_days=int(cfg.get('run_history',{}).get('retention_days',365)))
    model_usage=ModelUsageStore(approvals.path, retention_days=int(cfg.get('model_usage',{}).get('retention_days',365)))
    index_cfg=cfg.get('code_index',{})
    code_index=CodebaseIndex(
        ws,
        dimensions=int(index_cfg.get('dimensions',512)),
        max_files=int(index_cfg.get('max_files',2000)),
        max_file_bytes=int(index_cfg.get('max_file_bytes',512000)),
        max_chunk_chars=int(index_cfg.get('max_chunk_chars',3500)),
        max_chunks=int(index_cfg.get('max_chunks',12000)),
    )
    briefings=BriefingEngine(cfg,personal,memory,calendar,projects,processes,approvals,notifier,guardian=guardian,experiences=experiences)
    planner=TaskGraphManager(approvals.path)
    events_bus=EventBus(max_events=int(cfg.get('ui',{}).get('activity_history',500)), path=approvals.path)

    ocfg=cfg.get('ollama',{})
    ollama_provider=OllamaProvider(
        base_url=ocfg['base_url'], allow_remote=bool(ocfg.get('allow_remote',False)),
        allow_insecure_remote=bool(ocfg.get('allow_insecure_remote',False)),
    )
    aircfg=cfg.get('airllm',{})
    configured_airllm=[]
    for profile_cfg in cfg.get('profiles',{}).values():
        if not isinstance(profile_cfg,dict):
            continue
        for model_name in (profile_cfg.get('models') or {}).values():
            if AirLLMProvider.is_airllm_model(str(model_name or '')):
                configured_airllm.append(str(model_name))
    if bool(aircfg.get('enabled',False)) or configured_airllm:
        airllm_provider=AirLLMProvider(
            configured_models=configured_airllm,
            compression=aircfg.get('compression'),
            layer_shards_saving_path=aircfg.get('layer_shards_saving_path'),
            hf_token_env=str(aircfg.get('hf_token_env','HF_TOKEN')),
            prefetching=bool(aircfg.get('prefetching',True)),
            delete_original=bool(aircfg.get('delete_original',False)),
            max_input_tokens=int(aircfg.get('max_input_tokens',8192)),
            max_new_tokens=int(aircfg.get('max_new_tokens',512)),
        )
        provider=CompositeModelProvider(ollama_provider,airllm_provider)
    else:
        provider=ollama_provider
    mm=ModelManager(provider, resource_manager=resources, event_bus=events_bus)
    desktop_controller=DesktopController(ws, approval, cfg, provider=provider, model_manager=mm, quiet_provider=personal.is_quiet)
    keep_alive=int(cfg['ollama'].get('keep_alive_seconds',45)); context_tokens=int(pcfg.get('context_tokens',4096))
    browser_cfg=cfg.get('browser',{})
    browser_enabled=bool(browser_cfg.get('enabled',True)) and (profile!='lite' or bool(browser_cfg.get('lite_enabled',False)))
    browser=BrowserController(ws,approval,headless=bool(browser_cfg.get('headless',False)),quiet_provider=personal.is_quiet)

    specialists=SpecialistRouter(
        mm, pcfg['models'], keep_alive=keep_alive, max_handoffs=int(pcfg['max_handoffs']),
        context_tokens=context_tokens, resource_manager=resources,
        timeout_seconds=float(cfg.get('policy',{}).get('specialist_timeout_seconds',60)),
        model_usage=model_usage,
    )
    peers=PeerAgentManager(
        cfg, profile, hw.to_dict(),
        lambda role, task, context: specialists.delegate(role, task, context),
    )
    repairs=AutonomousRepairLoop(
        improvements, evaluations, approval,
        lambda task, context: specialists.delegate('coder', task, context),
        cfg,
    )

    tool_registry=ToolRegistry()
    tool_registry.extend(build_filesystem_tools(ws,approval,bool(cfg.get('policy',{}).get('require_write_approval',False)),snapshots))
    tool_registry.extend(build_shell_tools(ws,approval,cfg,processes,event_bus=events_bus,snapshot_manager=snapshots))
    tool_registry.extend(build_project_tools(ws,projects,code_index,snapshots,approval))
    tool_registry.extend(build_group_tools(group_controller))
    tool_registry.extend(build_git_tools(ws,approval))
    tool_registry.extend(build_web_tools(ws,cfg,approval,quarantine,browser=browser,snapshot_manager=snapshots))
    tool_registry.extend(build_browser_tools(browser,enabled=browser_enabled))
    tool_registry.extend(build_database_tools(cfg))
    tool_registry.extend(build_personal_tools(memory,notifier))
    tool_registry.extend(build_calendar_tools(calendar))
    tool_registry.extend(build_personal_state_tools(personal))
    tool_registry.extend(build_briefing_tools(briefings))
    tool_registry.extend(build_session_tools(sessions))
    tool_registry.extend(build_experience_tools(experiences, knowledge_gaps))
    tool_registry.extend(build_run_history_tools(run_history))
    tool_registry.extend(build_peer_tools(peers))
    tool_registry.extend(build_planning_tools(planner))
    if bool(cfg.get('connectors',{}).get('enabled',True)):
        tool_registry.extend(build_connector_tools(connector_manager))
    tool_registry.extend(build_routine_tools(routines))
    tool_registry.extend(build_improvement_tools(improvements, evaluations, canaries, repairs))
    tool_registry.extend(build_voice_tools(voice))
    tool_registry.extend(build_security_tools(ws,approval,guardian,security_sensors))
    if bool(cfg.get('desktop',{}).get('enabled',True)):
        tool_registry.extend(build_desktop_tools(ws,approval,desktop_controller))
    tools=tool_registry.all()

    orchestrator=Orchestrator(mm,pcfg['models']['orchestrator'],tools,specialists,
                              keep_alive=keep_alive,max_steps=int(pcfg['max_tool_steps']),context_tokens=context_tokens,
                              skills=skills,resource_manager=resources,session_store=(sessions if bool(session_cfg.get('enabled',True)) else None),
                              max_session_messages=int(session_cfg.get('max_context_messages',24)), experiences=experiences, event_bus=events_bus, run_history=run_history, model_usage=model_usage)
    mobile_bridge=MobileBridge(cfg, connector_manager, orchestrator)
    return Runtime(cfg,profile,hw,ws,snapshots,memory,projects,groups,group_controller,processes,approvals,
                   approval,watches,skills,notifier,resources,quarantine,voice,routines,improvements,evaluations,repairs,canaries,browser,
                   personal,calendar,sessions,connectors,connector_manager,briefings,guardian,security_sensors,experiences,knowledge_gaps,run_history,model_usage,code_index,planner,events_bus,orchestrator,mobile_bridge,peers,mm,desktop_controller)
