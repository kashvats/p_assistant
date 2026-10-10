from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock
import yaml

from fastapi.testclient import TestClient
import pytest
from typer.testing import CliRunner

from living_assistant.api import app as api_app
from living_assistant.cli import app
from living_assistant.cli.helpers import project_app
from living_assistant.security.api_auth import get_api_token
from living_assistant.system.codebase_onboarding import (
    CodebaseOnboardingEngine,
    OnboardingResult,
    OnboardingStatus,
)
from living_assistant.system.graph_validator import SystemGraphValidator


# =============================================================================
# Tier 1: Functional Feature Tests (10 tests)
# =============================================================================

def test_f3_onboard_python_repo_ast_and_symbols(tmp_path: Path):
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    (app_dir / "main.py").write_text("from fastapi import FastAPI\napp = FastAPI()\n", encoding="utf-8")
    (app_dir / "models.py").write_text("class User:\n    pass\n\nclass Order:\n    pass\n", encoding="utf-8")
    (app_dir / "utils.py").write_text("def f1():\n    return 1\n\ndef f2():\n    return 2\n\ndef f3():\n    return 3\n", encoding="utf-8")

    engine = CodebaseOnboardingEngine()
    result = engine.onboard_repository(tmp_path)

    assert result.status == "SUCCESS"
    assert result.ast_summary["total_classes"] == 2
    assert result.ast_summary["total_functions"] == 3
    assert result.indexed_symbols > 0


def test_f3_onboard_dependency_extraction(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "0.1.0"\ndependencies = ["fastapi>=0.115", "pydantic>=2.8"]\n',
        encoding="utf-8",
    )
    (tmp_path / "requirements.txt").write_text("requests==2.31.0\n", encoding="utf-8")

    engine = CodebaseOnboardingEngine()
    result = engine.onboard_repository(tmp_path)

    assert "python" in result.dependencies
    assert "fastapi>=0.115" in result.dependencies["python"]
    assert "pydantic>=2.8" in result.dependencies["python"]
    assert "requests==2.31.0" in result.dependencies["python"]


def test_f3_onboard_convention_detection(tmp_path: Path):
    pkg_dir = tmp_path / "src" / "my_pkg"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "__init__.py").write_text("", encoding="utf-8")

    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_basic.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")

    (tmp_path / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (tmp_path / "ruff.toml").write_text("line-length = 100\n", encoding="utf-8")

    engine = CodebaseOnboardingEngine()
    result = engine.onboard_repository(tmp_path)

    assert result.conventions["test_framework"] == "pytest"
    assert result.conventions["package_layout"] == "src-layout"
    assert "ruff" in result.conventions["linter_formatter"]


def test_f3_onboard_system_graph_generation(tmp_path: Path):
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    (app_dir / "server.py").write_text("def run_server():\n    pass\n", encoding="utf-8")
    (app_dir / "db.py").write_text("class Database:\n    pass\n", encoding="utf-8")

    engine = CodebaseOnboardingEngine()
    result = engine.onboard_repository(tmp_path, update_graph=True)

    assert result.system_graph_path is not None
    graph_path = Path(result.system_graph_path)
    assert graph_path.exists()
    diag = SystemGraphValidator.validate_file(graph_path, repo_root=tmp_path)
    assert diag.ok is True
    assert len(diag.errors) == 0


def test_f3_onboard_multilingual_repo(tmp_path: Path):
    backend_dir = tmp_path / "backend"
    backend_dir.mkdir()
    (backend_dir / "main.py").write_text("def run():\n    pass\n", encoding="utf-8")

    frontend_dir = tmp_path / "frontend"
    frontend_dir.mkdir()
    (frontend_dir / "package.json").write_text(
        json.dumps({"name": "frontend-app", "dependencies": {"react": "^18.2.0"}}),
        encoding="utf-8",
    )

    engine = CodebaseOnboardingEngine()
    result = engine.onboard_repository(tmp_path)

    assert "python" in result.detected_types
    assert "node" in result.detected_types
    assert "python" in result.dependencies
    assert "node" in result.dependencies


def test_f4_cli_project_onboard_command_registration():
    command_names = [c.name for c in project_app.registered_commands]
    assert "onboard" in command_names


def test_f4_cli_project_onboard_execution(tmp_path: Path):
    (tmp_path / "hello.py").write_text("print('hello world')\n", encoding="utf-8")

    runner = CliRunner()
    res = runner.invoke(app, ["project", "onboard", str(tmp_path)])
    assert res.exit_code == 0
    assert "SUCCESS" in res.stdout
    assert tmp_path.name in res.stdout


def test_f4_cli_project_onboard_json_flag(tmp_path: Path):
    (tmp_path / "hello.py").write_text("print('hello json')\n", encoding="utf-8")

    runner = CliRunner()
    res = runner.invoke(app, ["project", "onboard", str(tmp_path), "--json"])
    assert res.exit_code == 0
    parsed = json.loads(res.stdout)
    assert parsed["status"] == "SUCCESS"
    assert parsed["repo_path"] == str(tmp_path)


def test_f4_api_post_projects_onboard_endpoint(tmp_path: Path):
    (tmp_path / "app.py").write_text("def start():\n    pass\n", encoding="utf-8")
    token = get_api_token()
    client = TestClient(api_app, headers={"Authorization": f"Bearer {token}"})

    res = client.post("/projects/onboard", json={"path": str(tmp_path), "update_graph": True})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "SUCCESS"
    assert data["system_graph_path"] is not None
    assert Path(data["system_graph_path"]).exists()


def test_f4_api_post_projects_onboard_no_update_graph(tmp_path: Path):
    (tmp_path / "app.py").write_text("def start():\n    pass\n", encoding="utf-8")
    token = get_api_token()
    client = TestClient(api_app, headers={"Authorization": f"Bearer {token}"})

    res = client.post("/projects/onboard", json={"path": str(tmp_path), "update_graph": False})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "SUCCESS"
    assert data["system_graph_path"] is None
    assert data["system_graph_nodes_generated"] > 0


# =============================================================================
# Tier 2: Boundary & Edge-Case Tests (10 tests)
# =============================================================================

def test_f3_boundary_nonexistent_directory():
    engine = CodebaseOnboardingEngine()
    result = engine.onboard_repository("/path/does/not/exist/999999")
    assert result.status == "FAILED"
    assert result.error is not None
    assert len(result.error) > 0


def test_f3_boundary_empty_directory(tmp_path: Path):
    engine = CodebaseOnboardingEngine()
    result = engine.onboard_repository(tmp_path)
    assert result.status == "SUCCESS"
    assert result.ast_summary["total_files"] == 0
    assert result.indexed_symbols == 0


def test_f3_boundary_syntax_error_file(tmp_path: Path):
    (tmp_path / "good.py").write_text("def hello():\n    return 1\n", encoding="utf-8")
    (tmp_path / "broken.py").write_text("def broken(: syntax error\n", encoding="utf-8")

    engine = CodebaseOnboardingEngine()
    result = engine.onboard_repository(tmp_path)
    assert result.status == "SUCCESS"
    assert result.ast_summary["total_functions"] == 1
    assert len(result.ast_summary["syntax_errors"]) == 1
    assert result.ast_summary["syntax_errors"][0]["file"] == "broken.py"


def test_f3_boundary_incremental_system_graph_update(tmp_path: Path):
    graph_dir = tmp_path / "agent" / "architecture"
    graph_dir.mkdir(parents=True)
    legacy_yaml = {
        "system": {
            "name": "legacy-test",
            "version": "0.1.0",
            "nodes": [
                {
                    "id": "NODE_LEGACY",
                    "type": "service",
                    "responsibility": "Legacy module component",
                    "state": "ACTIVE",
                    "dependencies": [],
                }
            ],
        }
    }
    (graph_dir / "system.graph.yaml").write_text(yaml.dump(legacy_yaml), encoding="utf-8")
    (tmp_path / "new_module.py").write_text("def new_feature():\n    return 'new'\n", encoding="utf-8")

    engine = CodebaseOnboardingEngine()
    result = engine.onboard_repository(tmp_path, update_graph=True)

    assert result.status == "SUCCESS"
    updated_data = yaml.safe_load((graph_dir / "system.graph.yaml").read_text(encoding="utf-8"))
    node_ids = [n["id"] for n in updated_data["system"]["nodes"]]
    assert "NODE_LEGACY" in node_ids
    assert "NODE_NEW_MODULE" in node_ids
    assert len(node_ids) == len(set(node_ids))


def test_f3_boundary_secret_redaction_and_sensitive_paths(tmp_path: Path):
    (tmp_path / ".env").write_text("PASSWORD=super-secret-pw-123\n", encoding="utf-8")
    secret_token = "ghp_123456789012345678901234567890"
    (tmp_path / "app.py").write_text(
        f'TOKEN = "{secret_token}"\ndef secret_runner():\n    """Doc with {secret_token}."""\n    pass\n',
        encoding="utf-8",
    )

    engine = CodebaseOnboardingEngine()
    result = engine.onboard_repository(tmp_path)

    rendered = json.dumps(result.model_dump())
    assert ".env" not in [f["file"] for f in result.ast_summary["functions"]]
    assert "super-secret-pw-123" not in rendered
    assert secret_token not in rendered


def test_f4_boundary_cli_invalid_path():
    runner = CliRunner()
    res = runner.invoke(app, ["project", "onboard", "/invalid/nonexistent/path/xyz"])
    assert res.exit_code == 1
    assert "Directory does not exist" in res.stdout


def test_f4_boundary_api_invalid_path():
    token = get_api_token()
    client = TestClient(api_app, headers={"Authorization": f"Bearer {token}"})
    res = client.post("/projects/onboard", json={"path": "/invalid/nonexistent/path/xyz"})
    assert res.status_code == 400
    assert "does not exist" in res.json()["detail"]


def test_f4_boundary_api_unauthorized(tmp_path: Path):
    (tmp_path / "hello.py").write_text("print('hello')\n", encoding="utf-8")
    unauth_client = TestClient(api_app)
    res = unauth_client.post("/projects/onboard", json={"path": str(tmp_path)})
    assert res.status_code == 401


def test_f4_boundary_cli_no_update_graph_flag(tmp_path: Path):
    (tmp_path / "code.py").write_text("def run():\n    pass\n", encoding="utf-8")
    runner = CliRunner()
    res = runner.invoke(app, ["project", "onboard", str(tmp_path), "--no-update-graph"])
    assert res.exit_code == 0
    assert not (tmp_path / "agent" / "architecture" / "system.graph.yaml").exists()


def test_f4_boundary_api_malformed_json_payload():
    token = get_api_token()
    client = TestClient(api_app, headers={"Authorization": f"Bearer {token}"})
    res = client.post("/projects/onboard", json={"path": 12345})
    assert res.status_code == 422


# =============================================================================
# Tier 3: Cross-Feature Integration Tests (3 tests)
# =============================================================================

def test_f3_f4_cross_feature_cli_to_index_and_validator(tmp_path: Path):
    (tmp_path / "service.py").write_text("class MyService:\n    def execute(self):\n        return 42\n", encoding="utf-8")
    runner = CliRunner()
    res = runner.invoke(app, ["project", "onboard", str(tmp_path)])
    assert res.exit_code == 0

    graph_file = tmp_path / "agent" / "architecture" / "system.graph.yaml"
    assert graph_file.exists()
    diag = SystemGraphValidator.validate_file(graph_file, repo_root=tmp_path)
    assert diag.ok is True
    assert len(diag.errors) == 0


def test_f4_cross_feature_api_to_project_registry(tmp_path: Path):
    (tmp_path / "app.py").write_text("print('registered app')\n", encoding="utf-8")
    token = get_api_token()
    client = TestClient(api_app, headers={"Authorization": f"Bearer {token}"})

    res = client.post("/projects/onboard", json={"path": str(tmp_path)})
    assert res.status_code == 200
    project_name = res.json()["project_name"]

    res_list = client.get("/projects")
    assert res_list.status_code == 200
    assert project_name in res_list.json()


def test_f3_cross_feature_memory_adapter_graceful_fallback(tmp_path: Path):
    (tmp_path / "sample.py").write_text("def calculate():\n    return 100\n", encoding="utf-8")
    mock_adapter = MagicMock()
    mock_adapter.available.return_value = False

    engine = CodebaseOnboardingEngine(codebase_memory=mock_adapter)
    result = engine.onboard_repository(tmp_path)
    assert result.status == "SUCCESS"
    assert result.ast_summary["total_functions"] == 1


# =============================================================================
# Tier 4: Real-World Workload Scenarios (1 test)
# =============================================================================

def test_tier4_scenario1_full_brownfield_repo_onboarding(tmp_path: Path):
    # Construct complete brownfield service
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "auth-service"\nversion = "1.0.0"\ndependencies = ["fastapi>=0.115", "pydantic>=2.8"]\n\n'
        '[tool.pytest.ini_options]\ntestpaths = ["tests"]\n',
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("# Auth Service\n", encoding="utf-8")

    src_app = tmp_path / "src" / "app"
    src_app.mkdir(parents=True)
    (src_app / "main.py").write_text(
        "from fastapi import FastAPI\napp = FastAPI()\n\n"
        "@app.get('/health')\ndef health():\n    return {'status': 'ok'}\n\n"
        "@app.get('/version')\ndef version():\n    return '1.0'\n",
        encoding="utf-8",
    )

    services_dir = src_app / "services"
    services_dir.mkdir()
    (services_dir / "auth.py").write_text(
        "class AuthService:\n"
        "    def login(self, username, password):\n        return True\n"
        "    def logout(self, token):\n        pass\n"
        "    def refresh(self, token):\n        return 'new'\n"
        "    def verify(self, token):\n        return True\n",
        encoding="utf-8",
    )

    models_dir = src_app / "models"
    models_dir.mkdir()
    (models_dir / "user.py").write_text(
        "class User:\n    id: int\n    username: str\n",
        encoding="utf-8",
    )

    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_auth.py").write_text(
        "def test_login():\n    assert True\n\ndef test_logout():\n    assert True\n",
        encoding="utf-8",
    )

    engine = CodebaseOnboardingEngine()
    result = engine.onboard_repository(tmp_path, update_graph=True)

    assert result.status == "SUCCESS"
    assert result.project_name == "auth-service"
    assert "python" in result.detected_types
    assert result.ast_summary["total_classes"] >= 2
    assert result.ast_summary["total_functions"] >= 4
    assert "fastapi>=0.115" in result.dependencies["python"]
    assert result.conventions["test_framework"] == "pytest"
    assert result.conventions["package_layout"] == "src-layout"
    assert result.indexed_symbols > 0
    assert result.system_graph_nodes_generated >= 4
    assert result.system_graph_path is not None

    diag = SystemGraphValidator.validate_file(result.system_graph_path, repo_root=tmp_path)
    assert diag.ok is True
    assert len(diag.errors) == 0
