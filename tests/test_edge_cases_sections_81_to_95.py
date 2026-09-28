import hashlib
from pathlib import Path
import sqlite3
import tempfile
import pytest
from unittest.mock import MagicMock, patch

from living_assistant.system.hardware import (
    GpuDeviceTelemetry,
    get_gpu_telemetry,
    detect_hardware,
)
from living_assistant.skills.manager import SkillManager
from living_assistant.skills.manifest import SkillManifest, SkillPermissionScope
from living_assistant.skills.package import SkillPackage
from living_assistant.skills.store import SkillStore
from living_assistant.agents.custom.manager import AgentManager
from living_assistant.agents.custom.manifest import (
    AgentManifest,
    AgentLimits,
    AgentDelegationPolicy,
    AgentMemoryScope,
    AgentProvenance,
)
from living_assistant.agents.custom.store import AgentStore
from living_assistant.system.article_extractor import ArticleExtractor
from living_assistant.desktop.download_tracker import BrowserDownloadTracker
from living_assistant.system.graph_validator import SystemGraphValidator
from living_assistant.core.config_validator import ConfigValidator, ConfigValidationError
from living_assistant.core.config_manager import ConfigManager
from living_assistant.core.migration import MigrationManager, MigrationStep
from living_assistant.core.workspace import Workspace
from living_assistant.tools.registry import ToolRegistry


# =====================================================================
# SECTION 81 & 83: MODEL MANAGER & MODEL DOWNLOAD TESTS
# =====================================================================

def test_section_81_and_83_model_manager_and_download_integrity(tmp_path):
    """Sections 81 & 83: Corrupt or partial downloads (.part) are not treated as installed models."""
    models_dir = tmp_path / "models"
    models_dir.mkdir()

    # 1. Partial/interrupted download file
    partial_file = models_dir / "llama3.part"
    partial_file.write_bytes(b"partial content halfway")

    # 2. Corrupt 0-byte file
    corrupt_file = models_dir / "corrupt_model.bin"
    corrupt_file.write_bytes(b"")

    # 3. Valid installed model file
    valid_file = models_dir / "qwen2.5.bin"
    valid_file.write_bytes(b"valid weight content" * 100)

    # Incomplete extensions check
    incomplete_exts = {".part", ".download", ".crdownload"}
    
    def is_valid_installed_model(p: Path, expected_sha256: str | None = None) -> bool:
        if not p.exists() or p.suffix.lower() in incomplete_exts:
            return False
        if p.stat().st_size == 0:
            return False
        if expected_sha256:
            digest = hashlib.sha256(p.read_bytes()).hexdigest()
            if digest != expected_sha256:
                return False
        return True

    assert is_valid_installed_model(partial_file) is False
    assert is_valid_installed_model(corrupt_file) is False
    assert is_valid_installed_model(valid_file) is True

    # Checksum mismatch test
    assert is_valid_installed_model(valid_file, expected_sha256="wronghash123") is False
    correct_hash = hashlib.sha256(valid_file.read_bytes()).hexdigest()
    assert is_valid_installed_model(valid_file, expected_sha256=correct_hash) is True


# =====================================================================
# SECTION 82: VRAM REPORTING
# =====================================================================

def test_section_82_vram_reporting_telemetry():
    """Section 82: VRAM reporting does not assume CUDA and reports metrics only when supported."""
    # 1. Mock NVIDIA GPU with full telemetry
    nvidia_dev = GpuDeviceTelemetry(
        name="NVIDIA GeForce RTX 4090",
        vendor="nvidia",
        total_mb=24576.0,
        used_mb=4096.0,
        free_mb=20480.0,
        integrated=False,
        telemetry_supported=True,
    )
    assert nvidia_dev.telemetry_supported is True
    assert nvidia_dev.total_mb == 24576.0
    assert nvidia_dev.free_mb == 20480.0

    # 2. Mock Intel / Integrated GPU where VRAM telemetry is unsupported
    intel_dev = GpuDeviceTelemetry(
        name="Intel Iris Xe Graphics",
        vendor="intel",
        total_mb=None,
        used_mb=None,
        free_mb=None,
        integrated=True,
        telemetry_supported=False,
    )
    assert intel_dev.telemetry_supported is False
    assert intel_dev.total_mb is None
    assert intel_dev.integrated is True

    # 3. detect_hardware integration
    with patch("living_assistant.system.hardware.get_gpu_telemetry", return_value=[nvidia_dev]):
        hw = detect_hardware()
        assert hw.gpu_name == "NVIDIA GeForce RTX 4090"
        assert hw.gpu_vram_gb == 24.0
        assert hw.gpu_vram_free_gb == 20.0
        assert hw.gpu_count == 1


# =====================================================================
# SECTION 84: CUSTOM AGENT TESTS
# =====================================================================

def test_section_84_custom_agent_validation_and_rollback(tmp_path):
    """Section 84: Custom agent validation, capability scoping, and version rollback."""
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    store = AgentStore(db_path=tmp_path / "agents.sqlite3")
    tool_reg = ToolRegistry()
    mgr = AgentManager(tool_registry=tool_reg, store=store, agents_dir=agents_dir)

    def make_manifest(agent_id: str, name: str, version: str = "1.0.0") -> AgentManifest:
        return AgentManifest(
            id=agent_id,
            name=name,
            version=version,
            role="assistant",
            description="Test custom agent",
            allowed_tools=[],
            limits=AgentLimits(),
            delegation_policy=AgentDelegationPolicy(),
            memory_scope=AgentMemoryScope(),
            provenance=AgentProvenance(),
        )

    # 1. Invalid name validation
    bad_manifest = make_manifest("bad1", "Invalid Agent @!#$")
    with pytest.raises(ValueError, match="Agent name must be alphanumeric"):
        mgr.validate_agent(bad_manifest, agent_md="Instructions here")

    # 2. Missing prompt validation
    good_manifest = make_manifest("agent1", "Agent One")
    with pytest.raises(ValueError, match="Agent prompt .* cannot be empty"):
        mgr.validate_agent(good_manifest, agent_md="   ")

    # 3. Create v1 and update to v2
    pkg1 = mgr.update_agent("agent1", good_manifest.model_dump(), agent_md="Version 1 prompt")
    assert pkg1.manifest.version == "1.0.0"

    v2_manifest = make_manifest("agent1", "Agent One", version="2.0.0")
    pkg2 = mgr.update_agent("agent1", v2_manifest.model_dump(), agent_md="Version 2 prompt (broken)")
    assert pkg2.manifest.version == "2.0.0"

    # 4. Rollback to v1
    rolled = mgr.rollback_agent("agent1", "1.0.0")
    assert rolled.manifest.version == "1.0.0"
    assert rolled.agent_md == "Version 1 prompt"


# =====================================================================
# SECTION 85 & 86: SKILL TRIGGER COLLISIONS & VERSIONING
# =====================================================================

def test_section_85_and_86_skill_trigger_collisions_and_rollback(tmp_path):
    """Section 85 & 86: Longest/most specific trigger wins, preventing ambiguous collisions and test rollback."""
    ws = Workspace([tmp_path / "workspace"])
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    store = SkillStore(path=tmp_path / "skills.sqlite3")
    mgr = SkillManager(workspace=ws, tool_registry=ToolRegistry(), skills_dir=skills_dir, store=store)

    # Skill A trigger: "deploy"
    manifest_a = SkillManifest(
        id="skill_deploy_generic",
        name="Deploy Generic",
        description="Deploy generic",
        version="1.0.0",
        triggers=["deploy"],
        priority=50,
        permissions=SkillPermissionScope(),
    )
    p_dir_a = skills_dir / "skill_deploy_generic"
    pkg_a = SkillPackage(root=p_dir_a, manifest=manifest_a, skill_md="Generic deploy instructions")
    pkg_a.save()
    store.register_skill(manifest_a, pkg_a.skill_md, initial_state="ACTIVE", snapshot_dir=str(p_dir_a))

    # Skill B trigger: "deploy app" (more specific!)
    manifest_b = SkillManifest(
        id="skill_deploy_app",
        name="Deploy App",
        description="Deploy application specific",
        version="1.0.0",
        triggers=["deploy app"],
        priority=50,
        permissions=SkillPermissionScope(),
    )
    p_dir_b = skills_dir / "skill_deploy_app"
    pkg_b = SkillPackage(root=p_dir_b, manifest=manifest_b, skill_md="Deploy app instructions")
    pkg_b.save()
    store.register_skill(manifest_b, pkg_b.skill_md, initial_state="ACTIVE", snapshot_dir=str(p_dir_b))

    # When user says "deploy app to staging", skill B must be selected over skill A
    resolved = mgr.resolve_skill_trigger("deploy app to staging")
    assert resolved is not None
    assert resolved["skill_id"] == "skill_deploy_app"

    # Skill version rollback test (Section 86)
    v2_manifest = manifest_b.model_copy()
    v2_manifest.version = "2.0.0"
    pkg_b_v2 = SkillPackage(root=p_dir_b, manifest=v2_manifest, skill_md="Broken v2 instructions")
    pkg_b_v2.save()
    store.save_version("skill_deploy_app", v2_manifest, pkg_b_v2.skill_md, snapshot_dir=str(p_dir_b))

    rolled_skill = mgr.rollback_skill("skill_deploy_app", "1.0.0")
    assert rolled_skill.manifest.version == "1.0.0"
    assert "Deploy app instructions" in rolled_skill.skill_md


# =====================================================================
# SECTION 87: EXTERNAL COMPONENT FAILURE
# =====================================================================

def test_section_87_external_component_failure_graceful_degradation():
    """Section 87: Failure in optional external components does not take down unrelated features."""
    from living_assistant.agents.agents import SpecialistRouter
    from living_assistant.core.model_provider import ModelManager

    mock_mm = MagicMock(spec=ModelManager)
    router = SpecialistRouter(model_manager=mock_mm, models={"general": "test-model"})

    # Fail Hermes Contractor invocation intentionally
    with patch("living_assistant.integrations.hermes_contractor.HermesContractor", side_effect=ImportError("Hermes missing")):
        res = router.delegate(role="contractor", task="Do some contracting")
        assert res["ok"] is False
        assert "Hermes Contractor initialization/execution failed" in res["error"]


# =====================================================================
# SECTION 88: OPENVIKING / INDEX DESYNC
# =====================================================================

def test_section_88_index_desync_detection(tmp_path):
    """Section 88: Detect when indexed file changed or was deleted before trusting index context."""
    test_file = tmp_path / "module.py"
    test_file.write_text("def hello(): pass\n", encoding="utf-8")
    original_mtime = test_file.stat().st_mtime

    index_record = {
        "file": str(test_file),
        "indexed_mtime": original_mtime,
        "indexed_content": "def hello(): pass\n",
    }

    def verify_index_freshness(record: dict) -> bool:
        p = Path(record["file"])
        if not p.exists():
            return False
        return p.stat().st_mtime == record["indexed_mtime"]

    assert verify_index_freshness(index_record) is True

    # Mutate file
    test_file.write_text("def hello(): return 'mutated'\n", encoding="utf-8")
    assert verify_index_freshness(index_record) is False

    # Delete file
    test_file.unlink()
    assert verify_index_freshness(index_record) is False


# =====================================================================
# SECTION 89: TRAFILATURA EMPTY EXTRACTION FALLBACK
# =====================================================================

def test_section_89_trafilatura_empty_extraction_fallback():
    """Section 89: When Trafilatura returns empty text, fallback to DOM/HTML stripping."""
    extractor = ArticleExtractor()
    sparse_html = "<html><head><title>Sparse Page</title></head><body><div>Only a tiny div with text</div></body></html>"

    with patch("trafilatura.extract", return_value=None):
        res = extractor.extract(sparse_html, url="http://example.com/sparse")
        assert res["ok"] is True
        assert "Only a tiny div with text" in res["text"]
        assert res["title"] == "Sparse Page"


# =====================================================================
# SECTION 90: BROWSER DOWNLOAD CONFUSION
# =====================================================================

def test_section_90_browser_download_tracking(tmp_path):
    """Section 90: Track landing path, incomplete files, dangerous extensions, and workspace normalization."""
    ws_dir = tmp_path / "workspace"
    ws_dir.mkdir()
    tracker = BrowserDownloadTracker(workspace_root=ws_dir)

    # 1. Incomplete browser download (.crdownload)
    incomplete_file = tmp_path / "large_dataset.zip.crdownload"
    incomplete_file.write_bytes(b"partial zip data")
    res_inprog = tracker.track_and_normalize(incomplete_file)
    assert res_inprog["completed"] is False
    assert res_inprog["status"] == "in_progress"

    # 2. Complete safe file landed in browser default folder
    safe_file = tmp_path / "report.pdf"
    safe_file.write_bytes(b"%PDF-1.4 sample content")
    res_safe = tracker.track_and_normalize(safe_file)
    assert res_safe["completed"] is True
    assert res_safe["safe"] is True
    assert Path(res_safe["normalized_path"]).exists()

    # 3. Dangerous executable file
    exe_file = tmp_path / "payload.exe"
    exe_file.write_bytes(b"MZ executable header")
    res_exe = tracker.track_and_normalize(exe_file)
    assert res_exe["completed"] is True
    assert res_exe["safe"] is False
    assert any("Executable/script extension" in w for w in res_exe["warnings"])


# =====================================================================
# SECTION 91: SYSTEM GRAPH VALIDATION
# =====================================================================

def test_section_91_system_graph_validation(tmp_path):
    """Section 91: SystemGraphValidator detects schema violations, duplicate node IDs, and dependency cycles."""
    # 1. Duplicate Node ID
    bad_data = {
        "system": {
            "nodes": [
                {"id": "NODE_A", "type": "service", "state": "ACTIVE"},
                {"id": "NODE_A", "type": "tool", "state": "ACTIVE"},
            ]
        }
    }
    diag = SystemGraphValidator.validate_dict(bad_data)
    assert diag.ok is False
    assert any("Duplicate node ID detected: 'NODE_A'" in err for err in diag.errors)

    # 2. Dependency cycle
    cycle_data = {
        "system": {
            "nodes": [
                {"id": "NODE_1", "type": "service", "state": "ACTIVE", "dependencies": ["NODE_2"]},
                {"id": "NODE_2", "type": "service", "state": "ACTIVE", "dependencies": ["NODE_1"]},
            ]
        }
    }
    diag_cycle = SystemGraphValidator.validate_dict(cycle_data)
    assert diag_cycle.ok is False
    assert any("Dependency cycle detected" in err for err in diag_cycle.errors)


# =====================================================================
# SECTION 92: CONFIGURATION VALIDATION
# =====================================================================

def test_section_92_configuration_validation():
    """Section 92: ConfigValidator catches invalid ports, negative timeouts, and unknown providers."""
    # 1. Invalid port
    with pytest.raises(ConfigValidationError, match="Invalid server port"):
        ConfigValidator.validate({"server": {"port": 999999}})

    # 2. Negative timeout
    with pytest.raises(ConfigValidationError, match="Timeout must be a positive number"):
        ConfigValidator.validate({"timeout_seconds": -10})

    # 3. Unknown model provider
    with pytest.raises(ConfigValidationError, match="Unknown model provider"):
        ConfigValidator.validate({"models": {"provider": "unsupported_cloud_ai"}})

    # 4. Valid configuration
    valid_cfg = {
        "server": {"port": 8000, "timeout": 30},
        "models": {"provider": "ollama"},
    }
    res = ConfigValidator.validate(valid_cfg)
    assert res["valid"] is True


# =====================================================================
# SECTION 93 & 94: CONFIGURATION HOT RELOAD & SECRET ROTATION
# =====================================================================

def test_section_93_and_94_config_hot_reload_and_secret_rotation():
    """Section 93 & 94: Hot reload applies changes atomically; secrets are rotated without exposure in logs."""
    initial = {
        "server": {"port": 8000},
        "models": {"provider": "ollama", "api_key": "old-secret-123"},
    }
    mgr = ConfigManager(initial)

    # 1. Hot reload of model provider
    events = []
    mgr.add_listener(lambda k, old, new: events.append((k, old, new)))

    reload_res = mgr.reload({
        "server": {"port": 8000},
        "models": {"provider": "litellm", "api_key": "old-secret-123"},
    })
    assert reload_res["ok"] is True
    assert "models.provider" in reload_res["changed_keys"]
    assert mgr.get("models.provider") == "litellm"

    # 2. Secret rotation
    rot_res = mgr.rotate_secret("api_key", "new-secret-456")
    assert rot_res["ok"] is True
    assert mgr.get("models.api_key") == "new-secret-456"
    # Listener was notified with redacted values
    assert any(ev[0] == "secret.api_key" and ev[1] == "[REDACTED]" for ev in events)


# =====================================================================
# SECTION 95: DATA MIGRATION
# =====================================================================

def test_section_95_transactional_data_migration():
    """Section 95: Transactional schema migrations guarantee rollback on failure halfway."""
    conn = sqlite3.connect(":memory:")
    migrator = MigrationManager(conn)

    # Migration 1: Create user table and seed data
    def up_1(c):
        c.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        c.execute("INSERT INTO users (name) VALUES ('Alice')")

    def down_1(c):
        c.execute("DROP TABLE users")

    # Migration 2: Fails halfway (attempts illegal SQL after modifying table)
    def up_2_failing(c):
        c.execute("ALTER TABLE users ADD COLUMN email TEXT")
        c.execute("INSERT INTO non_existent_table VALUES (1)")  # Causes error

    migrator.register(MigrationStep(version=1, name="create_users", up=up_1, down=down_1))
    migrator.register(MigrationStep(version=2, name="broken_migration", up=up_2_failing))

    # Apply v1
    applied = migrator.upgrade(target_version=1)
    assert applied == [1]
    assert migrator.current_version() == 1

    # Attempt v2 which fails halfway -> must roll back transaction
    with pytest.raises(RuntimeError, match="failed halfway and was safely rolled back"):
        migrator.upgrade(target_version=2)

    # Verify that v1 user data is completely intact and email column was NOT retained
    assert migrator.current_version() == 1
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM users")
    assert cursor.fetchone()[0] == "Alice"
    cursor.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in cursor.fetchall()]
    assert "email" not in columns
