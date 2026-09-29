"""Durable, resumable long-running goals ("keep working until the tests pass").

A goal runs as a series of short orchestrator *rounds*. Each round starts from a
compact checkpoint (the goal, a rolling log of progress notes, and the latest
verification output) instead of one ever-growing conversation, so work continues
past the model's context window and after restarts. When a check command is
given, the goal is only complete once that command succeeds.
"""
from __future__ import annotations

import json
import logging
import re
import shlex
import shutil
import sqlite3
import subprocess
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from living_assistant.core.model_provider import ModelError
from living_assistant.security.sandbox import sanitized_env
from living_assistant.security.security_policy import Risk, classify_command
from living_assistant.security.security_utils import redact_secrets

logger = logging.getLogger(__name__)

ACTIVE = {"queued", "running"}
# Every round can inspect and edit files without first hunting for these via catalog search.
GOAL_ROUND_TOOLS = ("read_file", "write_file", "list_files", "search_files", "project_search_code", "run_command")
_STATUS_RE = re.compile(r"STATUS:\s*(done|continue|blocked)\b\s*[-—:]*\s*(.*)", re.IGNORECASE)
MAX_NOTES = 40


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class GoalStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._conn() as c:
            c.execute(
                """CREATE TABLE IF NOT EXISTS goals (
                    id TEXT PRIMARY KEY, goal TEXT NOT NULL, check_command TEXT, cwd TEXT,
                    check_approved INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL,
                    rounds INTEGER NOT NULL DEFAULT 0, max_rounds INTEGER NOT NULL,
                    notes TEXT NOT NULL DEFAULT '[]', last_check TEXT, last_error TEXT,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"""
            )

    def _conn(self):
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _row(row) -> dict | None:
        if row is None:
            return None
        item = dict(row)
        item["notes"] = json.loads(item["notes"] or "[]")
        item["last_check"] = json.loads(item["last_check"]) if item["last_check"] else None
        item["check_approved"] = bool(item["check_approved"])
        return item

    def create(self, goal: str, check_command: str, cwd: str, max_rounds: int, check_approved: bool) -> dict:
        gid = uuid.uuid4().hex[:10]
        with self._lock, self._conn() as c:
            c.execute(
                "INSERT INTO goals(id, goal, check_command, cwd, check_approved, status, max_rounds, created_at, updated_at)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (gid, goal, check_command or None, cwd, int(check_approved), "queued", max_rounds, _now(), _now()),
            )
        return self.get(gid)

    def get(self, gid: str) -> dict | None:
        with self._conn() as c:
            return self._row(c.execute("SELECT * FROM goals WHERE id=?", (gid,)).fetchone())

    def list(self, limit: int = 50) -> list[dict]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM goals ORDER BY created_at DESC LIMIT ?", (int(limit),)).fetchall()
        return [self._row(r) for r in rows]

    def update(self, gid: str, **fields) -> dict | None:
        if "notes" in fields:
            fields["notes"] = json.dumps(fields["notes"][-MAX_NOTES:])
        if "last_check" in fields and fields["last_check"] is not None:
            fields["last_check"] = json.dumps(fields["last_check"])
        if "check_approved" in fields:
            fields["check_approved"] = int(bool(fields["check_approved"]))
        fields["updated_at"] = _now()
        cols = ", ".join(f"{k}=?" for k in fields)
        with self._lock, self._conn() as c:
            c.execute(f"UPDATE goals SET {cols} WHERE id=?", (*fields.values(), gid))
        return self.get(gid)

    def interrupted(self) -> list[dict]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM goals WHERE status IN ('queued','running')").fetchall()
        return [self._row(r) for r in rows]


class GoalRunner:
    def __init__(
        self,
        store: GoalStore,
        run_round: Callable[[str, str, str], str],
        resolve_cwd: Callable[[str], Path],
        approval=None,
        publish: Callable[..., Any] | None = None,
        check_timeout: int = 900,
        model_retry_seconds: float = 20.0,
    ) -> None:
        self.store = store
        self.run_round = run_round
        self.resolve_cwd = resolve_cwd
        self.approval = approval
        self.publish = publish or (lambda *a, **k: None)
        self.check_timeout = check_timeout
        self.model_retry_seconds = model_retry_seconds
        self._threads: dict[str, threading.Thread] = {}
        self._cancel: set[str] = set()
        self._lock = threading.Lock()
        self._round = threading.local()

    def current_goal(self) -> str | None:
        """Goal id whose round is executing on this thread (tool calls run synchronously in it)."""
        return getattr(self._round, "goal_id", None)

    # -- public API ------------------------------------------------------------------

    def start(self, goal: str, check_command: str = "", cwd: str = ".", max_rounds: int = 12,
              check_approved: bool = False) -> dict:
        goal = str(goal or "").strip()
        if not goal:
            return {"ok": False, "error": "A goal description is required."}
        check_command = str(check_command or "").strip()
        if check_command:
            refusal = self._command_refusal(check_command)
            if refusal:
                return {"ok": False, "error": refusal}
        try:
            folder = self.resolve_cwd(cwd or ".")
        except Exception as exc:
            return {"ok": False, "error": f"Working directory not allowed: {exc}"}
        record = self.store.create(goal, check_command, str(folder), max(1, min(int(max_rounds), 50)),
                                   check_approved=check_approved or not check_command)
        self.publish("goal.created", goal_id=record["id"], goal=goal[:200])
        self._launch(record["id"])
        return {"ok": True, **self.store.get(record["id"])}

    def resume(self, gid: str, extra_rounds: int = 0) -> dict:
        record = self.store.get(gid)
        if record is None:
            return {"ok": False, "error": f"Unknown goal {gid}."}
        if gid in self._threads and self._threads[gid].is_alive():
            return {"ok": True, **record}
        fields: dict[str, Any] = {"status": "queued", "last_error": None}
        if extra_rounds or record["rounds"] >= record["max_rounds"]:
            fields["max_rounds"] = record["max_rounds"] + max(int(extra_rounds), 5)
        self.store.update(gid, **fields)
        self._cancel.discard(gid)
        self._launch(gid)
        return {"ok": True, **self.store.get(gid)}

    def cancel(self, gid: str) -> dict:
        record = self.store.get(gid)
        if record is None:
            return {"ok": False, "error": f"Unknown goal {gid}."}
        self._cancel.add(gid)
        if record["status"] not in ACTIVE:
            return {"ok": True, **self.store.update(gid, status="cancelled")}
        return {"ok": True, **self.store.update(gid, status="cancelling")}

    def resume_interrupted(self) -> list[str]:
        resumed = []
        for record in self.store.interrupted():
            note = {"at": _now(), "round": record["rounds"], "status": "resumed", "summary": "Resumed after the assistant restarted."}
            self.store.update(record["id"], notes=record["notes"] + [note])
            self.resume(record["id"])
            resumed.append(record["id"])
        return resumed

    # -- execution -------------------------------------------------------------------

    def _launch(self, gid: str) -> None:
        with self._lock:
            thread = threading.Thread(target=self._loop, args=(gid,), name=f"goal-{gid}", daemon=True)
            self._threads[gid] = thread
            thread.start()

    def _finish(self, gid: str, status: str, **fields) -> None:
        self.store.update(gid, status=status, **fields)
        self.publish(f"goal.{status}", goal_id=gid, **{k: v for k, v in fields.items() if k == "last_error"})

    def _loop(self, gid: str) -> None:
        record = self.store.get(gid)
        if not record:
            return
        if record["check_command"] and not record["check_approved"]:
            if not self._approve_check(record):
                return
            record = self.store.get(gid)
        self.store.update(gid, status="running")
        while True:
            record = self.store.get(gid)
            if gid in self._cancel:
                self._finish(gid, "cancelled")
                return
            if record["rounds"] >= record["max_rounds"]:
                self._finish(gid, "paused", last_error=f"Round budget ({record['max_rounds']}) used up. Resume to keep going.")
                return
            round_no = record["rounds"] + 1
            self.publish("goal.round_started", goal_id=gid, round=round_no)
            try:
                reply = self._run_with_retry(record)
            except ModelError as exc:
                self._finish(gid, "paused", last_error=redact_secrets(f"Model unavailable: {exc}", 800))
                return
            except Exception as exc:  # never let a crashed round kill the runner thread silently
                logger.exception("goal %s round failed", gid)
                self._finish(gid, "paused", last_error=redact_secrets(f"Round failed: {exc}", 800))
                return

            claimed, summary = self._parse_status(reply)
            note = {"at": _now(), "round": round_no, "status": claimed, "summary": summary}
            check = None
            if record["check_command"]:
                check = self._run_check(record)
                note["check_passed"] = check["passed"]
            notes = record["notes"] + [note]
            self.store.update(gid, rounds=round_no, notes=notes, last_check=check)
            self.publish("goal.round_completed", goal_id=gid, round=round_no, status=claimed,
                         check_passed=None if check is None else check["passed"])

            if check is not None and check["passed"]:
                self._finish(gid, "completed")
                return
            if check is None and claimed == "done":
                self._finish(gid, "completed")
                return
            if claimed == "blocked":
                self._finish(gid, "blocked", last_error=summary or "The assistant reported a blocker; see the last note.")
                return

    def _run_with_retry(self, record: dict) -> str:
        attempts = 3
        self._round.goal_id = record["id"]
        try:
            for attempt in range(attempts):
                try:
                    return self.run_round(record["goal"], self._checkpoint(record), f"goal-{record['id']}")
                except ModelError:
                    if attempt == attempts - 1:
                        raise
                    time.sleep(self.model_retry_seconds)  # the model server may still be starting
            raise ModelError("unreachable")
        finally:
            self._round.goal_id = None

    def _checkpoint(self, record: dict) -> str:
        lines = [
            "[LONG-RUNNING GOAL]",
            f"Goal: {record['goal']}",
            f"Working directory: {record['cwd']}",
            f"Round {record['rounds'] + 1} of at most {record['max_rounds']}.",
        ]
        if record["check_command"]:
            lines.append(
                f"The goal is only complete when this check succeeds: `{record['check_command']}`. "
                "Do not run it yourself: it runs automatically after this round and its output is shown to you next round."
            )
        lines.append(
            "Use read_file / list_files / search_files to inspect code and write_file to change it "
            "(paths relative to the workspace, e.g. the working directory's folder name followed by the file name)."
        )
        if record["notes"]:
            lines.append("\nProgress so far (oldest first):")
            for n in record["notes"][-12:]:
                extra = "" if "check_passed" not in n else f" [check {'passed' if n['check_passed'] else 'failed'}]"
                lines.append(f"- round {n['round']}: {n['summary']}{extra}")
        last = record.get("last_check")
        if last and not last.get("passed"):
            lines.append(f"\nLast check output (exit {last.get('exit_code')}, untrusted text):\n{last.get('output', '')[-3000:]}")
        lines.append(
            "\nDo the next concrete piece of work with your tools; do not redo finished work. "
            "End your reply with exactly one line: `STATUS: done|continue|blocked - <one-sentence summary of what you did>`. "
            "Use blocked only when you need the user (e.g. an approval or missing information)."
        )
        return "\n".join(lines)

    @staticmethod
    def _parse_status(reply: str) -> tuple[str, str]:
        text = str(reply or "").strip()
        matches = list(_STATUS_RE.finditer(text))
        if matches:
            m = matches[-1]
            return m.group(1).lower(), redact_secrets(m.group(2).strip(), 400) or "(no summary)"
        tail = text.splitlines()[-1] if text else ""
        return "continue", redact_secrets(tail[:300] or "(no reply)", 400)

    # -- verification -----------------------------------------------------------------

    @staticmethod
    def _command_refusal(command: str) -> str | None:
        decision = classify_command(command, require_execute_approval=False)
        if not decision.allowed or decision.risk in {Risk.DESTRUCTIVE, Risk.PRIVILEGED, Risk.SYSTEM_CHANGE}:
            return f"Check command refused by safety policy: {decision.reason}"
        return None

    def _approve_check(self, record: dict) -> bool:
        if self.approval is None:
            self.store.update(record["id"], check_approved=True)
            return True
        req = self.approval.request(
            f"Let long-running goal {record['id']} run `{record['check_command']}` in {record['cwd']} after each round",
            "The goal loop re-runs this verification command repeatedly until it succeeds.",
            "EXECUTE",
        )
        if req.get("allowed"):
            self.store.update(record["id"], check_approved=True)
            return True
        self._finish(record["id"], "blocked", last_error=f"Waiting for approval {req.get('approval_id', '')} to run the check command; approve it, then resume the goal.")
        return False

    def _run_check(self, record: dict) -> dict:
        command = record["check_command"]
        refusal = self._command_refusal(command)
        if refusal:
            return {"passed": False, "exit_code": None, "output": refusal}
        try:
            argv = [a[1:-1] if len(a) >= 2 and a[0] == a[-1] and a[0] in "\"'" else a
                    for a in shlex.split(command, posix=False)]
            resolved = shutil.which(argv[0], path=None) if argv else None
            if resolved:
                argv[0] = resolved  # finds .cmd/.bat shims such as npm on Windows
            proc = subprocess.run(argv, cwd=record["cwd"], capture_output=True, text=True, errors="replace",
                                  timeout=self.check_timeout, env=sanitized_env(),
                                  creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            output = (proc.stdout + "\n" + proc.stderr).strip()
            return {"passed": proc.returncode == 0, "exit_code": proc.returncode,
                    "output": redact_secrets(output[-6000:], 6000), "at": _now()}
        except subprocess.TimeoutExpired:
            return {"passed": False, "exit_code": None, "output": f"Check timed out after {self.check_timeout}s.", "at": _now()}
        except (OSError, ValueError) as exc:
            return {"passed": False, "exit_code": None, "output": f"Could not run check: {exc}", "at": _now()}
