"""Deterministic project audit: syntax, security, dependencies, SEO, test discovery, health score.

Standard library only, so it runs anywhere with `python audit.py <command> <folder>` and prints JSON.
The same file is imported by the assistant's company engine as its automatic quality gate, so the
skill and the gate can never disagree. Everything except `run-checks` only reads files.

Commands:
  health <folder> [--run]   overall score + findings (add --run to also execute the discovered checks)
  report <folder>           everything static at once (lint, dead code, security, deps, health, SEO, checks)
  syntax <folder>           Python files that do not parse
  lint <folder>             Python lint + dead-code candidates
  security <folder>         security findings: AST for Python, rules for other files (tests excluded,
                            secret files never read, secret values never printed)
  deps <folder>             dependency pinning / lockfile hygiene (offline)
  seo <folder>              static SEO audit of HTML/templates
  checks <folder>           which test/lint/type checks the project has
  run-checks <folder>       run those checks and report pass/fail (executes project code)

Merges the assistant's former ProjectAuditor (AST security pass, lint, dead code, pyproject) with ports from
the user's ai-coding-assistant project (test_discovery, verification_service, security_review,
dependency_health, seo_auditor, project_health). system/project_auditor.py is now a thin adapter over this file.
"""
from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

SKIP_DIRS = {".git", ".hg", ".svn", "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
             ".venv", "venv", "env", "dist", "build", ".next", "coverage", ".cache", ".turbo", "site-packages"}
SOURCE_EXT = {".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rs", ".rb", ".php", ".cs", ".html", ".htm"}
MAX_FILES = 2000
MAX_BYTES = 8_000_000
MAX_FILE_BYTES = 512_000


def iter_files(root: Path, suffixes: set[str] | None = None, limit: int = MAX_FILES) -> Iterable[Path]:
    """Files under root, skipping dependency/build folders and symlinks, bounded."""
    emitted, stack = 0, [root]
    while stack and emitted < limit:
        folder = stack.pop()
        try:
            entries = sorted(folder.iterdir(), key=lambda p: p.name)
        except OSError:
            continue
        for p in entries:
            if p.is_symlink():
                continue
            if p.is_dir():
                if p.name not in SKIP_DIRS and not p.name.startswith("."):
                    stack.append(p)
            elif suffixes is None or p.suffix.lower() in suffixes:
                emitted += 1
                yield p
                if emitted >= limit:
                    return


def rel(root: Path, p: Path) -> str:
    return p.relative_to(root).as_posix()


def is_test_path(path: str) -> bool:
    name = Path(path).name
    return path.startswith(("tests/", "test/")) or "/tests/" in path or name.startswith("test_") or name.endswith("_test.py")


def read(p: Path) -> str | None:
    try:
        if p.stat().st_size > MAX_FILE_BYTES:
            return None
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


# ---- syntax ---------------------------------------------------------------------------------

def syntax(root: Path) -> dict:
    """Parse every Python file (nothing is executed or compiled to disk)."""
    errors, checked = [], 0
    for p in iter_files(root, {".py"}):
        text = read(p)
        if text is None:
            continue
        checked += 1
        try:
            ast.parse(text, filename=str(p))
        except SyntaxError as exc:
            errors.append({"path": rel(root, p), "line": exc.lineno, "message": exc.msg})
    return {"ok": not errors, "files_checked": checked, "errors": errors[:50]}


# ---- security -------------------------------------------------------------------------------

# Secret files are never read (their values must not end up in a report).
SENSITIVE = re.compile(r"(?i)(^|/)(\.env(\..*)?|.*\.(pem|key|p12|pfx)|id_(rsa|dsa|ecdsa|ed25519)(\.pub)?|credentials(\.json)?|secrets?\.(json|ya?ml|toml))$")
SECRET_NAME = re.compile(r"(?i)(password|passwd|pwd|token|secret|api[_-]?key|access[_-]?key|private[_-]?key|credential)")
SECRET_VALUE = re.compile(r"(?:gh[pousr]_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{10,})")

# Text rules for what the Python AST pass below does not see (other languages, templates, SQL strings).
TEXT_RULES = [
    ("critical", "private-key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"), "Private key in source"),
    ("high", "sql-fstring", re.compile(r"(?is)(?:execute|executemany)\s*\(\s*f['\"][^)]*(?:select|insert|update|delete)"),
     "SQL built with an f-string (use ? placeholders)"),
    ("high", "yaml-unsafe-load", re.compile(r"\byaml\.load\s*\([^\n]*Loader\s*=\s*yaml\.(?:Loader|UnsafeLoader)", re.I),
     "Unsafe YAML loader"),
    ("medium", "sql-format", re.compile(r"(?is)(?:execute|executemany)\s*\(\s*['\"][^'\"]*(?:select|insert|update|delete)[^'\"]*['\"]\s*(?:%|\.format\()"),
     "SQL built with % or .format (use ? placeholders)"),
    ("medium", "template-safe-filter", re.compile(r"\|\s*safe\b"), "Template output marked |safe (XSS risk if it holds user input)"),
    ("medium", "debug-server", re.compile(r"\.run\s*\([^\n]*debug\s*=\s*True"), "Debug server enabled in code"),
]
# For non-Python source the AST pass cannot run, so these text versions stand in for it.
NON_PY_RULES = [
    ("high", "dangerous-call:eval", re.compile(r"(?<![\w.$])eval\s*\("), "eval() on dynamic input"),
    ("high", "hardcoded-credential-assignment", re.compile(r"(?i)(?:api[_-]?key|secret|password|token)\s*[:=]\s*['\"][^'\"\n]{8,}['\"]"),
     "Possible hard-coded credential"),
]


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _call_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def python_scan(path: str, text: str) -> dict:
    """AST pass over one Python file: security findings, lint issues, top-level definitions and names used."""
    security, lint, defs, refs = [], [], [], set()
    for lineno, line in enumerate(text.splitlines(), 1):
        if len(line) > 120:
            lint.append({"rule": "line-too-long", "path": path, "line": lineno})
        if line.rstrip() != line:
            lint.append({"rule": "trailing-whitespace", "path": path, "line": lineno})
    try:
        tree = ast.parse(text, filename=path)
    except SyntaxError as exc:
        lint.append({"rule": "syntax-error", "path": path, "line": exc.lineno or 0, "message": exc.msg})
        return {"security": security, "lint": lint, "defs": defs, "refs": refs, "parsed": False}
    def add(severity, rule, node, message, **extra):
        security.append({"severity": severity, "rule": rule, "path": path, "line": getattr(node, "lineno", 0),
                         "message": message, **extra})
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            refs.add(node.id)
        elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
            refs.add(node.attr)
        elif isinstance(node, ast.ExceptHandler) and node.type is None:
            lint.append({"rule": "bare-except", "path": path, "line": node.lineno})
        elif isinstance(node, ast.ImportFrom) and any(a.name == "*" for a in node.names):
            lint.append({"rule": "wildcard-import", "path": path, "line": node.lineno})
        elif isinstance(node, ast.Call):
            name = _call_name(node.func)
            if name in {"eval", "exec", "os.system"}:
                add("high", f"dangerous-call:{name}", node, f"{name}() runs dynamic code/commands")
            if name.startswith("subprocess.") and any(kw.arg == "shell" and isinstance(kw.value, ast.Constant)
                                                      and kw.value.value is True for kw in node.keywords):
                add("critical", "subprocess-shell-true", node, "Shell execution with shell=True")
            if name in {"pickle.load", "pickle.loads"}:
                add("high", "unsafe-pickle-load", node, "Unsafe pickle deserialization")
            if any(kw.arg == "verify" and isinstance(kw.value, ast.Constant) and kw.value.value is False
                   for kw in node.keywords):
                add("medium", "tls-verification-disabled", node, "TLS verification disabled")
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            value = node.value
            if isinstance(value, ast.Constant) and isinstance(value.value, str) and len(value.value) >= 6:
                for target in targets:
                    if isinstance(target, ast.Name) and SECRET_NAME.search(target.id):
                        add("high", "hardcoded-credential-assignment", node, "Hard-coded credential", name=target.id)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and not node.decorator_list \
                and not node.name.startswith(("__", "test_")):
            defs.append({"name": node.name, "path": path, "line": node.lineno, "kind": type(node).__name__})
    return {"security": security, "lint": lint, "defs": defs, "refs": refs, "parsed": True}


def _file_security(path: str, text: str) -> list[dict]:
    findings = python_scan(path, text)["security"] if path.endswith(".py") else []
    rules = TEXT_RULES + ([] if path.endswith(".py") else NON_PY_RULES)
    for severity, rule, pattern, message in rules:
        m = pattern.search(text)
        if m:
            findings.append({"severity": severity, "rule": rule, "path": path, "line": text.count("\n", 0, m.start()) + 1,
                             "message": message})
    for lineno, line in enumerate(text.splitlines(), 1):
        if SECRET_VALUE.search(line):  # the value itself is never copied into the finding
            findings.append({"severity": "high", "rule": "hardcoded-secret-pattern", "path": path, "line": lineno,
                             "message": "Text that looks like a real API key or token"})
    return findings


def security(root: Path, files: Iterable[str] | None = None) -> dict:
    """Security findings: an AST pass for Python, text rules for everything else. Test files are excluded
    (they often hold deliberately unsafe examples) and secret files are never read."""
    wanted = {str(f).replace("\\", "/") for f in files} if files is not None else None
    findings = []
    for p in iter_files(root, SOURCE_EXT | {".cfg", ".ini", ".toml", ".yml", ".yaml", ".json", ".jinja", ".j2"}):
        path = rel(root, p)
        if is_test_path(path) or SENSITIVE.search(path) or (wanted is not None and path not in wanted):
            continue
        text = read(p)
        if text is not None:
            findings.extend(_file_security(path, text))
    counts = {s: sum(1 for f in findings if f["severity"] == s) for s in ("critical", "high", "medium", "low")}
    return {"ok": counts["critical"] == 0 and counts["high"] == 0, "counts": counts, "findings": findings[:200]}


def lint(root: Path) -> dict:
    """Python lint without running anything: syntax errors, bare except, wildcard imports, and dead-code
    candidates (top-level functions/classes never referenced anywhere in the project)."""
    issues, defs, refs, files = [], [], set(), 0
    for p in iter_files(root, {".py"}):
        path = rel(root, p)
        if SENSITIVE.search(path):
            continue
        text = read(p)
        if text is None:
            continue
        files += 1
        scan = python_scan(path, text)
        issues.extend(scan["lint"])
        defs.extend(scan["defs"])
        refs |= scan["refs"]
    dead = [{**d, "confidence": "candidate"} for d in defs if d["name"] not in refs]
    syntax_errors = sum(1 for i in issues if i["rule"] == "syntax-error")
    score = max(0, 100 - min(100, syntax_errors * 20 + (len(issues) - syntax_errors) * 2))
    return {"python_files": files, "score": score, "issue_count": len(issues), "issues": issues[:200],
            "dead_code": {"candidate_count": len(dead), "candidates": dead[:200]}}


# ---- dependencies ---------------------------------------------------------------------------

_REQ = re.compile(r"^\s*([A-Za-z0-9_.-]+)\s*(\[[^\]]*\])?\s*([<>=!~].*)?$")


def deps(root: Path) -> dict:
    """Offline dependency hygiene: Python requirements/pyproject (no version, not pinned, conflicting pins),
    Node versions and lockfile. Nothing is downloaded."""
    issues: list[dict] = []  # one per problem dependency, with the rule names the coding API reports
    manifests, total, exact = [], 0, {}

    def python_dep(text: str, source: str) -> None:
        nonlocal total
        line = text.split("#", 1)[0].split(";", 1)[0].strip()
        if not line or line.startswith(("-", "git+", "http://", "https://")) or " @ " in line:
            return
        m = _REQ.match(line)
        if not m:
            return
        total += 1
        name, spec = m.group(1).lower().replace("_", "-"), (m.group(3) or "").strip()
        if not spec:
            issues.append({"rule": "python-unbounded-dependency", "dependency": line[:160], "path": source, "severity": "medium"})
        elif spec.startswith("==") and "," not in spec and "*" not in spec:
            exact.setdefault(name, set()).add(spec[2:].strip())
        else:
            issues.append({"rule": "python-unpinned-dependency", "dependency": line[:160], "path": source, "severity": "low"})

    for path in sorted(root.glob("requirements*.txt"))[:12]:
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        before = total
        for raw in lines:
            python_dep(raw, path.name)
        manifests.append({"type": "requirements", "path": path.name, "dependencies": total - before})
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        try:
            import tomllib
            data = tomllib.loads(pyproject.read_text(encoding="utf-8", errors="ignore"))
            listed = list((data.get("project") or {}).get("dependencies") or [])
            for dep in listed:
                python_dep(str(dep), "pyproject.toml")
            manifests.append({"type": "pyproject", "path": "pyproject.toml", "dependencies": len(listed)})
        except Exception as exc:
            issues.append({"rule": "invalid-pyproject", "path": "pyproject.toml", "error": str(exc)[:200], "severity": "high"})
    for name, versions in exact.items():
        if len(versions) > 1:
            issues.append({"rule": "python-conflicting-pins", "dependency": f"{name}: {', '.join(sorted(versions))}",
                           "severity": "high"})
    package = root / "package.json"
    if package.exists():
        try:
            data = json.loads(package.read_text(encoding="utf-8", errors="ignore"))
            declared = {}
            for key in ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies"):
                if isinstance(data.get(key), dict):
                    declared.update(data[key])
            total += len(declared)
            for name, version in declared.items():
                if str(version).strip().lower() in {"", "*", "latest", "x"}:
                    issues.append({"rule": "node-unbounded-dependency", "dependency": str(name)[:120], "severity": "medium"})
            locks = ("package-lock.json", "npm-shrinkwrap.json", "pnpm-lock.yaml", "yarn.lock", "bun.lock", "bun.lockb")
            lock = next((f for f in locks if (root / f).exists()), None)
            if declared and not lock:
                issues.append({"rule": "node-lockfile-missing", "path": "package.json", "severity": "medium"})
            manifests.append({"type": "node", "path": "package.json", "dependencies": len(declared), "lockfile": lock})
        except (OSError, ValueError) as exc:
            issues.append({"rule": "invalid-package-json", "path": "package.json", "error": str(exc)[:200], "severity": "high"})
    penalty = {"high": 30, "medium": 8, "low": 2}
    score = max(0, 100 - min(100, sum(penalty.get(i["severity"], 3) for i in issues)))
    return {"ok": not any(i["severity"] == "high" for i in issues), "score": score, "manifests": manifests,
            "dependency_count": total, "issues": issues[:200], "issue_count": len(issues),
            "findings": [{"severity": i["severity"], "code": i["rule"],
                          "message": f"{i['rule'].replace('-', ' ')}: {i.get('dependency') or i.get('path')}"} for i in issues[:50]]}


# ---- SEO ------------------------------------------------------------------------------------

def _has(pattern: str, text: str) -> bool:
    return re.search(pattern, text, re.I | re.S) is not None


def seo(root: Path) -> dict:
    """Static SEO audit of HTML pages and templates (no network, no rendering)."""
    findings, scanned = [], []
    for p in iter_files(root, {".html", ".htm", ".jinja", ".j2", ".jsx", ".tsx", ".vue", ".svelte"}, limit=250):
        text = read(p)
        if text is None:
            continue
        path = rel(root, p)
        scanned.append(path)
        partial = "{% extends" in text or "{%extends" in text  # a child template: <head> lives in the base
        def add(code, severity, message):
            findings.append({"code": code, "severity": severity, "message": message, "file": path})
        if not partial:
            if not (_has(r"<title\b[^>]*>\s*[^<]{1,200}\s*</title>", text) or _has(r"{%\s*block\s+title", text)):
                add("SEO-TITLE-MISSING", "high", "No page title")
            if not _has(r"<meta\b[^>]*name\s*=\s*['\"]description['\"]", text):
                add("SEO-DESCRIPTION-MISSING", "medium", "No meta description")
            if _has(r"<html\b", text) and not _has(r"<html\b[^>]*\blang\s*=", text):
                add("SEO-LANG-MISSING", "medium", "<html> has no lang attribute")
            if _has(r"<head\b", text) and not _has(r"<meta\b[^>]*name\s*=\s*['\"]viewport['\"]", text):
                add("SEO-VIEWPORT-MISSING", "medium", "No responsive viewport meta tag")
        h1 = len(re.findall(r"<h1\b", text, re.I))
        if h1 > 1:
            add("SEO-H1-MULTIPLE", "low", f"{h1} <h1> headings")
        missing_alt = len(re.findall(r"<img\b(?![^>]*\balt\s*=)[^>]*>", text, re.I | re.S))
        if missing_alt:
            add("SEO-IMG-ALT-MISSING", "medium", f"{missing_alt} image(s) without alt text")
        if _has(r"<meta\b[^>]*name\s*=\s*['\"]robots['\"][^>]*noindex", text):
            add("SEO-NOINDEX", "medium", "noindex directive (intended?)")
    if not scanned:
        findings.append({"code": "SEO-NO-PAGES", "severity": "info", "message": "No HTML pages or templates found"})
    penalty = {"high": 14, "medium": 7, "low": 3, "info": 0}
    score = max(0, 100 - sum(penalty[f["severity"]] for f in findings))
    return {"score": score, "files_scanned": len(scanned), "findings": findings[:100],
            "limitations": "Static source check only; does not render pages or crawl a live site."}


# ---- tests and checks -----------------------------------------------------------------------

def project_python(root: Path) -> str:
    """The project's own interpreter (its venv) when it has one, else the python on PATH."""
    for venv in (".venv", "venv", "env"):
        for candidate in (root / venv / "Scripts" / "python.exe", root / venv / "bin" / "python"):
            if candidate.exists():
                return str(candidate)
    return "python"


def checks(root: Path) -> dict:
    """The machine checks a project offers (nothing is run)."""
    plan: list[dict] = []
    py_files = list(iter_files(root, {".py"}, limit=400))
    if py_files:
        tests = [p for p in py_files if is_test_path(rel(root, p))]
        if tests or (root / "pytest.ini").exists():
            plan.append({"args": [project_python(root), "-m", "pytest", "-q", "-p", "no:cacheprovider"],
                         "purpose": "Python test suite (pytest)", "kind": "tests"})
    package = root / "package.json"
    if package.exists():
        try:
            scripts = (json.loads(package.read_text(encoding="utf-8")).get("scripts") or {})
        except (OSError, ValueError):
            scripts = {}
        npm = "npm.cmd" if os.name == "nt" else "npm"
        if "typecheck" in scripts:
            plan.append({"args": [npm, "run", "typecheck"], "purpose": "TypeScript type check", "kind": "typecheck"})
        test_script = str(scripts.get("test") or "")
        if test_script and "no test specified" not in test_script:
            plan.append({"args": [npm, "test"], "purpose": "Node test suite", "kind": "tests"})
        if "lint" in scripts:
            plan.append({"args": [npm, "run", "lint"], "purpose": "Lint", "kind": "lint"})
    return {"plan": plan, "has_checks": bool(plan), "python": project_python(root) if py_files else None}


def run_checks(root: Path, timeout: int = 300) -> dict:
    """Run the discovered checks in the project folder. This EXECUTES project code."""
    results = []
    for item in checks(root)["plan"]:
        try:
            proc = subprocess.run(item["args"], cwd=str(root), capture_output=True, text=True, timeout=timeout,
                                  encoding="utf-8", errors="replace", env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
            code = proc.returncode
            # pytest exit code 5 = no tests collected: nothing failed
            passed = code == 0 or (code == 5 and "pytest" in item["args"])
            out = (proc.stdout or "") + (proc.stderr or "")
            summary = next((ln.strip() for ln in reversed(out.splitlines())
                            if re.search(r"\b(passed|failed|error|no tests ran)\b", ln)), "")
            results.append({"purpose": item["purpose"], "command": " ".join(item["args"]), "passed": passed,
                            "returncode": code, "summary": summary[:300], "output_tail": out[-3000:]})
        except FileNotFoundError as exc:
            results.append({"purpose": item["purpose"], "command": " ".join(item["args"]), "passed": False,
                            "returncode": None, "summary": f"not runnable: {exc}", "output_tail": ""})
        except subprocess.TimeoutExpired:
            results.append({"purpose": item["purpose"], "command": " ".join(item["args"]), "passed": False,
                            "returncode": None, "summary": f"timed out after {timeout}s", "output_tail": ""})
    return {"ran": bool(results), "passed": all(r["passed"] for r in results) if results else None, "results": results}


# ---- health ---------------------------------------------------------------------------------

def health(root: Path, run: bool = False) -> dict:
    """A reproducible score (0-100) with the findings behind it."""
    syn, sec, dep, chk, lt = syntax(root), security(root), deps(root), checks(root), lint(root)
    source = [p for p in iter_files(root, SOURCE_EXT)]
    todo, large = 0, []
    for p in source[:600]:
        text = read(p) or ""
        todo += text.upper().count("TODO") + text.upper().count("FIXME")
        lines = text.count("\n") + 1
        if lines >= 800:
            large.append({"path": rel(root, p), "lines": lines})
    tests_present = any(is_test_path(rel(root, p)) for p in source)
    readme = any((root / n).exists() for n in ("README.md", "README.rst", "README.txt"))
    findings: list[dict] = []
    if not syn["ok"]:
        findings.append({"category": "quality", "severity": "critical", "message": f"{len(syn['errors'])} Python file(s) do not parse",
                         "items": syn["errors"][:10]})
    for f in sec["findings"][:20]:
        findings.append({"category": "security", **f})
    for f in dep["findings"]:
        findings.append({"category": "dependencies", **f})
    if source and not tests_present:
        findings.append({"category": "tests", "severity": "medium", "message": "No automated tests found"})
    if not readme:
        findings.append({"category": "knowledge", "severity": "low", "message": "No README"})
    if (root / ".env").exists() and not (root / ".env.example").exists():
        findings.append({"category": "knowledge", "severity": "medium", "message": ".env exists but .env.example is missing"})
    for f in large[:5]:
        findings.append({"category": "architecture", "severity": "low", "message": f"Large file {f['path']} ({f['lines']} lines)"})

    ran = run_checks(root) if run and chk["has_checks"] else None
    if ran is not None:
        tests_score = 20 + 80 * (sum(r["passed"] for r in ran["results"]) / max(1, len(ran["results"])))
        for r in ran["results"]:
            if not r["passed"]:
                findings.append({"category": "tests", "severity": "high", "message": f"Failing: {r['purpose']} - {r['summary']}"})
    else:
        tests_score = 75 if chk["has_checks"] else 45
    c = sec["counts"]
    dims = {
        "tests": tests_score,
        "security": max(0, 100 - 35 * c["critical"] - 20 * c["high"] - 7 * c["medium"] - 2 * c["low"]),
        "quality": max(0, min(lt["score"], 100 - min(20, todo * 2) - min(20, 4 * len(large))
                              - (15 if source and not tests_present else 0) - (40 if not syn["ok"] else 0))),
        "knowledge": 100 if readme else 45,
        "dependencies": dep["score"],
    }
    weights = {"tests": 0.32, "security": 0.26, "quality": 0.18, "knowledge": 0.1, "dependencies": 0.14}
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    findings.sort(key=lambda f: order.get(f.get("severity"), 9))
    return {"score": round(sum(dims[k] * w for k, w in weights.items()), 1),
            "dimensions": {k: round(v, 1) for k, v in dims.items()}, "findings": findings[:60],
            "checks": chk["plan"], "check_results": ran,
            "facts": {"source_files": len(source), "tests_present": tests_present, "readme": readme, "todo_count": todo}}


def report(root: Path) -> dict:
    """Everything static in one result (the shape the coding API and CLI have always returned, plus the
    health dimensions, SEO and discovered checks)."""
    lt, sec, dep, hl = lint(root), security(root), deps(root), health(root, run=False)
    files = list(iter_files(root))
    return {
        "ok": True, "path": str(root), "bounded": True,
        "scan": {"files_scanned": len(files), "bytes_scanned": sum(p.stat().st_size for p in files if p.exists()),
                 "truncated": len(files) >= MAX_FILES, "max_files": MAX_FILES},
        "dependencies": {k: dep[k] for k in ("manifests", "dependency_count", "issues", "issue_count")},
        "python_files": lt["python_files"],
        "lint": {"score": lt["score"], "issue_count": lt["issue_count"], "issues": lt["issues"]},
        "dead_code": lt["dead_code"],
        "security": {"finding_count": len(sec["findings"]), "severity_counts": {k: v for k, v in sec["counts"].items() if v},
                     "findings": sec["findings"]},
        "health_score": hl["score"], "dimensions": hl["dimensions"], "findings": hl["findings"],
        "checks": hl["checks"], "seo": {k: v for k, v in seo(root).items() if k != "limitations"},
    }


COMMANDS = {"health": health, "report": report, "syntax": syntax, "lint": lint, "security": security, "deps": deps,
            "seo": seo, "checks": checks, "run-checks": run_checks}


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] not in COMMANDS:
        print(__doc__)
        return 2
    root = Path(argv[2] if len(argv) > 2 and not argv[2].startswith("--") else ".").resolve()
    if not root.is_dir():
        print(json.dumps({"error": f"not a folder: {root}"}))
        return 2
    result = health(root, run="--run" in argv) if argv[1] == "health" else COMMANDS[argv[1]](root)
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
