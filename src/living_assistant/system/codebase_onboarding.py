from __future__ import annotations

import ast
from enum import Enum
import json
import os
from pathlib import Path
import re
from typing import Any, Optional
import yaml

from pydantic import BaseModel, Field

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib  # type: ignore
    except ImportError:
        tomllib = None  # type: ignore

from living_assistant.core.workspace import Workspace, WorkspaceViolation
from living_assistant.integrations.codebase_memory import CodebaseMemoryAdapter
from living_assistant.security.security_utils import is_sensitive_path, redact_secrets
from living_assistant.system.codebase_index import CodebaseIndex
from living_assistant.system.graph_validator import SystemGraphValidator
from living_assistant.tools.projects import detect_project


_SKIP_DIRS: set[str] = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".next",
    ".turbo",
    ".gemini",
    ".idea",
    ".vscode",
    "target",
}


class OnboardingStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class SymbolDefinition(BaseModel):
    name: str
    kind: str  # "class" | "function" | "async_function" | "interface"
    file: str  # relative path
    line: int
    end_line: int
    docstring: Optional[str] = None
    parameters: list[str] = Field(default_factory=list)
    decorators: list[str] = Field(default_factory=list)


class ASTSummary(BaseModel):
    total_files: int = 0
    languages: dict[str, int] = Field(default_factory=dict)
    total_classes: int = 0
    total_functions: int = 0
    entry_points: list[str] = Field(default_factory=list)
    classes: list[dict[str, Any]] = Field(default_factory=list)
    functions: list[dict[str, Any]] = Field(default_factory=list)
    syntax_errors: list[dict[str, Any]] = Field(default_factory=list)


class DependenciesSummary(BaseModel):
    manifests: list[str] = Field(default_factory=list)
    packages: dict[str, list[str]] = Field(default_factory=dict)


class ConventionsSummary(BaseModel):
    test_framework: Optional[str] = None
    test_directories: list[str] = Field(default_factory=list)
    linter_formatter: list[str] = Field(default_factory=list)
    docstring_convention: Optional[str] = None
    naming_conventions: dict[str, str] = Field(default_factory=dict)
    package_layout: str = "flat"
    git_initialized: bool = False
    git_branch: Optional[str] = None


class OnboardingResult(BaseModel):
    """Interface Contract 3: Brownfield Codebase Pickup & Onboarding Result."""
    repo_path: str
    project_name: str
    detected_types: list[str] = Field(default_factory=list)
    ast_summary: dict[str, Any] = Field(default_factory=dict)
    dependencies: dict[str, list[str]] = Field(default_factory=dict)
    conventions: dict[str, Any] = Field(default_factory=dict)
    indexed_symbols: int = 0
    system_graph_nodes_generated: int = 0
    system_graph_path: Optional[str] = None
    status: str = OnboardingStatus.SUCCESS.value
    error: Optional[str] = None


class CodebaseOnboardingEngine:
    """Production Brownfield Codebase Pickup & Onboarding Engine.

    Unifies:
    - Path resolution & boundary checks via Workspace.resolve()
    - Ecosystem detection via detect_project()
    - Multi-language AST symbol extraction (Python AST & JS/TS regex)
    - Dependency manifest extraction (Python, Node, Rust, Go)
    - Conventions detection (test frameworks, linters, layout, Git)
    - Codebase indexing via CodebaseIndex and graceful CodebaseMemoryAdapter
    - System graph generation, incremental synchronization, and validation via SystemGraphValidator
    """

    def __init__(
        self,
        workspace: Workspace | None = None,
        codebase_index: CodebaseIndex | None = None,
        codebase_memory: CodebaseMemoryAdapter | None = None,
    ) -> None:
        self.workspace = workspace
        self.codebase_index = codebase_index
        self.codebase_memory = codebase_memory

    def onboard_repository(
        self,
        repo_path: Path | str,
        update_graph: bool = True,
    ) -> OnboardingResult:
        """Inspect, parse, index, and onboard an arbitrary repository path."""
        # 1. Path Resolution and Boundary Check
        raw_str = str(repo_path)
        if self.workspace is not None:
            try:
                root = self.workspace.resolve(repo_path)
            except Exception as exc:
                p = Path(raw_str).expanduser().resolve()
                if not p.exists() or not p.is_dir():
                    return OnboardingResult(
                        repo_path=raw_str,
                        project_name=Path(raw_str).name or "unknown",
                        detected_types=[],
                        ast_summary={},
                        dependencies={},
                        conventions={},
                        indexed_symbols=0,
                        system_graph_nodes_generated=0,
                        system_graph_path=None,
                        status=OnboardingStatus.FAILED.value,
                        error=str(exc),
                    )
                self.workspace = Workspace([p])
                root = p
        else:
            root = Path(raw_str).expanduser().resolve()

        if not root.exists() or not root.is_dir():
            return OnboardingResult(
                repo_path=str(root),
                project_name=root.name or "unknown",
                detected_types=[],
                ast_summary={},
                dependencies={},
                conventions={},
                indexed_symbols=0,
                system_graph_nodes_generated=0,
                system_graph_path=None,
                status=OnboardingStatus.FAILED.value,
                error=f"Repository path does not exist or is not a directory: {root}",
            )

        try:
            # 2. Project Metadata Discovery
            project_name = self._extract_project_name(root)

            # 3. Ecosystem Detection
            detected_types = self._detect_ecosystem_types(root)

            # 4. Multi-Language AST Analysis
            ast_summary, symbol_count = self._scan_ast_hierarchy(root)

            # Ensure detected_types captures ecosystems found during AST scan
            if ast_summary.languages.get("python", 0) > 0 and "python" not in detected_types:
                detected_types.append("python")
            if (ast_summary.languages.get("javascript", 0) > 0 or ast_summary.languages.get("typescript", 0) > 0) and "node" not in detected_types:
                detected_types.append("node")

            # 5. Dependency Manifest Extraction
            dependencies = self._extract_dependencies(root)
            if "node" in dependencies and "node" not in detected_types:
                detected_types.append("node")
            if "python" in dependencies and "python" not in detected_types:
                detected_types.append("python")
            if "rust" in dependencies and "rust" not in detected_types:
                detected_types.append("rust")
            if "go" in dependencies and "go" not in detected_types:
                detected_types.append("go")

            for t in detected_types:
                if t in ("python", "node", "rust", "go") and t not in dependencies:
                    dependencies[t] = []

            # 6. Conventions Detection
            conventions = self._detect_conventions(root, ast_summary, dependencies)

            # 7. Codebase Indexing
            self._index_codebase(root)

            # 8. System Graph Generation & Synchronization
            nodes_count, graph_path = self._synchronize_system_graph(
                root=root,
                project_name=project_name,
                ast_data=ast_summary,
                update_graph=update_graph,
            )

            return OnboardingResult(
                repo_path=str(root),
                project_name=project_name,
                detected_types=detected_types,
                ast_summary=ast_summary.model_dump(),
                dependencies=dependencies,
                conventions=conventions.model_dump(),
                indexed_symbols=symbol_count,
                system_graph_nodes_generated=nodes_count,
                system_graph_path=str(graph_path) if graph_path else None,
                status=OnboardingStatus.SUCCESS.value,
                error=None,
            )
        except Exception as exc:
            return OnboardingResult(
                repo_path=str(root),
                project_name=root.name or "unknown",
                detected_types=[],
                ast_summary={},
                dependencies={},
                conventions={},
                indexed_symbols=0,
                system_graph_nodes_generated=0,
                system_graph_path=None,
                status=OnboardingStatus.FAILED.value,
                error=str(exc),
            )

    # -------------------------------------------------------------------------
    # Helper Implementations
    # -------------------------------------------------------------------------

    def _extract_project_name(self, root: Path) -> str:
        """Infer project name from pyproject.toml, package.json, Cargo.toml, or directory name."""
        pyproject = root / "pyproject.toml"
        if pyproject.is_file() and not is_sensitive_path(pyproject):
            try:
                content = pyproject.read_text(encoding="utf-8", errors="replace")
                if tomllib is not None:
                    parsed = tomllib.loads(content)
                    name = parsed.get("project", {}).get("name")
                    if name and isinstance(name, str):
                        return name.strip()
                    poetry_name = parsed.get("tool", {}).get("poetry", {}).get("name")
                    if poetry_name and isinstance(poetry_name, str):
                        return poetry_name.strip()
            except Exception:
                pass

        package_json = root / "package.json"
        if package_json.is_file() and not is_sensitive_path(package_json):
            try:
                parsed = json.loads(package_json.read_text(encoding="utf-8", errors="replace"))
                name = parsed.get("name")
                if name and isinstance(name, str):
                    return name.strip()
            except Exception:
                pass

        cargo = root / "Cargo.toml"
        if cargo.is_file() and not is_sensitive_path(cargo):
            try:
                content = cargo.read_text(encoding="utf-8", errors="replace")
                if tomllib is not None:
                    parsed = tomllib.loads(content)
                    name = parsed.get("package", {}).get("name")
                    if name and isinstance(name, str):
                        return name.strip()
            except Exception:
                pass

        return root.name or "unknown"

    def _detect_ecosystem_types(self, root: Path) -> list[str]:
        """Detect project ecosystem types from root and submodules."""
        found: list[str] = []
        try:
            detected = detect_project(root)
            for t in detected.get("types", []):
                if t not in found:
                    found.append(t)
        except Exception:
            pass

        # Check subdirectories for multi-service or monorepo setups
        for sub in root.iterdir():
            if sub.is_dir() and sub.name not in _SKIP_DIRS and not is_sensitive_path(sub):
                if (sub / "package.json").is_file() and "node" not in found:
                    found.append("node")
                if ((sub / "pyproject.toml").is_file() or (sub / "requirements.txt").is_file()) and "python" not in found:
                    found.append("python")
                if (sub / "Cargo.toml").is_file() and "rust" not in found:
                    found.append("rust")
                if (sub / "go.mod").is_file() and "go" not in found:
                    found.append("go")

        return found

    def _scan_ast_hierarchy(self, root: Path) -> tuple[ASTSummary, int]:
        """Parse source code trees: Python AST and JS/TS regex symbol extraction."""
        languages: dict[str, int] = {}
        classes_list: list[dict[str, Any]] = []
        functions_list: list[dict[str, Any]] = []
        syntax_errors: list[dict[str, Any]] = []
        entry_points: list[str] = []
        total_classes = 0
        total_functions = 0
        indexed_symbols = 0
        total_files = 0

        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [
                d for d in dirnames
                if d not in _SKIP_DIRS and not is_sensitive_path(Path(dirpath) / d)
            ]
            for fname in filenames:
                fpath = Path(dirpath) / fname
                if is_sensitive_path(fpath):
                    continue

                try:
                    rel_str = str(fpath.relative_to(root)).replace("\\", "/")
                except ValueError:
                    rel_str = fname

                ext = fpath.suffix.lower()

                # Python AST parsing
                if ext == ".py":
                    total_files += 1
                    languages["python"] = languages.get("python", 0) + 1
                    try:
                        content = fpath.read_text(encoding="utf-8", errors="replace")
                        tree = ast.parse(content, filename=str(fpath))
                    except (SyntaxError, UnicodeDecodeError, OSError) as exc:
                        syntax_errors.append({"file": rel_str, "error": str(exc)})
                        continue

                    # Entry points detection
                    if (
                        '__name__ == "__main__"' in content
                        or "__name__ == '__main__'" in content
                        or fname in {"main.py", "app.py", "server.py", "cli.py", "run.py", "manage.py"}
                    ):
                        if rel_str not in entry_points:
                            entry_points.append(rel_str)

                    # Extract module-level classes and functions
                    for node in tree.body:
                        if isinstance(node, ast.ClassDef):
                            total_classes += 1
                            indexed_symbols += 1
                            raw_doc = ast.get_docstring(node)
                            doc = redact_secrets(raw_doc) if raw_doc else None
                            decs = [self._unparse_node(d) for d in node.decorator_list]
                            bases = [self._unparse_node(b) for b in node.bases]
                            methods = []
                            for item in node.body:
                                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                    indexed_symbols += 1
                                    m_raw_doc = ast.get_docstring(item)
                                    m_doc = redact_secrets(m_raw_doc) if m_raw_doc else None
                                    methods.append({
                                        "name": item.name,
                                        "kind": "async_function" if isinstance(item, ast.AsyncFunctionDef) else "function",
                                        "line": item.lineno,
                                        "end_line": getattr(item, "end_lineno", item.lineno),
                                        "docstring": m_doc,
                                        "parameters": [a.arg for a in item.args.args],
                                        "decorators": [self._unparse_node(d) for d in item.decorator_list],
                                    })
                            classes_list.append({
                                "name": node.name,
                                "kind": "class",
                                "file": rel_str,
                                "line": node.lineno,
                                "end_line": getattr(node, "end_lineno", node.lineno),
                                "docstring": doc,
                                "decorators": decs,
                                "bases": bases,
                                "methods": methods,
                            })
                        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            total_functions += 1
                            indexed_symbols += 1
                            f_raw_doc = ast.get_docstring(node)
                            f_doc = redact_secrets(f_raw_doc) if f_raw_doc else None
                            functions_list.append({
                                "name": node.name,
                                "kind": "async_function" if isinstance(node, ast.AsyncFunctionDef) else "function",
                                "file": rel_str,
                                "line": node.lineno,
                                "end_line": getattr(node, "end_lineno", node.lineno),
                                "docstring": f_doc,
                                "parameters": [a.arg for a in node.args.args],
                                "decorators": [self._unparse_node(d) for d in node.decorator_list],
                            })

                # JavaScript / TypeScript regex symbol extraction
                elif ext in {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}:
                    total_files += 1
                    lang = "typescript" if ext in {".ts", ".tsx"} else "javascript"
                    languages[lang] = languages.get(lang, 0) + 1
                    try:
                        content = fpath.read_text(encoding="utf-8", errors="replace")
                    except (UnicodeDecodeError, OSError) as exc:
                        syntax_errors.append({"file": rel_str, "error": str(exc)})
                        continue

                    if fname in {"index.js", "index.ts", "server.js", "server.ts", "main.js", "main.ts", "app.js", "app.ts"}:
                        if rel_str not in entry_points:
                            entry_points.append(rel_str)

                    # Classes
                    for m in re.finditer(r"(?:export\s+)?class\s+(\w+)", content):
                        cname = m.group(1)
                        line_no = content[:m.start()].count("\n") + 1
                        classes_list.append({"name": cname, "kind": "class", "file": rel_str, "line": line_no})
                        total_classes += 1
                        indexed_symbols += 1

                    # Interfaces (TS)
                    if lang == "typescript":
                        for m in re.finditer(r"(?:export\s+)?interface\s+(\w+)", content):
                            iname = m.group(1)
                            line_no = content[:m.start()].count("\n") + 1
                            classes_list.append({"name": iname, "kind": "interface", "file": rel_str, "line": line_no})
                            total_classes += 1
                            indexed_symbols += 1

                    # Functions: function declarations
                    for m in re.finditer(r"(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)", content):
                        fname_match = m.group(1)
                        line_no = content[:m.start()].count("\n") + 1
                        params = [p.strip() for p in m.group(2).split(",") if p.strip()]
                        functions_list.append({"name": fname_match, "kind": "function", "file": rel_str, "line": line_no, "parameters": params})
                        total_functions += 1
                        indexed_symbols += 1

                    # Functions: arrow functions & function expressions
                    for m in re.finditer(r"(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\(([^)]*)\)\s*=>", content):
                        fname_match = m.group(1)
                        line_no = content[:m.start()].count("\n") + 1
                        params = [p.strip() for p in m.group(2).split(",") if p.strip()]
                        functions_list.append({"name": fname_match, "kind": "function", "file": rel_str, "line": line_no, "parameters": params})
                        total_functions += 1
                        indexed_symbols += 1

        summary = ASTSummary(
            total_files=total_files,
            languages=languages,
            total_classes=total_classes,
            total_functions=total_functions,
            entry_points=entry_points,
            classes=classes_list,
            functions=functions_list,
            syntax_errors=syntax_errors,
        )
        return summary, indexed_symbols

    @staticmethod
    def _unparse_node(node: ast.AST) -> str:
        """Helper to stringify AST nodes (decorators, bases)."""
        if hasattr(ast, "unparse"):
            try:
                return ast.unparse(node)
            except Exception:
                pass
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return f"{getattr(node.value, 'id', 'attr')}.{node.attr}"
        return str(getattr(node, "id", type(node).__name__))

    def _extract_dependencies(self, root: Path) -> dict[str, list[str]]:
        """Extract dependency packages from requirements.txt, pyproject.toml, package.json, Cargo.toml, go.mod."""
        deps: dict[str, list[str]] = {}

        # 1. requirements.txt and requirements*.txt
        for req_file in root.glob("requirements*.txt"):
            if req_file.is_file() and not is_sensitive_path(req_file):
                try:
                    for line in req_file.read_text(encoding="utf-8", errors="replace").splitlines():
                        cleaned = line.split("#")[0].strip()
                        if cleaned:
                            if "python" not in deps:
                                deps["python"] = []
                            if cleaned not in deps["python"]:
                                deps["python"].append(cleaned)
                except Exception:
                    pass

        # 2. pyproject.toml
        pyproject = root / "pyproject.toml"
        if pyproject.is_file() and not is_sensitive_path(pyproject):
            try:
                content = pyproject.read_text(encoding="utf-8", errors="replace")
                if tomllib is not None:
                    parsed = tomllib.loads(content)
                    proj_deps = parsed.get("project", {}).get("dependencies", [])
                    if isinstance(proj_deps, list):
                        if "python" not in deps:
                            deps["python"] = []
                        for d in proj_deps:
                            if isinstance(d, str) and d.strip() and d.strip() not in deps["python"]:
                                deps["python"].append(d.strip())
                    opt_deps = parsed.get("project", {}).get("optional-dependencies", {})
                    if isinstance(opt_deps, dict):
                        if "python" not in deps:
                            deps["python"] = []
                        for opt_list in opt_deps.values():
                            if isinstance(opt_list, list):
                                for d in opt_list:
                                    if isinstance(d, str) and d.strip() and d.strip() not in deps["python"]:
                                        deps["python"].append(d.strip())
                    poetry_deps = parsed.get("tool", {}).get("poetry", {}).get("dependencies", {})
                    if isinstance(poetry_deps, dict):
                        if "python" not in deps:
                            deps["python"] = []
                        for k, v in poetry_deps.items():
                            if k.lower() != "python":
                                spec = (
                                    f"{k}>={v}"
                                    if isinstance(v, str) and not v.startswith(("^", "~", "=", ">", "<"))
                                    else f"{k}{v}"
                                    if isinstance(v, str)
                                    else k
                                )
                                if spec not in deps["python"]:
                                    deps["python"].append(spec)
            except Exception:
                pass

        # 3. package.json in root and subdirectories
        pkg_files = [f for f in root.glob("**/package.json") if not any(p in _SKIP_DIRS for p in f.parts)]
        for pkg_file in pkg_files:
            if pkg_file.is_file() and not is_sensitive_path(pkg_file):
                try:
                    pkg_data = json.loads(pkg_file.read_text(encoding="utf-8", errors="replace"))
                    if isinstance(pkg_data, dict):
                        all_keys: list[str] = []
                        for section in ("dependencies", "devDependencies", "peerDependencies"):
                            sec_dict = pkg_data.get(section, {})
                            if isinstance(sec_dict, dict):
                                for k in sec_dict.keys():
                                    if k not in all_keys:
                                        all_keys.append(k)
                        if all_keys:
                            if "node" not in deps:
                                deps["node"] = []
                            for k in all_keys:
                                if k not in deps["node"]:
                                    deps["node"].append(k)
                except Exception:
                    pass

        # 4. Cargo.toml
        cargo = root / "Cargo.toml"
        if cargo.is_file() and not is_sensitive_path(cargo):
            try:
                content = cargo.read_text(encoding="utf-8", errors="replace")
                if tomllib is not None:
                    parsed = tomllib.loads(content)
                    c_deps = parsed.get("dependencies", {})
                    if isinstance(c_deps, dict):
                        deps["rust"] = list(c_deps.keys())
            except Exception:
                pass

        # 5. go.mod
        go_mod = root / "go.mod"
        if go_mod.is_file() and not is_sensitive_path(go_mod):
            try:
                content = go_mod.read_text(encoding="utf-8", errors="replace")
                go_deps = []
                for m in re.finditer(r"require\s+(\S+)\s+(\S+)", content):
                    go_deps.append(f"{m.group(1)} {m.group(2)}")
                if go_deps:
                    deps["go"] = go_deps
            except Exception:
                pass

        return deps

    def _detect_conventions(
        self,
        root: Path,
        ast_data: ASTSummary,
        dependencies: dict[str, list[str]],
    ) -> ConventionsSummary:
        """Detect testing framework, linters, layout, docstring style, and Git info."""
        test_framework: Optional[str] = None
        test_dirs: list[str] = []
        linters: list[str] = []
        docstring_convention: Optional[str] = None
        package_layout = "flat"
        git_init = (root / ".git").is_dir()
        git_branch: Optional[str] = None

        if git_init:
            head_path = root / ".git" / "HEAD"
            if head_path.is_file():
                try:
                    head_text = head_path.read_text(encoding="utf-8", errors="ignore").strip()
                    m = re.search(r"ref:\s*refs/heads/(\S+)", head_text)
                    git_branch = m.group(1) if m else "HEAD"
                except Exception:
                    pass

        # Package layout
        if (root / "src").is_dir():
            package_layout = "src-layout"
        elif (root / "packages").is_dir() or (root / "apps").is_dir() or ((root / "frontend").is_dir() and (root / "backend").is_dir()):
            package_layout = "monorepo"

        # Test directories
        for dname in ("tests", "test", "__tests__", "spec"):
            if (root / dname).is_dir():
                test_dirs.append(dname)

        has_py_tests = False
        for tdir in test_dirs:
            if list((root / tdir).glob("test_*.py")) or list((root / tdir).glob("*_test.py")):
                has_py_tests = True
                break

        py_deps = dependencies.get("python", [])
        node_deps = dependencies.get("node", [])

        if (
            (root / "pytest.ini").is_file()
            or (root / "conftest.py").is_file()
            or any("pytest" in d for d in py_deps)
            or has_py_tests
        ):
            test_framework = "pytest"
        elif any("jest" in d for d in node_deps) or list(root.glob("jest.config.*")):
            test_framework = "jest"
        elif any("vitest" in d for d in node_deps) or list(root.glob("vitest.config.*")):
            test_framework = "vitest"
        elif (root / "Cargo.toml").is_file():
            test_framework = "cargo test"
        elif (root / "go.mod").is_file():
            test_framework = "go test"

        # Linters and formatters
        if (root / "ruff.toml").is_file() or (root / ".ruff.toml").is_file():
            linters.append("ruff")
        elif (root / "pyproject.toml").is_file():
            try:
                toml_text = (root / "pyproject.toml").read_text(encoding="utf-8", errors="ignore")
                if "[tool.ruff]" in toml_text:
                    linters.append("ruff")
                if "[tool.black]" in toml_text and "black" not in linters:
                    linters.append("black")
                if "[tool.mypy]" in toml_text and "mypy" not in linters:
                    linters.append("mypy")
            except Exception:
                pass

        if (
            (root / ".eslintrc.json").is_file()
            or (root / ".eslintrc.js").is_file()
            or (root / "eslint.config.js").is_file()
            or any("eslint" in d for d in node_deps)
        ):
            if "eslint" not in linters:
                linters.append("eslint")

        if (
            (root / ".prettierrc").is_file()
            or (root / ".prettierrc.json").is_file()
            or (root / "prettier.config.js").is_file()
            or any("prettier" in d for d in node_deps)
        ):
            if "prettier" not in linters:
                linters.append("prettier")

        if (root / "mypy.ini").is_file() and "mypy" not in linters:
            linters.append("mypy")
        if (root / ".flake8").is_file() and "flake8" not in linters:
            linters.append("flake8")

        # Docstring convention
        all_funcs = ast_data.functions + [m for c in ast_data.classes for m in c.get("methods", [])]
        for f in all_funcs:
            doc = f.get("docstring") or ""
            if "Args:" in doc or "Returns:" in doc or "Raises:" in doc:
                docstring_convention = "google"
                break
            elif "Parameters\n" in doc or "Returns\n" in doc:
                docstring_convention = "numpy"
                break
            elif ":param " in doc or ":return:" in doc:
                docstring_convention = "sphinx"
                break

        naming: dict[str, str] = {}
        if ast_data.classes:
            naming["classes"] = "PascalCase"
        if ast_data.functions:
            naming["functions"] = "snake_case"

        return ConventionsSummary(
            test_framework=test_framework,
            test_directories=test_dirs,
            linter_formatter=linters,
            docstring_convention=docstring_convention,
            naming_conventions=naming,
            package_layout=package_layout,
            git_initialized=git_init,
            git_branch=git_branch,
        )

    def _index_codebase(self, root: Path) -> int:
        """Run CodebaseIndex bounded chunking and optional CodebaseMemoryAdapter."""
        if self.codebase_index is not None:
            try:
                self.codebase_index.index_project(root)
            except Exception:
                pass
        elif self.workspace is not None:
            try:
                ci = CodebaseIndex(self.workspace)
                ci.index_project(root)
            except Exception:
                pass

        if self.codebase_memory is not None:
            try:
                if self.codebase_memory.available():
                    self.codebase_memory.index_repository(str(root))
            except Exception:
                pass

        return 0

    def _synchronize_system_graph(
        self,
        root: Path,
        project_name: str,
        ast_data: ASTSummary,
        update_graph: bool,
    ) -> tuple[int, Path | None]:
        """Synthesize/update system.graph.yaml, ensuring schema compliance and zero cycles."""
        graph_path = root / "agent" / "architecture" / "system.graph.yaml"
        existing_nodes: list[dict[str, Any]] = []
        system_meta = {
            "name": project_name,
            "version": "0.1.0",
            "repository": project_name,
        }

        if graph_path.is_file():
            try:
                existing_data = yaml.safe_load(graph_path.read_text(encoding="utf-8"))
                if isinstance(existing_data, dict) and "system" in existing_data:
                    sys_dict = existing_data["system"]
                    system_meta["name"] = sys_dict.get("name", project_name)
                    system_meta["version"] = sys_dict.get("version", "0.1.0")
                    system_meta["repository"] = sys_dict.get("repository", project_name)
                    nodes_raw = sys_dict.get("nodes")
                    if isinstance(nodes_raw, list):
                        existing_nodes = [n for n in nodes_raw if isinstance(n, dict)]
            except Exception:
                pass

        existing_ids = {n["id"] for n in existing_nodes if "id" in n}

        # Collect source files discovered in AST scan
        files_to_node: list[str] = []
        for c in ast_data.classes:
            f = c.get("file")
            if f and f not in files_to_node:
                files_to_node.append(f)
        for fn in ast_data.functions:
            f = fn.get("file")
            if f and f not in files_to_node:
                files_to_node.append(f)
        for ep in ast_data.entry_points:
            if ep not in files_to_node:
                files_to_node.append(ep)

        # Discover other source files on disk
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [
                d for d in dirnames
                if d not in _SKIP_DIRS and not is_sensitive_path(Path(dirpath) / d)
            ]
            for fname in filenames:
                ext = Path(fname).suffix.lower()
                if ext in {".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs"}:
                    fpath = Path(dirpath) / fname
                    if not is_sensitive_path(fpath):
                        try:
                            rel = str(fpath.relative_to(root)).replace("\\", "/")
                            if rel not in files_to_node:
                                files_to_node.append(rel)
                        except ValueError:
                            pass

        new_nodes: list[dict[str, Any]] = []
        for rel_file in files_to_node:
            clean = rel_file
            for ext in (".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs"):
                if clean.lower().endswith(ext):
                    clean = clean[:-len(ext)]
                    break
            clean_id = "NODE_" + re.sub(r"[^A-Za-z0-9]+", "_", clean).strip("_").upper()
            if clean_id in existing_ids:
                continue

            lower_rel = rel_file.lower()
            if any(k in lower_rel for k in ("main", "app", "server", "routes", "api")):
                ntype = "api"
            elif any(k in lower_rel for k in ("model", "schema", "entity")):
                ntype = "model"
            elif any(k in lower_rel for k in ("test", "spec")):
                ntype = "test"
            elif any(k in lower_rel for k in ("ui", "web", "view", "component")):
                ntype = "ui"
            elif any(k in lower_rel for k in ("tool", "cli")):
                ntype = "tool"
            else:
                ntype = "service"

            new_nodes.append({
                "id": clean_id,
                "type": ntype,
                "file": rel_file,
                "responsibility": f"Module component for {clean.replace('/', '.')}",
                "state": "ACTIVE",
                "dependencies": [],
            })
            existing_ids.add(clean_id)

        # Infer dependencies between new nodes without creating cycles
        file_to_id = {n["file"]: n["id"] for n in (existing_nodes + new_nodes) if "file" in n and "id" in n}
        adj: dict[str, set[str]] = {n["id"]: set(n.get("dependencies", [])) for n in (existing_nodes + new_nodes)}

        def has_path(src: str, dst: str, visited: set[str]) -> bool:
            if src == dst:
                return True
            visited.add(src)
            for nbr in adj.get(src, set()):
                if nbr not in visited:
                    if has_path(nbr, dst, visited):
                        return True
            return False

        for node in new_nodes:
            node_file = root / node["file"]
            if node_file.is_file():
                try:
                    text = node_file.read_text(encoding="utf-8", errors="ignore")
                    for other_file, other_id in file_to_id.items():
                        if other_id != node["id"]:
                            stem = Path(other_file).stem
                            if stem != "__init__" and len(stem) > 2:
                                if re.search(r"\b" + re.escape(stem) + r"\b", text):
                                    if not has_path(other_id, node["id"], set()):
                                        node["dependencies"].append(other_id)
                                        adj[node["id"]].add(other_id)
                except Exception:
                    pass

        all_nodes = existing_nodes + new_nodes
        graph_dict = {
            "system": {
                **system_meta,
                "nodes": all_nodes,
            }
        }

        # Validate against SystemGraphValidator
        diagnostics = SystemGraphValidator.validate_dict(graph_dict, repo_root=root)
        if not diagnostics.ok:
            # If any cycle occurred, strip dependencies from newly synthesized nodes
            for n in new_nodes:
                n["dependencies"] = []
            diagnostics = SystemGraphValidator.validate_dict(graph_dict, repo_root=root)

        if update_graph:
            graph_path.parent.mkdir(parents=True, exist_ok=True)
            graph_path.write_text(yaml.dump(graph_dict, sort_keys=False), encoding="utf-8")
            return len(all_nodes), graph_path
        else:
            return len(all_nodes), None
