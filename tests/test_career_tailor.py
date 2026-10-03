import pytest
from living_assistant.career.profile import CandidateProfile, ScreenerProfile
from living_assistant.career.parser import ParsedJob, ATSPlatform, ContactEmail
from living_assistant.career.tailor import TailoringEngine, OutreachEmailDraft

def test_tailor_cold_outreach():
    profile = CandidateProfile(
        full_name="Jordan Lee",
        email="jordan@example.com",
        skills=["Python", "Distributed Systems", "Kubernetes"],
        github_url="https://github.com/jordanlee",
        linkedin_url="https://linkedin.com/in/jordanlee"
    )
    job = ParsedJob(
        title="Staff Infrastructure Engineer",
        company="CloudScale",
        url="https://cloudscale.io/jobs/infra",
        platform=ATSPlatform.GENERIC,
        description="Looking for distributed systems experts to scale Kubernetes clusters."
    )
    contact = ContactEmail(email="recruiting@cloudscale.io", source="careers_page", is_hiring_specific=True)
    
    engine = TailoringEngine()
    draft = engine.generate_cold_outreach(profile, job, contact)
    assert draft.recipient == "recruiting@cloudscale.io"
    assert "Staff Infrastructure Engineer" in draft.subject
    assert "CloudScale" in draft.subject
    assert "Jordan Lee" in draft.body
    assert "Kubernetes" in draft.body or "Distributed Systems" in draft.body
    assert "https://github.com/jordanlee" in draft.body
    assert draft.status == "draft"

def test_tailor_cover_letter():
    profile = CandidateProfile(
        full_name="Morgan Chen",
        email="morgan@example.com",
        skills=["React", "TypeScript", "Tailwind CSS"],
        summary="Frontend architect with 6 years experience crafting web apps."
    )
    job = ParsedJob(
        title="Senior Frontend Engineer",
        company="DesignTech",
        url="https://boards.greenhouse.io/designtech/jobs/42",
        platform=ATSPlatform.GREENHOUSE,
        description="Build responsive user interfaces using React and modern CSS."
    )
    engine = TailoringEngine()
    letter = engine.generate_cover_letter(profile, job)
    assert "Morgan Chen" in letter
    assert "Senior Frontend Engineer" in letter
    assert "DesignTech" in letter
    assert "React" in letter

def test_tailor_screening_answers():
    profile = CandidateProfile(
        full_name="Taylor Swiftly",
        email="taylor@example.com",
        screener=ScreenerProfile(
            legally_authorized=True,
            requires_visa_sponsorship=False,
            target_compensation="$160,000",
            notice_period_weeks=3
        )
    )
    job = ParsedJob(
        title="Backend Dev",
        company="Acme",
        url="https://jobs.lever.co/acme/1",
        platform=ATSPlatform.LEVER,
        description="Go and Python backend."
    )
    engine = TailoringEngine()
    questions = [
        "Are you legally authorized to work in the United States?",
        "Will you now or in the future require visa sponsorship?",
        "What are your salary expectations?",
        "What is your notice period?"
    ]
    answers = engine.generate_screening_answers(profile, job, questions)
    assert answers["Are you legally authorized to work in the United States?"] == "Yes"
    assert answers["Will you now or in the future require visa sponsorship?"] == "No"
    assert "$160,000" in answers["What are your salary expectations?"]
    assert "3 weeks" in answers["What is your notice period?"]
