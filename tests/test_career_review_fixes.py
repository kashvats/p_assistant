from pathlib import Path
from unittest.mock import MagicMock
import pytest

from living_assistant.career.filler import JobFormFiller
from living_assistant.career.parser import ATSPlatform, JobParser, ParsedJob
from living_assistant.career.profile import CareerProfileStore, ResumeParser
from living_assistant.career.tailor import TailoringEngine
from living_assistant.career.tracker import ApplicationStatus, ApplicationTracker


def test_corrupt_or_empty_resume_returns_error(tmp_path: Path):
    store = CareerProfileStore(storage_dir=tmp_path)
    # Empty file
    res_empty = store.save_resume_file("empty.pdf", b"")
    assert res_empty["ok"] is False
    assert "empty" in res_empty["error"].lower()

    # Corrupt binary PDF
    corrupt_pdf_bytes = b"%PDF-1.4\ncorrupt garbage bytes \x00\xff\xfe that are not valid pdf"
    res_corrupt = store.save_resume_file("corrupt.pdf", corrupt_pdf_bytes)
    assert res_corrupt["ok"] is False
    assert "corrupt" in res_corrupt["error"].lower() or "failed" in res_corrupt["error"].lower()


def test_tracker_persists_job_description_and_requirements(tmp_path: Path):
    tracker = ApplicationTracker(db_path=tmp_path / "apps.db")
    job = ParsedJob(
        title="Staff Engineer",
        company="Acme Corp",
        url="https://jobs.lever.co/acme/1",
        platform=ATSPlatform.LEVER,
        description="Deep knowledge of distributed Raft consensus and Rust.",
        requirements=["Raft", "Rust", "Distributed Systems"],
    )
    rec = tracker.create_application(job)
    assert rec.description == "Deep knowledge of distributed Raft consensus and Rust."
    assert "Raft" in rec.requirements

    # Reload from SQLite
    reloaded = tracker.get_application(rec.id)
    assert reloaded is not None
    assert reloaded.description == "Deep knowledge of distributed Raft consensus and Rust."
    assert "Raft" in reloaded.requirements


def test_iframe_detection_in_job_parser():
    html_with_iframe = """
    <html>
      <body>
        <h1>Careers at HealthTech</h1>
        <div class="job-container">
          <iframe src="https://boards.greenhouse.io/embed/job_app?for=healthtech&token=405912"></iframe>
        </div>
      </body>
    </html>
    """
    parser = JobParser()
    ats = parser.detect_ats("https://healthtech.com/careers/engineer", html=html_with_iframe)
    assert ats == ATSPlatform.GREENHOUSE
    iframe_url = parser.extract_iframe_url(html_with_iframe)
    assert "boards.greenhouse.io" in iframe_url


def test_tailor_does_not_fabricate_recruiter_email():
    engine = TailoringEngine()
    profile = MagicMock()
    profile.full_name = "Jane Candidate"
    profile.skills = ["Python"]
    profile.github_url = ""
    profile.linkedin_url = ""
    profile.email = "jane@example.com"
    profile.phone = "123456"

    job = ParsedJob(
        title="Backend Dev",
        company="Stealth Startup",
        url="https://stealth.io/job",
        platform=ATSPlatform.GENERIC,
        description="Python backend",
    )
    # Contact is None: must NOT fabricate "recruiting@stealthstartup.com"
    draft = engine.generate_cold_outreach(profile, job, contact=None)
    assert draft.recipient == ""


def test_approval_gate_strict_rejection(tmp_path: Path):
    tracker = ApplicationTracker(db_path=tmp_path / "apps.db")
    job = ParsedJob(
        title="Dev", company="Corp", url="https://jobs.lever.co/corp/1", platform=ATSPlatform.LEVER, description="Dev"
    )
    rec = tracker.create_application(job)

    # When approval_manager is None, execute_submission must fail rather than blindly accepting tokens
    filler = JobFormFiller(browser_controller=None, approval_manager=None, tracker=tracker)
    res = filler.execute_submission(rec.id, approval_token="arbitrary_token")
    assert res["ok"] is False
    assert "no approval manager" in res["error"].lower() or "approval denied" in res["error"].lower()
