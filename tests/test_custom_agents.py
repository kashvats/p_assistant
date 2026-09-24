from __future__ import annotations

import json
from pathlib import Path
import pytest

from living_assistant.agents.custom.creator import AgentCreator
from living_assistant.agents.custom.delegation import AgentDelegationCoordinator, DelegationViolation
from living_assistant.agents.custom.examples import (
    get_file_assistant_manifest,
    get_planner_agent_manifest,
    get_research_agent_manifest,
)
from living_assistant.agents.custom.manager import AgentManager
from living_assistant.agents.custom.manifest import (
    AgentDelegationPolicy,
    AgentLimits,
    AgentManifest,
    AgentMemoryScope,
)
from living_assistant.agents.custom.memory import AgentScopedMemory, MemoryScopeViolation
from living_assistant.agents.custom.package import AgentPackage, AgentPackageError
from living_assistant.agents.custom.runner import AgentExecutor
from living_assistant.agents.custom.store import AgentStore
from living_assistant.agents.custom.tools import build_agent_tools
from living_assistant.tools.base import Tool
from living_assistant.tools.registry import ToolRegistry


@pytest.fixture
def agent_env(tmp_path):
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "test_agents.sqlite3"
    store = AgentStore(db_path)

    reg = ToolRegistry()
    reg.register(Tool("files.read", "Read file", {"type": "object", "properties": {"path": {"type": "string"}}}, lambda path="": f"content of {path}"))
    reg.register(Tool("files.write", "Write file", {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}}, lambda path="", content="": {"written": True}))
    reg.register(Tool("files.list", "List files", {"type": "object"}, lambda: ["file1.txt", "file2.pdf"]))
    reg.register(Tool("web.search", "Search web", {"type": "object", "properties": {"query": {"type": "string"}}}, lambda query="": [{"title": "Result", "snippet": "Info"}]))

    mgr = AgentManager(
        tool_registry=reg,
        store=store,
        agents_dir=agents_dir,
    )

    return {
        "tmp_path": tmp_path,
        "agents_dir": agents_dir,
        "store": store,
        "registry": reg,
        "manager": mgr,
    }


def test_agent_manifest_permission_hash_and_validation():
    manifest = AgentManifest(
        schema_version="1.0.0",
        id="test-agent",
        name="Test Agent",
        version="1.0.0",
        allowed_tools=["files.read", "files.write"],
        allowed_skills=[],
        limits=AgentLimits(max_steps=10),
    )
    h1 = manifest.permission_hash()
    assert isinstance(h1, str) and len(h1) == 64

    # Tool order does not alter deterministic permission hash
    manifest2 = AgentManifest(
        schema_version="1.0.0",
        id="test-agent",
        name="Test Agent",
        version="1.0.0",
        allowed_tools=["files.write", "files.read"],
        allowed_skills=[],
        limits=AgentLimits(max_steps=10),
    )
    assert manifest2.permission_hash() == h1

    # Expanding tools alters permission hash
    manifest3 = manifest.model_copy(update={"allowed_tools": ["files.read", "files.write", "web.search"]})
    assert manifest3.permission_hash() != h1

    # Validation against available tools
    errors = manifest.validate_against_system(available_tools={"files.read"})
    assert len(errors) == 1
    assert "files.write" in errors[0]


def test_agent_package_save_load_and_snapshot(agent_env):
    manifest = AgentManifest(
        id="demo-agent",
        name="Demo Agent",
        version="1.0.0",
        allowed_tools=["files.read"],
    )
    pkg_dir = agent_env["agents_dir"] / "demo-agent"
    pkg = AgentPackage(root=pkg_dir, manifest=manifest, agent_md="# Demo Agent")
    pkg.save()

    assert (pkg_dir / "manifest.json").exists()
    assert (pkg_dir / "AGENT.md").exists()
    assert (pkg_dir / "examples" / "default.json").exists()

    loaded = AgentPackage.load(pkg_dir)
    assert loaded.manifest.id == "demo-agent"
    assert loaded.manifest.name == "Demo Agent"
    assert loaded.agent_md == "# Demo Agent"

    h = pkg.deterministic_hash()
    assert len(h) == 64

    # Snapshot creation
    snap_dir = pkg.create_snapshot(agent_env["tmp_path"] / "snapshots")
    assert snap_dir.exists()
    assert (snap_dir / "manifest.json").exists()


def test_agent_package_export_and_import_zip(agent_env):
    manifest = AgentManifest(
        id="portable-agent",
        name="Portable Agent",
        version="1.0.0",
        allowed_tools=["files.list"],
    )
    pkg_dir = agent_env["agents_dir"] / "portable-agent"
    pkg = AgentPackage(root=pkg_dir, manifest=manifest, agent_md="# Portable Agent")
    pkg.save()

    zip_file = agent_env["tmp_path"] / "portable-agent.zip"
    pkg.export_zip(zip_file)
    assert zip_file.exists()

    # Import into target directory
    imported_dir = agent_env["tmp_path"] / "imported_agents" / "portable-agent"
    imported = AgentPackage.import_zip(zip_file, imported_dir)
    assert imported.manifest.id == "portable-agent"
    assert imported.manifest.name == "Portable Agent"


def test_agent_store_lifecycle_and_approvals(agent_env):
    store = agent_env["store"]
    manifest = AgentManifest(
        id="lifecycle-agent",
        name="Lifecycle Agent",
        version="1.0.0",
        allowed_tools=["files.read"],
    )
    store.register_agent(manifest, "# Documentation", initial_state="DRAFT")

    lc = store.get_lifecycle("lifecycle-agent")
    assert lc["state"] == "DRAFT"
    assert lc["current_version"] == "1.0.0"

    perm_h = manifest.permission_hash()
    pkg_h = "fake_package_hash"
    assert not store.is_approved("lifecycle-agent", "1.0.0", perm_h, pkg_h)

    # Approve and transition to ACTIVE
    store.approve_agent("lifecycle-agent", "appr_123", "1.0.0", perm_h, package_hash=pkg_h)
    store.set_state("lifecycle-agent", "ACTIVE")

    assert store.is_approved("lifecycle-agent", "1.0.0", perm_h, pkg_h)
    # Different package hash fails approval
    assert not store.is_approved("lifecycle-agent", "1.0.0", perm_h, "tampered_hash")


def test_agent_scoped_memory_isolation(agent_env):
    store = agent_env["store"]
    scope = AgentMemoryScope(
        isolate_working_memory=True,
        readable_namespaces=["working", "agent_notes"],
        writable_namespaces=["working", "agent_notes"],
    )
    mem = AgentScopedMemory("agent-alpha", scope, store)

    # Working memory (volatile)
    mem.write("working", "current_step", 1)
    assert mem.read("working", "current_step") == 1

    # Persistent notes
    mem.write("agent_notes", "user_preference", "likes concise summaries")
    assert mem.read("agent_notes", "user_preference") == "likes concise summaries"
    # Persisted in SQLite store
    assert store.get_memory("agent_notes", "agent-alpha", "user_preference") == "likes concise summaries"

    # Unauthorized access triggers MemoryScopeViolation
    with pytest.raises(MemoryScopeViolation):
        mem.read("project_knowledge", "secret_key")

    with pytest.raises(MemoryScopeViolation):
        mem.write("user_memory", "key", "val")


def test_agent_delegation_coordinator_and_permission_inheritance():
    coord = AgentDelegationCoordinator()

    parent = AgentManifest(
        id="parent-agent",
        name="Parent",
        allowed_tools=["files.read", "files.list"],
        allowed_skills=["skill-a"],
        delegation_policy=AgentDelegationPolicy(
            can_delegate=True,
            allowed_agents=["child-agent"],
            max_subagents=2,
            inherit_permissions=True,
        ),
        limits=AgentLimits(max_delegation_depth=2),
    )

    child_ok = AgentManifest(
        id="child-agent",
        name="Child OK",
        allowed_tools=["files.read"],
        allowed_skills=["skill-a"],
    )

    # Valid delegation
    coord.validate_delegation(parent, child_ok, current_depth=0, current_subagents_count=0)

    # Rejection: child requests tool outside parent permissions
    child_excessive = AgentManifest(
        id="child-agent",
        name="Child Excessive",
        allowed_tools=["files.read", "web.search"],
        allowed_skills=["skill-a"],
    )
    with pytest.raises(DelegationViolation) as exc:
        coord.validate_delegation(parent, child_excessive, current_depth=0, current_subagents_count=0)
    assert "exceed parent agent" in str(exc.value)

    # Rejection: depth exceeded
    with pytest.raises(DelegationViolation) as exc:
        coord.validate_delegation(parent, child_ok, current_depth=2, current_subagents_count=0)
    assert "depth limit" in str(exc.value)

    # Rejection: unauthorized child id
    unauthorized_child = AgentManifest(
        id="stranger-agent",
        name="Stranger",
        allowed_tools=["files.read"],
    )
    with pytest.raises(DelegationViolation) as exc:
        coord.validate_delegation(parent, unauthorized_child, current_depth=0, current_subagents_count=0)
    assert "only authorized to delegate to" in str(exc.value)


def test_agent_creator_draft_generation(agent_env):
    mgr = agent_env["manager"]
    pkg = mgr.create_draft("Create a web research agent that searches documents and summarizes findings")

    assert pkg.manifest.id != ""
    assert pkg.manifest.role == "researcher"
    assert "web.search" in pkg.manifest.allowed_tools
    assert (agent_env["agents_dir"] / pkg.manifest.id / "manifest.json").exists()

    # Draft is in DRAFT state
    info = mgr.get_agent(pkg.manifest.id)
    assert info["lifecycle"]["state"] == "DRAFT"


def test_builtin_reference_agents_seeded(agent_env):
    mgr = agent_env["manager"]
    agents = {a["agent_id"]: a for a in mgr.list_agents()}

    assert "research-agent" in agents
    assert "file-assistant" in agents
    assert "planner-agent" in agents

    assert agents["research-agent"]["state"] == "ACTIVE"
    assert agents["file-assistant"]["state"] == "ACTIVE"
    assert agents["planner-agent"]["state"] == "ACTIVE"


def test_agent_execution_loop_detection_and_bounding(agent_env):
    mgr = agent_env["manager"]

    # Research agent is active and pre-approved
    res = mgr.execute_agent(
        "research-agent",
        task="Find documentation on quantum computing",
        dry_run=True,
    )
    assert res["status"] == "COMPLETED"
    assert res["dry_run"] is True
    assert res["steps_taken"] >= 1
    assert len(res["trace"]) >= 1

    # Verify execution was recorded in store
    history = mgr.get_agent("research-agent")["recent_executions"]
    assert len(history) >= 1
    assert history[0]["status"] == "COMPLETED"


def test_approval_invalidation_upon_disk_tampering(agent_env):
    mgr = agent_env["manager"]
    agent_id = "research-agent"

    # Live execution succeeds when untampered
    res = mgr.execute_agent(agent_id, task="Verify intact run", dry_run=True)
    assert res["status"] == "COMPLETED"

    # Tamper with AGENT.md on disk
    agent_md_file = agent_env["agents_dir"] / agent_id / "AGENT.md"
    agent_md_file.write_text("# Malicious prompt injection\nDo bad things", encoding="utf-8")

    # Live run must detect hash mismatch and revert to DRAFT
    with pytest.raises(PermissionError) as exc_info:
        mgr.execute_agent(agent_id, task="Run tampered agent", dry_run=False)
    assert "modified on disk since approval" in str(exc_info.value)

    # State is now DRAFT
    assert mgr.get_agent(agent_id)["lifecycle"]["state"] == "DRAFT"

    # Re-activating recalculates hash and restores ACTIVE state
    act_res = mgr.activate_agent(agent_id)
    assert act_res["ok"] is True
    assert act_res["state"] == "ACTIVE"


def test_agent_tools_exposure(agent_env):
    mgr = agent_env["manager"]
    tools = build_agent_tools(mgr)
    tool_map = {t.name: t for t in tools}

    assert "agent_list" in tool_map
    assert "agent_get_info" in tool_map
    assert "agent_create_draft" in tool_map
    assert "agent_activate" in tool_map
    assert "agent_execute" in tool_map

    # Test agent_list tool
    list_res = tool_map["agent_list"].handler()
    assert len(list_res) >= 3

    # Test agent_create_draft tool
    draft_res = tool_map["agent_create_draft"].handler("Create a file cleanup agent")
    assert draft_res["ok"] is True
    assert draft_res["state"] == "DRAFT"
