from __future__ import annotations

import os
import re
import time
from collections import OrderedDict
from pathlib import Path

from living_assistant.core.config import data_dir, project_root
from living_assistant.core.workspace import Workspace
from living_assistant.security.security_utils import redact_secrets

from .base import Tool

_SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".mypy_cache", ".pytest_cache", "dist", "build", "external-components", "site-packages"}
_LOG_SUFFIXES = {".log", ".out", ".err"}
_ERROR_RE = re.compile(r"\b(ERROR|CRITICAL|FATAL|PANIC|Traceback|Exception|Unhandled|failed|failure)\b|\bE\d{4}\b", re.IGNORECASE)
_WARN_RE = re.compile(r"\b(WARN|WARNING|deprecated)\b", re.IGNORECASE)
_NOISE_RE = re.compile(r"0x[0-9a-f]+|[0-9a-f]{8,}|\d+(?:\.\d+)*|'[^']*'|\"[^\"]*\"", re.IGNORECASE)
_MAX_READ_BYTES = 8 * 1024 * 1024


def _signature(line: str) -> str:
    return _NOISE_RE.sub("#", line.strip())[:200]


def _tail_lines(path: Path, max_lines: int) -> tuple[list[str], int]:
    size = path.stat().st_size
    with path.open("rb") as fh:
        start = max(0, size - _MAX_READ_BYTES)
        fh.seek(start)
        data = fh.read()
    lines = data.decode("utf-8", errors="replace").splitlines()
    if start > 0 and lines:
        lines = lines[1:]
    return lines[-max_lines:], size


def _analyze(lines: list[str], offset: int = 0, pattern: re.Pattern | None = None) -> dict:
    groups: "OrderedDict[str, dict]" = OrderedDict()
    warnings = 0
    tracebacks: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if pattern is not None and not pattern.search(line):
            i += 1
            continue
        if line.lstrip().startswith("Traceback (most recent call last)"):
            block = [line]
            j = i + 1
            while j < len(lines) and (lines[j].startswith((" ", "\t")) or not lines[j].strip()):
                block.append(lines[j])
                j += 1
            if j < len(lines):
                block.append(lines[j])
            if len(tracebacks) < 5:
                tracebacks.append(redact_secrets("\n".join(block[-25:]), 4000))
            key = _signature(block[-1])
            g = groups.setdefault(key, {"count": 0, "first_line": offset + i + 1, "sample": redact_secrets(block[-1], 500)})
            g["count"] += 1
            g["last_line"] = offset + j + 1
            i = j + 1
            continue
        if _ERROR_RE.search(line):
            key = _signature(line)
            g = groups.setdefault(key, {"count": 0, "first_line": offset + i + 1, "sample": redact_secrets(line, 500)})
            g["count"] += 1
            g["last_line"] = offset + i + 1
        elif _WARN_RE.search(line):
            warnings += 1
        i += 1
    errors = sorted(groups.values(), key=lambda g: (-g["count"], -g.get("last_line", 0)))
    return {
        "error_count": sum(g["count"] for g in errors),
        "distinct_errors": len(errors),
        "warning_count": warnings,
        "top_errors": errors[:15],
        "tracebacks": tracebacks,
    }


def build_log_tools(workspace: Workspace, registry=None) -> list[Tool]:
    def roots() -> list[Path]:
        found = [*workspace.roots, data_dir() / "logs", project_root()]
        if registry is not None:
            try:
                for item in (registry.list() or {}).values():
                    if isinstance(item, dict) and item.get("path"):
                        found.append(Path(item["path"]))
            except Exception:
                pass
        out, seen = [], set()
        for r in found:
            try:
                rp = Path(r).expanduser().resolve()
            except OSError:
                continue
            if rp.exists() and rp not in seen:
                seen.add(rp)
                out.append(rp)
        return out

    def resolve(path: str) -> Path:
        raw = Path(str(path)).expanduser()
        candidates = [raw] if raw.is_absolute() else [r / raw for r in roots()]
        allowed = roots()
        for cand in candidates:
            rp = cand.resolve()
            if rp.is_file() and any(rp == a or a in rp.parents for a in allowed):
                return rp
        raise FileNotFoundError(
            f"No readable log file '{path}' inside the workspace, the assistant logs, or a registered project. "
            "Use logs_list to see available log files."
        )

    def logs_list(query: str = "", limit: int = 50):
        q = str(query or "").lower()
        files = []
        for root in roots():
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".")]
                in_logs_dir = "log" in Path(dirpath).name.lower()
                for name in filenames:
                    p = Path(dirpath) / name
                    if p.suffix.lower() not in _LOG_SUFFIXES and not in_logs_dir:
                        continue
                    if q and q not in str(p).lower():
                        continue
                    try:
                        st = p.stat()
                    except OSError:
                        continue
                    if st.st_size == 0:
                        continue
                    files.append((st.st_mtime, p, st.st_size))
                if len(files) > 5000:
                    break
        files.sort(reverse=True)
        limit = max(1, min(int(limit), 200))
        return {
            "ok": True,
            "searched_roots": [str(r) for r in roots()],
            "files": [
                {"path": str(p), "size_bytes": size, "modified": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mt))}
                for mt, p, size in files[:limit]
            ],
            "total_found": len(files),
        }

    def logs_scan(path: str, lines: int = 2000, pattern: str = "", follow_seconds: int = 0):
        try:
            target = resolve(path)
        except FileNotFoundError as exc:
            return {"ok": False, "error": str(exc)}
        lines = max(10, min(int(lines), 50_000))
        regex = None
        if pattern:
            try:
                regex = re.compile(pattern, re.IGNORECASE)
            except re.error as exc:
                return {"ok": False, "error": f"Invalid pattern: {exc}"}
        tail, size = _tail_lines(target, lines)
        report = {"ok": True, "path": str(target), "lines_scanned": len(tail), **_analyze(tail, pattern=regex)}
        report["last_lines"] = [redact_secrets(x, 800) for x in tail[-20:]]

        follow = max(0, min(int(follow_seconds), 300))
        if follow:
            deadline = time.monotonic() + follow
            new_lines: list[str] = []
            position = size
            while time.monotonic() < deadline:
                time.sleep(1.0)
                try:
                    current = target.stat().st_size
                except OSError:
                    break
                if current < position:
                    position = 0
                if current > position:
                    with target.open("rb") as fh:
                        fh.seek(position)
                        chunk = fh.read(min(current - position, _MAX_READ_BYTES))
                    position += len(chunk)
                    new_lines.extend(chunk.decode("utf-8", errors="replace").splitlines())
            report["monitor"] = {
                "watched_seconds": follow,
                "new_lines": len(new_lines),
                **_analyze(new_lines, pattern=regex),
                "latest": [redact_secrets(x, 800) for x in new_lines[-20:]],
            }
        return report

    return [
        Tool(
            "logs_list",
            "List log files (application logs, server logs, process output) in the workspace, the assistant's own logs, and registered projects, newest first.",
            {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Optional substring to filter paths, e.g. 'api' or 'server'."},
                    "limit": {"type": "integer", "default": 50},
                },
            },
            logs_list,
        ),
        Tool(
            "logs_scan",
            (
                "Analyze or monitor a log file: find errors, exceptions, tracebacks and warnings, grouped by repeated "
                "signature with counts. Set follow_seconds to watch the log live and report new errors."
            ),
            {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Log file path from logs_list (absolute or relative)."},
                    "lines": {"type": "integer", "default": 2000, "description": "How many trailing lines to analyze."},
                    "pattern": {"type": "string", "description": "Optional regex; only matching lines are analyzed."},
                    "follow_seconds": {"type": "integer", "default": 0, "description": "Watch for new lines for this long (max 300)."},
                },
                "required": ["path"],
            },
            logs_scan,
        ),
    ]
