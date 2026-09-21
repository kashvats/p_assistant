from __future__ import annotations

from living_assistant.learning.experience import ExperienceEngine
from living_assistant.learning.knowledge_gap_detection import KnowledgeGapDetector
from living_assistant.tools.experiencetools import build_experience_tools


def _engine(tmp_path):
    return ExperienceEngine(
        tmp_path / "experience.sqlite3",
        {"experience": {"enabled": True, "auto_capture": True, "episode_retention_days": 365}},
    )


def test_recurring_failed_topic_surfaces_as_learning_opportunity(tmp_path):
    exp = _engine(tmp_path)
    tasks = [
        "configure kafka consumer lag monitor",
        "configure kafka consumer lag alert",
        "configure kafka consumer lag dashboard",
    ]
    for task in tasks:
        exp.record_episode(task, "shell", {"cmd": "check"}, {"ok": False, "error": "timeout"}, project="retail")
    exp.record_episode(
        "configure kafka consumer lag monitor",
        "shell",
        {"cmd": "check"},
        {"ok": True},
        project="retail",
    )

    detector = KnowledgeGapDetector(exp, {"knowledge_gaps": {"similarity_threshold": 0.4}})
    result = detector.detect(project="retail", min_failures=2, min_failure_rate=0.5)
    assert result["ok"] is True
    assert result["gap_count"] >= 1
    gap = result["learning_opportunities"][0]
    assert gap["failures"] >= 3
    assert "kafka" in gap["keywords"]
    assert "learning_opportunity" in gap


def test_single_failure_is_not_called_a_consistent_gap(tmp_path):
    exp = _engine(tmp_path)
    exp.record_episode("debug redis timeout", "shell", {}, {"ok": False, "error": "timeout"}, project="one")
    detector = KnowledgeGapDetector(exp)
    result = detector.detect(project="one")
    assert result["learning_opportunities"] == []


def test_project_filter_keeps_unrelated_projects_separate(tmp_path):
    exp = _engine(tmp_path)
    for _ in range(3):
        exp.record_episode("deploy fastapi service", "shell", {}, {"ok": False}, project="alpha")
        exp.record_episode("deploy fastapi service", "shell", {}, {"ok": True}, project="beta")
    detector = KnowledgeGapDetector(exp)
    alpha = detector.detect(project="alpha", min_failure_rate=0.8)
    beta = detector.detect(project="beta", min_failure_rate=0.8)
    assert alpha["gap_count"] == 1
    assert beta["gap_count"] == 0


def test_gap_output_never_reintroduces_redacted_secret(tmp_path):
    exp = _engine(tmp_path)
    secret = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ123456"
    for _ in range(2):
        exp.record_episode(f"debug github auth {secret}", "connector", {}, {"ok": False}, project="secure")
    result = KnowledgeGapDetector(exp).detect(project="secure")
    assert secret not in str(result)
    assert "REDACTED" in str(result)


def test_experience_tools_surface_knowledge_gap_detector(tmp_path):
    exp = _engine(tmp_path)
    detector = KnowledgeGapDetector(exp)
    names = {tool.name for tool in build_experience_tools(exp, detector)}
    assert "knowledge_gaps" in names
