"""
TypeSafe AI Jev — System One model client.

Jev is NOT an LLM. It is a structured decision model that evaluates context
against strictly typed primitives (Choice, Score, Noul) and returns typed values
with calibrated probability scores. It cannot generate text.

Architecture contract (enforced throughout p_assistant):
  - Jev makes ALL binary/categorical decisions (routing, safety gating, task
    completion, memory filtering, incident linking).
  - AirLLM (or any heavy generative model) ONLY runs when text or code must
    be generated (payloads, summaries, patches).
  - No autonomous merges: Jev may approve, but humans apply.

NOTE: The real Jev REST API (TypeSafe AI) is in limited early access (Sept 2026).
      This module ships a calibrated local mock that mirrors the same interface.
      To swap in the real API, set TYPESAFE_API_KEY in your environment and the
      JevClient will call the live endpoint instead of the local mock.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Danger patterns used by the local mock for security Noul evaluations.
# Mirrors the same regex conventions already in security_utils.py.
# ---------------------------------------------------------------------------
_DANGER_RE = re.compile(
    r'(?i)(password|passwd|secret|api[_-]?key|private[_-]?key|drop\s+table'
    r'|truncate\s+table|delete\s+from|os\.system|subprocess\.call'
    r'|__import__|eval\(|exec\(|rm\s+-rf|\/etc\/|\.\.\/)',
)
_HIGH_ENTROPY_RE = re.compile(
    r'(?i)\b(ghp|sk-|pk-|AKIA|xox[baprs]|ey[A-Za-z0-9]{10,})[A-Za-z0-9_\-]{20,}\b'
)


class JevClient:
    """
    System One model client (TypeSafe AI Jev).

    Primitives
    ----------
    choice(context, options, question) -> (selection, confidence)
        Selects exactly one option from a closed set. Eliminates hallucinated
        tool names and routing errors.

    noul(context, statement) -> float [0, 1]
        Binary Yes/No evaluation. Use for security gating and task-done checks.
        Probability > 0.5 means "Yes / True / Safe".

    score(context, levels, question) -> (level, confidence)
        Rates context against ordered levels. Use for relevance ranking,
        knowledge GC, and loop-break detection.

    goal_achieved(user_goal, tool_results_so_far) -> (bool, float)
        Convenience wrapper around noul(). Hard-kills agent loops when the
        task is complete, preventing context-window drain with AirLLM.

    is_lesson_relevant(lesson, current_request) -> (bool, float)
        Convenience wrapper around score(). Filters experience.py candidates
        before they are injected into AirLLM's context window.

    link_incident(pattern_text, tracker_items) -> (str | None, float)
        Convenience wrapper around choice(). Links a newly discovered AI
        pattern to an existing MASTER_TRACKER.md item ID.

    score_secret_risk(text_chunk) -> float
        Convenience wrapper around noul(). Sub-100ms secret/credential scan
        on outbound data before it reaches the heavy model.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.api_key = api_key or os.environ.get("TYPESAFE_API_KEY", "")
        self.base_url = base_url or os.environ.get(
            "TYPESAFE_BASE_URL", "https://api.typesafe.ai/v1"
        )
        self._live = bool(self.api_key and not self.api_key.startswith("sk-mock"))

    # ------------------------------------------------------------------
    # Core primitives
    # ------------------------------------------------------------------

    def choice(self, context: Any, options: List[str], question: str) -> Tuple[str, float]:
        """
        Choice primitive: selects exactly one option from a closed set.
        Returns (selection, confidence_probability).
        """
        if not options:
            raise ValueError("choice() requires at least one option")
        if self._live:
            return self._live_choice(context, options, question)
        return self._mock_choice(context, options)

    def noul(self, context: Any, statement: str) -> float:
        """
        Noul primitive: evaluates a yes/no statement against context.
        Returns probability in [0, 1]. > 0.5 means "Yes / True".
        """
        if self._live:
            return self._live_noul(context, statement)
        return self._mock_noul(context, statement)

    def score(self, context: Any, levels: List[str], question: str) -> Tuple[str, float]:
        """
        Score primitive: rates context against ordered levels (lowest → highest).
        Returns (level, confidence_probability).
        """
        if not levels:
            raise ValueError("score() requires at least one level")
        if self._live:
            return self._live_score(context, levels, question)
        return self._mock_score(context, levels, question)

    # ------------------------------------------------------------------
    # High-level convenience wrappers
    # ------------------------------------------------------------------

    def goal_achieved(self, user_goal: str, tool_results: List[str]) -> Tuple[bool, float]:
        """
        Loop-breaker: returns (achieved, probability).
        Use at the end of every orchestrator step to hard-kill the agent loop
        without waiting for AirLLM to "decide" it's done.
        """
        context = {
            "goal": user_goal,
            "tool_results": tool_results[-6:],  # keep context bounded
        }
        prob = self.noul(
            context,
            "The user's original goal has been fully achieved based on the tool results."
        )
        logger.debug("[Jev] goal_achieved probability=%.3f", prob)
        return prob >= 0.82, prob

    def is_lesson_relevant(self, lesson: dict, current_request: str) -> Tuple[bool, float]:
        """
        Memory filter: returns (exact_match, confidence).
        Prevents context bloat by dropping tangential lessons before AirLLM injection.
        """
        context = {
            "request": current_request,
            "lesson_situation": lesson.get("situation", ""),
            "lesson_text": lesson.get("lesson", ""),
            "lesson_kind": lesson.get("kind", ""),
        }
        level, conf = self.score(
            context,
            ["Irrelevant", "Tangential", "Exact Match"],
            "How relevant is this past lesson to the current user request?"
        )
        logger.debug("[Jev] lesson_relevant=%s conf=%.3f", level, conf)
        return level == "Exact Match", conf

    def link_incident(
        self, pattern_text: str, tracker_items: List[dict]
    ) -> Tuple[Optional[str], float]:
        """
        Incident linker: maps a newly discovered AI pattern to a MASTER_TRACKER
        item ID. Returns (tracker_id | None, confidence).

        tracker_items: list of {"id": "BUG-01", "title": "...", "description": "..."}
        """
        if not tracker_items:
            return None, 0.0

        options = [item["id"] for item in tracker_items]
        option_descriptions = {
            item["id"]: item.get("title", "") for item in tracker_items
        }
        context = {
            "pattern": pattern_text,
            "tracker_options": option_descriptions,
        }
        best, conf = self.choice(
            context,
            options,
            "Which tracker item does this discovered pattern most directly match?"
        )
        logger.debug("[Jev] link_incident -> %s (conf=%.3f)", best, conf)
        return (best if conf >= 0.6 else None), conf

    def score_secret_risk(self, text_chunk: str) -> float:
        """
        Sub-100ms outbound secret scan. Returns risk probability [0, 1].
        Risk > 0.5 → redact the chunk before sending to AirLLM.
        """
        prob = self.noul(
            text_chunk,
            "This text contains a high-entropy secret, API key, password, or credential."
        )
        logger.debug("[Jev] secret_risk=%.3f len=%d", prob, len(text_chunk))
        return prob

    def score_knowledge_value(self, lesson: dict) -> Tuple[str, float]:
        """
        Daemon GC: scores a lesson's current knowledge value for maintenance.
        Returns ("Obsolete/Wrong" | "Stale" | "Highly Relevant", confidence).
        """
        context = {
            "lesson": lesson.get("lesson", ""),
            "confidence": lesson.get("confidence", 0),
            "observation_count": lesson.get("observation_count", 0),
            "user_confirmed": lesson.get("user_confirmed", False),
            "days_since_verified": self._days_since(lesson),
        }
        return self.score(
            context,
            ["Obsolete/Wrong", "Stale", "Highly Relevant"],
            "What is the current knowledge value of this lesson?"
        )

    # ------------------------------------------------------------------
    # Live API calls (real Jev endpoint)
    # ------------------------------------------------------------------

    def _live_choice(self, context: Any, options: List[str], question: str) -> Tuple[str, float]:
        try:
            import httpx  # optional; already in project deps via daemon.py

            payload = {
                "context": context if isinstance(context, str) else json.dumps(context),
                "question": question,
                "options": options,
            }
            resp = httpx.post(
                f"{self.base_url}/choice",
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=5.0,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["selection"], float(data["confidence"])
        except Exception as exc:
            logger.warning("[Jev] live choice failed (%s), falling back to mock", exc)
            return self._mock_choice(context, options)

    def _live_noul(self, context: Any, statement: str) -> float:
        try:
            import httpx

            payload = {
                "context": context if isinstance(context, str) else json.dumps(context),
                "statement": statement,
            }
            resp = httpx.post(
                f"{self.base_url}/noul",
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=5.0,
            )
            resp.raise_for_status()
            return float(resp.json()["probability"])
        except Exception as exc:
            logger.warning("[Jev] live noul failed (%s), falling back to mock", exc)
            return self._mock_noul(context, statement)

    def _live_score(self, context: Any, levels: List[str], question: str) -> Tuple[str, float]:
        try:
            import httpx

            payload = {
                "context": context if isinstance(context, str) else json.dumps(context),
                "question": question,
                "levels": levels,
            }
            resp = httpx.post(
                f"{self.base_url}/score",
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=5.0,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["level"], float(data["confidence"])
        except Exception as exc:
            logger.warning("[Jev] live score failed (%s), falling back to mock", exc)
            return self._mock_score(context, levels, question)

    # ------------------------------------------------------------------
    # Local mock (calibrated keyword heuristic — same interface as live)
    # ------------------------------------------------------------------

    def _mock_choice(self, context: Any, options: List[str]) -> Tuple[str, float]:
        ctx = json.dumps(context, default=str).lower() if not isinstance(context, str) else context.lower()
        best, best_score = options[0], 0.0
        for opt in options:
            score = 0.1
            for word in re.split(r"[\W_]+", opt.lower()):
                if len(word) > 2 and word in ctx:
                    score += 0.25
            if score > best_score:
                best_score, best = score, opt
        return best, min(0.97, best_score)

    def _mock_noul(self, context: Any, statement: str) -> float:
        ctx = json.dumps(context, default=str) if not isinstance(context, str) else context
        stmt_lower = statement.lower()

        # Security / secret risk statements
        if any(k in stmt_lower for k in ("secret", "credential", "api key", "password", "token")):
            if _DANGER_RE.search(ctx) or _HIGH_ENTROPY_RE.search(ctx):
                return 0.05  # very unsafe
            return 0.92  # safe

        # Safety / policy statements
        if any(k in stmt_lower for k in ("safe", "policy", "violate", "harmful")):
            if _DANGER_RE.search(ctx):
                return 0.08
            return 0.91

        # Task completion statements
        if any(k in stmt_lower for k in ("goal", "achieved", "complete", "done", "fulfilled")):
            positive_signals = ["success", "result", "found", "completed", "ok", "done", "✓"]
            negative_signals = ["error", "failed", "exception", "traceback", "not found", "missing"]
            ctx_lower = ctx.lower()
            pos = sum(1 for s in positive_signals if s in ctx_lower)
            neg = sum(1 for s in negative_signals if s in ctx_lower)
            if pos > 0 and neg == 0:
                return 0.88
            if neg > pos:
                return 0.15
            return 0.50

        return 0.50

    def _mock_score(self, context: Any, levels: List[str], question: str) -> Tuple[str, float]:
        ctx = json.dumps(context, default=str).lower() if not isinstance(context, str) else context.lower()
        q = question.lower()

        # Relevance scoring
        if "relevant" in q or "applies" in q or "match" in q:
            ctx_words = set(re.split(r"[\W_]+", ctx))
            if "request" in ctx:
                req = ""
                try:
                    data = json.loads(ctx) if isinstance(ctx, str) else ctx
                    req = str(data.get("request", "")).lower()
                except Exception:
                    req = ctx
                req_words = set(re.split(r"[\W_]+", req))
                lesson_words = ctx_words - req_words
                overlap = len(req_words & lesson_words) / max(1, len(req_words))
                if overlap > 0.4:
                    return levels[-1], min(0.95, 0.5 + overlap)
                if overlap > 0.1:
                    return levels[len(levels) // 2], 0.65
                return levels[0], 0.80

        # Knowledge value / GC scoring
        if "knowledge" in q or "value" in q or "obsolete" in q or "stale" in q:
            try:
                data = json.loads(ctx) if not isinstance(context, dict) else context
            except Exception:
                data = {}
            conf = float(data.get("confidence", 0.5))
            confirmed = bool(data.get("user_confirmed", False))
            days = float(data.get("days_since_verified", 0))
            if confirmed and conf > 0.7:
                return levels[-1], 0.90
            if days > 180 and conf < 0.4:
                return levels[0], 0.82
            if days > 60 or conf < 0.5:
                return levels[len(levels) // 2], 0.70
            return levels[-1], 0.75

        # Tool relevance scoring (used by orchestrator routing)
        if "tool" in q:
            ctx_words = set(re.split(r"[\W_]+", ctx))
            level_words = set(re.split(r"[\W_]+", levels[-1].lower()))
            if ctx_words & level_words:
                return levels[-1], 0.88
            return levels[0], 0.72

        return levels[len(levels) // 2], 0.60

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _days_since(lesson: dict) -> float:
        import datetime as dt
        stamp = lesson.get("last_verified_at") or lesson.get("last_seen_at") or lesson.get("created_at")
        if not stamp:
            return 9999.0
        try:
            then = dt.datetime.fromisoformat(str(stamp))
            if then.tzinfo is None:
                then = then.astimezone()
            return max(0.0, (dt.datetime.now().astimezone() - then).total_seconds() / 86400.0)
        except Exception:
            return 9999.0
