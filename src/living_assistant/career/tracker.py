from __future__ import annotations

from contextlib import contextmanager
import json
import sqlite3
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterator

from living_assistant.career.parser import ParsedJob
from living_assistant.career.tailor import OutreachEmailDraft
from living_assistant.core.config import data_dir


class ApplicationStatus(str, Enum):
    SAVED = "saved"
    ANALYZED = "analyzed"
    READY_FOR_REVIEW = "ready_for_review"
    APPLIED = "applied"
    INTERVIEWING = "interviewing"
    REJECTED = "rejected"
    OFFER = "offer"


@dataclass
class JobApplicationRecord:
    id: str
    company: str
    title: str
    url: str
    platform: str
    status: ApplicationStatus
    description: str = ""
    requirements: list[str] = field(default_factory=list)
    recruiter_emails: list[str] = field(default_factory=list)
    cover_letter: str = ""
    outreach_email_draft: dict[str, Any] = field(default_factory=dict)
    submitted_fields: dict[str, Any] = field(default_factory=dict)
    screenshot_path: str = ""
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value if isinstance(self.status, ApplicationStatus) else str(self.status)
        return data


class ApplicationTracker:
    """SQLite-backed tracker for job opportunities, statuses, contacts, and outreach materials."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path else data_dir() / "career" / "career_applications.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS career_applications (
                    id TEXT PRIMARY KEY,
                    company TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    status TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    requirements TEXT NOT NULL DEFAULT '[]',
                    recruiter_emails TEXT NOT NULL,
                    cover_letter TEXT NOT NULL,
                    outreach_email_draft TEXT NOT NULL,
                    submitted_fields TEXT NOT NULL,
                    screenshot_path TEXT NOT NULL,
                    notes TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            cur = conn.execute("PRAGMA table_info(career_applications)")
            columns = {row["name"] for row in cur.fetchall()}
            if "description" not in columns:
                conn.execute("ALTER TABLE career_applications ADD COLUMN description TEXT NOT NULL DEFAULT ''")
            if "requirements" not in columns:
                conn.execute("ALTER TABLE career_applications ADD COLUMN requirements TEXT NOT NULL DEFAULT '[]'")
            conn.commit()

    def _row_to_record(self, row: sqlite3.Row) -> JobApplicationRecord:
        emails = json.loads(row["recruiter_emails"]) if row["recruiter_emails"] else []
        draft = json.loads(row["outreach_email_draft"]) if row["outreach_email_draft"] else {}
        fields = json.loads(row["submitted_fields"]) if row["submitted_fields"] else {}
        reqs = json.loads(row["requirements"]) if "requirements" in row.keys() and row["requirements"] else []
        desc = row["description"] if "description" in row.keys() else ""
        return JobApplicationRecord(
            id=row["id"],
            company=row["company"],
            title=row["title"],
            url=row["url"],
            platform=row["platform"],
            status=ApplicationStatus(row["status"]),
            description=desc,
            requirements=reqs,
            recruiter_emails=emails,
            cover_letter=row["cover_letter"],
            outreach_email_draft=draft,
            submitted_fields=fields,
            screenshot_path=row["screenshot_path"],
            notes=row["notes"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def create_application(
        self,
        job: ParsedJob,
        recruiter_emails: list[str] | None = None,
        notes: str = "",
    ) -> JobApplicationRecord:
        now = datetime.now(timezone.utc).isoformat()
        app_id = str(uuid.uuid4())
        emails = recruiter_emails if recruiter_emails is not None else [c.email for c in job.contacts]
        platform_str = job.platform.value if hasattr(job.platform, "value") else str(job.platform)

        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO career_applications (
                    id, company, title, url, platform, status,
                    description, requirements, recruiter_emails, cover_letter,
                    outreach_email_draft, submitted_fields, screenshot_path,
                    notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    app_id,
                    job.company,
                    job.title,
                    job.url,
                    platform_str,
                    ApplicationStatus.ANALYZED.value,
                    job.description or "",
                    json.dumps(job.requirements or []),
                    json.dumps(emails),
                    "",
                    json.dumps({}),
                    json.dumps({}),
                    "",
                    notes,
                    now,
                    now,
                ),
            )
            conn.commit()

        rec = self.get_application(app_id)
        if not rec:
            raise RuntimeError("Failed to create application record")
        return rec

    def get_application(self, app_id: str) -> JobApplicationRecord | None:
        with self._connection() as conn:
            cur = conn.execute("SELECT * FROM career_applications WHERE id = ?", (app_id,))
            row = cur.fetchone()
            if not row:
                return None
            return self._row_to_record(row)

    def list_applications(
        self, status: ApplicationStatus | None = None
    ) -> list[JobApplicationRecord]:
        with self._connection() as conn:
            if status is not None:
                cur = conn.execute(
                    "SELECT * FROM career_applications WHERE status = ? ORDER BY created_at DESC",
                    (status.value,),
                )
            else:
                cur = conn.execute("SELECT * FROM career_applications ORDER BY created_at DESC")
            return [self._row_to_record(r) for r in cur.fetchall()]

    def update_status(
        self, app_id: str, status: ApplicationStatus, notes: str = ""
    ) -> JobApplicationRecord:
        now = datetime.now(timezone.utc).isoformat()
        with self._connection() as conn:
            if notes:
                conn.execute(
                    """
                    UPDATE career_applications
                    SET status = ?, notes = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (status.value, notes, now, app_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE career_applications
                    SET status = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (status.value, now, app_id),
                )
            conn.commit()

        rec = self.get_application(app_id)
        if not rec:
            raise ValueError(f"Application {app_id} not found")
        return rec

    def save_cover_letter(self, app_id: str, cover_letter: str) -> JobApplicationRecord:
        now = datetime.now(timezone.utc).isoformat()
        with self._connection() as conn:
            conn.execute(
                """
                UPDATE career_applications
                SET cover_letter = ?, updated_at = ?
                WHERE id = ?
                """,
                (cover_letter, now, app_id),
            )
            conn.commit()

        rec = self.get_application(app_id)
        if not rec:
            raise ValueError(f"Application {app_id} not found")
        return rec

    def save_outreach(
        self, app_id: str, draft: OutreachEmailDraft
    ) -> JobApplicationRecord:
        now = datetime.now(timezone.utc).isoformat()
        with self._connection() as conn:
            conn.execute(
                """
                UPDATE career_applications
                SET outreach_email_draft = ?, updated_at = ?
                WHERE id = ?
                """,
                (json.dumps(draft.to_dict()), now, app_id),
            )
            conn.commit()

        rec = self.get_application(app_id)
        if not rec:
            raise ValueError(f"Application {app_id} not found")
        return rec

    def save_submission(
        self, app_id: str, submitted_fields: dict[str, Any], screenshot_path: str = ""
    ) -> JobApplicationRecord:
        now = datetime.now(timezone.utc).isoformat()
        with self._connection() as conn:
            conn.execute(
                """
                UPDATE career_applications
                SET submitted_fields = ?, screenshot_path = ?, updated_at = ?
                WHERE id = ?
                """,
                (json.dumps(submitted_fields), screenshot_path, now, app_id),
            )
            conn.commit()

        rec = self.get_application(app_id)
        if not rec:
            raise ValueError(f"Application {app_id} not found")
        return rec
