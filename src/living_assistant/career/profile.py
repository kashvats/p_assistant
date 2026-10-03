from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from living_assistant.core.config import data_dir


@dataclass
class ScreenerProfile:
    legally_authorized: bool = True
    requires_visa_sponsorship: bool = False
    target_compensation: str = ""
    notice_period_weeks: int = 2
    citizenship: str = ""
    eeoc_gender: str = "Decline to self-identify"
    eeoc_race: str = "Decline to self-identify"
    eeoc_veteran: str = "Decline to self-identify"
    eeoc_disability: str = "Decline to self-identify"


@dataclass
class CandidateProfile:
    full_name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    linkedin_url: str = ""
    github_url: str = ""
    portfolio_url: str = ""
    summary: str = ""
    skills: list[str] = field(default_factory=list)
    work_history: list[dict[str, Any]] = field(default_factory=list)
    education: list[dict[str, Any]] = field(default_factory=list)
    screener: ScreenerProfile = field(default_factory=ScreenerProfile)
    resume_file_path: str = ""
    resume_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CandidateProfile:
        screener_data = data.get("screener", {})
        screener = ScreenerProfile(**screener_data) if isinstance(screener_data, dict) else ScreenerProfile()
        return cls(
            full_name=data.get("full_name", ""),
            email=data.get("email", ""),
            phone=data.get("phone", ""),
            location=data.get("location", ""),
            linkedin_url=data.get("linkedin_url", ""),
            github_url=data.get("github_url", ""),
            portfolio_url=data.get("portfolio_url", ""),
            summary=data.get("summary", ""),
            skills=list(data.get("skills", [])),
            work_history=list(data.get("work_history", [])),
            education=list(data.get("education", [])),
            screener=screener,
            resume_file_path=data.get("resume_file_path", ""),
            resume_text=data.get("resume_text", ""),
        )


class ResumeParser:
    """Extracts raw text and structure from resumes in PDF, DOCX, MD, and text formats."""

    def extract_text(self, file_path: str | Path) -> str:
        path = Path(file_path)
        if not path.is_file():
            return ""
        if path.stat().st_size == 0:
            return ""

        suffix = path.suffix.lower()

        if suffix in {".txt", ".md", ".markdown"}:
            try:
                return path.read_text(encoding="utf-8", errors="replace").strip()
            except Exception:
                return ""

        if suffix == ".docx":
            try:
                import docx  # python-docx

                doc = docx.Document(str(path))
                paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
                return "\n".join(paragraphs).strip()
            except Exception:
                pass

        if suffix == ".pdf":
            # Attempt pypdf
            try:
                import pypdf

                reader = pypdf.PdfReader(str(path))
                text_parts = []
                for page in reader.pages:
                    t = page.extract_text()
                    if t:
                        text_parts.append(t)
                if text_parts:
                    return "\n".join(text_parts).strip()
            except Exception:
                pass

            # Attempt fitz (PyMuPDF)
            try:
                import fitz

                doc = fitz.open(str(path))
                text_parts = []
                for page in doc:
                    text_parts.append(page.get_text())
                if text_parts:
                    return "\n".join(text_parts).strip()
            except Exception:
                pass

        # Fallback reading raw string tokens
        try:
            return path.read_text(encoding="utf-8", errors="ignore").strip()
        except Exception:
            return ""


class CareerProfileStore:
    """Persistent storage for candidate profile and master resume documents."""

    def __init__(self, storage_dir: Path | None = None) -> None:
        self.storage_dir = Path(storage_dir) if storage_dir else data_dir() / "career"
        self.resumes_dir = self.storage_dir / "resumes"
        self.profile_path = self.storage_dir / "career_profile.json"
        self.parser = ResumeParser()
        self._ensure_storage()

    def _ensure_storage(self) -> None:
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.resumes_dir.mkdir(parents=True, exist_ok=True)

    def get_profile(self) -> CandidateProfile:
        if not self.profile_path.is_file():
            default_profile = CandidateProfile()
            self._save(default_profile)
            return default_profile
        try:
            data = json.loads(self.profile_path.read_text(encoding="utf-8"))
            return CandidateProfile.from_dict(data)
        except Exception:
            return CandidateProfile()

    def update_profile(self, updates: dict[str, Any]) -> CandidateProfile:
        profile = self.get_profile()
        for k, v in updates.items():
            if k == "screener" and isinstance(v, dict):
                for sk, sv in v.items():
                    if hasattr(profile.screener, sk):
                        setattr(profile.screener, sk, sv)
            elif hasattr(profile, k):
                setattr(profile, k, v)
        self._save(profile)
        return profile

    def save_resume_file(self, filename: str, content: bytes) -> str:
        safe_name = Path(filename).name
        target_path = self.resumes_dir / safe_name
        target_path.write_bytes(content)

        extracted_text = self.parser.extract_text(target_path)
        self.update_profile({
            "resume_file_path": str(target_path),
            "resume_text": extracted_text,
        })
        return str(target_path)

    def _save(self, profile: CandidateProfile) -> None:
        self._ensure_storage()
        self.profile_path.write_text(
            json.dumps(profile.to_dict(), indent=2),
            encoding="utf-8",
        )
