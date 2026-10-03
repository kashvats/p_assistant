# Job Application & Career Outreach Subsystem Design

**Date:** 2026-10-03  
**Status:** Approved  
**Author:** AI Assistant & Human Partner  

## 1. Executive Summary

The Job Application & Career Outreach Subsystem extends Living Assistant (`organism`) with candidate profile management, intelligent resume ingestion, job opening analysis, automated ATS form pre-filling with human approval gates, application tracking, and recruiter email harvesting with automated cold email drafting.

This subsystem enables the assistant to take a candidate's master resume and structured profile, analyze job postings across all major platforms (Greenhouse, Lever, Ashby, LinkedIn Easy Apply, Indeed, and direct career pages), pre-fill application forms in an isolated browser, pause before submission for user confirmation with screenshot evidence, record application telemetry, and harvest recruiter/company emails to generate high-converting cold outreach email drafts.

---

## 2. Goals & Non-Goals

### Goals
- **Master Resume & Profile Management:** Ingest and parse candidate resumes in PDF, DOCX, and Markdown formats. Maintain a persistent candidate profile (`career_profile.json`) for contact info, education, work experience, portfolio links, and standard screener questionnaire answers (work authorization, visa sponsorship, target compensation, notice period).
- **Job Ingestion & Parsing:** Extract role title, company name, location, remote status, core requirements, and ATS provider from target URLs or pasted job descriptions.
- **Recruiter Contact Harvesting:** Extract public recruiter, talent acquisition, and company contact emails (`jobs@`, `recruiting@`, or named recruiter addresses) from the job posting and company domain for cold outreach.
- **Tailoring Engine:** Generate tailored cover letters, targeted screening question responses, and personalized cold outreach emails without fabricating qualifications or hallucinating skills.
- **Dual-Engine Form Filling:** Pre-fill application forms using deterministic DOM field mapping for standard ATS platforms (Greenhouse, Lever, Ashby, BambooHR) and browser automation fallback for multi-step wizards (LinkedIn Easy Apply, Indeed).
- **Strict Approval Gate:** Pause immediately before the final application submission. Provide a visual screenshot and field summary to the user; execute submission only upon explicit user consent via `ApprovalManager`.
- **Application Tracking:** Maintain an SQLite database (`career_applications.db`) recording all prospect opportunities, company contacts, tailored materials, submission dates, and application statuses.
- **Multi-Interface Access:** Expose functionality through Agent tools, REST API endpoints, CLI commands (`organism career`), and WebUI dashboard views.

### Non-Goals
- **Blind Unsupervised Mass-Applying:** The assistant will not spam submissions without user oversight. Every final submission requires explicit user confirmation.
- **Credential Scraping or Captcha Bypassing:** The system will not attempt illicit CAPTCHA circumvention; if a CAPTCHA or multi-factor authentication prompt appears, it requests user takeover in the browser session.
- **Falsification of Experience:** The LLM prompts strictly prohibit inventing skills or inflating qualifications to match job descriptions.

---

## 3. Architecture & System Components

The subsystem resides in `src/living_assistant/career/` and connects to existing core services (BrowserController, ApprovalManager, SecurityGuardian, SQLite):

```
+-----------------------------------------------------------------------------------+
|                               Living Assistant Core                               |
|                                                                                   |
|  +--------------------+   +---------------------+   +--------------------------+  |
|  | WebUI / Dashboard  |   |    CLI Interface    |   | Autonomous Orchestrator  |  |
|  +---------+----------+   +----------+----------+   +------------+-------------+  |
|            |                         |                           |                |
|            v                         v                           v                |
|  +--------------------+   +----------------------------------------------------+  |
|  |   API Endpoints    |   |                    Career Tools                    |  |
|  | (/career/*)        |   | (career_profile_*, career_job_*, career_apply,...) |  |
|  +---------+----------+   +----------------------+-----------------------------+  |
|            |                                     |                                |
|            +------------------+------------------+                                |
|                               |                                                   |
|                               v                                                   |
|  +-----------------------------------------------------------------------------+  |
|  |                        Career Subsystem (career/)                           |  |
|  |                                                                             |  |
|  |  +-----------------------+                    +--------------------------+  |  |
|  |  |  CareerProfileStore   |<-------------------|   ResumeParserEngine     |  |  |
|  |  |  (profile.json + PII) |                    |   (PDF, DOCX, Markdown)  |  |  |
|  |  +-----------+-----------+                    +--------------------------+  |  |
|  |              |                                                              |  |
|  |              v                                                              |  |
|  |  +-----------------------+                    +--------------------------+  |  |
|  |  |  JobParser & Contact  |                    |   Tailoring & Outreach   |  |  |
|  |  |  Extractor            |------------------->|   Engine                 |  |  |
|  |  |  (ATS + Emails)       |                    |   (Cover Letter + Email) |  |  |
|  |  +-----------+-----------+                    +------------+-------------+  |  |
|  |              |                                             |                |  |
|  |              v                                             v                |  |
|  |  +-----------------------------------------------------------------------+  |  |
|  |  |                     Dual-Engine Form Filler                           |  |  |
|  |  |   - Deterministic ATS Mapper (Greenhouse, Lever, Ashby, BambooHR)     |  |  |
|  |  |   - Interactive Browser-Use Agent Fallback (LinkedIn, Indeed, Custom) |  |  |
|  |  +-----------------------------------+-----------------------------------+  |  |
|  |                                      |                                      |  |
|  |                                      v                                      |  |
|  |  +-----------------------------------------------------------------------+  |  |
|  |  |                ApplicationTracker (SQLite Database)                   |  |  |
|  |  +-----------------------------------------------------------------------+  |  |
|  +--------------------------------------|--------------------------------------+  |
|                                         |                                         |
|                                         v                                         |
|  +--------------------+   +---------------------+   +--------------------------+  |
|  | BrowserController  |   |   ApprovalManager   |   |    Security Guardian     |  |
|  | (Playwright Engine)|   |   (Human-in-Loop)   |   |   (PII & SSRF Defense)   |  |
|  +--------------------+   +---------------------+   +--------------------------+  |
+-----------------------------------------------------------------------------------+
```

### Component Details

#### 3.1 CareerProfileStore (`src/living_assistant/career/profile.py`)
- **Location:** Stores candidate files in `~/.living_assistant/career/` (`data_dir() / "career"`):
  - `resumes/`: Uploaded master resume files (e.g. `master_resume.pdf`).
  - `career_profile.json`: Structured candidate data:
    - **Contact:** Full name, email, phone, location, LinkedIn URL, GitHub URL, portfolio URL.
    - **Work History:** Company, title, start/end dates, accomplishments/highlights.
    - **Education:** Institution, degree, graduation year, field of study.
    - **Skills:** Primary skills, technologies, frameworks, certifications.
    - **Screener Defaults:** Legally authorized to work in country (boolean), requires visa sponsorship (boolean), target compensation/salary, notice period (weeks), citizenship/work permit type, EEOC standard preferences (race, gender, veteran status, disability status - with "Decline to self-identify" support).
- **ResumeParserEngine:** Extracts raw and formatted text from uploaded PDF (using PyMuPDF/pdfplumber fallback), DOCX (python-docx), and plain Markdown files.

#### 3.2 JobParser & ContactExtractor (`src/living_assistant/career/parser.py`)
- **Job Ingestion:** Fetches job posting URLs using existing `BrowserController` or safe HTTP client with user-agent emulation.
- **Content Sanitization:** Pipes all external HTML through `sanitize_external_observation()` to neutralize prompt injection payloads before passing to LLM.
- **ATS Identification:** Detects provider signatures:
  - `boards.greenhouse.io` or embedded Greenhouse iframe -> `ATSPlatform.GREENHOUSE`
  - `jobs.lever.co` -> `ATSPlatform.LEVER`
  - `jobs.ashbyhq.com` -> `ATSPlatform.ASHBY`
  - `linkedin.com/jobs` -> `ATSPlatform.LINKEDIN`
  - `indeed.com` -> `ATSPlatform.INDEED`
  - Other -> `ATSPlatform.GENERIC`
- **Metadata Extraction:** Extracts job title, company name, location, remote/hybrid status, description, qualifications, and deadline.
- **Contact & Recruiter Email Extraction:**
  - Performs regex search on page text, DOM `mailto:` links, and metadata for recruiter/talent emails (e.g. `recruiting@`, `talent@`, `careers@`, `jobs@`, or personal `firstname.lastname@company.com`).
  - Probes root domain's `/about`, `/contact`, `/team`, or `/careers` sub-pages if direct email is not on the job posting.
  - Returns a list of candidate contact emails with confidence ratings and source URLs.

#### 3.3 Tailoring & Cold Outreach Engine (`src/living_assistant/career/tailor.py`)
- **Cover Letter Tailoring:** Crafts a customized 3-4 paragraph cover letter aligning candidate's real experience with the job's core challenges.
- **Screening Question Response:** Answers specific form prompts (e.g., "Why do you want to join our engineering team?", "Describe a distributed systems challenge you solved") drawing directly from candidate's project history.
- **Cold Outreach Email Generation:** Drafts a concise, professional cold email:
  - **Subject:** E.g., `Application & Intro: [Candidate Name] - [Job Title]`
  - **Recipient:** Target recruiter or team lead email discovered by `ContactExtractor`.
  - **Body:** Hook expressing interest in company's mission, 2-3 bullet points demonstrating direct alignment with the job's hard requirements, link to portfolio/GitHub, and a low-friction call-to-action (e.g., "Would you be open to a 10-minute chat this week?").

#### 3.4 Dual-Engine Form Filler (`src/living_assistant/career/filler.py`)
- **Engine A: Deterministic ATS Field Mapper (Greenhouse, Lever, Ashby)**
  - Direct selector mapping for high-frequency input fields:
    - Name: `input[name*='name']`, `input#first_name`, `input#last_name`
    - Email: `input[type='email']`, `input[name*='email']`
    - Phone: `input[type='tel']`, `input[name*='phone']`
    - Resume file upload: `input[type='file'][name*='resume']`
    - LinkedIn / GitHub / Website URLs: `input[name*='linkedin']`, `input[name*='github']`, `input[name*='website']`
    - Custom questions: Matches label text against candidate profile and generated questionnaire responses.
    - File attachment: Attaches the candidate's master resume PDF directly via Playwright's `setInputFiles()`.
- **Engine B: Autonomous Browser Agent Fallback (LinkedIn Easy Apply, Indeed, Generic)**
  - Operates through Playwright session steps.
  - Navigates multi-step dialogs ("Next", "Review", "Continue").
  - Identifies unhandled fields and uses candidate profile context to complete them.
- **Pre-Submission Stop & Approval Hook:**
  - Upon reaching the final step (where the next action is "Submit Application" / "Send Application"), execution halts.
  - Takes a high-resolution screenshot of the filled application page.
  - Collects all entered field key-values.
  - Issues an approval request through `ApprovalManager`:
    - `ApprovalContext`: Action = `career_submit_application`, Target = `{company, title, url}`.
    - Awaits user decision (`approve` or `deny`).
  - Only after approval is granted does the filler execute the final submit action.

#### 3.5 ApplicationTracker (`src/living_assistant/career/tracker.py`)
- **Database:** SQLite database `career_applications.db` in `data_dir() / "career"`.
- **Schema:**
  - `id`: UUID primary key.
  - `company`: Company name.
  - `title`: Role title.
  - `url`: Application posting URL.
  - `platform`: Greenhouse, Lever, Ashby, LinkedIn, Indeed, Generic.
  - `status`: `saved`, `analyzed`, `ready_for_review`, `applied`, `interviewing`, `rejected`, `offer`.
  - `recruiter_emails`: JSON array of harvested contact emails.
  - `cover_letter`: Generated tailored cover letter text.
  - `outreach_email_draft`: JSON object with subject, recipient, body, and status (`draft`, `sent`).
  - `submitted_fields`: JSON dump of values filled in the form.
  - `screenshot_path`: Path to stored pre-submit screenshot.
  - `created_at`: Timestamp.
  - `updated_at`: Timestamp.

---

## 4. Security, Privacy & Safety Controls

1. **PII Isolation:**
   - Candidate resume, contact info, and screener answers are stored exclusively on the user's local filesystem in `~/.living_assistant/career/`.
   - File permissions are restricted to the current user.
   - PII is never sent to external servers other than the explicit employer application form approved by the user.
2. **Untrusted Web Content Defense:**
   - External job posting HTML is treated as untrusted observation data.
   - All text fed to the LLM passes through `sanitize_external_observation()` to protect against prompt injection instructions embedded in job listings.
3. **Hard Human Approval Gate:**
   - Submitting a job application is classified as a mutating external action.
   - The system is architecturally blocked from clicking any final submission button without an explicit interactive approval token generated by `ApprovalManager`.
4. **Outreach Safety:**
   - Cold emails are saved strictly in `draft` status within the tracker.
   - The assistant does not dispatch emails without user confirmation.
5. **SSRF & Network Sandboxing:**
   - All URL fetches obey `safe_browser_url()` and `url_network_scope()`, preventing attempts to browse internal cloud metadata or local subnet IPs.

---

## 5. API & CLI Specification

### 5.1 REST API (`src/living_assistant/api_routes/career.py`)

- `GET /api/v1/career/profile`: Returns candidate profile and resume status.
- `PUT /api/v1/career/profile`: Updates candidate profile fields and screener defaults.
- `POST /api/v1/career/resume/upload`: Uploads a master resume file (PDF, DOCX, Markdown).
- `POST /api/v1/career/jobs/analyze`: Ingests and analyzes a job URL; returns parsed requirements and discovered recruiter emails.
- `POST /api/v1/career/jobs/apply`: Launches the assisted application flow (fills form, captures screenshot, requests approval).
- `POST /api/v1/career/jobs/confirm-submit`: Completes submission after user approval.
- `GET /api/v1/career/applications`: Lists all tracked job applications with filtering by status.
- `GET /api/v1/career/applications/{id}`: Returns application details, screenshot, and cold email draft.
- `PATCH /api/v1/career/applications/{id}`: Updates application status (e.g., `interviewing`, `rejected`).
- `POST /api/v1/career/applications/{id}/outreach`: Generates or regenerates cold outreach email draft.

### 5.2 Agent Tools (`src/living_assistant/tools/careertools.py`)

- `career_profile_get()`: Inspect current candidate profile and resume details.
- `career_profile_update(profile_data)`: Update candidate profile fields.
- `career_job_analyze(url)`: Parse job posting, extract role requirements and recruiter emails.
- `career_apply(url, auto_tailor=True)`: Fill application form and stage for user approval.
- `career_applications_list(status=None)`: List applications and contact pipelines.
- `career_outreach_generate(application_id)`: Generate a tailored cold email for a role.

### 5.3 CLI Commands (`organism career`)

- `organism career profile [--resume <file>]`: View or configure candidate profile and resume.
- `organism career analyze <url>`: Parse job description and harvest recruiter contacts.
- `organism career apply <url>`: Launch assisted application in browser.
- `organism career list`: Display tracked applications and outreach pipeline.
- `organism career outreach <id>`: View or generate cold outreach email draft.

---

## 6. Testing & Verification Strategy

1. **Unit Testing (`tests/test_career_profile.py`):**
   - Verify profile creation, persistence, and updating in `career_profile.json`.
   - Verify parsing of PDF, DOCX, and Markdown resume files.
   - Verify standard screener answer lookup and defaults.
2. **Unit Testing (`tests/test_career_parser.py`):**
   - Verify ATS platform detection for Greenhouse, Lever, Ashby, LinkedIn, and Indeed URLs.
   - Verify regex and DOM extraction of recruiter and company contact emails from sample HTML fixtures.
   - Verify observation sanitization against prompt injection test fixtures.
3. **Unit Testing (`tests/test_career_tailor.py`):**
   - Verify tailored cover letter generation without hallucinated claims.
   - Verify cold outreach email generation structure (subject, recipient, pitch bullets, CTA).
   - Verify screening question answer synthesis from candidate experience.
4. **Integration Testing (`tests/test_career_filler.py`):**
   - Test deterministic field mapping against mock HTML forms for Greenhouse, Lever, and Ashby.
   - Verify resume file attachment handling via Playwright mock.
   - Verify that execution strictly halts before form submission and calls `ApprovalManager`.
   - Verify that rejection at the approval gate aborts submission without mutating the page.
5. **API & End-to-End Testing (`tests/test_career_api.py`):**
   - Test all `/api/v1/career/*` endpoints using FastAPI `TestClient`.
   - Verify application tracking SQLite operations (create, read, update status).
