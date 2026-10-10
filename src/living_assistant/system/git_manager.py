"""
Autonomous Git Change Manager & Recovery Checkpoints Subsystem (Milestone 5 / Feature F11).
Living Assistant - Canonical Version Control & State Recovery Engine.

Manages:
- Task baselines (Git commit SHA, branch name, dirty state, worktrees).
- Dual-layer checkpoints (WorkspaceSnapshotManager archives + git write-tree SHA + commit SHA + diff patch/stat).
- SQLite persistence of baselines, checkpoints, and task-associated commits.
- Safe multi-level rollback (checkpoint restore, targeted checkout, compensating revert, worktree cleanup).
- Strict prohibition of destructive resets (git reset --hard is forbidden).
- Workspace confinement verified via workspace.resolve(path).
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
import shutil
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from living_assistant.core.config import data_dir
from living_assistant.core.sqlite_utils import ThreadLocalSQLite
from living_assistant.core.workspace import Workspace, WorkspaceViolation
from living_assistant.system.workspace_snapshots import WorkspaceSnapshotManager

logger = logging.getLogger("living_assistant.system.git_manager")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS task_baselines(
  task_id TEXT PRIMARY KEY,
  commit_sha TEXT NOT NULL,
  branch TEXT NOT NULL,
  is_dirty INTEGER NOT NULL,
  uncommitted_files_json TEXT NOT NULL,
  worktree_path TEXT,
  is_worktree INTEGER NOT NULL DEFAULT 0,
  baseline_snapshot_id TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS task_checkpoints(
  checkpoint_id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  reason TEXT NOT NULL,
  snapshot_id TEXT,
  git_tree_sha TEXT,
  commit_sha TEXT,
  created_at TEXT NOT NULL,
  files_changed_json TEXT NOT NULL,
  diff_stat TEXT,
  diff_patch TEXT
);
CREATE INDEX IF NOT EXISTS idx_checkpoints_task_time ON task_checkpoints(task_id, created_at DESC);

CREATE TABLE IF NOT EXISTS task_commits(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id TEXT NOT NULL,
  commit_sha TEXT NOT NULL,
  message TEXT NOT NULL,
  committed_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_task_commits_task ON task_commits(task_id);
"""


@dataclass
class TaskBaseline:
    """Snapshot of repository and workspace state before an autonomous task begins."""
    task_id: str
    commit_sha: str
    branch: str
    is_dirty: bool
    uncommitted_files: List[str] = field(default_factory=list)
    worktree_path: Optional[str] = None
    is_worktree: bool = False
    baseline_snapshot_id: Optional[str] = None
    timestamp: str = field(default_factory=lambda: dt.datetime.now(dt.timezone.utc).isoformat())


@dataclass
class CheckpointRecord:
    """Dual-layer checkpoint metadata created during task execution."""
    checkpoint_id: str
    task_id: str
    reason: str
    snapshot_id: Optional[str]
    git_tree_sha: Optional[str]
    commit_sha: Optional[str] = None
    created_at: str = field(default_factory=lambda: dt.datetime.now(dt.timezone.utc).isoformat())
    files_changed_since_baseline: List[str] = field(default_factory=list)
    diff_stat: Optional[str] = None
    diff_patch: Optional[str] = None


@dataclass
class RollbackResult:
    """Result of an autonomous rollback operation."""
    ok: bool
    method: str
    restored_files: int
    files: List[str] = field(default_factory=list)
    error: Optional[str] = None
    checkpoint_id: Optional[str] = None
    reverted_commits: List[str] = field(default_factory=list)


class GitChangeManager:
    """
    Canonical Autonomous Git & Workspace Change Manager (F11).
    Guarantees that task operations can be inspected, associated with commits,
    persisted across restarts via SQLite, and rolled back non-destructively
    without ever running 'git reset --hard'.
    """

    def __init__(
        self,
        workspace: Workspace,
        snapshot_manager: Optional[WorkspaceSnapshotManager] = None,
        db_path: Optional[Path] = None,
        repo_path: Optional[Path | str] = None,
    ) -> None:
        self.workspace = workspace
        target_root = Path(repo_path) if repo_path is not None else (
            workspace.roots[0] if getattr(workspace, "roots", None) else Path(".")
        )
        # Enforce workspace boundary: raises WorkspaceViolation if target_root escapes
        self.root = self.workspace.resolve(target_root)

        # Determine top-level git repository root if inside git
        try:
            probe = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=str(self.root),
                capture_output=True,
                text=True,
                timeout=5,
            )
            if probe.returncode == 0 and probe.stdout.strip():
                self.top_level = Path(probe.stdout.strip()).resolve()
            else:
                self.top_level = self.root
        except Exception:
            self.top_level = self.root

        self.snapshot_manager = snapshot_manager or WorkspaceSnapshotManager(workspace=workspace)
        self.db_path = db_path or (data_dir() / "assistant.sqlite3")
        self.conn = ThreadLocalSQLite(self.db_path)
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

        self._baselines: Dict[str, TaskBaseline] = {}
        self._checkpoints: Dict[str, List[CheckpointRecord]] = {}
        self._lock = threading.Lock()

    def get_git_status(self) -> Dict[str, Any]:
        """Inspects current Git state: HEAD commit, branch, and uncommitted files."""
        commit_sha = "unknown"
        branch = "unknown"
        uncommitted: List[str] = []

        try:
            p1 = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(self.root),
                capture_output=True,
                text=True,
                timeout=5,
            )
            if p1.returncode == 0:
                commit_sha = p1.stdout.strip()

            p2 = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=str(self.root),
                capture_output=True,
                text=True,
                timeout=5,
            )
            if p2.returncode == 0:
                branch = p2.stdout.strip()

            p3 = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(self.root),
                capture_output=True,
                text=True,
                timeout=5,
            )
            if p3.returncode == 0:
                for line in p3.stdout.splitlines():
                    if line.strip():
                        parts = line.strip().split(maxsplit=1)
                        if len(parts) == 2:
                            uncommitted.append(parts[1].strip())
        except Exception as exc:
            logger.debug("Git status check fallback: %s", exc)

        return {
            "commit_sha": commit_sha,
            "branch": branch,
            "is_dirty": len(uncommitted) > 0,
            "uncommitted_files": uncommitted,
        }

    def establish_baseline(
        self,
        task_id: str,
        use_worktree: bool = False,
        worktree_branch: Optional[str] = None,
        worktree_path: Optional[str | Path] = None,
    ) -> TaskBaseline:
        """
        Captures pre-task baseline. If the working tree is dirty when established,
        or if git is uninitialized (commit_sha == 'unknown'),
        an automatic pre-task baseline snapshot is recorded to preserve pre-existing state.
        """
        st = self.get_git_status()
        baseline_snapshot_id: Optional[str] = None

        if st["is_dirty"] or st["commit_sha"] == "unknown":
            try:
                snap = self.snapshot_manager.create(
                    project_root=self.root,
                    reason=f"Task {task_id}: Pre-task baseline snapshot",
                )
                if isinstance(snap, dict):
                    baseline_snapshot_id = snap.get("snapshot_id") or snap.get("id")
                else:
                    baseline_snapshot_id = getattr(snap, "snapshot_id", None) or getattr(snap, "id", None)
            except Exception as exc:
                logger.warning("Automatic pre-task snapshot creation error: %s", exc)

        baseline = TaskBaseline(
            task_id=task_id,
            commit_sha=st["commit_sha"],
            branch=st["branch"],
            is_dirty=st["is_dirty"],
            uncommitted_files=st["uncommitted_files"],
            worktree_path=str(worktree_path) if worktree_path else None,
            is_worktree=use_worktree,
            baseline_snapshot_id=baseline_snapshot_id,
        )

        with self._lock:
            self._baselines[task_id] = baseline

        # Persist to SQLite
        try:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO task_baselines
                (task_id, commit_sha, branch, is_dirty, uncommitted_files_json, worktree_path, is_worktree, baseline_snapshot_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    baseline.task_id,
                    baseline.commit_sha,
                    baseline.branch,
                    1 if baseline.is_dirty else 0,
                    json.dumps(baseline.uncommitted_files),
                    baseline.worktree_path,
                    1 if baseline.is_worktree else 0,
                    baseline.baseline_snapshot_id,
                    baseline.timestamp,
                ),
            )
            self.conn.commit()
        except Exception as exc:
            logger.warning("Failed to persist baseline to SQLite: %s", exc)

        logger.info(
            "Established task baseline for %s (commit=%s, dirty=%s, snapshot=%s)",
            task_id,
            baseline.commit_sha[:8] if baseline.commit_sha else "unknown",
            baseline.is_dirty,
            baseline.baseline_snapshot_id,
        )
        return baseline

    def get_baseline(self, task_id: str) -> Optional[TaskBaseline]:
        """Retrieves task baseline from memory cache or persistent SQLite store."""
        if task_id in self._baselines:
            return self._baselines[task_id]

        try:
            cur = self.conn.execute(
                "SELECT * FROM task_baselines WHERE task_id = ?",
                (task_id,),
            )
            row = cur.fetchone()
            if row:
                baseline = TaskBaseline(
                    task_id=row["task_id"],
                    commit_sha=row["commit_sha"],
                    branch=row["branch"],
                    is_dirty=bool(row["is_dirty"]),
                    uncommitted_files=json.loads(row["uncommitted_files_json"]),
                    worktree_path=row["worktree_path"],
                    is_worktree=bool(row["is_worktree"]),
                    baseline_snapshot_id=row["baseline_snapshot_id"],
                    timestamp=row["created_at"],
                )
                self._baselines[task_id] = baseline
                return baseline
        except Exception as exc:
            logger.debug("Failed to retrieve baseline from SQLite: %s", exc)

        return None

    def create_checkpoint(
        self,
        task_id: str,
        reason: str = "Pre-task state",
        include_diff: bool = True,
    ) -> CheckpointRecord:
        """
        Creates a dual-layer checkpoint:
        1. Source filesystem snapshot via WorkspaceSnapshotManager.
        2. Git write-tree SHA, commit SHA, unified diff patch, and diffstat.
        """
        snapshot_id: Optional[str] = None
        try:
            snap = self.snapshot_manager.create(project_root=self.root, reason=f"Task {task_id}: {reason}")
            if isinstance(snap, dict):
                snapshot_id = snap.get("snapshot_id") or snap.get("id")
            else:
                snapshot_id = getattr(snap, "snapshot_id", None) or getattr(snap, "id", None)
        except Exception as exc:
            logger.warning("Snapshot creation error: %s", exc)

        files_changed = self.get_changed_files(task_id)

        git_tree_sha: Optional[str] = None
        try:
            p = subprocess.run(
                ["git", "write-tree"],
                cwd=str(self.root),
                capture_output=True,
                text=True,
                timeout=5,
            )
            if p.returncode == 0:
                git_tree_sha = p.stdout.strip()
        except Exception:
            pass

        commit_sha: Optional[str] = None
        try:
            p_sha = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(self.root),
                capture_output=True,
                text=True,
                timeout=5,
            )
            if p_sha.returncode == 0:
                commit_sha = p_sha.stdout.strip()
        except Exception:
            pass

        diff_patch: Optional[str] = None
        diff_stat: Optional[str] = None
        if include_diff:
            diff_patch = self.get_diff()
            try:
                p_stat = subprocess.run(
                    ["git", "diff", "--stat", "HEAD"],
                    cwd=str(self.root),
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if p_stat.returncode == 0:
                    diff_stat = p_stat.stdout
            except Exception:
                pass

        with self._lock:
            existing = self.get_checkpoints(task_id)
            idx = len(existing) + 1
            while True:
                candidate_id = f"chk_{task_id}_{idx}"
                cur = self.conn.execute(
                    "SELECT 1 FROM task_checkpoints WHERE checkpoint_id = ?",
                    (candidate_id,),
                )
                if not cur.fetchone():
                    checkpoint_id = candidate_id
                    break
                idx += 1

            record = CheckpointRecord(
                checkpoint_id=checkpoint_id,
                task_id=task_id,
                reason=reason,
                snapshot_id=snapshot_id,
                git_tree_sha=git_tree_sha,
                commit_sha=commit_sha,
                files_changed_since_baseline=files_changed,
                diff_stat=diff_stat,
                diff_patch=diff_patch,
            )

            if task_id not in self._checkpoints:
                self._checkpoints[task_id] = []
            self._checkpoints[task_id].append(record)

            try:
                self.conn.execute(
                    """
                    INSERT INTO task_checkpoints
                    (checkpoint_id, task_id, reason, snapshot_id, git_tree_sha, commit_sha, created_at, files_changed_json, diff_stat, diff_patch)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.checkpoint_id,
                        record.task_id,
                        record.reason,
                        record.snapshot_id,
                        record.git_tree_sha,
                        record.commit_sha,
                        record.created_at,
                        json.dumps(record.files_changed_since_baseline),
                        record.diff_stat,
                        record.diff_patch,
                    ),
                )
                self.conn.commit()
            except Exception as exc:
                logger.warning("Failed to persist checkpoint to SQLite: %s", exc)

            return record

    def get_checkpoints(self, task_id: str) -> List[CheckpointRecord]:
        """Returns all checkpoints for task_id ordered by timestamp."""
        try:
            cur = self.conn.execute(
                "SELECT * FROM task_checkpoints WHERE task_id = ? ORDER BY created_at ASC",
                (task_id,),
            )
            rows = cur.fetchall()
            if rows:
                db_records = [
                    CheckpointRecord(
                        checkpoint_id=r["checkpoint_id"],
                        task_id=r["task_id"],
                        reason=r["reason"],
                        snapshot_id=r["snapshot_id"],
                        git_tree_sha=r["git_tree_sha"],
                        commit_sha=r["commit_sha"],
                        created_at=r["created_at"],
                        files_changed_since_baseline=json.loads(r["files_changed_json"]),
                        diff_stat=r["diff_stat"],
                        diff_patch=r["diff_patch"],
                    )
                    for r in rows
                ]
                self._checkpoints[task_id] = db_records
                return db_records
        except Exception as exc:
            logger.debug("Failed to query checkpoints from SQLite: %s", exc)

        return list(self._checkpoints.get(task_id, []))

    def get_checkpoint(self, checkpoint_id: str) -> Optional[CheckpointRecord]:
        """Retrieves a single checkpoint by ID from cache or SQLite."""
        for ck_list in self._checkpoints.values():
            for rec in ck_list:
                if rec.checkpoint_id == checkpoint_id:
                    return rec

        try:
            cur = self.conn.execute(
                "SELECT * FROM task_checkpoints WHERE checkpoint_id = ?",
                (checkpoint_id,),
            )
            r = cur.fetchone()
            if r:
                return CheckpointRecord(
                    checkpoint_id=r["checkpoint_id"],
                    task_id=r["task_id"],
                    reason=r["reason"],
                    snapshot_id=r["snapshot_id"],
                    git_tree_sha=r["git_tree_sha"],
                    commit_sha=r["commit_sha"],
                    created_at=r["created_at"],
                    files_changed_since_baseline=json.loads(r["files_changed_json"]),
                    diff_stat=r["diff_stat"],
                    diff_patch=r["diff_patch"],
                )
        except Exception as exc:
            logger.debug("Failed to query checkpoint %s from SQLite: %s", checkpoint_id, exc)

        return None

    def get_changed_files(self, task_id: Optional[str] = None) -> List[str]:
        """Returns list of files changed relative to Git HEAD or baseline uncommitted list."""
        st = self.get_git_status()
        current_uncommitted = set(st["uncommitted_files"])

        if task_id:
            baseline = self.get_baseline(task_id)
            if baseline:
                baseline_uncommitted = set(baseline.uncommitted_files)
                newly_touched = current_uncommitted - baseline_uncommitted
                return sorted(list(newly_touched) if newly_touched else list(current_uncommitted))

        return sorted(list(current_uncommitted))

    def get_diff(self, paths: Optional[List[str]] = None, staged: bool = False) -> str:
        """Returns unified diff of workspace changes within confinement."""
        cmd = ["git", "diff"]
        if staged:
            cmd.append("--cached")
        if paths:
            # Enforce workspace boundary check on each supplied path
            for p in paths:
                self.workspace.resolve(p)
            cmd.append("--")
            cmd.extend(paths)
        try:
            p = subprocess.run(
                cmd,
                cwd=str(self.root),
                capture_output=True,
                text=True,
                timeout=10,
            )
            if p.returncode == 0:
                return p.stdout
        except Exception as exc:
            logger.debug("Git diff failed: %s", exc)
        return ""

    def rollback_to_checkpoint(self, checkpoint_id: str) -> Dict[str, Any]:
        """
        Non-destructive rollback (Level 2): Restores workspace from WorkspaceSnapshotManager archive.
        Never executes 'git reset --hard' to prevent loss of external uncommitted files.
        """
        found_record = self.get_checkpoint(checkpoint_id)

        if not found_record:
            return {
                "ok": False,
                "error": f"Checkpoint '{checkpoint_id}' not found.",
            }

        if not found_record.snapshot_id:
            return {
                "ok": False,
                "error": f"Checkpoint '{checkpoint_id}' has no associated snapshot archive.",
            }

        try:
            restore_res = self.snapshot_manager.restore(found_record.snapshot_id)
            return {
                "ok": True,
                "checkpoint_id": checkpoint_id,
                "restored_files": restore_res.get("restored_files", 0),
                "method": "workspace_snapshot_restore",
            }
        except Exception as exc:
            return {
                "ok": False,
                "checkpoint_id": checkpoint_id,
                "error": f"Rollback failed: {exc}",
            }

    def rollback_to_baseline(self, task_id: str, strategy: str = "auto") -> Dict[str, Any]:
        """
        Safely rolls back changes made during a task without destructive resets:
        - Never restores intermediate checkpoints (checkpoints[0]).
        - Cleans working tree relative to HEAD (targeted checkout of tracked files,
          safe unlinking of untracked files and symlinks without external resolution).
        - Reverts compensating task commits (Level 3: git revert) in reverse order.
        - Restores baseline pre-task snapshot (Level 2) if baseline was dirty or non-git at establishment.
        - Cleans up worktrees (Level 4) if worktree isolation was used.
        """
        baseline = self.get_baseline(task_id)
        if not baseline:
            return {
                "ok": False,
                "error": f"No baseline found for task {task_id}.",
                "restored_files": 0,
                "files": [],
            }

        restored_count = 0
        reverted_files: List[str] = []
        methods_used: List[str] = []

        # -------------------------------------------------------------------------
        # Step 1: Clean Working Tree relative to current HEAD (Level 1)
        # -------------------------------------------------------------------------
        changed = self.get_changed_files(task_id)
        baseline_uncommitted = set(baseline.uncommitted_files if baseline else [])

        tracked_to_checkout: List[str] = []
        untracked_to_remove: List[str] = []

        for f in changed:
            clean_name = f.strip('"').rstrip("/\\")
            cand_entry = self.root / clean_name
            # Lexical confinement check: ensure entry does not escape repository root via ../
            try:
                norm_cand = Path(os.path.abspath(cand_entry))
                norm_cand.relative_to(self.root)
            except ValueError:
                # On Windows drive letters or case, verify commonpath
                try:
                    if os.path.commonpath([str(self.root).lower(), str(norm_cand).lower()]) != str(self.root).lower():
                        raise WorkspaceViolation(f"Changed file path escapes repository root: {f}")
                except Exception:
                    raise WorkspaceViolation(f"Changed file path escapes repository root: {f}")

            # Check Git tracking status
            probe = subprocess.run(
                ["git", "ls-files", "--error-unmatch", clean_name],
                cwd=str(self.root),
                capture_output=True,
                text=True,
            )
            if probe.returncode == 0:
                tracked_to_checkout.append(clean_name)
            else:
                # Only remove untracked file if it was not already uncommitted at baseline establishment
                if clean_name not in baseline_uncommitted and f not in baseline_uncommitted:
                    untracked_to_remove.append(clean_name)

        # Checkout tracked files to clean state
        if tracked_to_checkout:
            try:
                p = subprocess.run(
                    ["git", "checkout", "HEAD", "--"] + tracked_to_checkout,
                    cwd=str(self.root),
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                if p.returncode == 0:
                    restored_count += len(tracked_to_checkout)
                    reverted_files.extend(tracked_to_checkout)
                    methods_used.append("git_checkout_head")
                else:
                    logger.warning("Targeted checkout failed: %s", p.stderr)
            except Exception as exc:
                logger.warning("Safe file rollback failed: %s", exc)

        # Safely remove untracked files and symlinks
        for unf in untracked_to_remove:
            target_path = self.root / unf
            try:
                # Critical security: check is_symlink() BEFORE any resolve() to avoid following external targets
                if target_path.is_symlink():
                    try:
                        target_path.unlink()
                    except OSError:
                        target_path.rmdir()
                    restored_count += 1
                    reverted_files.append(unf)
                elif target_path.is_file():
                    target_path.unlink()
                    restored_count += 1
                    reverted_files.append(unf)
                elif target_path.is_dir():
                    shutil.rmtree(target_path)
                    restored_count += 1
                    reverted_files.append(unf)
            except Exception as exc:
                logger.warning("Failed to remove untracked artifact %s: %s", unf, exc)

        if untracked_to_remove:
            methods_used.append("untracked_artifact_cleanup")

        # -------------------------------------------------------------------------
        # Step 2: Level 3 Revert Compensating Task Commits
        # -------------------------------------------------------------------------
        task_commits = self.get_task_commits(task_id)
        reverted_commits: List[str] = []
        for tc in reversed(task_commits):
            rev_res = self.safe_revert_commit(tc["commit_sha"], task_id=task_id)
            if rev_res.get("ok"):
                reverted_commits.append(tc["commit_sha"])
            else:
                logger.warning("Reverting commit %s failed: %s", tc["commit_sha"], rev_res.get("error"))

        if reverted_commits:
            methods_used.append("git_revert")

        # -------------------------------------------------------------------------
        # Step 3: Level 2 Pre-Task Baseline Snapshot Restore (if baseline was dirty or non-git)
        # -------------------------------------------------------------------------
        if baseline.baseline_snapshot_id:
            try:
                restore_res = self.snapshot_manager.restore(baseline.baseline_snapshot_id)
                restored_count += restore_res.get("restored_files", 1)
                methods_used.append("workspace_snapshot_restore")
            except Exception as exc:
                logger.warning("Baseline snapshot restore failed: %s", exc)

        # -------------------------------------------------------------------------
        # Step 4: Level 4 Worktree Cleanup
        # -------------------------------------------------------------------------
        worktree_removed = False
        if baseline.is_worktree and baseline.worktree_path:
            try:
                subprocess.run(
                    ["git", "worktree", "remove", "--force", baseline.worktree_path],
                    cwd=str(self.root),
                    capture_output=True,
                    text=True,
                )
                worktree_removed = True
                methods_used.append("worktree_removal")
            except Exception as exc:
                logger.warning("Worktree remove failed: %s", exc)

        return {
            "ok": True,
            "task_id": task_id,
            "restored_files": restored_count,
            "files": reverted_files,
            "reverted_commits": reverted_commits,
            "worktree_removed": worktree_removed,
            "message": "No files changed." if (restored_count == 0 and not reverted_commits) else "",
            "method": "+".join(methods_used) if methods_used else "clean_baseline_noop",
        }

    def safe_revert_commit(self, commit_sha: str, task_id: Optional[str] = None) -> Dict[str, Any]:
        """Performs non-destructive git revert --no-edit on a specific commit (Level 3)."""
        try:
            p = subprocess.run(
                ["git", "revert", "--no-edit", commit_sha],
                cwd=str(self.root),
                capture_output=True,
                text=True,
                timeout=15,
            )
            if p.returncode == 0:
                return {"ok": True, "reverted_commit": commit_sha, "method": "git_revert"}
            return {"ok": False, "commit_sha": commit_sha, "error": p.stderr}
        except Exception as exc:
            return {"ok": False, "commit_sha": commit_sha, "error": str(exc)}

    def record_task_commit(self, task_id: str, commit_sha: str, message: str) -> None:
        """Records a git commit associated with a task ID in SQLite."""
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        try:
            self.conn.execute(
                "INSERT INTO task_commits (task_id, commit_sha, message, committed_at) VALUES (?, ?, ?, ?)",
                (task_id, commit_sha, message, now),
            )
            self.conn.commit()
        except Exception as exc:
            logger.warning("Failed to record task commit in SQLite: %s", exc)

    def get_task_commits(self, task_id: str) -> List[Dict[str, str]]:
        """Retrieves list of git commits recorded for a task ID."""
        try:
            cur = self.conn.execute(
                "SELECT task_id, commit_sha, message, committed_at FROM task_commits WHERE task_id = ? ORDER BY id ASC",
                (task_id,),
            )
            return [
                {
                    "task_id": r["task_id"],
                    "commit_sha": r["commit_sha"],
                    "message": r["message"],
                    "committed_at": r["committed_at"],
                }
                for r in cur.fetchall()
            ]
        except Exception as exc:
            logger.debug("Failed to query task commits: %s", exc)
            return []

    def safe_commit(self, task_id: str, message: str) -> Dict[str, Any]:
        """Safely commits changes locally associated with a task ID."""
        if not message.strip():
            return {"ok": False, "error": "Commit message is required."}

        formatted_msg = message if message.startswith(f"[{task_id}]") else f"[{task_id}] {message}"
        try:
            p = subprocess.run(
                ["git", "commit", "-m", formatted_msg],
                cwd=str(self.root),
                capture_output=True,
                text=True,
                timeout=15,
            )
            if p.returncode != 0:
                return {"ok": False, "error": p.stderr}

            p_sha = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(self.root),
                capture_output=True,
                text=True,
            )
            sha = p_sha.stdout.strip() if p_sha.returncode == 0 else "unknown"
            self.record_task_commit(task_id, sha, formatted_msg)
            return {"ok": True, "commit_sha": sha, "message": formatted_msg}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
