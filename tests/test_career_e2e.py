from pathlib import Path
from unittest.mock import MagicMock
import pytest

from living_assistant.career.filler import JobFormFiller
from living_assistant.career.parser import ATSPlatform, JobParser
from living_assistant.career.profile import CareerProfileStore
from living_assistant.career.tailor import TailoringEngine
from living_assistant.career.tracker import ApplicationStatus, ApplicationTracker


def test_career_subsystem_end_to_end(tmp_path: Path):
    # 1. Initialize stores
    career_dir = tmp_path / "career"
    profile_store = CareerProfileStore(storage_dir=career_dir)
    tracker = ApplicationTracker(db_path=career_dir / "career_applications.db")
    parser = JobParser()
    tailor = TailoringEngine()

    # 2. Ingest master resume
    resume_content = b"""# Alex Rivera
Staff Software Engineer
Email: alex.rivera@example.com | Phone: +1-555-0142 | Location: San Francisco, CA
GitHub: https://github.com/alexrivera | LinkedIn: https://linkedin.com/in/alexrivera

## Summary
Distributed systems architect with 8 years of experience building resilient cloud platforms with Python, Go, and Kubernetes.

## Core Skills
Python, Go, Distributed Systems, Kubernetes, FastAPI, PostgreSQL, Docker, Microservices

## Experience
- Principal Architect at CloudScale (2022-Present): Led core API scaling handling 2M requests/sec.
- Senior Backend Engineer at DataFlow (2018-2022): Designed distributed streaming pipelines.
"""
    saved_resume = profile_store.save_resume_file("master_resume.md", resume_content)
    assert Path(saved_resume).exists()

    # 3. Update candidate profile & screener preferences
    profile = profile_store.update_profile({
        "full_name": "Alex Rivera",
        "email": "alex.rivera@example.com",
        "phone": "+1-555-0142",
        "location": "San Francisco, CA",
        "github_url": "https://github.com/alexrivera",
        "linkedin_url": "https://linkedin.com/in/alexrivera",
        "skills": ["Python", "Go", "Distributed Systems", "Kubernetes", "FastAPI"],
        "screener": {
            "legally_authorized": True,
            "requires_visa_sponsorship": False,
            "target_compensation": "$210,000",
            "notice_period_weeks": 2,
        },
    })
    assert profile.full_name == "Alex Rivera"
    assert "Kubernetes" in profile.skills

    # 4. Job Posting Analysis & Recruiter Email Harvesting
    sample_job_html = """
    <html>
      <head><title>Staff Infrastructure Engineer at HyperGrowth AI - Careers</title></head>
      <body>
        <h1>Staff Infrastructure Engineer</h1>
        <div class="company-name">HyperGrowth AI</div>
        <div class="location">San Francisco, CA (Hybrid)</div>
        <div class="content">
          <p>We are scaling our AI inference cluster and looking for a Staff Engineer with Kubernetes and Python expertise.</p>
          <p>Questions about the role? Contact our lead technical recruiter at <a href="mailto:sarah.recruiting@hypergrowth.ai">sarah.recruiting@hypergrowth.ai</a> or reach jobs@hypergrowth.ai.</p>
        </div>
      </body>
    </html>
    """
    job_url = "https://jobs.ashbyhq.com/hypergrowth/staff-infra"
    parsed_job = parser.parse_posting(url=job_url, html=sample_job_html)

    assert parsed_job.platform == ATSPlatform.ASHBY
    assert parsed_job.company == "HyperGrowth AI" or parsed_job.company == "Hypergrowth"
    assert "Staff Infrastructure Engineer" in parsed_job.title

    harvested_emails = [c.email for c in parsed_job.contacts]
    assert "sarah.recruiting@hypergrowth.ai" in harvested_emails
    assert "jobs@hypergrowth.ai" in harvested_emails
    lead_recruiter = next(c for c in parsed_job.contacts if c.email == "sarah.recruiting@hypergrowth.ai")
    assert lead_recruiter.is_hiring_specific is True

    # 5. Application Record Creation
    app_record = tracker.create_application(parsed_job)
    assert app_record.status == ApplicationStatus.ANALYZED
    assert "sarah.recruiting@hypergrowth.ai" in app_record.recruiter_emails

    # 6. Tailor Cover Letter
    cover_letter = tailor.generate_cover_letter(profile, parsed_job)
    assert "Alex Rivera" in cover_letter
    assert "Staff Infrastructure Engineer" in cover_letter
    assert "Kubernetes" in cover_letter

    # 7. Form Filler with Approval Gate
    mock_browser = MagicMock()
    mock_approval = MagicMock()
    # Mock approval creation and resolution
    mock_approval.require_approval.return_value = {"approved": False, "pending": True, "token": "appr_tok_999"}
    mock_approval.verify_approval.return_value = True

    filler = JobFormFiller(browser_controller=mock_browser, approval_manager=mock_approval, tracker=tracker)
    preview = filler.stage_application(app_record.id, profile)

    assert preview.status == "ready_for_review"
    assert preview.fields_prepared["email"] == "alex.rivera@example.com"
    assert preview.fields_prepared["linkedin"] == "https://linkedin.com/in/alexrivera"
    assert preview.fields_prepared["resume_path"] == str(saved_resume)
    assert preview.fields_prepared["legally_authorized"] == "Yes"

    # Verify tracker is paused at ready_for_review
    staged_record = tracker.get_application(app_record.id)
    assert staged_record.status == ApplicationStatus.READY_FOR_REVIEW

    # 8. Grant Approval & Submit
    submit_result = filler.execute_submission(app_record.id, approval_token="appr_tok_999")
    assert submit_result["ok"] is True
    assert submit_result["status"] == "applied"

    final_record = tracker.get_application(app_record.id)
    assert final_record.status == ApplicationStatus.APPLIED

    # 9. Generate Personalized Cold Outreach Email to Recruiter
    outreach_draft = tailor.generate_cold_outreach(profile, parsed_job, lead_recruiter)
    assert outreach_draft.recipient == "sarah.recruiting@hypergrowth.ai"
    assert "Alex Rivera" in outreach_draft.subject
    assert "Staff Infrastructure Engineer" in outreach_draft.subject
    assert "https://github.com/alexrivera" in outreach_draft.body
    assert outreach_draft.status == "draft"

    saved_app = tracker.save_outreach(app_record.id, outreach_draft)
    assert saved_app.outreach_email_draft["recipient"] == "sarah.recruiting@hypergrowth.ai"
    assert saved_app.outreach_email_draft["subject"] == outreach_draft.subject
