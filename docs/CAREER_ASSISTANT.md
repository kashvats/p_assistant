# Career Assistant & Automated Job Application Subsystem

Living Assistant includes an automated career co-pilot capable of parsing candidate resumes, ingesting target job listings, harvesting recruiter contact emails, tailoring application materials, pre-filling ATS forms across all major platforms, and drafting personalized cold outreach emails.

---

## Key Capabilities

1. **Master Resume & Profile Management:**
   - Ingests and parses resumes in **PDF**, **DOCX**, and **Markdown/Plain Text** formats.
   - Stores structured candidate metadata: contact info, LinkedIn/GitHub/Portfolio URLs, education, work experience, skills, and standard screener questionnaire answers (work authorization, visa sponsorship, target compensation, notice period).
   - Stored locally under `~/.living_assistant/career/` (`data_dir() / "career"`), never exposed to third parties without user consent.

2. **Job Opening Analysis & ATS Identification:**
   - Detects ATS provider signatures: Greenhouse, Lever, Ashby, LinkedIn Easy Apply, Indeed, Workday, and generic web forms.
   - Parses core role responsibilities, required skills, and qualification thresholds.
   - Wraps all external web page content in `sanitize_external_observation()` to defend against prompt injection embedded in job listings.

3. **Recruiter & Hiring Contact Harvesting:**
   - Scans job posting DOM, `mailto:` links, and page text for talent acquisition contacts (`recruiting@`, `talent@`, `careers@`, `jobs@`, or named recruiter addresses).
   - Ranks discovered emails with confidence scores and flags hiring-specific contacts.

4. **Application Tailoring & Cold Outreach:**
   - Generates customized cover letters aligning candidate's real experience with the role.
   - Synthesizes answers to screener questionnaire prompts (e.g. sponsorship, notice period, why this role) without fabricating credentials.
   - Drafts targeted **Cold Outreach Emails** addressed to the recruiter or hiring manager with key pitch bullets and a low-friction call-to-action.

5. **Assisted Form Filling & Pre-Submit Approval Gate:**
   - Maps candidate profile fields directly into form inputs on standard ATS portals.
   - Attaches candidate's master resume PDF/DOCX automatically.
   - **Hard Approval Stop:** Pauses execution before the final "Submit Application" button. Displays a preview of prepared values and requests interactive approval via `ApprovalManager`.

6. **Application Pipeline Tracking:**
   - SQLite-backed store (`career_applications.db`) tracking every prospect, recruiter contact, submitted data, and status (`saved`, `analyzed`, `ready_for_review`, `applied`, `interviewing`, `rejected`, `offer`).

---

## Quick Start & CLI Usage

### 1. Configure Candidate Profile & Resume
```bash
# Upload and parse a master resume
organism career profile --resume path/to/master_resume.pdf

# Set candidate contact details
organism career profile --name "Alex Rivera" --email "alex@example.com" --phone "+1-555-0142" --github "https://github.com/alexdev"
```

### 2. Analyze a Job Opening & Harvest Recruiter Emails
```bash
organism career analyze "https://jobs.lever.co/company/job-id"
```

Output:
```
Analyzed successfully! Application ID: 5290b021-98a7-47be-b1e1-e0a514d79bfe
Company: Acme AI | Role: Senior Backend Engineer | ATS: lever

Harvested Recruiter / Hiring Emails:
 - talent@acme.ai (Confidence: 90%) (Hiring Specific)
 - jobs@acme.ai (Confidence: 85%) (Hiring Specific)
```

### 3. Pre-fill Application Form
```bash
organism career apply "https://jobs.lever.co/company/job-id"
```
The assistant pre-fills all candidate fields, attaches the resume, and stops with a confirmation prompt:
```
Application Prepared & Staged for Approval!
Company: Acme AI | Title: Senior Backend Engineer
Status: ready_for_review
Pre-filled fields:
  • first_name: Alex
  • email: alex@example.com
  • resume_path: .../resumes/master_resume.pdf
Approve final submission to employer? [y/N]:
```

### 4. Generate Cold Outreach Email
```bash
organism career outreach <application_id>
```

### 5. View Applications Pipeline
```bash
organism career list
```

---

## Web Dashboard Interface

Navigate to the **Career & Jobs** tab on the local web dashboard:
`http://127.0.0.1:8787/dashboard#career`

The dashboard provides:
- Live candidate profile and master resume preview.
- 1-click "Analyze & Harvest Emails" and "Pre-fill Application" URL actions.
- Real-time applications pipeline table with statuses, recruiter contacts, and cold email draft generator.
