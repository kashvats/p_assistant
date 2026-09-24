from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import threading
import time
from typing import Any

from living_assistant.security.security_utils import redact_secrets

logger = logging.getLogger(__name__)

STOPWORDS = {
    "a", "about", "above", "after", "again", "all", "am", "an", "and", "any", "are",
    "as", "at", "be", "because", "been", "before", "being", "below", "between",
    "both", "but", "by", "can", "did", "do", "does", "doing", "down", "during",
    "each", "few", "for", "from", "further", "had", "has", "have", "having", "he",
    "her", "here", "hers", "herself", "him", "himself", "his", "how", "i", "if",
    "in", "into", "is", "it", "its", "itself", "just", "me", "more", "most", "my",
    "myself", "no", "nor", "not", "now", "of", "off", "on", "once", "only", "or",
    "other", "our", "ours", "ourselves", "out", "over", "own", "same", "she",
    "should", "so", "some", "such", "than", "that", "the", "their", "theirs", "them",
    "themselves", "then", "there", "these", "they", "this", "those", "through",
    "to", "too", "under", "until", "up", "very", "was", "we", "were", "what",
    "when", "where", "which", "while", "who", "whom", "why", "with", "would", "you",
    "your", "yours", "yourself", "yourselves",
}


class GraftAdapter:
    """Production boundary around Graft persistent AI agent memory.

    Provides verified recall, hybrid retrieval, graph exploration, and knowledge retention
    for coding agents. Supports native Graft CLI binary when present, and seamlessly
    falls back to an embedded SQLite FTS5 storage engine.
    """

    _lock = threading.RLock()

    def __init__(
        self,
        command: str = "graft",
        path: str | Path | None = None,
        db_path: str | Path | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._command = str(command or "graft")
        self._path = Path(path).expanduser().resolve() if path else None
        self._timeout = float(timeout)
        self._binary_path: str | None = None
        self._resolved = False

        if db_path:
            self._db_path = Path(db_path).expanduser().resolve()
        else:
            self._db_path = Path.home() / ".graft" / "graft_embedded.sqlite3"

        self._init_embedded_db()

    # ------------------------------------------------------------------
    # Binary Resolution & Availability
    # ------------------------------------------------------------------

    def _resolve_binary(self) -> str | None:
        if self._resolved:
            return self._binary_path

        self._resolved = True
        if env_bin := os.environ.get("GRAFT_BIN"):
            if Path(env_bin).is_file():
                self._binary_path = env_bin
                return self._binary_path

        if shutil.which(self._command):
            self._binary_path = shutil.which(self._command)
            return self._binary_path

        candidates = [
            Path.home() / ".graft" / "bin" / ("graft.exe" if os.name == "nt" else "graft"),
            Path("external-components/Graft/build") / ("graft.exe" if os.name == "nt" else "graft"),
        ]
        if self._path:
            candidates.insert(0, self._path / "build" / ("graft.exe" if os.name == "nt" else "graft"))
            candidates.insert(0, self._path / "bin" / ("graft.exe" if os.name == "nt" else "graft"))

        for c in candidates:
            if c.is_file():
                self._binary_path = str(c.resolve())
                return self._binary_path

        return None

    def available(self) -> bool:
        """Check if Graft binary, checkout, or embedded engine is available."""
        if self._resolve_binary() is not None:
            return True
        checkout = Path("external-components/Graft/CMakeLists.txt").resolve()
        if checkout.is_file():
            return True
        return self._db_path is not None

    # ------------------------------------------------------------------
    # Embedded SQLite Engine Initialization
    # ------------------------------------------------------------------

    def _init_embedded_db(self) -> None:
        try:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(str(self._db_path)) as conn:
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS graft_memories (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT NOT NULL,
                        body TEXT NOT NULL,
                        keywords TEXT DEFAULT '',
                        profile TEXT DEFAULT 'default',
                        created_at REAL NOT NULL
                    );
                """)
                conn.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS graft_fts USING fts5(
                        title,
                        body,
                        keywords,
                        content='graft_memories',
                        content_rowid='id'
                    );
                """)
                conn.execute("""
                    CREATE TRIGGER IF NOT EXISTS graft_ai AFTER INSERT ON graft_memories BEGIN
                        INSERT INTO graft_fts(rowid, title, body, keywords)
                        VALUES (new.id, new.title, new.body, new.keywords);
                    END;
                """)
                conn.execute("""
                    CREATE TRIGGER IF NOT EXISTS graft_ad AFTER DELETE ON graft_memories BEGIN
                        INSERT INTO graft_fts(graft_fts, rowid, title, body, keywords)
                        VALUES('delete', old.id, old.title, old.body, old.keywords);
                    END;
                """)
                conn.commit()
        except Exception as exc:
            logger.warning("Failed to initialize embedded graft database: %s", exc)

    # ------------------------------------------------------------------
    # Core Operations
    # ------------------------------------------------------------------

    def query(self, prompt: str, profile: str | None = None) -> dict[str, Any]:
        """Verified recall: Fast top-1 lookup with confidence gating (STRONG, WEAK, MISS)."""
        bin_path = self._resolve_binary()
        if bin_path:
            args = ["query", prompt]
            res = self._run_cli(args, profile=profile)
            if res.get("ok"):
                return res

        # Embedded fallback
        return self._embedded_query(prompt, profile=profile)

    def retrieve(self, query: str, limit: int = 5, profile: str | None = None) -> dict[str, Any]:
        """Hybrid retrieval: Rank memories by relevant solutions and gotchas."""
        bin_path = self._resolve_binary()
        if bin_path:
            args = ["retrieve", query, "--limit", str(limit)]
            res = self._run_cli(args, profile=profile)
            if res.get("ok"):
                return res

        # Embedded fallback
        return self._embedded_retrieve(query, limit=limit, profile=profile)

    def insert(
        self,
        title: str,
        body: str,
        keywords: list[str] | None = None,
        profile: str | None = None,
    ) -> dict[str, Any]:
        """Insert a newly learned fix, gotcha, or architectural decision."""
        kws = [k.strip() for k in (keywords or []) if k.strip()]
        bin_path = self._resolve_binary()
        if bin_path:
            args = ["insert", "--title", title, "--body", body]
            for kw in kws:
                args.extend(["--keyword", kw])
            res = self._run_cli(args, profile=profile)
            if res.get("ok"):
                return res

        # Embedded fallback
        return self._embedded_insert(title, body, keywords=kws, profile=profile)

    def explore(self, id_or_query: str, depth: int = 2, profile: str | None = None) -> dict[str, Any]:
        """Graph exploration: Walk semantic and keyword relationships."""
        bin_path = self._resolve_binary()
        if bin_path:
            args = ["explore", str(id_or_query), "--depth", str(depth)]
            res = self._run_cli(args, profile=profile)
            if res.get("ok"):
                return res

        # Embedded fallback
        return self._embedded_explore(str(id_or_query), profile=profile)

    def list_memories(self, limit: int = 50, profile: str | None = None) -> dict[str, Any]:
        """List stored memories."""
        bin_path = self._resolve_binary()
        if bin_path:
            args = ["list", "--limit", str(limit)]
            res = self._run_cli(args, profile=profile)
            if res.get("ok"):
                return res

        return self._embedded_list(limit=limit, profile=profile)

    def delete(self, memory_id: str | int, profile: str | None = None) -> dict[str, Any]:
        """Delete a stored memory by ID."""
        bin_path = self._resolve_binary()
        if bin_path:
            args = ["delete", str(memory_id)]
            res = self._run_cli(args, profile=profile)
            if res.get("ok"):
                return res

        return self._embedded_delete(memory_id, profile=profile)

    def stats(self, profile: str | None = None) -> dict[str, Any]:
        """Get memory statistics and database health."""
        bin_path = self._resolve_binary()
        if bin_path:
            args = ["stats"]
            res = self._run_cli(args, profile=profile)
            if res.get("ok"):
                return res

        return self._embedded_stats(profile=profile)

    # ------------------------------------------------------------------
    # Subprocess CLI Execution
    # ------------------------------------------------------------------

    def _run_cli(self, sub_args: list[str], profile: str | None = None) -> dict[str, Any]:
        with self._lock:
            bin_path = self._resolve_binary()
            if not bin_path:
                return {"ok": False, "error": "Graft binary not found"}

            cmd = [bin_path, *sub_args]
            env = os.environ.copy()
            if profile:
                env["GRAFT_PROFILE"] = str(profile)

            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=self._timeout,
                    env=env,
                    check=False,
                )
                stdout = proc.stdout.strip()
                if proc.returncode in (0, 3):
                    try:
                        data = json.loads(stdout)
                        return {"ok": True, **(data if isinstance(data, dict) else {"result": data})}
                    except Exception:
                        return {"ok": True, "output": stdout}
                return {
                    "ok": False,
                    "error": redact_secrets(proc.stderr.strip() or stdout),
                    "exit_code": proc.returncode,
                }
            except subprocess.TimeoutExpired:
                return {"ok": False, "error": f"Graft command timed out after {self._timeout}s"}
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

    # ------------------------------------------------------------------
    # Embedded SQLite Implementations
    # ------------------------------------------------------------------

    def _embedded_insert(
        self,
        title: str,
        body: str,
        keywords: list[str],
        profile: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            prof = str(profile or "default")
            kw_str = " ".join(keywords) if keywords else ""
            now = time.time()
            with sqlite3.connect(str(self._db_path)) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO graft_memories(title, body, keywords, profile, created_at) VALUES (?, ?, ?, ?, ?)",
                    (title.strip(), body.strip(), kw_str, prof, now),
                )
                mem_id = cursor.lastrowid
                conn.commit()
            return {
                "ok": True,
                "id": mem_id,
                "title": title.strip(),
                "keywords": keywords,
                "engine": "embedded-sqlite-fts5",
            }

    def _embedded_query(self, prompt: str, profile: str | None = None) -> dict[str, Any]:
        with self._lock:
            prof = str(profile or "default")
            results = self._embedded_search(prompt, limit=1, profile=prof)
            if not results:
                return {
                    "ok": True,
                    "hit": "MISS",
                    "status": 0,
                    "result": {"hit": "MISS"},
                }

            top = results[0]
            score = top.get("score", 0.0)
            hit = "STRONG" if score >= 0.7 else "WEAK"
            return {
                "ok": True,
                "hit": hit,
                "result": {
                    "hit": hit,
                    "id": top["id"],
                    "title": top["title"],
                    "body": top["body"],
                    "keywords": top["keywords"],
                    "score": round(score, 3),
                },
            }

    def _embedded_retrieve(self, query: str, limit: int = 5, profile: str | None = None) -> dict[str, Any]:
        with self._lock:
            prof = str(profile or "default")
            results = self._embedded_search(query, limit=limit, profile=prof)
            return {
                "ok": True,
                "count": len(results),
                "results": results,
                "engine": "embedded-sqlite-fts5",
            }

    def _embedded_explore(self, id_or_query: str, profile: str | None = None) -> dict[str, Any]:
        with self._lock:
            prof = str(profile or "default")
            root: dict[str, Any] | None = None
            if id_or_query.isdigit():
                with sqlite3.connect(str(self._db_path)) as conn:
                    conn.row_factory = sqlite3.Row
                    cur = conn.execute(
                        "SELECT id, title, body, keywords, created_at FROM graft_memories WHERE id = ? AND profile = ?",
                        (int(id_or_query), prof),
                    )
                    row = cur.fetchone()
                    if row:
                        root = dict(row)

            if not root:
                top = self._embedded_search(id_or_query, limit=1, profile=prof)
                if top:
                    root = top[0]

            if not root:
                return {"ok": True, "nodes": [], "edges": []}

            # Find related memories via keywords or tokens
            kws = root.get("keywords", "").split() if isinstance(root.get("keywords"), str) else []
            related: list[dict[str, Any]] = []
            if kws:
                for kw in kws[:4]:
                    matches = self._embedded_search(kw, limit=3, profile=prof)
                    for m in matches:
                        if m["id"] != root["id"] and m not in related:
                            related.append(m)

            nodes = [
                {"id": root["id"], "title": root["title"], "type": "root"},
                *[{"id": r["id"], "title": r["title"], "type": "related"} for r in related],
            ]
            edges = [
                {"source": root["id"], "target": r["id"], "relationship": "related_concept"}
                for r in related
            ]
            return {"ok": True, "root": root, "nodes": nodes, "edges": edges}

    def _embedded_list(self, limit: int = 50, profile: str | None = None) -> dict[str, Any]:
        with self._lock:
            prof = str(profile or "default")
            with sqlite3.connect(str(self._db_path)) as conn:
                conn.row_factory = sqlite3.Row
                cur = conn.execute(
                    "SELECT id, title, body, keywords, created_at FROM graft_memories WHERE profile = ? ORDER BY id DESC LIMIT ?",
                    (prof, limit),
                )
                rows = [dict(r) for r in cur.fetchall()]
            return {"ok": True, "count": len(rows), "memories": rows}

    def _embedded_delete(self, memory_id: str | int, profile: str | None = None) -> dict[str, Any]:
        with self._lock:
            prof = str(profile or "default")
            with sqlite3.connect(str(self._db_path)) as conn:
                cur = conn.execute(
                    "DELETE FROM graft_memories WHERE id = ? AND profile = ?",
                    (int(memory_id), prof),
                )
                deleted = cur.rowcount
                conn.commit()
            return {"ok": True, "deleted": deleted > 0, "id": memory_id}

    def _embedded_stats(self, profile: str | None = None) -> dict[str, Any]:
        with self._lock:
            prof = str(profile or "default")
            with sqlite3.connect(str(self._db_path)) as conn:
                cur = conn.execute("SELECT COUNT(*) FROM graft_memories WHERE profile = ?", (prof,))
                count = cur.fetchone()[0]
            size = self._db_path.stat().st_size if self._db_path.is_file() else 0
            return {
                "ok": True,
                "memory_count": count,
                "engine": "embedded-sqlite-fts5",
                "db_path": str(self._db_path),
                "db_bytes": size,
            }

    def _embedded_search(self, query_text: str, limit: int = 5, profile: str = "default") -> list[dict[str, Any]]:
        raw_tokens = [t.strip().lower() for t in re.split(r"\W+", query_text) if len(t.strip()) >= 2]
        meaningful = [t for t in raw_tokens if t not in STOPWORDS]
        tokens = meaningful if meaningful else raw_tokens
        if not tokens:
            return []

        fts_query = " OR ".join(tokens)
        scored_candidates: list[dict[str, Any]] = []

        try:
            with sqlite3.connect(str(self._db_path)) as conn:
                conn.row_factory = sqlite3.Row
                cur = conn.execute(
                    """
                    SELECT m.id, m.title, m.body, m.keywords, m.created_at, fts.rank
                    FROM graft_fts fts
                    JOIN graft_memories m ON fts.rowid = m.id
                    WHERE graft_fts MATCH ? AND m.profile = ?
                    ORDER BY fts.rank ASC
                    LIMIT ?
                    """,
                    (fts_query, profile, limit * 2),
                )
                for row in cur.fetchall():
                    title_lower = row["title"].lower()
                    body_lower = row["body"].lower()
                    kw_lower = row["keywords"].lower() if row["keywords"] else ""
                    combined = f"{title_lower} {body_lower} {kw_lower}"

                    matched_terms = [t for t in tokens if t in combined]
                    if not matched_terms:
                        continue

                    overlap = len(matched_terms) / len(tokens)
                    title_matches = sum(1 for t in matched_terms if t in title_lower)
                    # Score combines lexical coverage and title focus
                    score = min(1.0, (overlap * 0.6) + (min(title_matches, 2) * 0.2) + 0.1)

                    scored_candidates.append({
                        "id": row["id"],
                        "title": row["title"],
                        "body": row["body"],
                        "keywords": row["keywords"].split() if row["keywords"] else [],
                        "score": round(score, 3),
                        "created_at": row["created_at"],
                    })
        except Exception:
            with sqlite3.connect(str(self._db_path)) as conn:
                conn.row_factory = sqlite3.Row
                cur = conn.execute(
                    """
                    SELECT id, title, body, keywords, created_at
                    FROM graft_memories
                    WHERE profile = ? AND (title LIKE ? OR body LIKE ?)
                    ORDER BY id DESC LIMIT ?
                    """,
                    (profile, f"%{tokens[0]}%", f"%{tokens[0]}%", limit),
                )
                for row in cur.fetchall():
                    title_lower = row["title"].lower()
                    body_lower = row["body"].lower()
                    combined = f"{title_lower} {body_lower}"
                    matched = [t for t in tokens if t in combined]
                    if matched:
                        score = min(1.0, len(matched) / len(tokens))
                        scored_candidates.append({
                            "id": row["id"],
                            "title": row["title"],
                            "body": row["body"],
                            "keywords": row["keywords"].split() if row["keywords"] else [],
                            "score": round(score, 3),
                            "created_at": row["created_at"],
                        })

        scored_candidates.sort(key=lambda x: x["score"], reverse=True)
        return scored_candidates[:limit]
