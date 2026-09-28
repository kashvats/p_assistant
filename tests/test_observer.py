from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from living_assistant.core.event_bus import EventBus
from living_assistant.learning.experience import ExperienceEngine
from living_assistant.system.observer import ProactiveInquiry, ProactiveScreenObserver


def test_proactive_inquiry_dataclass_serialization():
    inq = ProactiveInquiry(
        id="inq_123",
        question="Did this fix the issue?",
        context="VSCode main.py",
        recovery_candidate={"action": "add check"},
        created_at="2026-09-27T12:00:00",
        status="pending",
    )
    d = inq.to_dict()
    assert d["id"] == "inq_123"
    assert d["status"] == "pending"
    assert d["recovery_candidate"]["action"] == "add check"


def test_proactive_screen_observer_inquiry_lifecycle(tmp_path):
    bus = EventBus()
    db_file = tmp_path / "exp.db"
    exp = ExperienceEngine(path=db_file)

    observer = ProactiveScreenObserver(event_bus=bus, experience_engine=exp)

    inq = observer.trigger_inquiry(
        question="Did fix work?",
        context="Error in terminal",
        recovery_candidate={"situation": "Terminal build failure", "action_taken": "Fixed typo"},
    )
    assert inq.id.startswith("inq_")

    pending = observer.get_pending_inquiries()
    assert len(pending) == 1
    assert pending[0]["id"] == inq.id

    res = observer.resolve_inquiry(inq.id, fixed=True, feedback="Verified resolved")
    assert res["ok"] is True
    assert res["fixed"] is True
    assert res["learned_lesson"] is not None

    lessons = exp.list(limit=10)
    assert len(lessons) >= 1
    assert any("Terminal build failure" in str(l.get("situation", "")) for l in lessons)

    assert len(observer.get_pending_inquiries()) == 0
