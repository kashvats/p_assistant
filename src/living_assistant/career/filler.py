from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from living_assistant.career.parser import ATSPlatform
from living_assistant.career.profile import CandidateProfile
from living_assistant.career.tracker import ApplicationStatus, ApplicationTracker
from living_assistant.desktop.browser import safe_browser_url


@dataclass
class SubmissionPreview:
    app_id: str
    company: str
    title: str
    url: str
    status: str
    fields_prepared: dict[str, Any] = field(default_factory=dict)
    screenshot_path: str = ""
    approval_token: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "app_id": self.app_id,
            "company": self.company,
            "title": self.title,
            "url": self.url,
            "status": self.status,
            "fields_prepared": self.fields_prepared,
            "screenshot_path": self.screenshot_path,
            "approval_token": self.approval_token,
        }


class JobFormFiller:
    """Fills candidate details into ATS application forms and gates final submission on human approval."""

    def __init__(
        self,
        browser_controller: Any,
        approval_manager: Any,
        tracker: ApplicationTracker,
    ) -> None:
        self.browser_controller = browser_controller
        self.approval_manager = approval_manager
        self.tracker = tracker

    def map_form_fields(
        self, profile: CandidateProfile, platform: ATSPlatform | str
    ) -> dict[str, Any]:
        parts = profile.full_name.strip().split(maxsplit=1)
        first_name = parts[0] if parts else ""
        last_name = parts[1] if len(parts) > 1 else ""

        return {
            "first_name": first_name,
            "last_name": last_name,
            "full_name": profile.full_name,
            "email": profile.email,
            "phone": profile.phone,
            "location": profile.location,
            "linkedin": profile.linkedin_url,
            "github": profile.github_url,
            "website": profile.portfolio_url,
            "resume_path": profile.resume_file_path,
            "legally_authorized": "Yes" if profile.screener.legally_authorized else "No",
            "requires_sponsorship": "Yes" if profile.screener.requires_visa_sponsorship else "No",
            "desired_salary": profile.screener.target_compensation,
            "notice_period": f"{profile.screener.notice_period_weeks} weeks",
            "gender": profile.screener.eeoc_gender,
            "race": profile.screener.eeoc_race,
            "veteran": profile.screener.eeoc_veteran,
            "disability": profile.screener.eeoc_disability,
        }

    def stage_application(
        self, app_id: str, profile: CandidateProfile
    ) -> SubmissionPreview:
        record = self.tracker.get_application(app_id)
        if not record:
            raise ValueError(f"Application {app_id} not found in tracker")

        if record.url and not safe_browser_url(record.url):
            raise ValueError(f"Unsafe or invalid application URL: {record.url}")

        fields = self.map_form_fields(profile, record.platform)

        # Pre-submit approval request: the user approves it (Approvals page), then execute_submission runs.
        token = self._request_approval(app_id, record)

        # Update tracker
        self.tracker.update_status(app_id, ApplicationStatus.READY_FOR_REVIEW)
        self.tracker.save_submission(app_id, submitted_fields=fields, screenshot_path="")

        return SubmissionPreview(
            app_id=app_id,
            company=record.company,
            title=record.title,
            url=record.url,
            status=ApplicationStatus.READY_FOR_REVIEW.value,
            fields_prepared=fields,
            screenshot_path="",
            approval_token=token,
        )

    APPROVAL_ACTION = "career_submit_application"

    @staticmethod
    def _reason(record) -> str:
        return f"Apply to {record.company} for {record.title} ({record.url})"

    def _request_approval(self, app_id: str, record) -> str:
        """Ask for approval to submit; returns the approval id the user approves."""
        manager = self.approval_manager
        if manager is None:
            return ""
        if hasattr(manager, "require_approval"):  # token-style approval services
            res = manager.require_approval(self.APPROVAL_ACTION, {"app_id": app_id, "company": record.company,
                                                                  "title": record.title, "url": record.url})
            return str(res.get("token", "")) if isinstance(res, dict) else str(res or "")
        # The assistant's ApprovalManager: creates a pending approval (or consumes one the user already gave).
        res = manager.request(self.APPROVAL_ACTION, self._reason(record), "execute")
        return str(res.get("approval_id") or res.get("id") or "") if isinstance(res, dict) else ""

    def _approved(self, token: str, record) -> bool:
        manager = self.approval_manager
        if hasattr(manager, "verify_approval"):
            return bool(manager.verify_approval(token))
        # ApprovalManager: asking again for the same action consumes the approval the user gave (once).
        res = manager.request(self.APPROVAL_ACTION, self._reason(record), "execute")
        return bool(isinstance(res, dict) and res.get("allowed"))

    def execute_submission(
        self, app_id: str, approval_token: str
    ) -> dict[str, Any]:
        record = self.tracker.get_application(app_id)
        if not record:
            return {"ok": False, "error": f"Application {app_id} not found"}

        if self.approval_manager is None:
            return {
                "ok": False,
                "app_id": app_id,
                "error": "No approval manager configured; submission cannot be verified.",
            }

        if not self._approved(approval_token, record):
            return {
                "ok": False,
                "app_id": app_id,
                "error": "Approval denied or token expired/invalid; application was not submitted.",
            }

        # If browser controller has live session/submit method, execute it
        if hasattr(self.browser_controller, "submit_form"):
            try:
                self.browser_controller.submit_form(record.url)
            except Exception as e:
                return {"ok": False, "app_id": app_id, "error": f"Browser submission error: {e}"}

        self.tracker.update_status(app_id, ApplicationStatus.APPLIED, notes="Submitted after human approval")
        return {"ok": True, "app_id": app_id, "status": "applied"}
