from unittest.mock import MagicMock
import pytest
from living_assistant.career.filler import JobFormFiller, SubmissionPreview
from living_assistant.career.profile import CandidateProfile
from living_assistant.career.tracker import ApplicationTracker, ApplicationStatus
from living_assistant.career.parser import ParsedJob, ATSPlatform

def test_filler_pauses_for_approval(tmp_path):
    tracker = ApplicationTracker(db_path=tmp_path / "test.db")
    job = ParsedJob(
        title="Frontend Dev",
        company="StartupX",
        url="https://boards.greenhouse.io/startupx/jobs/111",
        platform=ATSPlatform.GREENHOUSE,
        description="React developer"
    )
    rec = tracker.create_application(job)
    
    mock_browser = MagicMock()
    mock_approval = MagicMock()
    # Mock approval request creation
    mock_approval.require_approval.return_value = {"approved": False, "pending": True, "token": "tok_123"}
    
    filler = JobFormFiller(browser_controller=mock_browser, approval_manager=mock_approval, tracker=tracker)
    preview = filler.stage_application(rec.id, CandidateProfile(full_name="Sam Smith", email="sam@example.com"))
    
    assert preview.app_id == rec.id
    assert preview.status == "ready_for_review"
    assert preview.company == "StartupX"
    assert preview.fields_prepared["email"] == "sam@example.com"
    
    # Verify approval was invoked
    mock_approval.require_approval.assert_called_once()
    call_args = mock_approval.require_approval.call_args[0]
    assert call_args[0] == "career_submit_application"
    
    # Reload record to ensure status updated to ready_for_review
    reloaded = tracker.get_application(rec.id)
    assert reloaded.status == ApplicationStatus.READY_FOR_REVIEW

def test_filler_executes_submit_only_with_valid_approval(tmp_path):
    tracker = ApplicationTracker(db_path=tmp_path / "test.db")
    job = ParsedJob(
        title="Backend Dev",
        company="ScaleCo",
        url="https://jobs.lever.co/scaleco/222",
        platform=ATSPlatform.LEVER,
        description="Python backend"
    )
    rec = tracker.create_application(job)
    
    mock_browser = MagicMock()
    mock_approval = MagicMock()
    filler = JobFormFiller(browser_controller=mock_browser, approval_manager=mock_approval, tracker=tracker)
    filler.stage_application(rec.id, CandidateProfile(full_name="Sam Smith", email="sam@example.com"))
    
    # 1. Denied approval
    mock_approval.verify_approval.return_value = False
    result_denied = filler.execute_submission(rec.id, approval_token="bad_tok")
    assert result_denied["ok"] is False
    assert "Approval denied" in result_denied["error"]
    assert tracker.get_application(rec.id).status == ApplicationStatus.READY_FOR_REVIEW

    # 2. Granted approval
    mock_approval.verify_approval.return_value = True
    result_approved = filler.execute_submission(rec.id, approval_token="good_tok")
    assert result_approved["ok"] is True
    assert tracker.get_application(rec.id).status == ApplicationStatus.APPLIED
