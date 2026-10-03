from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from living_assistant.career.parser import ContactEmail, ParsedJob
from living_assistant.career.profile import CandidateProfile


@dataclass
class OutreachEmailDraft:
    recipient: str
    subject: str
    body: str
    company: str
    title: str
    status: str = "draft"

    def to_dict(self) -> dict[str, Any]:
        return {
            "recipient": self.recipient,
            "subject": self.subject,
            "body": self.body,
            "company": self.company,
            "title": self.title,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OutreachEmailDraft:
        return cls(
            recipient=data.get("recipient", ""),
            subject=data.get("subject", ""),
            body=data.get("body", ""),
            company=data.get("company", ""),
            title=data.get("title", ""),
            status=data.get("status", "draft"),
        )


class TailoringEngine:
    """Generates tailored application materials, responses, and recruiter cold outreach drafts."""

    def generate_cover_letter(self, profile: CandidateProfile, job: ParsedJob) -> str:
        name = profile.full_name or "Applicant"
        title = job.title
        company = job.company
        skills_str = ", ".join(profile.skills[:5]) if profile.skills else "software engineering"
        summary = profile.summary or f"experienced professional specializing in {skills_str}."

        relevant_bullets = []
        for s in profile.skills[:4]:
            if s.lower() in job.description.lower() or not relevant_bullets:
                relevant_bullets.append(f"- Practical experience deploying and architecting with {s}.")

        if not relevant_bullets:
            relevant_bullets.append(f"- Solid foundation in {skills_str}.")

        bullets_text = "\n".join(relevant_bullets)

        letter = f"""Dear Hiring Team at {company},

I am writing to express my strong enthusiasm for the {title} position at {company}. With a proven background as a {summary}, I am confident in my ability to make an immediate, meaningful impact on your engineering initiatives.

A few highlights of what I bring to {company}:
{bullets_text}

I am deeply impressed by {company}'s focus and would welcome the opportunity to discuss how my skill set and dedication can help accelerate your roadmap. Thank you for your time and consideration.

Sincerely,
{name}
{profile.email}
{profile.phone}"""
        return letter.strip()

    def generate_screening_answers(
        self, profile: CandidateProfile, job: ParsedJob, questions: list[str]
    ) -> dict[str, str]:
        answers: dict[str, str] = {}
        screener = profile.screener

        for q in questions:
            q_lower = q.lower()
            if any(k in q_lower for k in ["authorized", "legally", "work authorization", "right to work"]):
                answers[q] = "Yes" if screener.legally_authorized else "No"
            elif any(k in q_lower for k in ["sponsorship", "visa", "require sponsorship"]):
                answers[q] = "Yes" if screener.requires_visa_sponsorship else "No"
            elif any(k in q_lower for k in ["salary", "compensation", "pay", "rate"]):
                answers[q] = screener.target_compensation or "Competitive / Open to discussion"
            elif any(k in q_lower for k in ["notice", "start date", "availability"]):
                answers[q] = f"{screener.notice_period_weeks} weeks"
            elif any(k in q_lower for k in ["linkedin"]):
                answers[q] = profile.linkedin_url or "Available upon request"
            elif any(k in q_lower for k in ["github", "code sample", "portfolio", "website"]):
                answers[q] = profile.github_url or profile.portfolio_url or "Available upon request"
            elif any(k in q_lower for k in ["why", "interest", "tell us"]):
                answers[q] = f"I am excited about {job.company}'s mission and the opportunity to contribute my expertise in {', '.join(profile.skills[:3])} to the {job.title} role."
            else:
                answers[q] = "N/A"

        return answers

    def generate_cold_outreach(
        self, profile: CandidateProfile, job: ParsedJob, contact: ContactEmail | None = None
    ) -> OutreachEmailDraft:
        recipient = contact.email if contact and contact.email else ""

        name = profile.full_name or "Applicant"
        skills = profile.skills or ["software engineering"]
        top_skills = [s for s in skills if s.lower() in job.description.lower()]
        if not top_skills:
            top_skills = skills[:3]

        skill_points = "\n".join([f"- Deep experience building with {s}" for s in top_skills])

        portfolio_line = ""
        if profile.github_url:
            portfolio_line += f"\nYou can review my recent work on GitHub: {profile.github_url}"
        if profile.linkedin_url:
            portfolio_line += f"\nLinkedIn: {profile.linkedin_url}"

        subject = f"Application & Intro: {name} - {job.title} at {job.company}"
        body = f"""Hi there,

I recently applied for the {job.title} role at {job.company} and wanted to reach out directly. Given {job.company}'s focus, I believe my background would be a strong match.

A few relevant highlights:
{skill_points}
{portfolio_line}

I would love to learn more about the team's upcoming challenges. Would you be open to a brief 10-minute chat this week?

Best regards,
{name}
{profile.email}
{profile.phone}""".strip()

        return OutreachEmailDraft(
            recipient=recipient,
            subject=subject,
            body=body,
            company=job.company,
            title=job.title,
            status="draft",
        )
