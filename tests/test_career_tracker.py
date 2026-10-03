import pytest
from living_assistant.career.tracker import ApplicationTracker, ApplicationStatus, JobApplicationRecord
from living_assistant.career.parser import ParsedJob, ATSPlatform
from living_assistant.career.tailor import OutreachEmailDraft

def test_tracker_crud(tmp_path):
    tracker = ApplicationTracker(db_path=tmp_path / "test_career.db")
    job = ParsedJob(
        title="Senior Python Engineer",
        company="TechCorp",
        url="https://jobs.lever.co/techcorp/123",
        platform=ATSPlatform.LEVER,
        description="Python backend role"
    )
    record = tracker.create_application(job, recruiter_emails=["recruiter@techcorp.com"])
    assert record.id is not None
    assert record.company == "TechCorp"
    assert record.title == "Senior Python Engineer"
    assert record.status == ApplicationStatus.ANALYZED
    assert "recruiter@techcorp.com" in record.recruiter_emails
    
    # Update status
    updated = tracker.update_status(record.id, ApplicationStatus.APPLIED, notes="Submitted via Lever")
    assert updated.status == ApplicationStatus.APPLIED
    assert updated.notes == "Submitted via Lever"
    
    # Save outreach draft
    draft = OutreachEmailDraft(
        recipient="recruiter@techcorp.com",
        subject="Intro",
        body="Hello",
        company="TechCorp",
        title="Senior Python Engineer"
    )
    saved_app = tracker.save_outreach(record.id, draft)
    assert saved_app.outreach_email_draft["subject"] == "Intro"

    # Reload from disk
    reloaded_tracker = ApplicationTracker(db_path=tmp_path / "test_career.db")
    fetched = reloaded_tracker.get_application(record.id)
    assert fetched is not None
    assert fetched.status == ApplicationStatus.APPLIED
    assert fetched.outreach_email_draft["recipient"] == "recruiter@techcorp.com"

    # List filtered
    apps = reloaded_tracker.list_applications(status=ApplicationStatus.APPLIED)
    assert len(apps) == 1
    assert apps[0].id == record.id
    
    apps_empty = reloaded_tracker.list_applications(status=ApplicationStatus.INTERVIEWING)
    assert len(apps_empty) == 0
