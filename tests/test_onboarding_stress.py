from __future__ import annotations

import json
import os
from pathlib import Path
import yaml

import pytest

from living_assistant.system.codebase_onboarding import (
    CodebaseOnboardingEngine,
    OnboardingResult,
    OnboardingStatus,
)
from living_assistant.system.graph_validator import SystemGraphValidator


# =============================================================================
# Adversarial Category 1: Malformed Files & Syntax Errors
# =============================================================================

def test_stress_severe_python_syntax_errors(tmp_path: Path):
    """Ensure malformed Python files with various syntax corruptions do not crash onboarding."""
    # 1. Unmatched parentheses/brackets
    (tmp_path / "unmatched.py").write_text("def broken():\n    ((((((([[[[[{{{\n", encoding="utf-8")
    # 2. Invalid indentation
    (tmp_path / "bad_indent.py").write_text("def foo():\nreturn 42\n", encoding="utf-8")
    # 3. Unexpected EOF in middle of statement
    (tmp_path / "incomplete.py").write_text("if True:\n", encoding="utf-8")
    # 4. Binary/null bytes inside .py file
    (tmp_path / "null_bytes.py").write_bytes(b"def func_with_null():\n    x = \x00\x00\x01\n")
    # 5. Non-UTF8 arbitrary byte garbage in .py file
    (tmp_path / "raw_bytes.py").write_bytes(b"\xff\xfe\x00\x00\x80\x90\xaa\xbb\xcc\xdddef broken_bytes():\n")
    # 6. Valid file alongside corrupted ones
    (tmp_path / "valid_service.py").write_text(
        "class ValidService:\n    def execute(self):\n        return 'success'\n",
        encoding="utf-8",
    )

    engine = CodebaseOnboardingEngine()
    result = engine.onboard_repository(tmp_path, update_graph=True)

    assert result.status == OnboardingStatus.SUCCESS.value
    # Syntax errors must be captured
    err_files = [e["file"] for e in result.ast_summary["syntax_errors"]]
    assert len(err_files) >= 5
    assert "unmatched.py" in err_files
    assert "bad_indent.py" in err_files
    assert "incomplete.py" in err_files

    # Valid service must still be discovered and indexed
    assert result.ast_summary["total_classes"] >= 1
    class_names = [c["name"] for c in result.ast_summary["classes"]]
    assert "ValidService" in class_names

    # System graph must be valid despite corrupted files
    assert result.system_graph_path is not None
    diag = SystemGraphValidator.validate_file(result.system_graph_path, repo_root=tmp_path)
    assert diag.ok is True
    assert len(diag.errors) == 0


def test_stress_empty_and_weird_named_python_files(tmp_path: Path):
    """Empty files, single character names, dot-py files."""
    (tmp_path / "empty.py").write_text("", encoding="utf-8")
    (tmp_path / "whitespace_only.py").write_text("   \n\t\n  \n", encoding="utf-8")
    (tmp_path / "comments_only.py").write_text("# Just a comment\n# Another comment\n", encoding="utf-8")
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "123_numeric.py").write_text("def numeric_func(): pass\n", encoding="utf-8")

    engine = CodebaseOnboardingEngine()
    result = engine.onboard_repository(tmp_path, update_graph=True)

    assert result.status == OnboardingStatus.SUCCESS.value
    assert result.ast_summary["total_files"] == 5
    assert len(result.ast_summary["syntax_errors"]) == 0

    assert result.system_graph_path is not None
    diag = SystemGraphValidator.validate_file(result.system_graph_path, repo_root=tmp_path)
    assert diag.ok is True
    assert len(diag.errors) == 0


# =============================================================================
# Adversarial Category 2: Large Files, Binary Files & Deep Nesting
# =============================================================================

def test_stress_binary_files_and_arbitrary_data(tmp_path: Path):
    """Repository containing various binary assets, executables, images, and archives."""
    # Write arbitrary binary files
    (tmp_path / "image.png").write_bytes(os.urandom(8192))
    (tmp_path / "document.pdf").write_bytes(os.urandom(16384))
    (tmp_path / "archive.zip").write_bytes(os.urandom(32768))
    (tmp_path / "binary_blob.bin").write_bytes(os.urandom(65536))
    (tmp_path / "executable.exe").write_bytes(b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff")

    # Legitimate code alongside binary files
    (tmp_path / "app.py").write_text("def run():\n    return 'running'\n", encoding="utf-8")

    engine = CodebaseOnboardingEngine()
    result = engine.onboard_repository(tmp_path, update_graph=True)

    assert result.status == OnboardingStatus.SUCCESS.value
    # Binary non-code files must not be treated as code or cause crashes
    assert result.ast_summary["total_files"] == 1
    assert result.ast_summary["total_functions"] == 1

    diag = SystemGraphValidator.validate_file(result.system_graph_path, repo_root=tmp_path)
    assert diag.ok is True
    assert len(diag.errors) == 0


def test_stress_deeply_nested_hierarchy_and_unicode_paths(tmp_path: Path):
    """Deeply nested directories (10+ levels) and directory names with special characters."""
    deep_dir = tmp_path
    for segment in ["layer_1", "lâyer_2 with spaces", "sub-layer.3", "l4", "l5", "l6", "l7", "l8", "l9", "l10"]:
        deep_dir = deep_dir / segment
    deep_dir.mkdir(parents=True)

    (deep_dir / "deep_component.py").write_text(
        "class DeepComponent:\n    def deep_method(self):\n        return True\n",
        encoding="utf-8",
    )
    (tmp_path / "root_entry.py").write_text("import sys\n", encoding="utf-8")

    engine = CodebaseOnboardingEngine()
    result = engine.onboard_repository(tmp_path, update_graph=True)

    assert result.status == OnboardingStatus.SUCCESS.value
    assert result.ast_summary["total_classes"] == 1
    assert result.system_graph_nodes_generated >= 2

    graph_data = yaml.safe_load(Path(result.system_graph_path).read_text(encoding="utf-8"))
    node_ids = [n["id"] for n in graph_data["system"]["nodes"]]
    # Node ID must be clean alphanumeric+underscores without illegal chars
    for nid in node_ids:
        assert nid.replace("_", "").isalnum()

    diag = SystemGraphValidator.validate_file(result.system_graph_path, repo_root=tmp_path)
    assert diag.ok is True
    assert len(diag.errors) == 0


def test_stress_large_code_file_many_functions(tmp_path: Path):
    """A single large Python file with 500 generated functions."""
    lines = ["# Large file with many functions\n"]
    for i in range(500):
        lines.append(f"def func_{i:04d}(arg1, arg2):\n    return {i}\n\n")
    (tmp_path / "huge_module.py").write_text("".join(lines), encoding="utf-8")

    engine = CodebaseOnboardingEngine()
    result = engine.onboard_repository(tmp_path, update_graph=True)

    assert result.status == OnboardingStatus.SUCCESS.value
    assert result.ast_summary["total_functions"] == 500
    assert result.indexed_symbols >= 500

    diag = SystemGraphValidator.validate_file(result.system_graph_path, repo_root=tmp_path)
    assert diag.ok is True
    assert len(diag.errors) == 0


# =============================================================================
# Adversarial Category 3: Empty & Unrecognized Directories
# =============================================================================

def test_stress_completely_empty_directory(tmp_path: Path):
    """Completely blank empty directory."""
    empty_dir = tmp_path / "blank_repo"
    empty_dir.mkdir()

    engine = CodebaseOnboardingEngine()
    result = engine.onboard_repository(empty_dir, update_graph=True)

    assert result.status == OnboardingStatus.SUCCESS.value
    assert result.ast_summary["total_files"] == 0
    assert result.ast_summary["total_classes"] == 0
    assert result.ast_summary["total_functions"] == 0
    assert result.indexed_symbols == 0
    assert result.system_graph_nodes_generated == 0

    assert result.system_graph_path is not None
    diag = SystemGraphValidator.validate_file(result.system_graph_path, repo_root=empty_dir)
    assert diag.ok is True
    assert len(diag.errors) == 0


def test_stress_only_unrecognized_extensions(tmp_path: Path):
    """Directory containing only files with non-programming or unrecognized extensions."""
    unrecog_dir = tmp_path / "unrecog"
    unrecog_dir.mkdir()

    (unrecog_dir / "notes.log").write_text("2026-10-08 info log", encoding="utf-8")
    (unrecog_dir / "data.csv").write_text("col1,col2\n1,2\n", encoding="utf-8")
    (unrecog_dir / "file.xyz").write_text("custom xyz format", encoding="utf-8")
    (unrecog_dir / "archive.tar.gz").write_bytes(b"\x1f\x8b\x08\x00")
    (unrecog_dir / "config.unknown").write_text("foo=bar", encoding="utf-8")

    engine = CodebaseOnboardingEngine()
    result = engine.onboard_repository(unrecog_dir, update_graph=True)

    assert result.status == OnboardingStatus.SUCCESS.value
    assert result.detected_types == []
    assert result.ast_summary["total_files"] == 0
    assert result.indexed_symbols == 0

    diag = SystemGraphValidator.validate_file(result.system_graph_path, repo_root=unrecog_dir)
    assert diag.ok is True
    assert len(diag.errors) == 0


def test_stress_only_empty_subdirectories(tmp_path: Path):
    """Directory tree with only empty directories."""
    (tmp_path / "sub1" / "sub2" / "sub3").mkdir(parents=True)
    (tmp_path / "another_sub").mkdir()

    engine = CodebaseOnboardingEngine()
    result = engine.onboard_repository(tmp_path, update_graph=True)

    assert result.status == OnboardingStatus.SUCCESS.value
    assert result.ast_summary["total_files"] == 0
    assert result.system_graph_nodes_generated == 0


# =============================================================================
# Adversarial Category 4: Circular Imports, Module Cycles & Graph Validator
# =============================================================================

def test_stress_direct_circular_dependency(tmp_path: Path):
    """Two modules directly referencing each other (mod_alpha imports mod_beta, mod_beta imports mod_alpha)."""
    (tmp_path / "mod_alpha.py").write_text(
        "import mod_beta\n\nclass AlphaService:\n    def call_beta(self):\n        return mod_beta.BetaService()\n",
        encoding="utf-8",
    )
    (tmp_path / "mod_beta.py").write_text(
        "import mod_alpha\n\nclass BetaService:\n    def call_alpha(self):\n        return mod_alpha.AlphaService()\n",
        encoding="utf-8",
    )

    engine = CodebaseOnboardingEngine()
    result = engine.onboard_repository(tmp_path, update_graph=True)

    assert result.status == OnboardingStatus.SUCCESS.value
    assert result.system_graph_path is not None

    # Validate generated system.graph.yaml
    diag = SystemGraphValidator.validate_file(result.system_graph_path, repo_root=tmp_path)
    assert diag.ok is True, f"System graph failed validation: {diag.errors}"
    assert len(diag.errors) == 0, f"Detected errors: {diag.errors}"


def test_stress_three_way_circular_dependency(tmp_path: Path):
    """Three modules forming an indirect cycle: node_one -> node_two -> node_three -> node_one."""
    (tmp_path / "srv_one.py").write_text(
        "import srv_two\nclass ServiceOne:\n    pass\n",
        encoding="utf-8",
    )
    (tmp_path / "srv_two.py").write_text(
        "import srv_three\nclass ServiceTwo:\n    pass\n",
        encoding="utf-8",
    )
    (tmp_path / "srv_three.py").write_text(
        "import srv_one\nclass ServiceThree:\n    pass\n",
        encoding="utf-8",
    )

    engine = CodebaseOnboardingEngine()
    result = engine.onboard_repository(tmp_path, update_graph=True)

    assert result.status == OnboardingStatus.SUCCESS.value
    assert result.system_graph_path is not None

    diag = SystemGraphValidator.validate_file(result.system_graph_path, repo_root=tmp_path)
    assert diag.ok is True, f"Cycle escape detected in 3-way circular import: {diag.errors}"
    assert len(diag.errors) == 0


def test_stress_complex_dense_graph_with_cross_dependencies(tmp_path: Path):
    """Dense graph with multiple cross-dependencies and mutual references."""
    modules = ["alpha_engine", "beta_driver", "gamma_cache", "delta_router", "epsilon_store"]
    for i, mod in enumerate(modules):
        references = [m for j, m in enumerate(modules) if j != i]
        ref_text = "\n".join(f"import {m}" for m in references)
        content = f"{ref_text}\n\nclass {mod.title().replace('_', '')}:\n    pass\n"
        (tmp_path / f"{mod}.py").write_text(content, encoding="utf-8")

    engine = CodebaseOnboardingEngine()
    result = engine.onboard_repository(tmp_path, update_graph=True)

    assert result.status == OnboardingStatus.SUCCESS.value
    assert result.system_graph_path is not None

    diag = SystemGraphValidator.validate_file(result.system_graph_path, repo_root=tmp_path)
    assert diag.ok is True, f"Cycle escape detected in dense cross graph: {diag.errors}"
    assert len(diag.errors) == 0


def test_stress_graph_validator_detects_deliberate_cycle():
    """Directly test SystemGraphValidator with a deliberate cycle to confirm cycle detection works."""
    cyclic_dict = {
        "system": {
            "name": "cyclic-test",
            "nodes": [
                {"id": "NODE_A", "type": "service", "state": "ACTIVE", "dependencies": ["NODE_B"]},
                {"id": "NODE_B", "type": "service", "state": "ACTIVE", "dependencies": ["NODE_C"]},
                {"id": "NODE_C", "type": "service", "state": "ACTIVE", "dependencies": ["NODE_A"]},
            ],
        }
    }
    diag = SystemGraphValidator.validate_dict(cyclic_dict)
    assert diag.ok is False
    assert any("Dependency cycle detected" in err for err in diag.errors)
    assert any("NODE_A -> NODE_B -> NODE_C -> NODE_A" in err for err in diag.errors)


def test_stress_graph_validator_self_referencing_node():
    """Node that depends on itself."""
    self_cycle_dict = {
        "system": {
            "name": "self-cycle-test",
            "nodes": [
                {"id": "NODE_SELF", "type": "service", "state": "ACTIVE", "dependencies": ["NODE_SELF"]},
            ],
        }
    }
    diag = SystemGraphValidator.validate_dict(self_cycle_dict)
    assert diag.ok is False
    assert any("Dependency cycle detected" in err for err in diag.errors)
    assert any("NODE_SELF -> NODE_SELF" in err for err in diag.errors)


def test_stress_graph_validator_duplicate_nodes():
    """Duplicate node IDs."""
    dup_dict = {
        "system": {
            "name": "dup-test",
            "nodes": [
                {"id": "NODE_X", "type": "service", "state": "ACTIVE", "dependencies": []},
                {"id": "NODE_X", "type": "service", "state": "ACTIVE", "dependencies": []},
            ],
        }
    }
    diag = SystemGraphValidator.validate_dict(dup_dict)
    assert diag.ok is False
    assert any("Duplicate node ID detected" in err for err in diag.errors)


def test_stress_graph_validator_malformed_structures():
    """Malformed nodes (strings instead of dicts, missing id, invalid root)."""
    # 1. Invalid root
    assert SystemGraphValidator.validate_dict({"not_system": {}}).ok is False
    # 2. Nodes is not a list
    assert SystemGraphValidator.validate_dict({"system": {"nodes": "not_a_list"}}).ok is False
    # 3. Node is not a dict
    diag = SystemGraphValidator.validate_dict({"system": {"nodes": ["just_a_string"]}})
    assert diag.ok is False
    assert any("is not a dictionary" in err for err in diag.errors)
    # 4. Node missing id
    diag = SystemGraphValidator.validate_dict({"system": {"nodes": [{"type": "service"}]}})
    assert diag.ok is False
    assert any("missing an 'id'" in err for err in diag.errors)


# =============================================================================
# Adversarial Category 5: Advanced Edge Cases (ReDoS, Pre-existing cycles, Unicode)
# =============================================================================

def test_stress_minified_js_redos_resistance(tmp_path: Path):
    """Minified JS with a massive single line (100,000 characters) to ensure no ReDoS slowdown."""
    junk_line = "var a=1;const b=2;function foo(x){return x+1;}class Bar{constructor(){}}" * 1500
    (tmp_path / "minified.js").write_text(junk_line, encoding="utf-8")

    engine = CodebaseOnboardingEngine()
    result = engine.onboard_repository(tmp_path, update_graph=True)

    assert result.status == OnboardingStatus.SUCCESS.value
    assert "node" in result.detected_types
    assert result.ast_summary["total_files"] == 1


def test_stress_unicode_symbols_and_emojis(tmp_path: Path):
    """Source files with non-ASCII identifiers, UTF-8 strings, and emojis."""
    (tmp_path / "unicode_app.py").write_text(
        "# Unicode file 🚀\n"
        "class CaféService:\n"
        "    def commander_café(self, quantité: int):\n"
        "        return f'☕ {quantité}'\n",
        encoding="utf-8",
    )

    engine = CodebaseOnboardingEngine()
    result = engine.onboard_repository(tmp_path, update_graph=True)

    assert result.status == OnboardingStatus.SUCCESS.value
    assert result.ast_summary["total_classes"] == 1
    assert result.ast_summary["classes"][0]["name"] == "CaféService"


def test_stress_pre_existing_corrupted_system_graph_yaml(tmp_path: Path):
    """When a repo already has a corrupted system.graph.yaml on disk."""
    graph_dir = tmp_path / "agent" / "architecture"
    graph_dir.mkdir(parents=True)
    # Corrupted YAML syntax
    (graph_dir / "system.graph.yaml").write_text("system: { unclosed bracket", encoding="utf-8")
    (tmp_path / "app.py").write_text("def run(): pass\n", encoding="utf-8")

    engine = CodebaseOnboardingEngine()
    result = engine.onboard_repository(tmp_path, update_graph=True)

    assert result.status == OnboardingStatus.SUCCESS.value
    # Overwrites/recovers gracefully with valid system.graph.yaml
    diag = SystemGraphValidator.validate_file(result.system_graph_path, repo_root=tmp_path)
    assert diag.ok is True
    assert len(diag.errors) == 0


def test_stress_path_with_spaces_and_special_characters(tmp_path: Path):
    """Repository directory path itself containing spaces and hyphens."""
    repo_space_dir = tmp_path / "my complex project (v2.0) [test]"
    repo_space_dir.mkdir()
    (repo_space_dir / "main.py").write_text("def start(): return True\n", encoding="utf-8")

    engine = CodebaseOnboardingEngine()
    result = engine.onboard_repository(repo_space_dir, update_graph=True)

    assert result.status == OnboardingStatus.SUCCESS.value
    assert result.system_graph_path is not None
    assert Path(result.system_graph_path).exists()
    diag = SystemGraphValidator.validate_file(result.system_graph_path, repo_root=repo_space_dir)
    assert diag.ok is True

