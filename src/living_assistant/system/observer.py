from __future__ import annotations

import ctypes
import datetime as dt
import threading
import time
import uuid
# from dataclasses import dataclass, field, asdict
from typing import Any

from living_assistant.core.event_bus import EventBus
from living_assistant.learning.experience import ExperienceEngine
# from .security_utils import redact_secrets


def _get_active_window_text() -> str:
    """Read foreground window title using native Windows API."""
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        length = user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buff, length + 1)
            return buff.value
    except Exception:
        pass
    return "Desktop"


@dataclass
class ProactiveInquiry:
    id: str
    question: str
    context: str
    recovery_candidate: dict[str, Any]
    created_at: str
    status: str = "pending"  # pending | confirmed | rejected | dismissed

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ProactiveScreenObserver:
    """Observes screen changes and actions to ask contextual clarifying questions and learn verified lessons."""

    def __init__(
        self,
        event_bus: EventBus | None = None,
        experience_engine: ExperienceEngine | None = None,
        poll_interval: float = 2.5,
    ):
        self.event_bus = event_bus
        self.experiences = experience_engine
        self.poll_interval = max(1.0, float(poll_interval))
        self._lock = threading.Lock()
        self._pending_inquiries: dict[str, ProactiveInquiry] = {}
        
        self.current_window = _get_active_window_text()
        self.recent_windows: list[dict[str, Any]] = []
        self.last_detected_error: dict[str, Any] | None = None
        
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="ProactiveObserver")
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3.0)

    def _run_loop(self):
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception:
                pass
            time.sleep(self.poll_interval)

    def _tick(self):
        title = _get_active_window_text()
        now = dt.datetime.now().isoformat(timespec="seconds")

        if title and title != self.current_window and title != "Living Assistant":
            old = self.current_window
            self.current_window = title
            with self._lock:
                self.recent_windows.append({"from": old, "to": title, "at": now})
                if len(self.recent_windows) > 20:
                    self.recent_windows.pop(0)

            # Detect potential troubleshooting/error patterns in window titles
            title_lower = title.lower()
            error_keywords = ["error", "fail", "exception", "traceback", "problem", "crashed", "bug"]
            has_error = any(k in title_lower for k in error_keywords)

            if has_error:
                with self._lock:
                    self.last_detected_error = {
                        "window": title,
                        "timestamp": now,
                    }
            elif self.last_detected_error and not has_error:
                # User switched from an error state to an active editor/terminal -> Potential fix action
                with self._lock:
                    err = self.last_detected_error
                    self.last_detected_error = None

                # Only trigger if no other inquiry is currently pending
                if not self.get_pending_inquiries():
                    self.trigger_inquiry(
                        question=f"I noticed you were troubleshooting '{err['window']}' and switched to '{title}'. Did your fix resolve the issue?",
                        context=f"Error window: {err['window']} -> Fixed in: {title}",
                        recovery_candidate={
                            "situation": f"Encountered error in {err['window']}",
                            "action_taken": f"Switched to {title} to apply corrective action",
                            "better_action": f"Apply fix in {title}",
                        },
                    )

    def trigger_inquiry(
        self, question: str, context: str = "", recovery_candidate: dict | None = None
    ) -> ProactiveInquiry:
        inquiry_id = f"inq_{uuid.uuid4().hex[:8]}"
        inq = ProactiveInquiry(
            id=inquiry_id,
            question=question,
            context=context,
            recovery_candidate=recovery_candidate or {},
            created_at=dt.datetime.now().isoformat(timespec="seconds"),
        )
        with self._lock:
            self._pending_inquiries[inquiry_id] = inq

        if self.event_bus:
            self.event_bus.publish(
                "inquiry.created",
                id=inquiry_id,
                question=question,
                context=context,
            )
        return inq

    def get_pending_inquiries(self) -> list[dict[str, Any]]:
        with self._lock:
            return [inq.to_dict() for inq in self._pending_inquiries.values() if inq.status == "pending"]

    def resolve_inquiry(self, inquiry_id: str, fixed: bool, feedback: str = "") -> dict[str, Any]:
        with self._lock:
            inq = self._pending_inquiries.get(inquiry_id)
            if not inq:
                return {"ok": False, "error": "Unknown inquiry id"}
            inq.status = "confirmed" if fixed else "rejected"

        learned_lesson = None
        if fixed and self.experiences:
            # Commit verified recovery procedure to Experience Engine
            cand = inq.recovery_candidate or {}
            situation = cand.get("situation") or inq.context or "User reported problem"
            action = cand.get("action_taken") or feedback or "Applied user fix"
            lesson_text = f"When {situation}, user verified that '{action}' successfully resolved the issue."

            try:
                # Add lesson directly to Experience Engine with high confidence
                lesson_id = f"obs_{uuid.uuid4().hex[:8]}"
                now_str = dt.datetime.now().astimezone().isoformat(timespec="seconds")
                fingerprint = f"obs:{inquiry_id}:{hash(situation + action)}"
                
                query = """
                INSERT OR REPLACE INTO experience_lessons (
                    id, kind, project, situation, action_taken, outcome,
                    root_cause, better_action, lesson, source, status,
                    confidence, evidence_successes, evidence_failures,
                    observation_count, user_confirmed, verified,
                    conflict_count, fingerprint, metadata, created_at,
                    last_seen_at, last_verified_at
                ) VALUES (
                    ?, 'procedure', 'desktop', ?, ?, 'success',
                    ?, ?, ?, 'screen_observer', 'active',
                    0.95, 1, 0, 1, 1, 1, 0, ?, '{}', ?, ?, ?
                )
                """
                self.experiences.conn.execute(
                    query,
                    (
                        lesson_id,
                        situation,
                        action,
                        "Encountered error/issue",
                        action,
                        lesson_text,
                        fingerprint,
                        now_str,
                        now_str,
                        now_str,
                    ),
                )
                self.experiences.conn.commit()
                learned_lesson = {"id": lesson_id, "lesson": lesson_text, "confidence": 0.95}
            except Exception as _:
                pass

        if self.event_bus:
            self.event_bus.publish(
                "inquiry.resolved",
                id=inquiry_id,
                fixed=fixed,
                feedback=feedback,
                learned_lesson=learned_lesson,
            )

        with self._lock:
            self._pending_inquiries.pop(inquiry_id, None)

        return {
            "ok": True,
            "inquiry_id": inquiry_id,
            "fixed": fixed,
            "learned_lesson": learned_lesson,
        }
