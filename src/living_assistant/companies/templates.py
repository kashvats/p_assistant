"""Company templates: departments, employees and skill portfolios as data.

A template is only a starting point - a created company is an independent copy the user can change
(hire, remove, retitle, give skills). Skill names refer to SKILL.md skills in the skill library.
Employee tuple: (key, name, title, level, responsibilities, [(skill, tier), ...], mbti).
In each department the first "lead" is its head; specialists report to the head and heads report
to the department's ``reports`` director.
"""
from __future__ import annotations

from living_assistant.companies.store import CompanyStore

C, S, P = "core", "specialist", "supporting"

SOFTWARE = {
    "name": "Software Development Company",
    "description": "Plans, designs, builds, tests, secures, verifies and documents software projects end to end.",
    "mission": "Deliver working, verified software that does what the user asked - nothing claimed that was not run.",
    "skills": ["project-planning", "independent-verification", "technical-writing"],
    "departments": [
        {"key": "executive", "name": "Executive Office", "reports": None,
         "mission": "Owns company priorities, project intake, planning and final delivery decisions.",
         "skills": ["project-planning"],
         "employees": [
             ("company-director", "Avery", "Company Director", "director",
              "Sets priorities, approves plans and accepts deliveries for the company.",
              [("project-planning", C), ("requirements-analysis", S), ("security-review", P)], "ENTJ"),
             ("project-director", "Morgan", "Project Director", "director",
              "Turns requests into specifications and dependency-ordered plans; assigns work to departments; "
              "tracks progress and unblocks.",
              [("project-planning", C), ("requirements-analysis", C), ("system-architecture", S)], "ESTJ"),
             ("engineering-director", "Sam", "Engineering Director", "director",
              "Owns technical quality across engineering departments and resolves technical conflicts.",
              [("system-architecture", C), ("code-review", C), ("project-planning", S)], "INTJ"),
         ]},
        {"key": "product", "name": "Product", "reports": "project-director",
         "mission": "Defines what is built: requirements, user stories and acceptance criteria.",
         "skills": ["requirements-analysis"],
         "employees": [
             ("product-lead", "Riley", "Product Lead", "lead", "Owns scope and acceptance criteria.",
              [("requirements-analysis", C), ("project-planning", S), ("technical-writing", P)], "ENFJ"),
             ("business-analyst", "Jordan", "Business Analyst", "specialist",
              "Writes user stories, edge cases and testable acceptance criteria.",
              [("requirements-analysis", C), ("research-synthesis", P)], "ISTJ"),
         ]},
        {"key": "design", "name": "UI/UX Design", "reports": "project-director",
         "mission": "Designs user flows, screens and interface states.",
         "skills": ["ux-design"],
         "employees": [
             ("design-lead", "Quinn", "UI/UX Design Lead", "lead", "Owns user flows and the design system.",
              [("ux-design", C), ("requirements-analysis", P)], "INFP"),
             ("ui-designer", "Harper", "UI Designer", "specialist", "Produces screen layouts and HTML/CSS mockups.",
              [("ux-design", C), ("frontend-development", S)], "ISFP"),
         ]},
        {"key": "architecture", "name": "Architecture", "reports": "engineering-director",
         "mission": "Chooses the structure, technologies and contracts of each system.",
         "skills": ["system-architecture", "api-design"],
         "employees": [
             ("solution-architect", "Casey", "Solution Architect", "lead",
              "Designs components, data flow and folder layout; records decisions.",
              [("system-architecture", C), ("api-design", C), ("database-design", S)], "INTJ"),
         ]},
        {"key": "frontend", "name": "Frontend Engineering", "reports": "engineering-director",
         "mission": "Builds the user interfaces.",
         "skills": ["frontend-development"],
         "employees": [
             ("frontend-lead", "Rowan", "Frontend Lead", "lead", "Owns frontend structure and quality.",
              [("frontend-development", C), ("web-app-python", C), ("ux-design", S), ("code-review", S)], "ENTP"),
             ("frontend-engineer", "Skyler", "Frontend Engineer", "specialist", "Implements screens and components.",
              [("frontend-development", C), ("web-app-python", C), ("debugging", S)], "ISTP"),
         ]},
        {"key": "backend", "name": "Backend Engineering", "reports": "engineering-director",
         "mission": "Builds server code, business logic, CLIs and APIs.",
         "skills": ["backend-development", "api-design"],
         "employees": [
             ("backend-lead", "Taylor", "Backend Lead", "lead", "Owns backend design and code quality.",
              [("backend-development", C), ("web-app-python", C), ("api-design", S), ("code-review", S)], "INTJ"),
             ("backend-engineer", "Drew", "Backend Engineer", "specialist", "Implements services, logic and data access.",
              [("backend-development", C), ("web-app-python", C), ("debugging", S), ("database-design", P)], "ISTJ"),
         ]},
        {"key": "data", "name": "Data Engineering", "reports": "engineering-director",
         "mission": "Designs data models, storage and queries.",
         "skills": ["database-design"],
         "employees": [
             ("data-engineer", "Emerson", "Data Engineer", "lead", "Owns schemas, migrations and queries.",
              [("database-design", C), ("backend-development", S)], "INTP"),
         ]},
        {"key": "ai", "name": "AI Engineering", "reports": "engineering-director",
         "mission": "Adds model-powered features with evaluation and fallbacks.",
         "skills": ["ai-integration"],
         "employees": [
             ("ai-engineer", "Parker", "AI Engineer", "lead", "Builds prompts, model calls and evaluations.",
              [("ai-integration", C), ("backend-development", S), ("test-engineering", P)], "INTP"),
         ]},
        {"key": "integrations", "name": "Integrations & Automation", "reports": "engineering-director",
         "mission": "Connects systems and automates workflows.",
         "skills": ["automation-integration"],
         "employees": [
             ("integration-engineer", "Reese", "Integration Engineer", "lead", "Builds scripts, webhooks and API integrations.",
              [("automation-integration", C), ("backend-development", S)], "ESTP"),
         ]},
        {"key": "infra", "name": "Infrastructure & DevEx", "reports": "engineering-director",
         "mission": "Makes software installable, runnable and testable.",
         "skills": ["devops-setup"],
         "employees": [
             ("devops-engineer", "Blake", "DevOps Engineer", "lead", "Owns dependencies, run scripts and CI steps.",
              [("devops-setup", C), ("web-app-python", C), ("debugging", S), ("security-review", P)], "ISTJ"),
         ]},
        {"key": "security", "name": "Security", "reports": "engineering-director",
         "mission": "Finds and fixes security weaknesses before delivery.",
         "skills": ["security-review"],
         "employees": [
             ("security-engineer", "Kai", "Security Engineer", "lead", "Reviews code for vulnerabilities and gives fixes.",
              [("security-review", C), ("code-review", S)], "INTJ"),
         ]},
        {"key": "qa", "name": "Quality Assurance", "reports": "project-director",
         "mission": "Proves acceptance criteria with automated tests that were actually run.",
         "skills": ["test-engineering"],
         "employees": [
             ("qa-lead", "Jamie", "QA Lead", "lead", "Owns test strategy and test quality.",
              [("test-engineering", C), ("independent-verification", S), ("debugging", S)], "ISTJ"),
             ("qa-engineer", "Alex", "QA Engineer", "specialist", "Writes and runs tests; reports failures precisely.",
              [("test-engineering", C), ("web-app-python", S), ("debugging", P)], "ISFJ"),
         ]},
        {"key": "verification", "name": "Review & Verification", "reports": "project-director",
         "mission": "Independently verifies every deliverable against its acceptance criteria with real evidence.",
         "skills": ["independent-verification", "code-review"],
         "employees": [
             ("verification-lead", "Sage", "Verification Lead", "lead",
              "Independently checks deliverables; passes only what was proven.",
              [("independent-verification", C), ("code-review", C), ("test-engineering", S)], "INTJ"),
             ("code-reviewer", "Finley", "Code Reviewer", "specialist", "Reviews changes and verifies them independently.",
              [("code-review", C), ("independent-verification", C), ("security-review", P)], "ISTJ"),
         ]},
        {"key": "docs", "name": "Documentation & Delivery", "reports": "project-director",
         "mission": "Documents what was built and prepares the delivery.",
         "skills": ["technical-writing"],
         "employees": [
             ("technical-writer", "Ellis", "Technical Writer", "lead", "Writes READMEs, guides and delivery notes.",
              [("technical-writing", C), ("editing", S)], "INFJ"),
         ]},
    ],
}

RESEARCH = {
    "name": "Research & Content Studio",
    "description": "Researches questions with sources and turns findings into reports, articles and posts.",
    "mission": "Sourced, accurate research and clear writing - no claim without a source.",
    "skills": ["research-synthesis", "web-fact-check", "editing"],
    "departments": [
        {"key": "executive", "name": "Executive Office", "reports": None, "mission": "Plans projects and accepts deliveries.",
         "skills": ["project-planning"],
         "employees": [
             ("project-director", "Morgan", "Editor-in-Chief", "director", "Plans research and content projects.",
              [("project-planning", C), ("editing", S)], "ENTJ"),
         ]},
        {"key": "research", "name": "Research", "reports": "project-director",
         "mission": "Finds and synthesizes sourced information.", "skills": ["research-synthesis"],
         "employees": [
             ("research-lead", "Indigo", "Research Lead", "lead", "Owns research questions and source quality.",
              [("research-synthesis", C), ("web-fact-check", C)], "INTP"),
             ("analyst", "Robin", "Research Analyst", "specialist", "Searches, reads and summarizes sources.",
              [("research-synthesis", C), ("web-fact-check", S)], "ISTJ"),
         ]},
        {"key": "content", "name": "Content", "reports": "project-director",
         "mission": "Writes articles, posts and scripts.", "skills": ["content-writing"],
         "employees": [
             ("content-lead", "Charlie", "Content Lead", "lead", "Owns voice, structure and drafts.",
              [("content-writing", C), ("editing", S)], "ENFP"),
             ("writer", "Wren", "Writer", "specialist", "Drafts content from research briefs.",
              [("content-writing", C), ("email-writer", P)], "INFP"),
         ]},
        {"key": "verification", "name": "Editing & Fact-check", "reports": "project-director",
         "mission": "Independently checks facts and edits before delivery.",
         "skills": ["independent-verification", "web-fact-check"],
         "employees": [
             ("fact-checker", "Logan", "Fact-checker", "lead", "Verifies every claim against sources.",
              [("independent-verification", C), ("web-fact-check", C), ("editing", S)], "ISTJ"),
         ]},
    ],
}

OFFICE = {
    "name": "Office Operations",
    "description": "Handles everyday office work: emails, meeting notes, reports and file organisation.",
    "mission": "Get routine office work done quickly and correctly.",
    "skills": ["email-writer", "meeting-notes"],
    "departments": [
        {"key": "executive", "name": "Office Management", "reports": None, "mission": "Plans and checks the work.",
         "skills": ["project-planning"],
         "employees": [
             ("project-director", "Pat", "Office Manager", "director", "Splits requests into tasks and accepts results.",
              [("project-planning", C), ("weekly-report", S)], "ESTJ"),
         ]},
        {"key": "admin", "name": "Administration", "reports": "project-director",
         "mission": "Writes and organises.", "skills": ["email-writer", "meeting-notes", "file-organizer"],
         "employees": [
             ("assistant", "Lee", "Executive Assistant", "lead", "Writes emails, notes and reports.",
              [("email-writer", C), ("meeting-notes", C), ("weekly-report", S)], "ISFJ"),
             ("records-clerk", "Dana", "Records Clerk", "specialist", "Organises files and folders.",
              [("file-organizer", C)], "ISTJ"),
         ]},
        {"key": "verification", "name": "Quality Check", "reports": "project-director",
         "mission": "Checks the work independently.", "skills": ["independent-verification"],
         "employees": [
             ("reviewer", "Kim", "Reviewer", "lead", "Checks each result against what was asked.",
              [("independent-verification", C), ("editing", S)], "INTJ"),
         ]},
    ],
}

TEMPLATES = {"software": SOFTWARE, "research": RESEARCH, "office": OFFICE}


def template_summaries() -> list[dict]:
    return [{"id": tid, "name": t["name"], "description": t["description"],
             "departments": [d["name"] for d in t["departments"]],
             "employees": sum(len(d["employees"]) for d in t["departments"])} for tid, t in TEMPLATES.items()]


def build_company(store: CompanyStore, spec: dict, *, name: str = "", template: str = "",
                  known_skills: set[str] | None = None) -> dict:
    """Create a company from a template-shaped dict. Skills not in ``known_skills`` are kept on the
    employee with tier 'learning' so the gap is visible (they are not loadable until installed)."""
    company = store.create_company(name or spec["name"], template=template, description=spec.get("description", ""),
                                   mission=spec.get("mission", ""), skills=list(spec.get("skills") or []))
    by_key: dict[str, str] = {}
    heads: list[tuple[str, str | None]] = []
    for position, dep_spec in enumerate(spec.get("departments") or []):
        dep = store.add_department(company["id"], dep_spec["name"], key=dep_spec.get("key", ""),
                                   mission=dep_spec.get("mission", ""), skills=list(dep_spec.get("skills") or []),
                                   position=position)
        head = None
        for emp in dep_spec.get("employees") or []:
            key, ename, title, level, resp, skills, mbti = (list(emp) + [""] * 7)[:7]
            portfolio = []
            for skill_name, tier in skills or []:
                if known_skills is not None and skill_name not in known_skills:
                    tier = "learning"
                portfolio.append({"name": skill_name, "tier": tier})
            row = store.add_employee(company["id"], name=ename, title=title, level=level or "specialist",
                                     department_id=dep["id"], key=key, responsibilities=resp, mbti=mbti,
                                     skills=portfolio, reports_to=head if level == "specialist" else None)
            by_key[row["key"]] = row["id"]
            if head is None and level in ("lead", "director"):
                head = row["id"]
                store.update_department(dep["id"], head=head)
        heads.append((head, dep_spec.get("reports")))
    for head, reports in heads:  # department heads report to their director
        if head and reports and by_key.get(reports) and by_key[reports] != head:
            store.update_employee(head, reports_to=by_key[reports])
    store.event("company_staffed", company_id=company["id"], employees=len(by_key))
    return store.company_full(company["id"])
