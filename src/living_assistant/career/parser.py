from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import urlparse

from living_assistant.security.security_policy import sanitize_external_observation


class ATSPlatform(str, Enum):
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    ASHBY = "ashby"
    LINKEDIN = "linkedin"
    INDEED = "indeed"
    WORKDAY = "workday"
    GENERIC = "generic"


@dataclass
class ContactEmail:
    email: str
    name: str = ""
    source: str = ""
    is_hiring_specific: bool = False
    confidence: float = 0.5


@dataclass
class ParsedJob:
    title: str
    company: str
    url: str
    platform: ATSPlatform
    description: str
    location: str = ""
    remote: bool = False
    contacts: list[ContactEmail] = field(default_factory=list)
    requirements: list[str] = field(default_factory=list)
    sanitized: bool = True


HIRING_KEYWORDS = {
    "recruiting", "recruit", "talent", "careers", "career", "jobs", "job", "hiring",
    "people", "hr", "apply", "join", "interviews", "staffing"
}

IGNORED_EMAIL_DOMAINS = {
    "example.com", "domain.com", "email.com", "sentry.io", "w3.org", "schema.org"
}


class JobParser:
    """Parses job posting pages, identifies ATS platforms, and extracts hiring contacts."""

    def detect_ats(self, url: str, html: str = "") -> ATSPlatform:
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        path = parsed.path.lower()

        if "greenhouse.io" in netloc or "grnh.se" in netloc or "greenhouse" in html.lower():
            return ATSPlatform.GREENHOUSE
        if "lever.co" in netloc or "jobs.lever" in netloc or "lever" in html.lower():
            return ATSPlatform.LEVER
        if "ashbyhq.com" in netloc or "ashby" in html.lower():
            return ATSPlatform.ASHBY
        if "linkedin.com" in netloc:
            return ATSPlatform.LINKEDIN
        if "indeed.com" in netloc:
            return ATSPlatform.INDEED
        if "myworkdayjobs.com" in netloc or "workday" in netloc:
            return ATSPlatform.WORKDAY

        return ATSPlatform.GENERIC

    def extract_contacts(self, html: str, base_url: str = "") -> list[ContactEmail]:
        if not html:
            return []

        found_emails: dict[str, ContactEmail] = {}

        # 1. Check mailto links
        mailto_matches = re.findall(r'href=[\'"]mailto:([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', html, re.I)
        for email in mailto_matches:
            email_lower = email.lower()
            if self._is_valid_email(email_lower):
                is_hiring = any(k in email_lower for k in HIRING_KEYWORDS)
                found_emails[email_lower] = ContactEmail(
                    email=email_lower,
                    source=base_url or "mailto",
                    is_hiring_specific=is_hiring,
                    confidence=0.9 if is_hiring else 0.7,
                )

        # 2. General text regex search
        text_matches = re.findall(r'\b[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+\b', html)
        for email in text_matches:
            email_lower = email.lower()
            if self._is_valid_email(email_lower) and email_lower not in found_emails:
                is_hiring = any(k in email_lower for k in HIRING_KEYWORDS)
                found_emails[email_lower] = ContactEmail(
                    email=email_lower,
                    source=base_url or "page_text",
                    is_hiring_specific=is_hiring,
                    confidence=0.85 if is_hiring else 0.5,
                )

        # Sort by confidence descending
        return sorted(found_emails.values(), key=lambda c: (c.is_hiring_specific, c.confidence), reverse=True)

    def _is_valid_email(self, email: str) -> bool:
        if "@" not in email:
            return False
        user, domain = email.split("@", 1)
        if domain in IGNORED_EMAIL_DOMAINS:
            return False
        if any(domain.endswith(ext) for ext in [".png", ".jpg", ".svg", ".css", ".js"]):
            return False
        return len(user) > 0 and "." in domain

    def parse_posting(self, url: str, html: str) -> ParsedJob:
        ats = self.detect_ats(url, html)
        contacts = self.extract_contacts(html, base_url=url)

        # Extract title
        title = ""
        h1_match = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.I | re.S)
        if h1_match:
            title = re.sub(r'<[^>]+>', '', h1_match.group(1)).strip()

        if not title:
            title_tag = re.search(r'<title[^>]*>(.*?)</title>', html, re.I | re.S)
            if title_tag:
                raw_title = re.sub(r'<[^>]+>', '', title_tag.group(1)).strip()
                # e.g. "Senior Staff Engineer at CloudScale"
                title = raw_title.split(" - ")[0].split(" | ")[0].split(" at ")[0].strip()

        # Extract company
        company = ""
        company_tag = re.search(r'class=[\'"][^\'"]*company[^\'"]*[\'"][^>]*>(.*?)<', html, re.I)
        if company_tag:
            company = re.sub(r'<[^>]+>', '', company_tag.group(1)).strip()

        if not company:
            title_tag = re.search(r'<title[^>]*>(.*?)</title>', html, re.I | re.S)
            if title_tag and " at " in title_tag.group(1):
                part = title_tag.group(1).split(" at ")[1]
                company = part.split(" - ")[0].split(" | ")[0].strip()

        if not company:
            parsed_url = urlparse(url)
            path_parts = [p for p in parsed_url.path.split("/") if p]
            if ats == ATSPlatform.GREENHOUSE and path_parts:
                company = path_parts[0].capitalize()
            elif ats == ATSPlatform.LEVER and path_parts:
                company = path_parts[0].capitalize()
            elif ats == ATSPlatform.ASHBY and path_parts:
                company = path_parts[0].capitalize()
            else:
                domain_parts = parsed_url.netloc.split(".")
                company = domain_parts[0].capitalize() if domain_parts else "Company"

        # Extract clean plain-text description
        body_match = re.search(r'<body[^>]*>(.*?)</body>', html, re.I | re.S)
        raw_body = body_match.group(1) if body_match else html
        clean_text = re.sub(r'<script[^>]*>.*?</script>', '', raw_body, flags=re.I | re.S)
        clean_text = re.sub(r'<style[^>]*>.*?</style>', '', clean_text, flags=re.I | re.S)
        clean_text = re.sub(r'<[^>]+>', ' ', clean_text)
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()

        sanitized_description = sanitize_external_observation(clean_text)

        return ParsedJob(
            title=title or "Job Opening",
            company=company or "Company",
            url=url,
            platform=ats,
            description=sanitized_description,
            contacts=contacts,
            sanitized=True,
        )
