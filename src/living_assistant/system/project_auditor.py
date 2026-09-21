from __future__ import annotations

import ast
import json
import re
import tomllib
from collections import Counter
from pathlib import Path

from living_assistant.core.workspace import Workspace
from living_assistant.security.security_utils import is_sensitive_path

_SKIP_DIRS = {
    ".git", ".venv", "venv", "node_modules", "dist", "build", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".next", ".turbo",
}
_SECRET_NAME = re.compile(r"(?i)(password|passwd|pwd|token|secret|api[_-]?key|access[_-]?key|private[_-]?key|credential)")
_SECRET_VALUE = re.compile(r"(?i)(?:gh[pousr]_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16})")


def _decorated(node: ast.AST) -> bool:
    return bool(getattr(node, "decorator_list", []))


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _call_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


class ProjectAuditor:
    """Bounded, offline-safe static project health auditor."""

    def __init__(self, workspace: Workspace, max_files: int = 1500, max_file_bytes: int = 750_000):
        self.workspace = workspace
        self.max_files = max(50, min(int(max_files), 10_000))
        self.max_file_bytes = max(16_384, min(int(max_file_bytes), 5_000_000))

    def _files(self, root: Path) -> tuple[list[Path], bool]:
        files: list[Path] = []
        truncated = False
        for path in root.rglob("*"):
            if any(part in _SKIP_DIRS for part in path.relative_to(root).parts):
                continue
            if not path.is_file() or is_sensitive_path(path):
                continue
            try:
                if path.stat().st_size > self.max_file_bytes:
                    continue
            except OSError:
                continue
            files.append(path)
            if len(files) >= self.max_files:
                truncated = True
                break
        return files, truncated

    @staticmethod
    def _dependency_audit(root: Path) -> dict:
        manifests: list[dict] = []
        issues: list[dict] = []
        total = 0

        req = root / "requirements.txt"
        if req.exists() and not is_sensitive_path(req):
            deps = []
            for raw in req.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or line.startswith("-"):
                    continue
                deps.append(line)
                if not any(op in line for op in ("==", ">=", "<=", "~=", "!=", " @ ")):
                    issues.append({"rule": "python-unbounded-dependency", "dependency": line.split(";")[0][:160]})
            total += len(deps)
            manifests.append({"type": "requirements", "path": "requirements.txt", "dependencies": len(deps)})

        pyproject = root / "pyproject.toml"
        if pyproject.exists() and not is_sensitive_path(pyproject):
            try:
                data = tomllib.loads(pyproject.read_text(encoding="utf-8", errors="ignore"))
                deps = list((data.get("project") or {}).get("dependencies") or [])
                total += len(deps)
                for dep in deps:
                    text = str(dep)
                    if not any(op in text for op in ("==", ">=", "<=", "~=", "!=", " @ ", ">", "<")):
                        issues.append({"rule": "python-unbounded-dependency", "dependency": text[:160]})
                manifests.append({"type": "pyproject", "path": "pyproject.toml", "dependencies": len(deps)})
            except Exception as exc:
                issues.append({"rule": "invalid-pyproject", "path": "pyproject.toml", "error": str(exc)[:200]})

        package = root / "package.json"
        if package.exists() and not is_sensitive_path(package):
            try:
                data = json.loads(package.read_text(encoding="utf-8", errors="ignore"))
                deps = {}
                for key in ("dependencies", "devDependencies", "peerDependencies"):
                    deps.update(data.get(key) or {})
                total += len(deps)
                for name, version in deps.items():
                    if str(version).strip().lower() in {"", "*", "latest"}:
                        issues.append({"rule": "node-unbounded-dependency", "dependency": str(name)[:120]})
                lock = next((n for n in ("package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lockb") if (root / n).exists()), None)
                if deps and not lock:
                    issues.append({"rule": "node-lockfile-missing", "path": "package.json"})
                manifests.append({"type": "node", "path": "package.json", "dependencies": len(deps), "lockfile": lock})
            except Exception as exc:
                issues.append({"rule": "invalid-package-json", "path": "package.json", "error": str(exc)[:200]})

        return {"manifests": manifests, "dependency_count": total, "issues": issues, "issue_count": len(issues)}

    @staticmethod
    def _python_scan(root: Path, files: list[Path]) -> dict:
        lint: list[dict] = []
        security: list[dict] = []
        definitions: dict[str, list[dict]] = {}
        references: Counter[str] = Counter()
        python_files = 0

        for path in files:
            if path.suffix.lower() != ".py":
                continue
            python_files += 1
            rel = str(path.relative_to(root))
            text = path.read_text(encoding="utf-8", errors="replace")
            for lineno, line in enumerate(text.splitlines(), 1):
                if len(line) > 120:
                    lint.append({"rule": "line-too-long", "path": rel, "line": lineno})
                if line.rstrip() != line:
                    lint.append({"rule": "trailing-whitespace", "path": rel, "line": lineno})
                if _SECRET_VALUE.search(line):
                    security.append({"severity": "high", "rule": "hardcoded-secret-pattern", "path": rel, "line": lineno})
            try:
                tree = ast.parse(text, filename=rel)
            except SyntaxError as exc:
                lint.append({"rule": "syntax-error", "path": rel, "line": exc.lineno or 0, "message": exc.msg})
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                    references[node.id] += 1
                elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
                    references[node.attr] += 1
                elif isinstance(node, ast.ExceptHandler) and node.type is None:
                    lint.append({"rule": "bare-except", "path": rel, "line": getattr(node, "lineno", 0)})
                elif isinstance(node, ast.ImportFrom) and any(alias.name == "*" for alias in node.names):
                    lint.append({"rule": "wildcard-import", "path": rel, "line": node.lineno})
                elif isinstance(node, ast.Call):
                    name = _call_name(node.func)
                    if name in {"eval", "exec", "os.system"}:
                        security.append({"severity": "high", "rule": f"dangerous-call:{name}", "path": rel, "line": node.lineno})
                    if name.startswith("subprocess.") and any(
                        kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True
                        for kw in node.keywords
                    ):
                        security.append({"severity": "high", "rule": "subprocess-shell-true", "path": rel, "line": node.lineno})
                    if name in {"pickle.load", "pickle.loads"}:
                        security.append({"severity": "medium", "rule": "unsafe-pickle-load", "path": rel, "line": node.lineno})
                    if any(
                        kw.arg == "verify" and isinstance(kw.value, ast.Constant) and kw.value.value is False
                        for kw in node.keywords
                    ):
                        security.append({"severity": "medium", "rule": "tls-verification-disabled", "path": rel, "line": node.lineno})
                elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    value = node.value
                    if isinstance(value, ast.Constant) and isinstance(value.value, str) and len(value.value) >= 6:
                        for target in targets:
                            if isinstance(target, ast.Name) and _SECRET_NAME.search(target.id):
                                security.append({"severity": "high", "rule": "hardcoded-credential-assignment", "path": rel, "line": node.lineno, "name": target.id})

            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    if node.name.startswith("__") or node.name.startswith("test_") or _decorated(node):
                        continue
                    definitions.setdefault(node.name, []).append({"path": rel, "line": node.lineno, "kind": type(node).__name__})

        dead = []
        for name, locations in definitions.items():
            if references[name] == 0:
                for item in locations:
                    dead.append({"name": name, **item, "confidence": "candidate"})

        syntax_count = sum(1 for x in lint if x["rule"] == "syntax-error")
        lint_score = max(0, 100 - min(100, syntax_count * 20 + (len(lint) - syntax_count) * 2))
        severity_counts = dict(Counter(item["severity"] for item in security))
        return {
            "python_files": python_files,
            "lint": {"score": lint_score, "issue_count": len(lint), "issues": lint[:200]},
            "dead_code": {"candidate_count": len(dead), "candidates": dead[:200]},
            "security": {"finding_count": len(security), "severity_counts": severity_counts, "findings": security[:200]},
        }

    def audit(self, path: str | Path = ".") -> dict:
        root = self.workspace.resolve(path)
        if not root.is_dir():
            return {"ok": False, "error": "Project audit path must be a directory."}
        files, truncated = self._files(root)
        dependency = self._dependency_audit(root)
        code = self._python_scan(root, files)
        bytes_scanned = 0
        for file in files:
            try:
                bytes_scanned += file.stat().st_size
            except OSError:
                pass
        security_penalty = code["security"]["severity_counts"].get("high", 0) * 10 + code["security"]["severity_counts"].get("medium", 0) * 4
        health_score = max(0, min(100, code["lint"]["score"] - min(30, dependency["issue_count"] * 3) - min(40, security_penalty)))
        return {
            "ok": True,
            "path": str(root),
            "bounded": True,
            "scan": {"files_scanned": len(files), "bytes_scanned": bytes_scanned, "truncated": truncated, "max_files": self.max_files},
            "dependencies": dependency,
            **code,
            "health_score": health_score,
        }
