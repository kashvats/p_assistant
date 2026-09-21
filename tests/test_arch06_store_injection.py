from __future__ import annotations

import inspect

from living_assistant.connectors.connectors import ConnectorRegistry
from living_assistant.core.approval import ApprovalStore
from living_assistant.core.calendar_store import CalendarStore
from living_assistant.core.memory import MemoryStore
from living_assistant.core.personal_state import PersonalState
from living_assistant.core.sessions import SessionStore
from living_assistant.core.skills import SkillRegistry
from living_assistant.learning.canary import CanaryStore
from living_assistant.learning.eval_store import EvaluationStore
from living_assistant.learning.experience import ExperienceEngine
from living_assistant.learning.improvements import ImprovementStore
from living_assistant.security.quarantine import QuarantineVault
from living_assistant.security.security_guardian import SecurityGuardian
from living_assistant.security.security_sensors import SecuritySensorPlatform
from living_assistant.system.groups import ProjectGroupRegistry
from living_assistant.system.notifications import Notifier
from living_assistant.system.routines import RoutineRegistry
from living_assistant.system.watchers import WatchRegistry
from living_assistant.tools.projects import ProjectRegistry
from living_assistant.tools.shell import ProcessRegistry


STORE_PATH_PARAMETERS = {
    ConnectorRegistry: "path",
    ApprovalStore: "path",
    CalendarStore: "path",
    MemoryStore: "path",
    PersonalState: "path",
    SessionStore: "path",
    SkillRegistry: "path",
    CanaryStore: "path",
    EvaluationStore: "path",
    ExperienceEngine: "path",
    ImprovementStore: "path",
    QuarantineVault: "root",
    SecurityGuardian: "db_path",
    SecuritySensorPlatform: "db_path",
    ProjectGroupRegistry: "path",
    Notifier: "queue_path",
    RoutineRegistry: "path",
    WatchRegistry: "path",
    ProjectRegistry: "path",
    ProcessRegistry: "meta_path",
}


def test_persistent_stores_keep_injectable_storage_paths():
    missing = []
    for cls, parameter in STORE_PATH_PARAMETERS.items():
        if parameter not in inspect.signature(cls.__init__).parameters:
            missing.append(f"{cls.__module__}.{cls.__name__}:{parameter}")
    assert missing == []
