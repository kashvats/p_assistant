from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
import sqlite3
from typing import Callable, Any


@dataclass
class MigrationStep:
    version: int
    name: str
    up: Callable[[sqlite3.Connection], None]
    down: Callable[[sqlite3.Connection], None] | None = None


class MigrationManager:
    """Deterministic, transactional schema migration runner (Section 95).

    Guarantees user data integrity across fresh installs, single/multi-version upgrades,
    rollbacks, and transaction aborts on halfway failures.
    """

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._migrations: dict[int, MigrationStep] = {}
        self._init_migrations_table()

    def _init_migrations_table(self):
        with self.conn:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS _schema_migrations (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    applied_at TEXT NOT NULL
                )
                """
            )

    def register(self, step: MigrationStep) -> None:
        self._migrations[step.version] = step

    def current_version(self) -> int:
        cursor = self.conn.cursor()
        cursor.execute("SELECT MAX(version) FROM _schema_migrations")
        row = cursor.fetchone()
        return row[0] if (row and row[0] is not None) else 0

    def applied_versions(self) -> list[int]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT version FROM _schema_migrations ORDER BY version ASC")
        return [row[0] for row in cursor.fetchall()]

    def upgrade(self, target_version: int | None = None) -> list[int]:
        """Apply all pending migrations up to target_version transactionally."""
        current = self.current_version()
        available = sorted([v for v in self._migrations.keys() if v > current])
        if target_version is not None:
            available = [v for v in available if v <= target_version]

        applied: list[int] = []
        for v in available:
            step = self._migrations[v]
            # Transactional execution: any failure rolls back the migration step
            try:
                self.conn.execute("BEGIN TRANSACTION")
                step.up(self.conn)
                now = dt.datetime.now().isoformat()
                self.conn.execute(
                    "INSERT INTO _schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
                    (v, step.name, now),
                )
                self.conn.commit()
                applied.append(v)
            except Exception as exc:
                self.conn.rollback()
                raise RuntimeError(
                    f"Migration step {v} ('{step.name}') failed halfway and was safely rolled back: {exc}"
                ) from exc

        return applied

    def rollback(self, target_version: int) -> list[int]:
        """Roll back applied migrations down to target_version."""
        current = self.current_version()
        applied = self.applied_versions()
        to_rollback = sorted([v for v in applied if v > target_version], reverse=True)

        rolled_back: list[int] = []
        for v in to_rollback:
            step = self._migrations.get(v)
            if not step or not step.down:
                raise RuntimeError(f"Cannot rollback migration {v}: no down migration defined.")

            try:
                self.conn.execute("BEGIN TRANSACTION")
                step.down(self.conn)
                self.conn.execute("DELETE FROM _schema_migrations WHERE version = ?", (v,))
                self.conn.commit()
                rolled_back.append(v)
            except Exception as exc:
                self.conn.rollback()
                raise RuntimeError(
                    f"Rollback of migration {v} failed halfway and was safely aborted: {exc}"
                ) from exc

        return rolled_back
