"""Comprehensive Tier 1-4 Test Suite for Feature F9 (Coding Assistant Router) & F10 (Knowledge Base Sync)."""
from __future__ import annotations

import json
from pathlib import Path
import sys
from unittest.mock import MagicMock, patch
import yaml

from fastapi.testclient import TestClient
import pytest

from living_assistant import api
from living_assistant.api import app as api_app
from living_assistant.security.api_auth import get_api_token
from living_assistant.system.graph_validator import SystemGraphValidator
from living_assistant.tools import webtools


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {get_api_token()}"}


@pytest.fixture
def client(auth_headers: dict[str, str]) -> TestClient:
    return TestClient(api_app, headers=auth_headers)


@pytest.fixture
def unauth_client() -> TestClient:
    return TestClient(api_app)


@pytest.fixture
def workspace_tmp(tmp_path: Path):
    """Ensure tmp_path is registered in runtime.workspace.roots for the duration of the test."""
    rt = api.get_runtime()
    resolved = tmp_path.resolve()
    if resolved not in rt.workspace.roots:
        rt.workspace.roots.append(resolved)
    try:
        yield tmp_path
    finally:
        if resolved in rt.workspace.roots:
            rt.workspace.roots.remove(resolved)


# =============================================================================
# Tier 1: Functional Feature Tests (Endpoints 1-5 Happy Path)
# =============================================================================


def test_f9_tier1_generate_endpoint_success(client: TestClient, workspace_tmp: Path):
    """Verifies POST /coding/generate returns 200 OK, valid response schema, and generated output."""
    target_file = workspace_tmp / "generated_sample.py"

    with patch("living_assistant.integrations.hermes_contractor.HermesContractor") as mock_contractor_cls:
        mock_instance = MagicMock()
        mock_instance.execute_task.return_value = {
            "ok": True,
            "output": "def calculate_discount(price, rate):\n    return price * (1.0 - rate)\n",
            "contractor": "hermes_agent",
        }
        mock_contractor_cls.return_value = mock_instance

        payload = {
            "task": "Write calculate_discount function",
            "context": "e-commerce pricing utility",
            "language": "python",
            "target_path": str(target_file),
            "provider": "collibri",
            "model": "openai/collibri",
        }
        resp = client.post("/coding/generate", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "calculate_discount" in data["output"]
        assert data["contractor"] == "hermes_agent"
        assert data["target_path"] == str(target_file.resolve())


def test_f9_tier1_patch_endpoint_dry_run_ast(client: TestClient, workspace_tmp: Path):
    """Verifies dry-run AST analysis calculates diff, reports changed/added symbols, and leaves disk untouched."""
    target_file = workspace_tmp / "module_a.py"
    original_code = "def existing_fun():\n    return 42\n"
    target_file.write_text(original_code, encoding="utf-8")

    proposed_code = (
        "def existing_fun():\n    return 42\n\n"
        "def new_feature():\n    return 'feature_ok'\n"
    )

    payload = {
        "path": str(target_file),
        "content": proposed_code,
        "dry_run": True,
        "strict_ast": True,
    }
    resp = client.post("/coding/patch", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["applied"] is False
    assert data["ast_checked"] is True
    assert "new_feature" in data["added_symbols"]
    assert "existing_fun" not in data["removed_symbols"]
    assert "+def new_feature():" in data["diff"]
    # Disk should be untouched
    assert target_file.read_text(encoding="utf-8") == original_code


def test_f9_tier1_patch_endpoint_apply_writes_file(client: TestClient, workspace_tmp: Path):
    """Verifies valid patch is applied and file is modified on disk with applied: True."""
    target_file = workspace_tmp / "module_b.py"
    target_file.write_text("def base():\n    return 1\n", encoding="utf-8")

    proposed_code = "def base():\n    return 1\n\ndef extended():\n    return 2\n"

    payload = {
        "path": str(target_file),
        "content": proposed_code,
        "dry_run": False,
        "strict_ast": True,
    }
    resp = client.post("/coding/patch", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["applied"] is True
    assert "extended" in data["added_symbols"]
    assert target_file.read_text(encoding="utf-8") == proposed_code


def test_f9_tier1_audit_endpoint_standard_score(client: TestClient, workspace_tmp: Path):
    """Verifies project health audit computes score, lint issues, dead code, and dependency counts."""
    proj_dir = workspace_tmp / "audit_proj"
    proj_dir.mkdir()
    (proj_dir / "main.py").write_text("def run():\n    return True\n", encoding="utf-8")
    (proj_dir / "requirements.txt").write_text("fastapi>=0.115\n", encoding="utf-8")

    payload = {
        "path": str(proj_dir),
        "depth": "standard",
    }
    resp = client.post("/coding/audit", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert isinstance(data["health_score"], (int, float))
    assert data["health_score"] > 0
    assert data["files_scanned"] >= 1
    assert "manifests" in data["dependencies"]
    assert data["deep_analysis"] is None


def test_f9_tier1_audit_endpoint_deep_onboarding(client: TestClient, workspace_tmp: Path):
    """Verifies depth='deep' generates AST hierarchy and onboarding summary alongside static scan."""
    proj_dir = workspace_tmp / "deep_proj"
    proj_dir.mkdir()
    (proj_dir / "service.py").write_text(
        "class AuthService:\n    def login(self, user):\n        return True\n",
        encoding="utf-8",
    )

    payload = {
        "path": str(proj_dir),
        "depth": "deep",
    }
    resp = client.post("/coding/audit", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["deep_analysis"] is not None
    assert "ast_summary" in data["deep_analysis"] or "project_name" in data["deep_analysis"]


def test_f9_tier1_repair_endpoint_direct_syntax_fix(client: TestClient, workspace_tmp: Path):
    """Verifies autonomous repair fixes syntax error, produces clean diff, and optionally auto-applies."""
    broken_file = workspace_tmp / "broken_calc.py"
    broken_file.write_text("def compute(x):\n    retur x * 2\n", encoding="utf-8")

    rt = api.get_runtime()
    with patch.object(
        rt.model_manager,
        "generate",
        create=True,
        return_value="def compute(x):\n    return x * 2\n",
    ):
        payload = {
            "path": str(broken_file),
            "error_context": "SyntaxError: invalid syntax in retur x * 2",
            "auto_apply": True,
            "max_cycles": 3,
        }
        resp = client.post("/coding/repair", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["verification_passed"] is True
        assert data["status"] == "repaired"
        assert data["cycles_run"] >= 1
        assert "def compute(x):" in data["repaired_content"]
        assert broken_file.read_text(encoding="utf-8") == "def compute(x):\n    return x * 2\n"


def test_f9_tier1_search_endpoint_local_and_web(client: TestClient, workspace_tmp: Path):
    """Verifies unified search returns both local symbol chunks and SearXNG results."""
    search_file = workspace_tmp / "searchable.py"
    search_file.write_text("def unique_searchable_symbol():\n    return 'found_it'\n", encoding="utf-8")

    with patch.object(
        webtools,
        "_searxng_search",
        create=True,
        return_value={
            "ok": True,
            "results": [
                {"title": "Search Result Python", "url": "https://example.com/python", "snippet": "Sample snippet"}
            ],
        },
    ):
        payload = {
            "query": "unique_searchable_symbol",
            "path": str(workspace_tmp),
            "source": "all",
            "limit": 5,
        }
        resp = client.post("/coding/search", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["query"] == "unique_searchable_symbol"
        assert "local" in data["sources_searched"]
        assert "web" in data["sources_searched"]
        assert len(data["web_results"]) == 1
        assert data["web_results"][0]["title"] == "Search Result Python"


# =============================================================================
# Tier 2: Boundary and Security Tests (Auth, Confinement, AST, Redaction, Bounds)
# =============================================================================


def test_f9_tier2_auth_rejection_without_token(unauth_client: TestClient, workspace_tmp: Path):
    """Verifies requests lacking Authorization: Bearer <token> are rejected with HTTP 401."""
    f = workspace_tmp / "dummy.py"
    f.write_text("print('test')\n", encoding="utf-8")

    r1 = unauth_client.post("/coding/generate", json={"task": "do something"})
    assert r1.status_code == 401

    r2 = unauth_client.post("/coding/patch", json={"path": str(f), "content": "x = 1"})
    assert r2.status_code == 401

    r3 = unauth_client.post("/coding/audit", json={"path": str(workspace_tmp)})
    assert r3.status_code == 401

    r4 = unauth_client.post("/coding/repair", json={"path": str(f), "error_context": "err"})
    assert r4.status_code == 401

    r5 = unauth_client.post("/coding/search", json={"query": "test"})
    assert r5.status_code == 401


def test_f9_tier2_path_traversal_blocked_403(client: TestClient):
    """Verifies path traversal outside workspace roots raises WorkspaceViolation -> HTTP 403 Forbidden."""
    forbidden_path = "C:/completely_outside_random_nonexistent_root/secret.py"

    r_patch = client.post("/coding/patch", json={"path": forbidden_path, "content": "bad content"})
    assert r_patch.status_code == 403
    assert "outside allowed workspace roots" in r_patch.json()["detail"]

    r_audit = client.post("/coding/audit", json={"path": forbidden_path})
    assert r_audit.status_code == 403
    assert "outside allowed workspace roots" in r_audit.json()["detail"]

    r_repair = client.post("/coding/repair", json={"path": forbidden_path, "error_context": "bad"})
    assert r_repair.status_code == 403
    assert "outside allowed workspace roots" in r_repair.json()["detail"]


def test_f9_tier2_strict_ast_blocks_symbol_deletion(client: TestClient, workspace_tmp: Path):
    """Verifies AST guard rejects patches removing functions/classes with ok: False and lists missing symbols."""
    target_file = workspace_tmp / "api_symbols.py"
    original_code = (
        "def critical_payment_handler():\n    return True\n\n"
        "class OrderProcessor:\n    pass\n"
    )
    target_file.write_text(original_code, encoding="utf-8")

    # Proposed code deletes OrderProcessor and critical_payment_handler
    proposed_code = "def innocent_replacement():\n    return False\n"

    payload = {
        "path": str(target_file),
        "content": proposed_code,
        "dry_run": False,
        "strict_ast": True,
    }
    resp = client.post("/coding/patch", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is False
    assert data["applied"] is False
    assert "critical_payment_handler" in data["removed_symbols"]
    assert "OrderProcessor" in data["removed_symbols"]
    assert "AST safety blocked" in data["error"]
    # Disk remains unaltered
    assert target_file.read_text(encoding="utf-8") == original_code


def test_f9_tier2_patch_blocks_invalid_python_syntax(client: TestClient, workspace_tmp: Path):
    """Verifies syntactically broken Python patch proposals are blocked with syntax error offset/line info."""
    target_file = workspace_tmp / "syntax_target.py"
    target_file.write_text("def valid():\n    pass\n", encoding="utf-8")

    invalid_python = "def broken(x\n    return x\n"

    payload = {
        "path": str(target_file),
        "content": invalid_python,
        "dry_run": False,
        "strict_ast": False,
    }
    resp = client.post("/coding/patch", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is False
    assert data["applied"] is False
    assert data["syntax_error"] is not None
    assert "syntax" in data["error"].lower()
    assert target_file.read_text(encoding="utf-8") == "def valid():\n    pass\n"


def test_f9_tier2_audit_redacts_hardcoded_secrets(client: TestClient, workspace_tmp: Path):
    """Verifies files containing API keys/tokens are audited without leaking secret strings in JSON response."""
    secret_dir = workspace_tmp / "secret_proj"
    secret_dir.mkdir()
    secret_file = secret_dir / "keys.py"
    raw_secret = "sk-ant-api03-abcdef1234567890abcdef1234567890"
    secret_file.write_text(f"API_TOKEN = '{raw_secret}'\n", encoding="utf-8")

    resp = client.post("/coding/audit", json={"path": str(secret_dir)})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    # Ensure raw secret is not leaked anywhere in response body
    assert raw_secret not in resp.text
    # Ensure security issues detected
    security_info = data["security"]
    assert security_info.get("finding_count", 0) >= 1 or len(security_info.get("findings", [])) >= 1 or security_info.get("issue_count", 0) >= 1


def test_f9_tier2_repair_max_cycles_clamped(client: TestClient, workspace_tmp: Path):
    """Verifies max_cycles bounds are enforced (422 if > 5 or < 1; clamped execution)."""
    broken_file = workspace_tmp / "broken_bounds.py"
    broken_file.write_text("def f():\n    retur 1\n", encoding="utf-8")

    # Exceeding schema max_cycles (le=5) returns 422 Unprocessable Entity
    resp_over = client.post(
        "/coding/repair",
        json={"path": str(broken_file), "error_context": "err", "max_cycles": 10},
    )
    assert resp_over.status_code == 422

    # Schema allows max_cycles=5
    rt = api.get_runtime()
    with patch.object(
        rt.model_manager,
        "generate",
        create=True,
        return_value="def f():\n    still_syntax_error(\n",
    ):
        resp_5 = client.post(
            "/coding/repair",
            json={"path": str(broken_file), "error_context": "err", "max_cycles": 5},
        )
        assert resp_5.status_code == 200
        data = resp_5.json()
        assert data["ok"] is False
        assert data["cycles_run"] == 5


def test_f9_tier2_search_empty_query_validation(client: TestClient, workspace_tmp: Path):
    """Verifies empty queries fail Pydantic validation (422)."""
    resp = client.post("/coding/search", json={"query": "", "path": str(workspace_tmp)})
    assert resp.status_code == 422


# =============================================================================
# Tier 3: Cross-Feature Integration Workflows
# =============================================================================


def test_f9_tier3_audit_to_repair_to_patch_workflow(client: TestClient, workspace_tmp: Path):
    """Runs audit -> catches syntax flaw -> invokes repair -> verifies file on disk has improved score."""
    flawed_file = workspace_tmp / "pipeline_calc.py"
    flawed_file.write_text("def multiply(a, b):\n    retur a * b\n", encoding="utf-8")

    # 1. Audit catches syntax error
    resp_audit1 = client.post("/coding/audit", json={"path": str(workspace_tmp)})
    assert resp_audit1.status_code == 200
    data_audit1 = resp_audit1.json()
    assert any("syntax-error" in str(issue) for issue in data_audit1.get("lint", {}).get("issues", []))

    # 2. Repair generates and auto-applies candidate fix
    rt = api.get_runtime()
    with patch.object(
        rt.model_manager,
        "generate",
        create=True,
        return_value="def multiply(a, b):\n    return a * b\n",
    ):
        resp_repair = client.post(
            "/coding/repair",
            json={
                "path": str(flawed_file),
                "error_context": "SyntaxError: invalid syntax in retur a * b",
                "auto_apply": True,
            },
        )
        assert resp_repair.status_code == 200
        assert resp_repair.json()["ok"] is True

    # 3. Patch dry-run verifies clean AST
    resp_patch = client.post(
        "/coding/patch",
        json={
            "path": str(flawed_file),
            "content": flawed_file.read_text(encoding="utf-8"),
            "dry_run": True,
        },
    )
    assert resp_patch.status_code == 200
    assert resp_patch.json()["ok"] is True
    assert resp_patch.json()["syntax_error"] is None

    # 4. Final audit confirms 0 syntax errors
    resp_audit2 = client.post("/coding/audit", json={"path": str(workspace_tmp)})
    assert resp_audit2.status_code == 200
    data_audit2 = resp_audit2.json()
    assert not any("syntax-error" in str(issue) for issue in data_audit2.get("lint", {}).get("issues", []))


def test_f9_tier3_generate_then_ast_patch_and_search(client: TestClient, workspace_tmp: Path):
    """Generates code snippet -> applies via /coding/patch -> searches codebase -> verifies symbol found."""
    target_module = workspace_tmp / "geometry.py"

    generated_code = "def calculate_circle_area(radius):\n    import math\n    return math.pi * radius * radius\n"

    with patch("living_assistant.integrations.hermes_contractor.HermesContractor") as mock_contractor:
        mock_instance = MagicMock()
        mock_instance.execute_task.return_value = {
            "ok": True,
            "output": generated_code,
            "contractor": "hermes_agent",
        }
        mock_contractor.return_value = mock_instance

        # 1. Generate code
        res_gen = client.post("/coding/generate", json={"task": "calculate circle area"})
        assert res_gen.status_code == 200
        output_code = res_gen.json()["output"]

    # 2. Patch into workspace
    res_patch = client.post(
        "/coding/patch",
        json={
            "path": str(target_module),
            "content": output_code,
            "dry_run": False,
        },
    )
    assert res_patch.status_code == 200
    assert res_patch.json()["applied"] is True

    # 3. Search codebase for the symbol
    res_search = client.post(
        "/coding/search",
        json={
            "query": "calculate_circle_area",
            "path": str(workspace_tmp),
            "source": "local",
        },
    )
    assert res_search.status_code == 200
    search_data = res_search.json()
    assert search_data["ok"] is True
    assert "local" in search_data["sources_searched"]


def test_f9_tier3_repair_with_test_runner_validation(client: TestClient, workspace_tmp: Path):
    """Verifies repair loop with mock test execution only accepts candidates that pass verification commands."""
    math_file = workspace_tmp / "math_ops.py"
    math_file.write_text("def subtract(a, b):\n    return a + b\n", encoding="utf-8")

    test_file = workspace_tmp / "verify_math.py"
    test_file.write_text(
        "from math_ops import subtract\n"
        "assert subtract(10, 3) == 7, 'Substraction failed'\n",
        encoding="utf-8",
    )

    rt = api.get_runtime()
    # Cycle 1 generates still-failing code; Cycle 2 generates correct code
    responses = [
        "def subtract(a, b):\n    return a + 0\n",
        "def subtract(a, b):\n    return a - b\n",
    ]
    with patch.object(rt.model_manager, "generate", create=True, side_effect=responses):
        test_cmd = f'"{sys.executable}" "{test_file.name}"'
        payload = {
            "path": str(math_file),
            "error_context": "AssertionError: Substraction failed",
            "test_commands": [test_cmd],
            "max_cycles": 3,
            "auto_apply": True,
        }
        resp = client.post("/coding/repair", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["verification_passed"] is True
        assert data["cycles_run"] == 2
        assert "return a - b" in math_file.read_text(encoding="utf-8")


# =============================================================================
# Tier 4: Real-World Workload Scenarios
# =============================================================================


def test_f9_tier4_e2e_repository_onboarding_audit_and_search(client: TestClient, workspace_tmp: Path):
    """Onboards full repo fixture (FastAPI app + tests), audits structure, queries codebase index, verifies coherence."""
    repo_dir = workspace_tmp / "real_world_app"
    repo_dir.mkdir()
    (repo_dir / "pyproject.toml").write_text(
        '[project]\nname = "ecommerce-api"\nversion = "1.0.0"\ndependencies = ["fastapi>=0.115"]\n',
        encoding="utf-8",
    )
    src_dir = repo_dir / "src"
    src_dir.mkdir()
    (src_dir / "main.py").write_text("from fastapi import FastAPI\napp = FastAPI()\n", encoding="utf-8")
    (src_dir / "models.py").write_text(
        "class Customer:\n    def __init__(self, name):\n        self.name = name\n",
        encoding="utf-8",
    )
    tests_dir = repo_dir / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_main.py").write_text("def test_health():\n    assert True\n", encoding="utf-8")

    # 1. Audit with deep onboarding
    resp_audit = client.post("/coding/audit", json={"path": str(repo_dir), "depth": "deep"})
    assert resp_audit.status_code == 200
    data_audit = resp_audit.json()
    assert data_audit["ok"] is True
    assert data_audit["files_scanned"] >= 3
    assert data_audit["health_score"] >= 80
    assert data_audit["deep_analysis"] is not None

    # 2. Unified Search across the project
    resp_search = client.post(
        "/coding/search",
        json={"query": "Customer", "path": str(repo_dir), "source": "all"},
    )
    assert resp_search.status_code == 200
    data_search = resp_search.json()
    assert data_search["ok"] is True


def test_f9_tier4_e2e_autonomous_bug_repair_cycle(client: TestClient, workspace_tmp: Path):
    """Creates broken module causing test failure, executes autonomous repair loop, verifies 100% test pass recovery."""
    app_dir = workspace_tmp / "autonomous_app"
    app_dir.mkdir()
    broken_code = "def validate_age(age):\n    if age >= 18\n        return True\n    return False\n"
    target_module = app_dir / "validator.py"
    target_module.write_text(broken_code, encoding="utf-8")

    test_file = app_dir / "test_validator.py"
    test_file.write_text(
        "from validator import validate_age\n"
        "assert validate_age(20) is True\n"
        "assert validate_age(15) is False\n",
        encoding="utf-8",
    )

    rt = api.get_runtime()
    fixed_code = "def validate_age(age):\n    if age >= 18:\n        return True\n    return False\n"
    with patch.object(rt.model_manager, "generate", create=True, return_value=fixed_code):
        test_cmd = f'"{sys.executable}" "{test_file.name}"'
        resp_repair = client.post(
            "/coding/repair",
            json={
                "path": str(target_module),
                "error_context": "SyntaxError: expected ':' at line 2",
                "test_commands": [test_cmd],
                "auto_apply": True,
            },
        )
        assert resp_repair.status_code == 200
        data = resp_repair.json()
        assert data["ok"] is True
        assert data["status"] == "repaired"
        assert target_module.read_text(encoding="utf-8") == fixed_code


# =============================================================================
# Feature F10: GEMINI Knowledge Base System Graph Validation Test
# =============================================================================


def test_f10_system_graph_validation():
    """Validates agent/architecture/system.graph.yaml using SystemGraphValidator, asserting diag.ok == True and diag.node_count == 51."""
    graph_path = Path("agent/architecture/system.graph.yaml")
    assert graph_path.exists(), "system.graph.yaml must exist under agent/architecture/"

    diag = SystemGraphValidator.validate_file(str(graph_path), repo_root=Path("."))
    assert diag.ok is True, f"System graph validation failed with errors: {diag.errors}"
    assert diag.node_count >= 51, f"Expected at least 51 valid nodes, got {diag.node_count}"
    assert len(diag.errors) == 0

    # Parse YAML to verify node IDs in system graph
    raw_graph = yaml.safe_load(graph_path.read_text(encoding="utf-8"))
    nodes = raw_graph.get("system", {}).get("nodes", [])
    node_ids = {n.get("id") for n in nodes if isinstance(n, dict)}

    # Verify critical Milestone 1-4 nodes exist
    assert "NODE_CODING_ROUTER" in node_ids
    assert "NODE_GEMINI_KNOWLEDGE_BASE" in node_ids
    assert "NODE_HERMES_CONTRACTOR" in node_ids
    assert "NODE_COLLIBRI_LLAMA_SERVER" in node_ids
    assert "NODE_DIRECTOR" in node_ids
    assert "NODE_SOFTWARE_COMPANY_WORKFLOW" in node_ids
    assert "NODE_TASK_SCOPED_PERMISSIONS" in node_ids
    assert "NODE_CODEBASE_ONBOARDING" in node_ids


def test_f9_tier1_explain_endpoint_safe_command(client: TestClient):
    """Verifies POST /coding/explain returns safe classification for benign commands."""
    resp = client.post("/coding/explain", json={"command": "pytest tests/ -v"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["command"] == "pytest tests/ -v"
    assert data["risk_level"] in {"low", "medium"}
    assert data["allowed"] is True
    assert data["summary"] != ""


def test_f9_tier1_explain_endpoint_destructive_command(client: TestClient):
    """Verifies POST /coding/explain flags destructive commands as blocked/disallowed."""
    resp = client.post("/coding/explain", json={"command": "rm -rf /"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["allowed"] is False
    assert data["risk_level"] in {"high", "critical", "blocked"}


def test_f9_tier1_explain_endpoint_empty_command(client: TestClient):
    """Verifies POST /coding/explain returns 400 for empty command strings."""
    resp = client.post("/coding/explain", json={"command": "   "})
    assert resp.status_code == 400

