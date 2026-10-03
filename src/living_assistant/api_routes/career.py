from __future__ import annotations

from typing import Any
import urllib.request

from fastapi import APIRouter, File, Header, HTTPException, UploadFile
from pydantic import BaseModel, Field

from living_assistant.api_routes.dependencies import authorize, runtime
from living_assistant.career.filler import JobFormFiller
from living_assistant.career.parser import ATSPlatform, ContactEmail, JobParser, ParsedJob
from living_assistant.career.profile import CareerProfileStore
from living_assistant.career.tailor import TailoringEngine
from living_assistant.career.tracker import ApplicationStatus, ApplicationTracker
from living_assistant.desktop.browser import safe_browser_url
from living_assistant.security.security_utils import url_network_scope

router = APIRouter(tags=["career"])

_profile_store = CareerProfileStore()
_tracker = ApplicationTracker()
_parser = JobParser()
_tailor = TailoringEngine()


class JobAnalyzeRequest(BaseModel):
    url: str = Field("", description="Job posting URL")
    html_text: str = Field("", description="Optional raw HTML content")


class JobApplyRequest(BaseModel):
    url: str = Field("", description="Job posting URL to apply to")
    app_id: str = Field("", description="Existing application ID")


class JobConfirmSubmitRequest(BaseModel):
    app_id: str = Field(..., description="Application ID to submit")
    approval_token: str = Field(..., description="Approval token granted by human review")


class StatusUpdateRequest(BaseModel):
    status: str = Field(..., description="Target status: saved, analyzed, ready_for_review, applied, interviewing, rejected, offer")
    notes: str = Field("", description="Optional notes")


@router.get("/api/v1/career/profile")
def get_career_profile(authorization: str | None = Header(default=None)):
    authorize(authorization)
    profile = _profile_store.get_profile()
    return {"ok": True, "profile": profile.to_dict()}


@router.put("/api/v1/career/profile")
def update_career_profile(updates: dict[str, Any], authorization: str | None = Header(default=None)):
    authorize(authorization)
    updated = _profile_store.update_profile(updates)
    return {"ok": True, "profile": updated.to_dict()}


@router.post("/api/v1/career/resume/upload")
async def upload_resume(file: UploadFile = File(...), authorization: str | None = Header(default=None)):
    authorize(authorization)
    content = await file.read()
    filename = file.filename or "resume.pdf"
    res = _profile_store.save_resume_file(filename, content)
    if not res.get("ok"):
        raise HTTPException(status_code=400, detail=res.get("error", "Failed to parse resume."))
    profile = _profile_store.get_profile()
    return {
        "ok": True,
        "resume_path": res.get("path", ""),
        "extracted_chars": len(profile.resume_text),
        "profile": profile.to_dict(),
    }


@router.post("/api/v1/career/jobs/analyze")
def analyze_job(req: JobAnalyzeRequest, authorization: str | None = Header(default=None)):
    authorize(authorization)
    fetched_html = req.html_text
    if req.url and not fetched_html:
        if not safe_browser_url(req.url):
            raise HTTPException(status_code=400, detail=f"Invalid or blocked URL: {req.url}")
        scope, reason = url_network_scope(req.url)
        if scope != "public":
            raise HTTPException(status_code=400, detail=f"Blocked URL ({reason or 'private or invalid network address'})")
        try:
            r = urllib.request.Request(
                req.url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            )
            with urllib.request.urlopen(r, timeout=15) as resp:
                fetched_html = resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            fetched_html = f"<html><body><h1>Opening at {req.url}</h1><p>Failed direct fetch: {e}</p></body></html>"

    parsed = _parser.parse_posting(url=req.url, html=fetched_html)
    record = _tracker.create_application(parsed)

    return {
        "ok": True,
        "application_id": record.id,
        "company": parsed.company,
        "title": parsed.title,
        "platform": parsed.platform.value,
        "recruiter_emails": [c.email for c in parsed.contacts],
        "hiring_contacts": [
            {"email": c.email, "confidence": c.confidence, "is_hiring": c.is_hiring_specific}
            for c in parsed.contacts
        ],
        "status": record.status.value,
    }


@router.post("/api/v1/career/jobs/apply")
def stage_job_application(req: JobApplyRequest, authorization: str | None = Header(default=None)):
    authorize(authorization)
    target_id = req.app_id
    if not target_id:
        if not req.url:
            raise HTTPException(status_code=400, detail="Either app_id or url must be provided.")
        analyze_res = analyze_job(JobAnalyzeRequest(url=req.url), authorization=authorization)
        target_id = analyze_res["application_id"]

    record = _tracker.get_application(target_id)
    if not record:
        raise HTTPException(status_code=404, detail="Application not found")

    profile = _profile_store.get_profile()

    if not record.cover_letter:
        parsed_mock = ParsedJob(
            title=record.title,
            company=record.company,
            url=record.url,
            platform=ATSPlatform(record.platform) if record.platform in [p.value for p in ATSPlatform] else ATSPlatform.GENERIC,
            description=record.description or record.notes or record.title,
        )
        cl = _tailor.generate_cover_letter(profile, parsed_mock)
        _tracker.save_cover_letter(target_id, cl)

    rt = runtime()
    appr = rt.approval if rt is not None else None
    browser = rt.browser if rt is not None else None

    filler = JobFormFiller(browser_controller=browser, approval_manager=appr, tracker=_tracker)
    preview = filler.stage_application(target_id, profile)

    return {
        "ok": True,
        "application_id": target_id,
        "status": preview.status,
        "preview": preview.to_dict(),
        "message": "Application staged and paused before submit. Human approval required.",
    }


@router.post("/api/v1/career/jobs/confirm-submit")
def confirm_job_submission(req: JobConfirmSubmitRequest, authorization: str | None = Header(default=None)):
    authorize(authorization)
    rt = runtime()
    appr = rt.approval if rt is not None else None
    browser = rt.browser if rt is not None else None

    filler = JobFormFiller(browser_controller=browser, approval_manager=appr, tracker=_tracker)
    res = filler.execute_submission(req.app_id, req.approval_token)
    if not res.get("ok"):
        raise HTTPException(status_code=400, detail=res.get("error", "Submission rejected"))
    return res


@router.get("/api/v1/career/applications")
def list_career_applications(status: str | None = None, authorization: str | None = Header(default=None)):
    authorize(authorization)
    st_enum = ApplicationStatus(status) if status and status in [s.value for s in ApplicationStatus] else None
    records = _tracker.list_applications(status=st_enum)
    return {
        "ok": True,
        "applications": [r.to_dict() for r in records],
        "count": len(records),
    }


@router.get("/api/v1/career/applications/{app_id}")
def get_career_application(app_id: str, authorization: str | None = Header(default=None)):
    authorize(authorization)
    record = _tracker.get_application(app_id)
    if not record:
        raise HTTPException(status_code=404, detail="Application not found")
    return {"ok": True, "application": record.to_dict()}


@router.patch("/api/v1/career/applications/{app_id}")
def update_career_application_status(app_id: str, req: StatusUpdateRequest, authorization: str | None = Header(default=None)):
    authorize(authorization)
    if req.status not in [s.value for s in ApplicationStatus]:
        raise HTTPException(status_code=400, detail=f"Invalid status: {req.status}")
    updated = _tracker.update_status(app_id, ApplicationStatus(req.status), req.notes)
    return {"ok": True, "application": updated.to_dict()}


@router.post("/api/v1/career/applications/{app_id}/outreach")
def generate_career_outreach(app_id: str, authorization: str | None = Header(default=None)):
    authorize(authorization)
    record = _tracker.get_application(app_id)
    if not record:
        raise HTTPException(status_code=404, detail="Application not found")

    profile = _profile_store.get_profile()
    contact = None
    if record.recruiter_emails:
        contact = ContactEmail(email=record.recruiter_emails[0], is_hiring_specific=True)

    job_mock = ParsedJob(
        title=record.title,
        company=record.company,
        url=record.url,
        platform=ATSPlatform(record.platform) if record.platform in [p.value for p in ATSPlatform] else ATSPlatform.GENERIC,
        description=record.description or record.notes or f"Role at {record.company} for {record.title}",
    )
    draft = _tailor.generate_cold_outreach(profile, job_mock, contact)
    _tracker.save_outreach(app_id, draft)

    return {
        "ok": True,
        "application_id": app_id,
        "outreach_email": draft.to_dict(),
    }
