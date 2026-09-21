from __future__ import annotations

from living_assistant.approval import ApprovalManager, ApprovalStore
from living_assistant.improvements import ImprovementEngine, ImprovementStore
from living_assistant.learning.patch_engine import ASTSafePatchEngine
from living_assistant.workspace import Workspace


def _engine(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    approvals = ApprovalStore(tmp_path / "approval.sqlite3")
    return project, ImprovementEngine(
        Workspace([project]),
        ApprovalManager(interactive=False, store=approvals),
        ImprovementStore(tmp_path / "improvements.sqlite3"),
    )


def test_ast_patch_allows_modifying_existing_function_without_deleting_neighbors(tmp_path):
    project, engine = _engine(tmp_path)
    target = project / "module.py"
    target.write_text("def a():\n    return 1\n\ndef b():\n    return 2\n")
    proposed = "def a():\n    return 10\n\ndef b():\n    return 2\n"
    result = engine.propose("module.py", proposed, "change a", "test")
    assert result.get("id")
    assert result["patch_analysis"]["changed_symbols"] == ["a"]
    assert result["patch_analysis"]["removed_symbols"] == []


def test_ast_patch_blocks_accidental_function_deletion(tmp_path):
    project, engine = _engine(tmp_path)
    target = project / "module.py"
    target.write_text("def a():\n    return 1\n\ndef b():\n    return 2\n")
    result = engine.propose("module.py", "def a():\n    return 10\n", "bad rewrite", "test")
    assert result["blocked"] is True
    assert result["ast_guard"] is True
    assert "b" in result["removed_symbols"]
    assert engine.store.list() == []


def test_ast_patch_blocks_syntax_invalid_python(tmp_path):
    project, engine = _engine(tmp_path)
    (project / "module.py").write_text("def a():\n    return 1\n")
    result = engine.propose("module.py", "def a(:\n    pass\n", "bad syntax", "test")
    assert result["blocked"] is True
    assert "syntactically valid" in result["error"]


def test_ast_patch_tracks_methods_not_just_top_level_functions():
    patch = ASTSafePatchEngine().analyze(
        "class Service:\n    def start(self):\n        pass\n    def stop(self):\n        pass\n",
        "class Service:\n    def start(self):\n        pass\n",
        "service.py",
    )
    assert patch["ok"] is False
    assert "Service.stop" in patch["removed_symbols"]


def test_non_python_content_keeps_exact_file_diff_behavior():
    patch = ASTSafePatchEngine().analyze("a=1\n", "a=2\n", "settings.toml")
    assert patch["ok"] is True
    assert patch["ast_checked"] is False
    assert "-a=1" in patch["diff"] and "+a=2" in patch["diff"]


def test_apply_revalidates_stored_python_content_before_approval(tmp_path):
    project, engine = _engine(tmp_path)
    target = project / "module.py"
    target.write_text("def a():\n    return 1\n\ndef b():\n    return 2\n")
    created = engine.propose(
        "module.py",
        "def a():\n    return 10\n\ndef b():\n    return 2\n",
        "safe",
        "test",
    )
    engine.store.conn.execute(
        "UPDATE improvement_proposals SET proposed_content=? WHERE id=?",
        ("def a():\n    return 99\n", created["id"]),
    )
    engine.store.conn.commit()
    result = engine.apply(created["id"])
    assert result["blocked"] is True
    assert result["ast_guard"] is True
    assert "b" in result["removed_symbols"]
    assert target.read_text() == "def a():\n    return 1\n\ndef b():\n    return 2\n"
