from __future__ import annotations

import collections
import datetime as dt
import re
from typing import Any

from living_assistant.learning.experience import ExperienceEngine
from living_assistant.security.security_utils import redact_secrets

_WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_.-]{2,}")
_STOP = {
    "the", "and", "for", "with", "from", "this", "that", "into", "your", "you", "use", "using",
    "please", "make", "work", "fix", "run", "get", "set", "how", "what", "why", "can", "could",
    "should", "would", "about", "when", "where", "then", "than", "are", "was", "were", "have", "has",
}


def _task_tokens(task: str) -> set[str]:
    return {
        token.lower()
        for token in _WORD_RE.findall(task or "")
        if token.lower() not in _STOP and len(token) >= 3
    }


class KnowledgeGapDetector:
    """Find recurring high-failure task topics from existing experience episodes."""

    def __init__(self, experience: ExperienceEngine, config: dict | None = None):
        self.experience = experience
        cfg = ((config or {}).get("knowledge_gaps", {}) or {})
        self.lookback_days = max(7, min(int(cfg.get("lookback_days", 90)), 3650))
        self.max_episodes = max(100, min(int(cfg.get("max_episodes", 2000)), 10000))
        self.similarity_threshold = max(0.2, min(float(cfg.get("similarity_threshold", 0.5)), 0.95))

    @staticmethod
    def _similarity(left: set[str], right: set[str]) -> float:
        if not left or not right:
            return 0.0
        return len(left & right) / len(left | right)

    def detect(
        self,
        project: str | None = None,
        min_failures: int = 2,
        min_failure_rate: float = 0.6,
        limit: int = 10,
    ) -> dict:
        min_failures = max(2, min(int(min_failures), 100))
        min_failure_rate = max(0.0, min(float(min_failure_rate), 1.0))
        limit = max(1, min(int(limit), 100))
        cutoff = (dt.datetime.now().astimezone() - dt.timedelta(days=self.lookback_days)).isoformat(timespec="seconds")
        if project:
            rows = self.experience.conn.execute(
                """SELECT task,project,tool_name,success,created_at FROM experience_episodes
                   WHERE created_at>=? AND COALESCE(project,'')=? ORDER BY id DESC LIMIT ?""",
                (cutoff, str(project), self.max_episodes),
            ).fetchall()
        else:
            rows = self.experience.conn.execute(
                """SELECT task,project,tool_name,success,created_at FROM experience_episodes
                   WHERE created_at>=? ORDER BY id DESC LIMIT ?""",
                (cutoff, self.max_episodes),
            ).fetchall()

        episodes: list[dict[str, Any]] = []
        for row in rows:
            task = redact_secrets(row["task"], 1200)
            tokens = _task_tokens(task)
            if not tokens:
                continue
            episodes.append({
                "task": task,
                "tokens": tokens,
                "project": row["project"],
                "tool_name": row["tool_name"],
                "success": None if row["success"] is None else bool(row["success"]),
                "created_at": row["created_at"],
            })

        clusters: list[dict[str, Any]] = []
        # Seed clusters from failures only: a knowledge gap must have observed failure.
        for episode in [item for item in episodes if item["success"] is False]:
            best = None
            best_score = 0.0
            for cluster in clusters:
                score = self._similarity(episode["tokens"], cluster["tokens"])
                if score > best_score:
                    best, best_score = cluster, score
            if best is not None and best_score >= self.similarity_threshold:
                best["failures"].append(episode)
                best["tokens"] |= episode["tokens"]
            else:
                clusters.append({"tokens": set(episode["tokens"]), "failures": [episode]})

        gaps = []
        for cluster in clusters:
            failures = cluster["failures"]
            if len(failures) < min_failures:
                continue
            cluster_tokens = set(cluster["tokens"])
            related = [
                episode for episode in episodes
                if self._similarity(episode["tokens"], cluster_tokens) >= self.similarity_threshold
            ]
            successes = sum(1 for episode in related if episode["success"] is True)
            failures_count = sum(1 for episode in related if episode["success"] is False)
            attempts = successes + failures_count
            if attempts <= 0:
                continue
            failure_rate = failures_count / attempts
            if failures_count < min_failures or failure_rate < min_failure_rate:
                continue
            counts = collections.Counter(
                token for episode in failures for token in episode["tokens"]
            )
            topic_tokens = [token for token, _ in counts.most_common(5)]
            topic = " ".join(topic_tokens) or "repeated task failure"
            tools = sorted({str(episode["tool_name"]) for episode in related if episode.get("tool_name")})[:10]
            sample_tasks = list(dict.fromkeys(episode["task"] for episode in failures))[:3]
            last_seen = max(episode["created_at"] for episode in failures)
            gaps.append({
                "topic": topic,
                "keywords": topic_tokens,
                "project": project or (failures[0].get("project") if all(x.get("project") == failures[0].get("project") for x in failures) else None),
                "failures": failures_count,
                "successes": successes,
                "attempts": attempts,
                "failure_rate": round(failure_rate, 3),
                "tools": tools,
                "last_seen": last_seen,
                "sample_tasks": sample_tasks,
                "learning_opportunity": f"Review repeated failures around '{topic}' and capture a verified procedure or skill after a successful resolution.",
                "score": round(failures_count * failure_rate, 3),
            })
        gaps.sort(key=lambda item: (item["score"], item["last_seen"]), reverse=True)
        return {
            "ok": True,
            "project": project,
            "lookback_days": self.lookback_days,
            "episode_count": len(episodes),
            "gap_count": len(gaps[:limit]),
            "learning_opportunities": gaps[:limit],
        }
