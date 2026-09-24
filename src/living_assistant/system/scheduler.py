from __future__ import annotations

import datetime as dt
import json
import logging
from pathlib import Path
import sqlite3
import threading
import time
from typing import Any, Callable

from living_assistant.core.config import data_dir
from living_assistant.core.sqlite_utils import ThreadLocalSQLite
from living_assistant.security.security_utils import redact_secrets

logger = logging.getLogger("living_assistant.system.scheduler")


class ScheduledTaskStore:
    """Structured SQLite database for scheduled reminders, recurring cron jobs, and background maintenance."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.path = db_path or (data_dir() / "scheduler.sqlite3")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = ThreadLocalSQLite(self.path)
        self._init_db()

    def _init_db(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS scheduled_tasks (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                trigger_type TEXT NOT NULL,
                trigger_spec TEXT NOT NULL,
                action_type TEXT NOT NULL,
                action_payload TEXT NOT NULL,
                misfire_policy TEXT NOT NULL DEFAULT 'fire_immediately',
                status TEXT NOT NULL DEFAULT 'active',
                next_run_at TEXT,
                last_run_at TEXT,
                missed_count INTEGER DEFAULT 0,
                run_count INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_tasks_status ON scheduled_tasks(status);
            CREATE INDEX IF NOT EXISTS idx_tasks_category ON scheduled_tasks(category);
            CREATE INDEX IF NOT EXISTS idx_tasks_next_run ON scheduled_tasks(next_run_at);
            """
        )

    def save_task(self, task: dict) -> None:
        self.conn.execute(
            """
            INSERT INTO scheduled_tasks (
                id, name, category, trigger_type, trigger_spec, action_type,
                action_payload, misfire_policy, status, next_run_at, last_run_at,
                missed_count, run_count, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                category=excluded.category,
                trigger_type=excluded.trigger_type,
                trigger_spec=excluded.trigger_spec,
                action_type=excluded.action_type,
                action_payload=excluded.action_payload,
                misfire_policy=excluded.misfire_policy,
                status=excluded.status,
                next_run_at=excluded.next_run_at,
                last_run_at=excluded.last_run_at,
                missed_count=excluded.missed_count,
                run_count=excluded.run_count
            """,
            (
                task["id"],
                task["name"],
                task["category"],
                task["trigger_type"],
                json.dumps(task.get("trigger_spec", {})),
                task["action_type"],
                json.dumps(task.get("action_payload", {})),
                task.get("misfire_policy", "fire_immediately"),
                task.get("status", "active"),
                task.get("next_run_at"),
                task.get("last_run_at"),
                int(task.get("missed_count", 0)),
                int(task.get("run_count", 0)),
                task.get("created_at") or dt.datetime.now().isoformat(timespec="seconds"),
            ),
        )
        self.conn.commit()

    def get_task(self, task_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM scheduled_tasks WHERE id=?", (task_id,)
        ).fetchone()
        if not row:
            return None
        return self._format_row(row)

    def list_tasks(
        self, category: str | None = None, status: str | None = None
    ) -> list[dict]:
        query = "SELECT * FROM scheduled_tasks WHERE 1=1"
        params: list[Any] = []
        if category:
            query += " AND category=?"
            params.append(category)
        if status:
            query += " AND status=?"
            params.append(status)
        query += " ORDER BY COALESCE(next_run_at, '9999-99-99'), created_at DESC"
        rows = self.conn.execute(query, params).fetchall()
        return [self._format_row(r) for r in rows]

    def delete_task(self, task_id: str) -> bool:
        cur = self.conn.execute(
            "DELETE FROM scheduled_tasks WHERE id=?", (task_id,)
        )
        self.conn.commit()
        return cur.rowcount > 0

    def mark_executed(self, task_id: str, next_run_at: str | None = None) -> None:
        now_iso = dt.datetime.now().isoformat(timespec="seconds")
        status = "completed" if next_run_at is None else "active"
        self.conn.execute(
            """
            UPDATE scheduled_tasks
            SET last_run_at=?, next_run_at=?, run_count=run_count+1, status=?
            WHERE id=?
            """,
            (now_iso, next_run_at, status, task_id),
        )
        self.conn.commit()

    def mark_missed(self, task_id: str, next_run_at: str | None = None) -> None:
        now_iso = dt.datetime.now().isoformat(timespec="seconds")
        status = "completed" if next_run_at is None else "active"
        self.conn.execute(
            """
            UPDATE scheduled_tasks
            SET last_run_at=?, next_run_at=?, missed_count=missed_count+1, status=?
            WHERE id=?
            """,
            (now_iso, next_run_at, status, task_id),
        )
        self.conn.commit()

    def get_overdue_tasks(self, now: dt.datetime | None = None) -> list[dict]:
        now = now or dt.datetime.now()
        now_iso = now.isoformat(timespec="seconds")
        rows = self.conn.execute(
            """
            SELECT * FROM scheduled_tasks
            WHERE status='active' AND next_run_at IS NOT NULL AND next_run_at <= ?
            ORDER BY next_run_at
            """,
            (now_iso,),
        ).fetchall()
        return [self._format_row(r) for r in rows]

    def _format_row(self, row: Any) -> dict:
        d = dict(row)
        try:
            d["trigger_spec"] = json.loads(d["trigger_spec"])
        except Exception:
            pass
        try:
            d["action_payload"] = json.loads(d["action_payload"])
        except Exception:
            pass
        return d


class LivingScheduler:
    """Unified APScheduler manager with persistent task database, structured misfire recovery,

    recurring cron triggers, and scheduled indexing.
    """

    def __init__(
        self,
        db_path: Path | None = None,
        notifier: Any = None,
        memory: Any = None,
    ) -> None:
        self.store = ScheduledTaskStore(db_path=db_path)
        self.notifier = notifier
        self.memory = memory
        self._action_handlers: dict[str, Callable[[dict, bool], Any]] = {}
        self._lock = threading.RLock()
        self._scheduler: Any = None
        self._init_scheduler()
        self._register_default_handlers()

    def _init_scheduler(self) -> None:
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            self._scheduler = BackgroundScheduler(daemon=True)
            self._available = True
        except ImportError:
            self._scheduler = None
            self._available = False
            logger.warning("APScheduler library not available.")

    def _register_default_handlers(self) -> None:
        self.register_action_handler("notify", self._handle_notify_action)
        self.register_action_handler("todo", self._handle_todo_action)

    def register_action_handler(
        self, action_type: str, handler: Callable[[dict, bool], Any]
    ) -> None:
        with self._lock:
            self._action_handlers[action_type] = handler

    def start(self) -> bool:
        if not self._available or self._scheduler is None:
            return False
        with self._lock:
            if not self._scheduler.running:
                self._scheduler.start()
                self._load_active_jobs_from_store()
                logger.info("LivingScheduler started successfully.")
            return True

    def stop(self, wait: bool = True) -> bool:
        if self._scheduler is None:
            return True
        with self._lock:
            if self._scheduler.running:
                self._scheduler.shutdown(wait=wait)
                logger.info("LivingScheduler shut down.")
            return True

    @property
    def is_running(self) -> bool:
        return self._scheduler is not None and self._scheduler.running

    def _handle_notify_action(self, payload: dict, is_missed: bool) -> None:
        title = payload.get("title", "Living Assistant Reminder")
        message = payload.get("message", "")
        if is_missed:
            orig = payload.get("scheduled_for", "earlier")
            message = f"[MISSED REMINDER - Originally scheduled for {orig}] {message}"
        if self.notifier:
            self.notifier.send(title, message)
        if self.memory:
            self.memory.add_event("reminder_fired", {"title": title, "message": message, "missed": is_missed})

    def _handle_todo_action(self, payload: dict, is_missed: bool) -> None:
        title = payload.get("title", "Scheduled Todo")
        due_at = payload.get("due_at")
        if self.memory:
            self.memory.add_todo(title, due_at=due_at)

    def _execute_task(self, task_id: str, is_missed: bool = False) -> Any:
        task = self.store.get_task(task_id)
        if not task:
            return None
        action_type = task.get("action_type")
        payload = dict(task.get("action_payload", {}))
        payload["scheduled_for"] = task.get("next_run_at")

        handler = self._action_handlers.get(action_type)
        res = None
        if handler:
            try:
                res = handler(payload, is_missed)
            except Exception as exc:
                logger.error("Error executing scheduled action %s for task %s: %s", action_type, task_id, exc)

        # Update next run time for recurring jobs
        next_run_iso = None
        if self._scheduler and self.is_running:
            job = self._scheduler.get_job(task_id)
            if job and job.next_run_time:
                next_run_iso = job.next_run_time.isoformat(timespec="seconds")

        if is_missed:
            self.store.mark_missed(task_id, next_run_at=next_run_iso)
        else:
            self.store.mark_executed(task_id, next_run_at=next_run_iso)

        return res

    def schedule_reminder(
        self,
        title: str,
        due_at: dt.datetime | str,
        message: str | None = None,
        misfire_policy: str = "fire_immediately",
        task_id: str | None = None,
    ) -> dict:
        """Schedules a persistent one-shot reminder at a specific date/time."""
        if isinstance(due_at, str):
            target_dt = dt.datetime.fromisoformat(due_at)
        else:
            target_dt = due_at

        tid = task_id or f"rem_{int(time.time()*1000)}"
        msg = message or title
        task_data = {
            "id": tid,
            "name": title,
            "category": "reminder",
            "trigger_type": "date",
            "trigger_spec": {"run_date": target_dt.isoformat(timespec="seconds")},
            "action_type": "notify",
            "action_payload": {"title": title, "message": msg},
            "misfire_policy": misfire_policy,
            "status": "active",
            "next_run_at": target_dt.isoformat(timespec="seconds"),
        }
        self.store.save_task(task_data)

        if self._scheduler and self.is_running:
            from apscheduler.triggers.date import DateTrigger
            self._scheduler.add_job(
                self._execute_task,
                DateTrigger(run_date=target_dt),
                args=[tid, False],
                id=tid,
                replace_existing=True,
                misfire_grace_time=3600 * 24 * 7,  # Up to 7 days misfire tolerance
            )

        return task_data

    def schedule_cron(
        self,
        name: str,
        cron_expr: str,
        action_type: str,
        action_payload: dict,
        category: str = "cron",
        misfire_policy: str = "fire_immediately",
        task_id: str | None = None,
    ) -> dict:
        """Schedules a recurring task using a standard 5-part cron expression (min hour dom mon dow)."""
        parts = cron_expr.strip().split()
        if len(parts) != 5:
            raise ValueError(f"Cron expression must have 5 parts (minute hour dom month dow), got {len(parts)}: {cron_expr!r}")

        from apscheduler.triggers.cron import CronTrigger
        trigger = CronTrigger.from_crontab(cron_expr)
        tid = task_id or f"cron_{name.lower().replace(' ', '_')}_{int(time.time())}"

        now = dt.datetime.now()
        next_run = trigger.get_next_fire_time(None, now)
        next_run_iso = next_run.isoformat(timespec="seconds") if next_run else None

        task_data = {
            "id": tid,
            "name": name,
            "category": category,
            "trigger_type": "cron",
            "trigger_spec": {"cron_expr": cron_expr},
            "action_type": action_type,
            "action_payload": action_payload,
            "misfire_policy": misfire_policy,
            "status": "active",
            "next_run_at": next_run_iso,
        }
        self.store.save_task(task_data)

        if self._scheduler and self.is_running:
            self._scheduler.add_job(
                self._execute_task,
                trigger,
                args=[tid, False],
                id=tid,
                replace_existing=True,
                misfire_grace_time=3600 * 4,
            )

        return task_data

    def schedule_interval(
        self,
        name: str,
        seconds: int,
        action_type: str,
        action_payload: dict,
        category: str = "interval",
        task_id: str | None = None,
    ) -> dict:
        """Schedules a recurring task that runs every N seconds."""
        from apscheduler.triggers.interval import IntervalTrigger
        interval_sec = max(10, int(seconds))
        trigger = IntervalTrigger(seconds=interval_sec)
        tid = task_id or f"int_{name.lower().replace(' ', '_')}_{int(time.time())}"

        next_run = dt.datetime.now() + dt.timedelta(seconds=interval_sec)
        next_run_iso = next_run.isoformat(timespec="seconds")

        task_data = {
            "id": tid,
            "name": name,
            "category": category,
            "trigger_type": "interval",
            "trigger_spec": {"seconds": interval_sec},
            "action_type": action_type,
            "action_payload": action_payload,
            "status": "active",
            "next_run_at": next_run_iso,
        }
        self.store.save_task(task_data)

        if self._scheduler and self.is_running:
            self._scheduler.add_job(
                self._execute_task,
                trigger,
                args=[tid, False],
                id=tid,
                replace_existing=True,
            )

        return task_data

    def cancel_task(self, task_id: str) -> bool:
        with self._lock:
            if self._scheduler:
                try:
                    self._scheduler.remove_job(task_id)
                except Exception:
                    pass
            return self.store.delete_task(task_id)

    def list_tasks(self, category: str | None = None, status: str | None = None) -> list[dict]:
        return self.store.list_tasks(category=category, status=status)

    def recover_missed_tasks(self, now: dt.datetime | None = None) -> list[dict]:
        """Detects tasks that were scheduled to run during a system outage or sleep period,

        and executes the explicit missed-recovery policy.
        """
        now = now or dt.datetime.now()
        overdue = self.store.get_overdue_tasks(now=now)
        recovered = []

        for task in overdue:
            policy = task.get("misfire_policy", "fire_immediately")
            tid = task["id"]
            if policy == "fire_immediately":
                logger.info("Recovering missed task %s (scheduled for %s)", tid, task.get("next_run_at"))
                self._execute_task(tid, is_missed=True)
                recovered.append({"task_id": tid, "action": "fired_immediately", "name": task["name"]})
            elif policy == "ignore":
                logger.info("Ignoring missed task %s per policy", tid)
                self.store.mark_missed(tid, next_run_at=None if task["trigger_type"] == "date" else task.get("next_run_at"))
                recovered.append({"task_id": tid, "action": "ignored", "name": task["name"]})

        return recovered

    def schedule_codebase_indexing(
        self,
        codebase_index: Any,
        interval_hours: int = 6,
        resource_manager: Any = None,
    ) -> dict:
        """Schedules recurring codebase indexing with resource throttling awareness."""
        def _indexing_action(payload: dict, is_missed: bool):
            if resource_manager and hasattr(resource_manager, "should_throttle_background_tasks"):
                throttled, _ = resource_manager.should_throttle_background_tasks()
                if throttled:
                    logger.info("Skipping scheduled codebase indexing due to active user workload.")
                    return {"skipped": True, "reason": "throttled"}
            try:
                res = codebase_index.index_project()
                logger.info("Scheduled codebase indexing completed: %s files", res.get("files_indexed"))
                return res
            except Exception as e:
                logger.warning("Scheduled codebase indexing failed: %s", e)
                return {"ok": False, "error": str(e)}

        self.register_action_handler("scheduled_indexing", _indexing_action)
        cron_expr = f"0 */{max(1, min(interval_hours, 24))} * * *"
        return self.schedule_cron(
            name="Periodic Codebase Indexing",
            cron_expr=cron_expr,
            action_type="scheduled_indexing",
            action_payload={},
            category="indexing",
            task_id="system_codebase_indexing",
        )

    def schedule_briefings(
        self,
        briefing_engine: Any,
        morning_time: str = "08:30",
        evening_time: str = "20:30",
    ) -> list[dict]:
        """Schedules morning and evening briefings using structured cron triggers."""
        def _briefing_action(payload: dict, is_missed: bool):
            kind = payload.get("briefing_kind", "morning")
            try:
                briefing = briefing_engine.build(kind=kind)
                if self.notifier and briefing.get("text"):
                    self.notifier.send(f"{kind.capitalize()} Briefing", briefing["text"])
                return {"ok": True, "kind": kind}
            except Exception as e:
                logger.warning("Scheduled briefing %s failed: %s", kind, e)
                return {"ok": False, "error": str(e)}

        self.register_action_handler("daily_briefing", _briefing_action)

        # Parse morning HH:MM
        mh, mm = morning_time.split(":")
        morning_cron = f"{int(mm)} {int(mh)} * * *"
        t1 = self.schedule_cron(
            name="Morning Briefing",
            cron_expr=morning_cron,
            action_type="daily_briefing",
            action_payload={"briefing_kind": "morning"},
            category="briefing",
            task_id="daily_morning_briefing",
        )

        # Parse evening HH:MM
        eh, em = evening_time.split(":")
        evening_cron = f"{int(em)} {int(eh)} * * *"
        t2 = self.schedule_cron(
            name="Evening Briefing",
            cron_expr=evening_cron,
            action_type="daily_briefing",
            action_payload={"briefing_kind": "evening"},
            category="briefing",
            task_id="daily_evening_briefing",
        )

        return [t1, t2]

    def _load_active_jobs_from_store(self) -> None:
        """Synchronizes database tasks with the running APScheduler instance."""
        tasks = self.store.list_tasks(status="active")
        for task in tasks:
            tid = task["id"]
            ttype = task.get("trigger_type")
            tspec = task.get("trigger_spec", {})
            try:
                if ttype == "date":
                    from apscheduler.triggers.date import DateTrigger
                    run_date = dt.datetime.fromisoformat(tspec["run_date"])
                    if run_date > dt.datetime.now():
                        self._scheduler.add_job(
                            self._execute_task,
                            DateTrigger(run_date=run_date),
                            args=[tid, False],
                            id=tid,
                            replace_existing=True,
                            misfire_grace_time=3600 * 24 * 7,
                        )
                elif ttype == "cron":
                    from apscheduler.triggers.cron import CronTrigger
                    self._scheduler.add_job(
                        self._execute_task,
                        CronTrigger.from_crontab(tspec["cron_expr"]),
                        args=[tid, False],
                        id=tid,
                        replace_existing=True,
                        misfire_grace_time=3600 * 4,
                    )
                elif ttype == "interval":
                    from apscheduler.triggers.interval import IntervalTrigger
                    self._scheduler.add_job(
                        self._execute_task,
                        IntervalTrigger(seconds=int(tspec["seconds"])),
                        args=[tid, False],
                        id=tid,
                        replace_existing=True,
                    )
            except Exception as e:
                logger.warning("Could not re-schedule stored job %s: %s", tid, e)

    def stats(self) -> dict:
        return {
            "available": self._available,
            "running": self.is_running,
            "tasks_count": len(self.store.list_tasks()),
            "active_tasks_count": len(self.store.list_tasks(status="active")),
            "registered_actions": list(self._action_handlers.keys()),
        }


_GLOBAL_SCHEDULER: LivingScheduler | None = None
_GLOBAL_LOCK = threading.Lock()


def get_scheduler(db_path: Path | None = None, notifier: Any = None, memory: Any = None) -> LivingScheduler:
    """Singleton getter for LivingScheduler."""
    global _GLOBAL_SCHEDULER
    with _GLOBAL_LOCK:
        if _GLOBAL_SCHEDULER is None:
            _GLOBAL_SCHEDULER = LivingScheduler(db_path=db_path, notifier=notifier, memory=memory)
        return _GLOBAL_SCHEDULER
