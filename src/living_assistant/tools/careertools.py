from __future__ import annotations

from typing import Any
import urllib.request

from living_assistant.career.filler import JobFormFiller
from living_assistant.career.parser import JobParser
from living_assistant.career.profile import CareerProfileStore
from living_assistant.career.tailor import TailoringEngine
from living_assistant.career.tracker import ApplicationStatus, ApplicationTracker
from living_assistant.desktop.browser import safe_browser_url
from living_assistant.tools.base import Tool


def build_career_tools(
    profile_store: CareerProfileStore | None = None,
    tracker: ApplicationTracker | None = None,
    browser_controller: Any = None,
    approval_manager: Any = None,
    enabled: bool = True,
) -> list[Tool]:
    if not enabled:
        return []

    store = profile_store if profile_store is not None else CareerProfileStore()
    app_tracker = tracker if tracker is not None else ApplicationTracker()
    parser = JobParser()
    tailor = TailoringEngine()
    filler = JobFormFiller(
        browser_controller=browser_controller,
        approval_manager=approval_manager,
        tracker=app_tracker,
    )

    def career_profile_get(**kwargs) -> dict[str, Any]:
        profile = store.get_profile()
        return {"ok": True, "profile": profile.to_dict()}

    def career_profile_update(profile_data: dict[str, Any], **kwargs) -> dict[str, Any]:
        updated = store.update_profile(profile_data)
        return {"ok": True, "profile": updated.to_dict()}

    def career_job_analyze(url: str = "", html_text: str = "", **kwargs) -> dict[str, Any]:
        if not url and not html_text:
            return {"ok": False, "error": "Either url or html_text must be provided."}

        fetched_html = html_text
        if url and not fetched_html:
            if not safe_browser_url(url):
                return {"ok": False, "error": f"Invalid or unsafe URL: {url}"}
            try:
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                )
                with urllib.request.urlopen(req, timeout=15) as resp:
                    fetched_html = resp.read().decode("utf-8", errors="replace")
            except Exception as e:
                # If direct fetch fails, use fallback mock/minimal html
                fetched_html = f"<html><body><h1>Job at {url}</h1><p>Failed to direct fetch: {e}</p></body></html>"

        parsed = parser.parse_posting(url=url, html=fetched_html)
        app_record = app_tracker.create_application(parsed)

        return {
            "ok": True,
            "application_id": app_record.id,
            "company": parsed.company,
            "title": parsed.title,
            "platform": parsed.platform.value,
            "recruiter_emails": [c.email for c in parsed.contacts],
            "hiring_contacts": [
                {"email": c.email, "confidence": c.confidence, "is_hiring": c.is_hiring_specific}
                for c in parsed.contacts
            ],
            "status": app_record.status.value,
        }

    def career_apply(url: str = "", app_id: str = "", **kwargs) -> dict[str, Any]:
        target_app_id = app_id
        if not target_app_id:
            if not url:
                return {"ok": False, "error": "Either url or app_id must be provided."}
            analyze_res = career_job_analyze(url=url)
            if not analyze_res.get("ok"):
                return analyze_res
            target_app_id = analyze_res["application_id"]

        profile = store.get_profile()
        record = app_tracker.get_application(target_app_id)
        if not record:
            return {"ok": False, "error": f"Application {target_app_id} not found."}

        # Generate cover letter if none exists
        if not record.cover_letter:
            from living_assistant.career.parser import ATSPlatform, ParsedJob

            parsed_mock = ParsedJob(
                title=record.title,
                company=record.company,
                url=record.url,
                platform=ATSPlatform(record.platform) if record.platform in [p.value for p in ATSPlatform] else ATSPlatform.GENERIC,
                description=record.notes or record.title,
            )
            cl = tailor.generate_cover_letter(profile, parsed_mock)
            app_tracker._get_conn()
            with app_tracker._get_conn() as conn:
                conn.execute(
                    "UPDATE career_applications SET cover_letter = ? WHERE id = ?",
                    (cl, target_app_id),
                )
                conn.commit()

        preview = filler.stage_application(target_app_id, profile)
        return {
            "ok": True,
            "application_id": target_app_id,
            "status": preview.status,
            "preview": preview.to_dict(),
            "message": "Application pre-filled and paused before final submit. Awaiting human approval.",
        }

    def career_applications_list(status: str | None = None, **kwargs) -> dict[str, Any]:
        st_enum = ApplicationStatus(status) if status and status in [s.value for s in ApplicationStatus] else None
        records = app_tracker.list_applications(status=st_enum)
        return {
            "ok": True,
            "applications": [r.to_dict() for r in records],
            "count": len(records),
        }

    def career_outreach_generate(application_id: str, **kwargs) -> dict[str, Any]:
        record = app_tracker.get_application(application_id)
        if not record:
            return {"ok": False, "error": f"Application {application_id} not found."}

        profile = store.get_profile()
        from living_assistant.career.parser import ATSPlatform, ContactEmail, ParsedJob

        contact = None
        if record.recruiter_emails:
            contact = ContactEmail(email=record.recruiter_emails[0], is_hiring_specific=True)

        job_mock = ParsedJob(
            title=record.title,
            company=record.company,
            url=record.url,
            platform=ATSPlatform(record.platform) if record.platform in [p.value for p in ATSPlatform] else ATSPlatform.GENERIC,
            description=record.notes or f"Opening at {record.company} for {record.title}",
        )
        draft = tailor.generate_cold_outreach(profile, job_mock, contact)
        app_tracker.save_outreach(application_id, draft)

        return {
            "ok": True,
            "application_id": application_id,
            "outreach_email": draft.to_dict(),
        }

    return [
        Tool(
            name="career_profile_get",
            description="Inspect the candidate's career profile, skills, contact info, and master resume details.",
            parameters={"type": "object", "properties": {}},
            handler=career_profile_get,
        ),
        Tool(
            name="career_profile_update",
            description="Update the candidate's career profile (full_name, email, phone, skills, screener preferences).",
            parameters={
                "type": "object",
                "properties": {
                    "profile_data": {
                        "type": "object",
                        "description": "Dictionary of candidate profile fields to update.",
                    }
                },
                "required": ["profile_data"],
            },
            handler=career_profile_update,
        ),
        Tool(
            name="career_job_analyze",
            description="Analyze a target job posting URL or HTML text, extract requirements, and harvest recruiter emails.",
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Job application or posting URL."},
                    "html_text": {"type": "string", "description": "Optional raw HTML of the job posting."},
                },
            },
            handler=career_job_analyze,
        ),
        Tool(
            name="career_apply",
            description="Pre-fill a job application form using candidate's resume/profile, pausing before final submit for approval.",
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Job posting URL to apply to."},
                    "app_id": {"type": "string", "description": "Existing tracked application ID."},
                },
            },
            handler=career_apply,
        ),
        Tool(
            name="career_applications_list",
            description="List tracked job applications, current status, recruiter contacts, and notes.",
            parameters={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "Optional filter: saved, analyzed, ready_for_review, applied, interviewing, rejected, offer.",
                    }
                },
            },
            handler=career_applications_list,
        ),
        Tool(
            name="career_outreach_generate",
            description="Generate a personalized cold outreach email to recruiter/hiring manager for an application.",
            parameters={
                "type": "object",
                "properties": {
                    "application_id": {"type": "string", "description": "ID of the tracked job application."},
                },
                "required": ["application_id"],
            },
            handler=career_outreach_generate,
        ),
    ]
