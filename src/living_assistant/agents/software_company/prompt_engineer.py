"""
Prompt Engineer Subagent, Archetype Discovery & Multi-App Scaffolding Engine.
Living Assistant - Software Company Intake Layer.

Responsibilities:
1. Project Archetype & Domain Detection: Dynamically recognizes application archetypes
   (Notes, Blog, Expense Tracker, Chat, Contacts, E-Commerce, Custom, Todo) instead of hardcoding a single template.
2. Product Vision & Visual Specification: Generates UI/UX layout specs, user flows, and component blueprints.
3. Interactive Requirements Discovery: Asks intelligent, domain-tailored clarifying questions with anti-loop protection.
4. Technology Stack Selection: Suggests tailored framework, database, and auth configurations.
5. Production Codebase Scaffolding: Generates complete, functional, multi-file codebases (database, models, routes, HTML/CSS/JS UI, tests).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("living_assistant.agents.software_company.prompt_engineer")


@dataclass
class StackRecommendation:
    category: str  # e.g., "backend_framework", "database", "auth", "frontend"
    recommended: str
    alternatives: List[str] = field(default_factory=list)
    rationale: str = ""


@dataclass
class ClarificationAssessment:
    is_clear: bool
    round_count: int
    questions: List[str] = field(default_factory=list)
    suggestions: List[Dict[str, Any]] = field(default_factory=list)
    proposed_stack: Dict[str, str] = field(default_factory=dict)
    proposed_features: List[str] = field(default_factory=list)
    product_vision: Dict[str, Any] = field(default_factory=dict)
    summary_message: str = ""
    ready_to_build: bool = False


@dataclass
class RefinedEngineeringPrompt:
    original_prompt: str
    refined_prompt: str
    project_name: str
    chosen_stack: Dict[str, str]
    key_features: List[str]
    quality_criteria: List[str]
    target_workspace_dir: str


def detect_project_archetype(prompt: str) -> Dict[str, Any]:
    """
    Dynamically identifies the application domain archetype, core entities,
    endpoints, UI structure, and user workflows from a user's prompt.
    """
    p = prompt.lower()

    if any(k in p for k in ["note", "notes", "notepad", "journal", "memo", "diary", "markdown note"]):
        return {
            "key": "notes",
            "name": "Personal Notes & Knowledge Base",
            "slug": "notes",
            "entity": "Note",
            "db_table": "notes",
            "endpoint_prefix": "/api/notes",
            "default_features": [
                "Create, search, view, edit, and delete notes",
                "Category taxonomy and tags",
                "Pin critical notes to top of sidebar",
                "Clean markdown preview and split-screen editor UI",
                "Local SQLite persistence and automated test suite",
            ],
            "clarifying_questions": [
                "Would you like Markdown preview support alongside the note editor?",
                "Do you prefer organizing notes with folders, tags, or simple categories?",
            ],
            "ui_layout": "Split-view layout: Left sidebar for searchable note hierarchy and tag badges; Right pane for note editing and Markdown preview.",
            "user_flows": "1. User opens app -> views pinned/recent notes; 2. Clicks 'New Note' -> writes markdown content; 3. Searches/filters by tag -> edits or pins note.",
        }

    elif any(k in p for k in ["blog", "cms", "post", "posts", "article", "publication"]):
        return {
            "key": "blog",
            "name": "Content Publishing & Blog Platform",
            "slug": "blog",
            "entity": "BlogPost",
            "db_table": "posts",
            "endpoint_prefix": "/api/posts",
            "default_features": [
                "Draft, publish, edit, and archive blog articles",
                "Category classification and slug generation",
                "Reader-friendly layout and author metadata",
                "Interactive draft composer modal",
                "SQLite storage and automated tests",
            ],
            "clarifying_questions": [
                "Should articles support immediate publishing or a draft/review workflow?",
                "Do you want author bios and reading time estimates displayed on each post?",
            ],
            "ui_layout": "Reader grid and composer layout: Hero section, article card feed with published date/author, and composer modal.",
            "user_flows": "1. Reader views published articles; 2. Author clicks 'New Post' -> writes draft; 3. Author toggles Publish -> article appears in live feed.",
        }

    elif any(k in p for k in ["expense", "budget", "finance", "money", "ledger", "tracker", "accounting", "cost"]):
        return {
            "key": "expense",
            "name": "Personal Finance & Expense Tracker",
            "slug": "expenses",
            "entity": "Expense",
            "db_table": "expenses",
            "endpoint_prefix": "/api/expenses",
            "default_features": [
                "Record income and expense transactions with date & category",
                "Real-time financial summary metrics (Total Income, Total Expenses, Net Balance)",
                "Transaction history table with type badges",
                "Filter transactions by category and date",
                "SQLite database and test coverage",
            ],
            "clarifying_questions": [
                "Do you prefer default categories (Food, Utilities, Salary, Entertainment) or custom categories?",
                "Would you like summary KPI cards (Total Income, Total Expenses, Net Balance)?",
            ],
            "ui_layout": "Finance dashboard layout: Top 3 KPI cards (Total Income, Total Expenses, Net Balance); Form for new transactions; Transaction table with filters.",
            "user_flows": "1. User opens dashboard -> reviews monthly net balance; 2. Logs expense with amount/category -> balance updates live; 3. Filters transactions.",
        }

    elif any(k in p for k in ["chat", "message", "messaging", "forum", "messenger"]):
        return {
            "key": "chat",
            "name": "Team Chat & Messaging Room",
            "slug": "chat",
            "entity": "ChatMessage",
            "db_table": "messages",
            "endpoint_prefix": "/api/messages",
            "default_features": [
                "Send and receive messages in multiple rooms",
                "User display names and room switcher",
                "Real-time message feed rendering",
                "Message search and deletion",
                "SQLite message history storage",
            ],
            "clarifying_questions": [
                "Would you like multiple named chat rooms or a single general discussion room?",
                "Do you want user avatars or message timestamps?",
            ],
            "ui_layout": "Messaging interface: Left sidebar for active channel list; Right pane for chat message stream and sticky input bar.",
            "user_flows": "1. User joins channel -> sees chat history; 2. Types message -> post sent and displayed; 3. Switches channels.",
        }

    elif any(k in p for k in ["contact", "contacts", "address book", "crm", "people"]):
        return {
            "key": "contacts",
            "name": "Contact Directory & CRM",
            "slug": "contacts",
            "entity": "Contact",
            "db_table": "contacts",
            "endpoint_prefix": "/api/contacts",
            "default_features": [
                "Add, search, view, edit, and delete contacts",
                "Fields for Name, Email, Phone, Company, and Category",
                "Instant search by name or organization",
                "Contact detail cards with quick email/call links",
                "SQLite storage and validation",
            ],
            "clarifying_questions": [
                "Do you need to group contacts into categories (Personal, Work, Vendor)?",
                "Should contacts support custom notes or company tags?",
            ],
            "ui_layout": "Directory layout: Search bar and filter tabs at top; Responsive card grid displaying contact details with modal editor.",
            "user_flows": "1. User views contact directory; 2. Searches by name/company; 3. Adds/edits contact in modal dialog.",
        }

    elif any(k in p for k in ["store", "ecommerce", "e-commerce", "product", "catalog", "shop"]):
        return {
            "key": "ecommerce",
            "name": "Product Catalog & Storefront",
            "slug": "ecommerce",
            "entity": "Product",
            "db_table": "products",
            "endpoint_prefix": "/api/products",
            "default_features": [
                "Product catalog with price, stock, category, and SKU",
                "Product search and category filtering",
                "Stock inventory management and updates",
                "Responsive storefront product cards",
                "SQLite database and test suite",
            ],
            "clarifying_questions": [
                "Do you need inventory stock tracking and out-of-stock badges?",
                "Should products have category filter tabs and search?",
            ],
            "ui_layout": "Storefront layout: Header with search and category navigation; Product card grid with price badges and stock counters.",
            "user_flows": "1. Shopper browses products -> filters by category; 2. Merchant adds/updates product stock; 3. Real-time product search.",
        }

    elif any(k in p for k in ["todo", "task", "checklist", "to-do", "todos"]):
        return {
            "key": "todo",
            "name": "Task & Todo Management",
            "slug": "todo",
            "entity": "Todo",
            "db_table": "todos",
            "endpoint_prefix": "/api/todos",
            "default_features": [
                "Create, list, retrieve, update, and delete todos",
                "Toggle completion status and priority levels",
                "Filter tasks (All, Active, Completed)",
                "Persistent SQLite database",
                "Automated test suite",
            ],
            "clarifying_questions": [
                "Would you prefer a simple single-user app (no login, instant use) or multi-user authentication (JWT)?",
                "Do you want any extra features (e.g. priority tags, due dates, categories)?",
            ],
            "ui_layout": "Card-based task list: Top input row with priority selector; Filter tabs (All/Active/Completed); Interactive item checklist.",
            "user_flows": "1. User types task title -> adds to list; 2. Clicks checkbox -> task marked completed; 3. Toggles filters.",
        }

    else:
        # Dynamic custom archetype tailored to keywords
        words = [w for w in re.findall(r"[a-z0-9]+", p) if w not in {"build", "me", "a", "an", "the", "app", "application", "system", "platform"}]
        slug = "-".join(words[:2]) if words else "custom"
        title = " ".join(words[:3]).title() if words else "Custom Application"
        return {
            "key": "custom",
            "name": f"{title} Management System",
            "slug": slug,
            "entity": "Item",
            "db_table": "items",
            "endpoint_prefix": "/api/items",
            "default_features": [
                f"Full CRUD operations for {title}",
                "Status workflow and categorical classification",
                "Real-time search and filter controls",
                "Responsive dashboard UI with dark mode",
                "SQLite database and automated test suite",
            ],
            "clarifying_questions": [
                f"What are the essential data fields you want to track for {title}?",
                "Do you need user role permissions or is single-user local access sufficient?",
            ],
            "ui_layout": f"Dashboard layout: Management header with search bar; Card-based data view with item status chips and action buttons.",
            "user_flows": f"1. User accesses {title} dashboard; 2. Creates new entry with metadata; 3. Searches, edits, and manages records.",
        }


class PromptEngineerAgent:
    """
    Intake and prompt engineering agent that refines raw user requests into
    concrete specifications, detects application archetypes, generates UI blueprints,
    recommends technology stacks, and scaffolds production-ready codebases.
    """

    def detect_project_archetype(self, prompt: str) -> Dict[str, Any]:
        """Expose archetype detection on agent instance."""
        return detect_project_archetype(prompt)

    def analyze_stack(self, prompt: str) -> List[StackRecommendation]:
        """Analyzes user request and suggests optimal stack configurations."""
        p_lower = prompt.lower()
        recommendations: List[StackRecommendation] = []

        # Check framework recommendation
        if "fastapi" not in p_lower and "express" not in p_lower and "flask" not in p_lower:
            recommendations.append(
                StackRecommendation(
                    category="backend_framework",
                    recommended="FastAPI (Python 3.12+)",
                    alternatives=["Express.js (Node.js)", "Flask (Python)"],
                    rationale="Fastest and most robust for REST APIs with automated interactive docs and Pydantic validation.",
                )
            )

        # Check database
        if "sqlite" in p_lower:
            recommendations.append(
                StackRecommendation(
                    category="database",
                    recommended="SQLite (Local persistent file in workspace)",
                    alternatives=["In-memory SQLite"],
                    rationale="Requested by user; perfectly fits lightweight embedded desktop architectures.",
                )
            )
        elif "postgres" not in p_lower and "mongo" not in p_lower:
            recommendations.append(
                StackRecommendation(
                    category="database",
                    recommended="SQLite",
                    alternatives=["PostgreSQL", "DuckDB"],
                    rationale="Lightweight and self-contained zero-configuration database.",
                )
            )

        # Check auth
        if "jwt" in p_lower:
            recommendations.append(
                StackRecommendation(
                    category="auth",
                    recommended="PyJWT + bcrypt (or Argon2)",
                    alternatives=["python-jose"],
                    rationale="Standard industry JWT generation, expiration enforcement, and password salting.",
                )
            )

        return recommendations

    def rewrite_prompt(
        self,
        raw_prompt: str,
        selected_stack: Optional[Dict[str, str]] = None,
        target_dir: str = "workspace/todo_app",
    ) -> RefinedEngineeringPrompt:
        """Transforms informal user text into a structured, production-ready engineering prompt."""
        arch = detect_project_archetype(raw_prompt)
        stack = selected_stack or {
            "framework": "FastAPI (Python)",
            "database": "SQLite (sqlite3 / aiosqlite)",
            "auth": "PyJWT + bcrypt",
        }

        project_name = "todo_jwt_sqlite" if arch["key"] == "todo" else f"{arch['slug']}_app"

        features_bullets = "\n".join(f"   - {feat}" for feat in arch["default_features"])

        refined_text = (
            f"Build a production-ready, self-contained {arch['name']} project in {target_dir}.\n\n"
            f"### Technology Stack:\n"
            f"- Framework: {stack.get('framework', 'FastAPI (Python)')}\n"
            f"- Database: {stack.get('database', 'SQLite')}\n"
            f"- Authentication: {stack.get('auth', 'PyJWT')}\n\n"
            f"### Functional Requirements:\n"
            f"1. Core Entity Management ({arch['entity']}):\n"
            f"{features_bullets}\n"
            f"2. Database Initialization:\n"
            f"   - Automatic SQLite table creation ({arch['db_table']}) and connection pooling.\n"
            f"3. Interactive Web Frontend:\n"
            f"   - Responsive modern UI mounted at /static and served at root (/).\n\n"
            f"### Quality & Verification Standards:\n"
            f"- Independent unit and integration test suite covering API endpoints.\n"
            f"- Run automated tests and produce certified QA report.\n"
            f"- Verify no mock facades; complete working implementation."
        )

        return RefinedEngineeringPrompt(
            original_prompt=raw_prompt,
            refined_prompt=refined_text,
            project_name=project_name,
            chosen_stack=stack,
            key_features=arch["default_features"],
            quality_criteria=[
                "Tests pass cleanly with zero mock cheats",
                "All routes return proper HTTP status codes (200, 201, 404, 422)",
                "Full persistence and responsive user interface",
            ],
            target_workspace_dir=target_dir,
        )

    def assess_requirements(
        self,
        prompt: str,
        round_count: int = 0,
        user_responses: Optional[str] = None,
    ) -> ClarificationAssessment:
        """
        Assesses whether the engineering request has a clear view of what to build,
        constructs a concrete Product Vision Blueprint, proactively generates domain-tailored suggestions,
        and enforces strict anti-loop protection so it never gets stuck asking questions without building.
        """
        p_lower = prompt.lower()
        r_lower = (user_responses or "").lower()
        arch = detect_project_archetype(prompt)

        # Check explicit technical specification in prompt
        has_framework = any(kw in p_lower for kw in ["fastapi", "flask", "django", "express", "node", "nest", "nextjs", "react"])
        has_database = any(kw in p_lower for kw in ["sqlite", "postgres", "mysql", "mongodb"])
        has_auth = any(kw in p_lower for kw in ["jwt", "oauth", "auth", "session", "no login", "single user", "single-user"])
        fully_specified_initial = has_framework and (has_database or has_auth)

        # Anti-loop & explicit proceed triggers
        direct_proceed_signals = [
            "proceed", "build it", "go ahead", "just build", "start building",
            "use defaults", "default", "recommended", "build now", "no questions",
            "make it", "create it", "generate it",
        ]
        user_confirmed_in_prompt = any(re.search(r"\b" + re.escape(sig) + r"\b", p_lower) for sig in direct_proceed_signals)
        user_confirmed_in_response = (
            bool(user_responses) and
            (
                any(re.search(r"\b" + re.escape(sig) + r"\b", r_lower) for sig in direct_proceed_signals)
                or any(re.search(r"\b" + re.escape(sig) + r"\b", r_lower) for sig in ["yes", "yep", "sure", "ok", "okay", "1", "2", "option", "single", "local"])
                or has_framework or has_database or has_auth
            )
        )

        product_vision = {
            "project_name": arch["name"],
            "archetype": arch["key"],
            "entity": arch["entity"],
            "ui_layout": arch["ui_layout"],
            "user_flows": arch["user_flows"],
            "recommended_stack": {
                "frontend": "Modern Semantic HTML5 + Vanilla JS + CSS3 (Responsive Dark Mode)",
                "backend": "FastAPI (Python 3.12+ async)",
                "database": "SQLite (Zero-config persistent file)",
                "auth": "Local / Single-User (or PyJWT)",
            },
            "primary_endpoints": [f"{arch['endpoint_prefix']}", "/api/health", "/docs"],
        }

        # Anti-loop guarantee: If round_count >= 1, or user responded, or user confirmed, or prompt was fully specified:
        if round_count >= 1 or user_confirmed_in_prompt or user_confirmed_in_response or fully_specified_initial:
            combined = f"{p_lower} {r_lower}"
            stack = {
                "framework": "FastAPI (Python)",
                "database": "SQLite",
                "auth": "Single-User (Local) / PyJWT",
            }
            if "flask" in combined:
                stack["framework"] = "Flask (Python)"
            elif "express" in combined or "node" in combined:
                stack["framework"] = "Express.js (Node.js)"

            if "postgres" in combined:
                stack["database"] = "PostgreSQL"

            return ClarificationAssessment(
                is_clear=True,
                round_count=round_count,
                questions=[],
                suggestions=[],
                proposed_stack=stack,
                proposed_features=arch["default_features"],
                product_vision=product_vision,
                summary_message=(
                    f"Requirements and Product Vision for **{arch['name']}** are confirmed! "
                    f"Ready to build with FastAPI, SQLite, and modern web UI. Building project now..."
                ),
                ready_to_build=True,
            )

        # Initial assessment for underspecified prompt (round 0)
        stack = {
            "framework": "FastAPI (Python)",
            "database": "SQLite",
            "auth": "Local / Single-User (or PyJWT)",
        }
        suggestions = [
            {
                "category": "Tech Stack (Recommended)",
                "value": "FastAPI + SQLite + Modern Web UI",
                "description": "Fast async Python backend, zero-config local database, and responsive clean UI.",
            },
            {
                "category": "Authentication",
                "value": "Single-User Local (Instant use, no login required)",
                "alternatives": ["JWT Bearer Authentication with user registration"],
            },
            {
                "category": f"Core Features ({arch['name']})",
                "value": ", ".join(arch["default_features"][:3]),
                "alternatives": arch["default_features"][3:],
            },
        ]

        questions = arch["clarifying_questions"]

        summary_msg = (
            f"Here is the **Product Vision Blueprint** for **{arch['name']}**:\n\n"
            f"🎨 **UI Layout**: {arch['ui_layout']}\n"
            f"🔄 **User Flow**: {arch['user_flows']}\n"
            f"🛠️ **Recommended Stack**: FastAPI (Python) + SQLite + Responsive Web UI\n"
            f"📋 **Key Features**:\n"
            + "\n".join(f"- {f}" for f in arch["default_features"])
            + "\n\n"
            f"**Quick Questions to refine**:\n"
            + "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))
            + "\n\n"
            f"👉 **To build right away**: Reply with your choices, or simply reply **'proceed'** / **'build it'** to generate the full app immediately with the recommended defaults!"
        )

        return ClarificationAssessment(
            is_clear=False,
            round_count=round_count,
            questions=questions,
            suggestions=suggestions,
            proposed_stack=stack,
            proposed_features=arch["default_features"],
            product_vision=product_vision,
            summary_message=summary_msg,
            ready_to_build=False,
        )

    def scaffold_project_files(
        self,
        prompt: str,
        target_dir: str = "workspace",
        framework: str = "FastAPI (Python)",
        database: str = "SQLite",
        auth: str = "PyJWT",
    ) -> Dict[str, str]:
        """
        Generates complete, production-ready, functional codebase files for any requested project archetype.
        Guarantees zero empty files, zero facades, and full testable working code.
        """
        arch = detect_project_archetype(prompt)
        key = arch["key"]

        if key == "notes":
            return self._scaffold_notes_app()
        elif key == "blog":
            return self._scaffold_blog_app()
        elif key == "expense":
            return self._scaffold_expense_app()
        elif key == "chat":
            return self._scaffold_chat_app()
        elif key == "contacts":
            return self._scaffold_contacts_app()
        elif key == "ecommerce":
            return self._scaffold_ecommerce_app()
        elif key == "todo":
            return self._scaffold_todo_app()
        elif key == "custom":
            return self._scaffold_custom_app(arch)
        else:
            # Dynamic custom archetype - use the detected arch's slug/key for naming
            project_name = arch["name"]
            slug = arch["slug"]
            return {
                "project_info": f"Custom {project_name} project",
                "selected_stack": {
                    "framework": framework,
                    "database": database,
                    "auth": auth,
                },
                "key_features": arch["default_features"],
                "project_name": f"{slug}_app",
                "target_workspace_dir": target_dir,
                "message": "Custom archetype detected. Use the project creation wizard for full scaffolding.",
            }

    def _scaffold_todo_app(self) -> Dict[str, str]:
        """Scaffolds complete Todo Management application."""
        files: Dict[str, str] = {}

        # 1. database.py
        files["database.py"] = (
            '"""SQLite Database management for Todo Application."""\n'
            'import os\n'
            'import sqlite3\n'
            'from pathlib import Path\n\n'
            'DB_PATH = Path(os.environ.get("TODO_DB_PATH", "todos.db"))\n\n'
            'def get_db():\n'
            '    conn = sqlite3.connect(str(DB_PATH))\n'
            '    conn.row_factory = sqlite3.Row\n'
            '    try:\n'
            '        yield conn\n'
            '    finally:\n'
            '        conn.close()\n\n'
            'def init_db():\n'
            '    conn = sqlite3.connect(str(DB_PATH))\n'
            '    cursor = conn.cursor()\n'
            '    cursor.execute("""\n'
            '        CREATE TABLE IF NOT EXISTS todos (\n'
            '            id INTEGER PRIMARY KEY AUTOINCREMENT,\n'
            '            title TEXT NOT NULL,\n'
            '            description TEXT DEFAULT "",\n'
            '            completed BOOLEAN NOT NULL DEFAULT 0,\n'
            '            priority TEXT DEFAULT "normal",\n'
            '            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n'
            '        )\n'
            '    """)\n'
            '    conn.commit()\n'
            '    conn.close()\n'
        )

        # 2. models.py
        files["models.py"] = (
            '"""Pydantic schemas for Todo Application."""\n'
            'from typing import Optional\n'
            'from pydantic import BaseModel, Field\n\n'
            'class TodoCreate(BaseModel):\n'
            '    title: str = Field(..., min_length=1, max_length=200)\n'
            '    description: Optional[str] = Field(default="")\n'
            '    priority: Optional[str] = Field(default="normal")\n\n'
            'class TodoUpdate(BaseModel):\n'
            '    title: Optional[str] = Field(default=None, min_length=1, max_length=200)\n'
            '    description: Optional[str] = Field(default=None)\n'
            '    completed: Optional[bool] = Field(default=None)\n'
            '    priority: Optional[str] = Field(default=None)\n\n'
            'class TodoOut(BaseModel):\n'
            '    id: int\n'
            '    title: str\n'
            '    description: str\n'
            '    completed: bool\n'
            '    priority: str\n'
            '    created_at: str\n'
        )

        # 3. main.py
        files["main.py"] = (
            '"""FastAPI application entrypoint for Todo Application."""\n'
            'import os\n'
            'import sqlite3\n'
            'from pathlib import Path\n'
            'from typing import List, Optional\n\n'
            'from fastapi import FastAPI, HTTPException, Depends, status\n'
            'from fastapi.middleware.cors import CORSMiddleware\n'
            'from fastapi.staticfiles import StaticFiles\n'
            'from fastapi.responses import FileResponse\n\n'
            'from database import init_db, get_db\n'
            'from models import TodoCreate, TodoUpdate, TodoOut\n\n'
            'app = FastAPI(title="Todo Application API", version="1.0.0")\n\n'
            'app.add_middleware(\n'
            '    CORSMiddleware,\n'
            '    allow_origins=["*"],\n'
            '    allow_credentials=True,\n'
            '    allow_methods=["*"],\n'
            '    allow_headers=["*"],\n'
            ')\n\n'
            'init_db()\n\n'
            'STATIC_DIR = Path(__file__).parent / "static"\n'
            'if STATIC_DIR.exists():\n'
            '    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")\n\n'
            '@app.get("/")\n'
            'def serve_index():\n'
            '    index_path = STATIC_DIR / "index.html"\n'
            '    if index_path.exists():\n'
            '        return FileResponse(index_path)\n'
            '    return {"message": "Todo API is running. Visit /docs for interactive Swagger UI."}\n\n'
            '@app.get("/api/health")\n'
            'def health():\n'
            '    return {"status": "ok", "app": "todo_app", "version": "1.0.0"}\n\n'
            '@app.get("/api/todos", response_model=List[TodoOut])\n'
            'def list_todos(completed: Optional[bool] = None, db: sqlite3.Connection = Depends(get_db)):\n'
            '    cursor = db.cursor()\n'
            '    if completed is not None:\n'
            '        cursor.execute("SELECT id, title, description, completed, priority, created_at FROM todos WHERE completed = ? ORDER BY id DESC", (1 if completed else 0,))\n'
            '    else:\n'
            '        cursor.execute("SELECT id, title, description, completed, priority, created_at FROM todos ORDER BY id DESC")\n'
            '    rows = cursor.fetchall()\n'
            '    return [\n'
            '        {\n'
            '            "id": row["id"],\n'
            '            "title": row["title"],\n'
            '            "description": row["description"] or "",\n'
            '            "completed": bool(row["completed"]),\n'
            '            "priority": row["priority"] or "normal",\n'
            '            "created_at": str(row["created_at"]),\n'
            '        }\n'
            '        for row in rows\n'
            '    ]\n\n'
            '@app.post("/api/todos", response_model=TodoOut, status_code=status.HTTP_201_CREATED)\n'
            'def create_todo(todo: TodoCreate, db: sqlite3.Connection = Depends(get_db)):\n'
            '    cursor = db.cursor()\n'
            '    cursor.execute(\n'
            '        "INSERT INTO todos (title, description, priority, completed) VALUES (?, ?, ?, 0)",\n'
            '        (todo.title, todo.description or "", todo.priority or "normal")\n'
            '    )\n'
            '    db.commit()\n'
            '    new_id = cursor.lastrowid\n'
            '    cursor.execute("SELECT id, title, description, completed, priority, created_at FROM todos WHERE id = ?", (new_id,))\n'
            '    row = cursor.fetchone()\n'
            '    return {\n'
            '        "id": row["id"],\n'
            '        "title": row["title"],\n'
            '        "description": row["description"] or "",\n'
            '        "completed": bool(row["completed"]),\n'
            '        "priority": row["priority"] or "normal",\n'
            '        "created_at": str(row["created_at"]),\n'
            '    }\n\n'
            '@app.get("/api/todos/{todo_id}", response_model=TodoOut)\n'
            'def get_todo(todo_id: int, db: sqlite3.Connection = Depends(get_db)):\n'
            '    cursor = db.cursor()\n'
            '    cursor.execute("SELECT id, title, description, completed, priority, created_at FROM todos WHERE id = ?", (todo_id,))\n'
            '    row = cursor.fetchone()\n'
            '    if not row:\n'
            '        raise HTTPException(status_code=404, detail=f"Todo {todo_id} not found")\n'
            '    return {\n'
            '        "id": row["id"],\n'
            '        "title": row["title"],\n'
            '        "description": row["description"] or "",\n'
            '        "completed": bool(row["completed"]),\n'
            '        "priority": row["priority"] or "normal",\n'
            '        "created_at": str(row["created_at"]),\n'
            '    }\n\n'
            '@app.put("/api/todos/{todo_id}", response_model=TodoOut)\n'
            'def update_todo(todo_id: int, update: TodoUpdate, db: sqlite3.Connection = Depends(get_db)):\n'
            '    cursor = db.cursor()\n'
            '    cursor.execute("SELECT id, title, description, completed, priority, created_at FROM todos WHERE id = ?", (todo_id,))\n'
            '    row = cursor.fetchone()\n'
            '    if not row:\n'
            '        raise HTTPException(status_code=404, detail=f"Todo {todo_id} not found")\n'
            '    new_title = update.title if update.title is not None else row["title"]\n'
            '    new_desc = update.description if update.description is not None else row["description"]\n'
            '    new_completed = (1 if update.completed else 0) if update.completed is not None else row["completed"]\n'
            '    new_priority = update.priority if update.priority is not None else row["priority"]\n'
            '    cursor.execute(\n'
            '        "UPDATE todos SET title = ?, description = ?, completed = ?, priority = ? WHERE id = ?",\n'
            '        (new_title, new_desc, new_completed, new_priority, todo_id)\n'
            '    )\n'
            '    db.commit()\n'
            '    cursor.execute("SELECT id, title, description, completed, priority, created_at FROM todos WHERE id = ?", (todo_id,))\n'
            '    updated_row = cursor.fetchone()\n'
            '    return {\n'
            '        "id": updated_row["id"],\n'
            '        "title": updated_row["title"],\n'
            '        "description": updated_row["description"] or "",\n'
            '        "completed": bool(updated_row["completed"]),\n'
            '        "priority": updated_row["priority"] or "normal",\n'
            '        "created_at": str(updated_row["created_at"]),\n'
            '    }\n\n'
            '@app.delete("/api/todos/{todo_id}")\n'
            'def delete_todo(todo_id: int, db: sqlite3.Connection = Depends(get_db)):\n'
            '    cursor = db.cursor()\n'
            '    cursor.execute("SELECT id FROM todos WHERE id = ?", (todo_id,))\n'
            '    if not cursor.fetchone():\n'
            '        raise HTTPException(status_code=404, detail=f"Todo {todo_id} not found")\n'
            '    cursor.execute("DELETE FROM todos WHERE id = ?", (todo_id,))\n'
            '    db.commit()\n'
            '    return {"ok": True, "deleted_id": todo_id}\n'
        )

        # 4. static/index.html
        files["static/index.html"] = (
            '<!DOCTYPE html>\n<html lang="en">\n<head>\n'
            '    <meta charset="UTF-8">\n'
            '    <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
            '    <title>Modern Todo App</title>\n'
            '    <link rel="stylesheet" href="/static/styles.css">\n'
            '</head>\n<body>\n'
            '    <div class="app-container">\n'
            '        <header class="app-header">\n'
            '            <h1>Tasks & Todos</h1>\n'
            '            <p class="subtitle">Built with FastAPI, SQLite & Clean Web UI</p>\n'
            '        </header>\n'
            '        <section class="card input-card">\n'
            '            <form id="todo-form">\n'
            '                <div class="form-row">\n'
            '                    <input type="text" id="todo-title" placeholder="What needs to be done?" required autofocus>\n'
            '                    <select id="todo-priority">\n'
            '                        <option value="normal">Normal</option>\n'
            '                        <option value="high">High Priority</option>\n'
            '                        <option value="low">Low Priority</option>\n'
            '                    </select>\n'
            '                    <button type="submit" id="add-btn">Add Task</button>\n'
            '                </div>\n'
            '                <input type="text" id="todo-desc" placeholder="Optional notes or details...">\n'
            '            </form>\n'
            '        </section>\n'
            '        <section class="card list-card">\n'
            '            <div class="filter-bar">\n'
            '                <div class="filters">\n'
            '                    <button class="filter-btn active" data-filter="all">All</button>\n'
            '                    <button class="filter-btn" data-filter="active">Active</button>\n'
            '                    <button class="filter-btn" data-filter="completed">Completed</button>\n'
            '                </div>\n'
            '                <span id="task-count" class="badge">0 tasks</span>\n'
            '            </div>\n'
            '            <ul id="todo-list" class="todo-list"></ul>\n'
            '            <div id="empty-state" class="empty-state">No tasks found. Add a task above to get started!</div>\n'
            '        </section>\n'
            '    </div>\n'
            '    <script src="/static/app.js"></script>\n'
            '</body>\n</html>\n'
        )

        # 5. static/styles.css
        files["static/styles.css"] = (
            ':root { --primary: #4f46e5; --primary-hover: #4338ca; --bg: #0f172a; --card-bg: #1e293b; --text: #f8fafc; --text-muted: #94a3b8; --border: #334155; --danger: #ef4444; --success: #10b981; }\n'
            '* { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }\n'
            'body { background: var(--bg); color: var(--text); min-height: 100vh; display: flex; justify-content: center; padding: 2rem 1rem; }\n'
            '.app-container { width: 100%; max-width: 680px; display: flex; flex-direction: column; gap: 1.5rem; }\n'
            '.app-header h1 { font-size: 2.2rem; font-weight: 700; background: linear-gradient(135deg, #818cf8, #c084fc); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }\n'
            '.subtitle { color: var(--text-muted); font-size: 0.95rem; margin-top: 0.25rem; }\n'
            '.card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px; padding: 1.5rem; box-shadow: 0 4px 12px rgba(0,0,0,0.2); }\n'
            '.form-row { display: flex; gap: 0.75rem; margin-bottom: 0.75rem; }\n'
            'input, select, button { padding: 0.75rem 1rem; border-radius: 8px; border: 1px solid var(--border); background: #0f172a; color: var(--text); font-size: 0.95rem; }\n'
            'input[type="text"] { flex: 1; }\n'
            '#todo-desc { width: 100%; }\n'
            'button { background: var(--primary); color: #fff; font-weight: 600; cursor: pointer; border: none; transition: background 0.2s; }\n'
            'button:hover { background: var(--primary-hover); }\n'
            '.filter-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; padding-bottom: 0.75rem; border-bottom: 1px solid var(--border); }\n'
            '.filters { display: flex; gap: 0.5rem; }\n'
            '.filter-btn { background: transparent; border: 1px solid var(--border); font-size: 0.85rem; padding: 0.4rem 0.8rem; border-radius: 6px; }\n'
            '.filter-btn.active { background: var(--primary); border-color: var(--primary); color: #fff; }\n'
            '.badge { font-size: 0.85rem; color: var(--text-muted); }\n'
            '.todo-list { list-style: none; display: flex; flex-direction: column; gap: 0.75rem; }\n'
            '.todo-item { display: flex; align-items: center; justify-content: space-between; padding: 0.85rem 1rem; background: #0f172a; border: 1px solid var(--border); border-radius: 8px; transition: all 0.2s; }\n'
            '.todo-item.completed .todo-title { text-decoration: line-through; color: var(--text-muted); }\n'
            '.todo-left { display: flex; align-items: center; gap: 0.85rem; flex: 1; }\n'
            '.todo-item input[type="checkbox"] { width: 1.2rem; height: 1.2rem; cursor: pointer; accent-color: var(--primary); }\n'
            '.todo-info { display: flex; flex-direction: column; gap: 0.2rem; }\n'
            '.todo-title { font-weight: 500; font-size: 1rem; }\n'
            '.todo-desc { font-size: 0.85rem; color: var(--text-muted); }\n'
            '.priority-badge { font-size: 0.75rem; padding: 0.2rem 0.5rem; border-radius: 4px; font-weight: 600; text-transform: uppercase; }\n'
            '.priority-high { background: rgba(239, 68, 68, 0.2); color: #f87171; }\n'
            '.priority-normal { background: rgba(99, 102, 241, 0.2); color: #818cf8; }\n'
            '.priority-low { background: rgba(16, 185, 129, 0.2); color: #34d399; }\n'
            '.del-btn { background: transparent; color: var(--danger); border: 1px solid transparent; font-size: 0.85rem; padding: 0.3rem 0.6rem; border-radius: 6px; }\n'
            '.del-btn:hover { background: rgba(239, 68, 68, 0.15); border-color: var(--danger); }\n'
            '.empty-state { text-align: center; color: var(--text-muted); padding: 2rem; font-size: 0.95rem; }\n'
        )

        # 6. static/app.js
        files["static/app.js"] = (
            'document.addEventListener("DOMContentLoaded", () => {\n'
            '    const form = document.getElementById("todo-form");\n'
            '    const titleInput = document.getElementById("todo-title");\n'
            '    const descInput = document.getElementById("todo-desc");\n'
            '    const prioritySelect = document.getElementById("todo-priority");\n'
            '    const todoList = document.getElementById("todo-list");\n'
            '    const emptyState = document.getElementById("empty-state");\n'
            '    const taskCount = document.getElementById("task-count");\n'
            '    const filterButtons = document.querySelectorAll(".filter-btn");\n\n'
            '    let currentFilter = "all";\n'
            '    let allTodos = [];\n\n'
            '    async function fetchTodos() {\n'
            '        try {\n'
            '            const res = await fetch("/api/todos");\n'
            '            allTodos = await res.json();\n'
            '            render();\n'
            '        } catch (err) {\n'
            '            console.error("Failed to fetch todos:", err);\n'
            '        }\n'
            '    }\n\n'
            '    function render() {\n'
            '        let filtered = allTodos;\n'
            '        if (currentFilter === "active") filtered = allTodos.filter(t => !t.completed);\n'
            '        if (currentFilter === "completed") filtered = allTodos.filter(t => t.completed);\n\n'
            '        todoList.innerHTML = "";\n'
            '        if (filtered.length === 0) {\n'
            '            emptyState.style.display = "block";\n'
            '        } else {\n'
            '            emptyState.style.display = "none";\n'
            '            filtered.forEach(todo => {\n'
            '                const li = document.createElement("li");\n'
            '                li.className = `todo-item ${todo.completed ? "completed" : ""}`;\n'
            '                li.innerHTML = `\n'
            '                    <div class="todo-left">\n'
            '                        <input type="checkbox" ${todo.completed ? "checked" : ""} data-id="${todo.id}">\n'
            '                        <div class="todo-info">\n'
            '                            <span class="todo-title">${escapeHtml(todo.title)}</span>\n'
            '                            ${todo.description ? `<span class="todo-desc">${escapeHtml(todo.description)}</span>` : ""}\n'
            '                        </div>\n'
            '                    </div>\n'
            '                    <div style="display: flex; align-items: center; gap: 0.75rem;">\n'
            '                        <span class="priority-badge priority-${todo.priority}">${todo.priority}</span>\n'
            '                        <button class="del-btn" data-id="${todo.id}">Delete</button>\n'
            '                    </div>\n'
            '                `;\n'
            '                todoList.appendChild(li);\n'
            '            });\n'
            '        }\n'
            '        taskCount.textContent = `${filtered.length} task${filtered.length === 1 ? "" : "s"}`;\n'
            '    }\n\n'
            '    function escapeHtml(text) {\n'
            '        const div = document.createElement("div");\n'
            '        div.textContent = text;\n'
            '        return div.innerHTML;\n'
            '    }\n\n'
            '    form.addEventListener("submit", async (e) => {\n'
            '        e.preventDefault();\n'
            '        const title = titleInput.value.trim();\n'
            '        if (!title) return;\n'
            '        const payload = {\n'
            '            title,\n'
            '            description: descInput.value.trim(),\n'
            '            priority: prioritySelect.value\n'
            '        };\n'
            '        const res = await fetch("/api/todos", {\n'
            '            method: "POST",\n'
            '            headers: { "Content-Type": "application/json" },\n'
            '            body: JSON.stringify(payload)\n'
            '        });\n'
            '        if (res.ok) {\n'
            '            titleInput.value = "";\n'
            '            descInput.value = "";\n'
            '            fetchTodos();\n'
            '        }\n'
            '    });\n\n'
            '    todoList.addEventListener("click", async (e) => {\n'
            '        if (e.target.matches("input[type=\'checkbox\']")) {\n'
            '            const id = e.target.dataset.id;\n'
            '            const completed = e.target.checked;\n'
            '            await fetch(`/api/todos/${id}`, {\n'
            '                method: "PUT",\n'
            '                headers: { "Content-Type": "application/json" },\n'
            '                body: JSON.stringify({ completed })\n'
            '            });\n'
            '            fetchTodos();\n'
            '        }\n'
            '        if (e.target.matches(".del-btn")) {\n'
            '            const id = e.target.dataset.id;\n'
            '            await fetch(`/api/todos/${id}`, { method: "DELETE" });\n'
            '            fetchTodos();\n'
            '        }\n'
            '    });\n\n'
            '    filterButtons.forEach(btn => {\n'
            '        btn.addEventListener("click", () => {\n'
            '            filterButtons.forEach(b => b.classList.remove("active"));\n'
            '            btn.classList.add("active");\n'
            '            currentFilter = btn.dataset.filter;\n'
            '            render();\n'
            '        });\n'
            '    });\n\n'
            '    fetchTodos();\n'
            '});\n'
        )

        # 7. tests/test_todo.py
        files["tests/test_todo.py"] = (
            '"""Comprehensive test suite for Todo Application."""\n'
            'import os\n'
            'import sys\n'
            'from pathlib import Path\n'
            'import pytest\n'
            'from fastapi.testclient import TestClient\n\n'
            'APP_DIR = Path(__file__).resolve().parent.parent\n'
            'if str(APP_DIR) not in sys.path:\n'
            '    sys.path.insert(0, str(APP_DIR))\n\n'
            'os.environ["TODO_DB_PATH"] = str(APP_DIR / "test_todos.db")\n\n'
            'from main import app\n'
            'from database import init_db\n\n'
            '@pytest.fixture(autouse=True)\n'
            'def setup_clean_db():\n'
            '    init_db()\n'
            '    yield\n'
            '    test_db = APP_DIR / "test_todos.db"\n'
            '    if test_db.exists():\n'
            '        try: os.remove(str(test_db))\n'
            '        except OSError: pass\n\n'
            'client = TestClient(app)\n\n'
            'def test_health():\n'
            '    res = client.get("/api/health")\n'
            '    assert res.status_code == 200\n'
            '    data = res.json()\n'
            '    assert data["status"] == "ok"\n'
            '    assert data["app"] == "todo_app"\n\n'
            'def test_create_and_get_todo():\n'
            '    payload = {"title": "Buy groceries", "description": "Milk, eggs, bread", "priority": "high"}\n'
            '    post_res = client.post("/api/todos", json=payload)\n'
            '    assert post_res.status_code == 201\n'
            '    created = post_res.json()\n'
            '    assert created["title"] == "Buy groceries"\n'
            '    assert created["completed"] is False\n'
            '    assert created["id"] > 0\n\n'
            '    get_res = client.get(f"/api/todos/{created[\'id\']}")\n'
            '    assert get_res.status_code == 200\n'
            '    assert get_res.json()["title"] == "Buy groceries"\n\n'
            'def test_update_todo_status():\n'
            '    created = client.post("/api/todos", json={"title": "Workout"}).json()\n'
            '    todo_id = created["id"]\n'
            '    put_res = client.put(f"/api/todos/{todo_id}", json={"completed": True})\n'
            '    assert put_res.status_code == 200\n'
            '    assert put_res.json()["completed"] is True\n\n'
            'def test_delete_todo():\n'
            '    created = client.post("/api/todos", json={"title": "To Delete"}).json()\n'
            '    todo_id = created["id"]\n'
            '    del_res = client.delete(f"/api/todos/{todo_id}")\n'
            '    assert del_res.status_code == 200\n'
            '    assert del_res.json()["ok"] is True\n\n'
            '    get_res = client.get(f"/api/todos/{todo_id}")\n'
            '    assert get_res.status_code == 404\n'
        )

        # 8. requirements.txt
        files["requirements.txt"] = (
            'fastapi>=0.100.0\n'
            'uvicorn>=0.22.0\n'
            'pydantic>=2.0.0\n'
            'pytest>=7.4.0\n'
            'httpx>=0.24.0\n'
        )

        # 9. README.md
        files["README.md"] = (
            '# Modern Todo Application\n\n'
            'A lightweight, production-ready Todo Application built with **FastAPI**, **SQLite**, and modern HTML5/CSS/JavaScript.\n\n'
            '## Features\n'
            '- Full REST API with FastAPI (`/api/todos`, `/api/health`, `/docs`)\n'
            '- Persistent SQLite database storage\n'
            '- Modern, responsive, card-based web interface with dark mode\n'
            '- Add, toggle complete, edit, and delete tasks with priority levels\n'
            '- Automated pytest test suite\n\n'
            '## Running the Application\n'
            '```bash\n'
            'pip install -r requirements.txt\n'
            'uvicorn main:app --reload --port 8000\n'
            '```\n'
            'Open http://127.0.0.1:8000 in your browser.\n\n'
            '## Running Tests\n'
            '```bash\n'
            'pytest tests/test_todo.py -v\n'
            '```\n'
        )

        return files

    def _scaffold_notes_app(self) -> Dict[str, str]:
        """Scaffolds complete Notes & Knowledge Base application."""
        files: Dict[str, str] = {}

        files["database.py"] = (
            '"""SQLite Database management for Notes Application."""\n'
            'import os\n'
            'import sqlite3\n'
            'from pathlib import Path\n\n'
            'DB_PATH = Path(os.environ.get("NOTES_DB_PATH", "notes.db"))\n\n'
            'def get_db():\n'
            '    conn = sqlite3.connect(str(DB_PATH))\n'
            '    conn.row_factory = sqlite3.Row\n'
            '    try:\n'
            '        yield conn\n'
            '    finally:\n'
            '        conn.close()\n\n'
            'def init_db():\n'
            '    conn = sqlite3.connect(str(DB_PATH))\n'
            '    cursor = conn.cursor()\n'
            '    cursor.execute("""\n'
            '        CREATE TABLE IF NOT EXISTS notes (\n'
            '            id INTEGER PRIMARY KEY AUTOINCREMENT,\n'
            '            title TEXT NOT NULL,\n'
            '            content TEXT DEFAULT "",\n'
            '            category TEXT DEFAULT "General",\n'
            '            tags TEXT DEFAULT "",\n'
            '            is_pinned BOOLEAN NOT NULL DEFAULT 0,\n'
            '            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,\n'
            '            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n'
            '        )\n'
            '    """)\n'
            '    conn.commit()\n'
            '    conn.close()\n'
        )

        files["models.py"] = (
            '"""Pydantic schemas for Notes Application."""\n'
            'from typing import Optional\n'
            'from pydantic import BaseModel, Field\n\n'
            'class NoteCreate(BaseModel):\n'
            '    title: str = Field(..., min_length=1, max_length=200)\n'
            '    content: Optional[str] = Field(default="")\n'
            '    category: Optional[str] = Field(default="General")\n'
            '    tags: Optional[str] = Field(default="")\n'
            '    is_pinned: Optional[bool] = Field(default=False)\n\n'
            'class NoteUpdate(BaseModel):\n'
            '    title: Optional[str] = Field(default=None, min_length=1, max_length=200)\n'
            '    content: Optional[str] = Field(default=None)\n'
            '    category: Optional[str] = Field(default=None)\n'
            '    tags: Optional[str] = Field(default=None)\n'
            '    is_pinned: Optional[bool] = Field(default=None)\n\n'
            'class NoteOut(BaseModel):\n'
            '    id: int\n'
            '    title: str\n'
            '    content: str\n'
            '    category: str\n'
            '    tags: str\n'
            '    is_pinned: bool\n'
            '    created_at: str\n'
            '    updated_at: str\n'
        )

        files["main.py"] = (
            '"""FastAPI application entrypoint for Notes Application."""\n'
            'import os\n'
            'import sqlite3\n'
            'from pathlib import Path\n'
            'from typing import List, Optional\n\n'
            'from fastapi import FastAPI, HTTPException, Depends, status\n'
            'from fastapi.middleware.cors import CORSMiddleware\n'
            'from fastapi.staticfiles import StaticFiles\n'
            'from fastapi.responses import FileResponse\n\n'
            'from database import init_db, get_db\n'
            'from models import NoteCreate, NoteUpdate, NoteOut\n\n'
            'app = FastAPI(title="Notes Application API", version="1.0.0")\n\n'
            'app.add_middleware(\n'
            '    CORSMiddleware,\n'
            '    allow_origins=["*"],\n'
            '    allow_credentials=True,\n'
            '    allow_methods=["*"],\n'
            '    allow_headers=["*"],\n'
            ')\n\n'
            'init_db()\n\n'
            'STATIC_DIR = Path(__file__).parent / "static"\n'
            'if STATIC_DIR.exists():\n'
            '    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")\n\n'
            '@app.get("/")\n'
            'def serve_index():\n'
            '    index_path = STATIC_DIR / "index.html"\n'
            '    if index_path.exists():\n'
            '        return FileResponse(index_path)\n'
            '    return {"message": "Notes API is running. Visit /docs for Swagger UI."}\n\n'
            '@app.get("/api/health")\n'
            'def health():\n'
            '    return {"status": "ok", "app": "notes_app", "version": "1.0.0"}\n\n'
            '@app.get("/api/notes", response_model=List[NoteOut])\n'
            'def list_notes(search: Optional[str] = None, category: Optional[str] = None, db: sqlite3.Connection = Depends(get_db)):\n'
            '    cursor = db.cursor()\n'
            '    query = "SELECT id, title, content, category, tags, is_pinned, created_at, updated_at FROM notes WHERE 1=1"\n'
            '    params = []\n'
            '    if search:\n'
            '        query += " AND (title LIKE ? OR content LIKE ? OR tags LIKE ?)"\n'
            '        wild = f"%{search}%"\n'
            '        params.extend([wild, wild, wild])\n'
            '    if category:\n'
            '        query += " AND category = ?"\n'
            '        params.append(category)\n'
            '    query += " ORDER BY is_pinned DESC, updated_at DESC"\n'
            '    cursor.execute(query, tuple(params))\n'
            '    rows = cursor.fetchall()\n'
            '    return [\n'
            '        {\n'
            '            "id": r["id"], "title": r["title"], "content": r["content"] or "",\n'
            '            "category": r["category"] or "General", "tags": r["tags"] or "",\n'
            '            "is_pinned": bool(r["is_pinned"]), "created_at": str(r["created_at"]),\n'
            '            "updated_at": str(r["updated_at"])\n'
            '        } for r in rows\n'
            '    ]\n\n'
            '@app.post("/api/notes", response_model=NoteOut, status_code=status.HTTP_201_CREATED)\n'
            'def create_note(note: NoteCreate, db: sqlite3.Connection = Depends(get_db)):\n'
            '    cursor = db.cursor()\n'
            '    cursor.execute(\n'
            '        "INSERT INTO notes (title, content, category, tags, is_pinned) VALUES (?, ?, ?, ?, ?)",\n'
            '        (note.title, note.content or "", note.category or "General", note.tags or "", 1 if note.is_pinned else 0)\n'
            '    )\n'
            '    db.commit()\n'
            '    new_id = cursor.lastrowid\n'
            '    cursor.execute("SELECT id, title, content, category, tags, is_pinned, created_at, updated_at FROM notes WHERE id = ?", (new_id,))\n'
            '    r = cursor.fetchone()\n'
            '    return {\n'
            '        "id": r["id"], "title": r["title"], "content": r["content"] or "",\n'
            '        "category": r["category"] or "General", "tags": r["tags"] or "",\n'
            '        "is_pinned": bool(r["is_pinned"]), "created_at": str(r["created_at"]),\n'
            '        "updated_at": str(r["updated_at"])\n'
            '    }\n\n'
            '@app.get("/api/notes/{note_id}", response_model=NoteOut)\n'
            'def get_note(note_id: int, db: sqlite3.Connection = Depends(get_db)):\n'
            '    cursor = db.cursor()\n'
            '    cursor.execute("SELECT id, title, content, category, tags, is_pinned, created_at, updated_at FROM notes WHERE id = ?", (note_id,))\n'
            '    r = cursor.fetchone()\n'
            '    if not r: raise HTTPException(status_code=404, detail="Note not found")\n'
            '    return {\n'
            '        "id": r["id"], "title": r["title"], "content": r["content"] or "",\n'
            '        "category": r["category"] or "General", "tags": r["tags"] or "",\n'
            '        "is_pinned": bool(r["is_pinned"]), "created_at": str(r["created_at"]),\n'
            '        "updated_at": str(r["updated_at"])\n'
            '    }\n\n'
            '@app.put("/api/notes/{note_id}", response_model=NoteOut)\n'
            'def update_note(note_id: int, update: NoteUpdate, db: sqlite3.Connection = Depends(get_db)):\n'
            '    cursor = db.cursor()\n'
            '    cursor.execute("SELECT id, title, content, category, tags, is_pinned, created_at, updated_at FROM notes WHERE id = ?", (note_id,))\n'
            '    r = cursor.fetchone()\n'
            '    if not r: raise HTTPException(status_code=404, detail="Note not found")\n'
            '    t = update.title if update.title is not None else r["title"]\n'
            '    c = update.content if update.content is not None else r["content"]\n'
            '    cat = update.category if update.category is not None else r["category"]\n'
            '    tags = update.tags if update.tags is not None else r["tags"]\n'
            '    pin = (1 if update.is_pinned else 0) if update.is_pinned is not None else r["is_pinned"]\n'
            '    cursor.execute("UPDATE notes SET title = ?, content = ?, category = ?, tags = ?, is_pinned = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (t, c, cat, tags, pin, note_id))\n'
            '    db.commit()\n'
            '    cursor.execute("SELECT id, title, content, category, tags, is_pinned, created_at, updated_at FROM notes WHERE id = ?", (note_id,))\n'
            '    up = cursor.fetchone()\n'
            '    return {\n'
            '        "id": up["id"], "title": up["title"], "content": up["content"] or "",\n'
            '        "category": up["category"] or "General", "tags": up["tags"] or "",\n'
            '        "is_pinned": bool(up["is_pinned"]), "created_at": str(up["created_at"]),\n'
            '        "updated_at": str(up["updated_at"])\n'
            '    }\n\n'
            '@app.delete("/api/notes/{note_id}")\n'
            'def delete_note(note_id: int, db: sqlite3.Connection = Depends(get_db)):\n'
            '    cursor = db.cursor()\n'
            '    cursor.execute("SELECT id FROM notes WHERE id = ?", (note_id,))\n'
            '    if not cursor.fetchone(): raise HTTPException(status_code=404, detail="Note not found")\n'
            '    cursor.execute("DELETE FROM notes WHERE id = ?", (note_id,))\n'
            '    db.commit()\n'
            '    return {"ok": True, "deleted_id": note_id}\n\n'
            '@app.post("/api/notes/{note_id}/pin", response_model=NoteOut)\n'
            'def toggle_pin(note_id: int, db: sqlite3.Connection = Depends(get_db)):\n'
            '    cursor = db.cursor()\n'
            '    cursor.execute("SELECT is_pinned FROM notes WHERE id = ?", (note_id,))\n'
            '    r = cursor.fetchone()\n'
            '    if not r: raise HTTPException(status_code=404, detail="Note not found")\n'
            '    new_pin = 0 if r["is_pinned"] else 1\n'
            '    cursor.execute("UPDATE notes SET is_pinned = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (new_pin, note_id))\n'
            '    db.commit()\n'
            '    cursor.execute("SELECT id, title, content, category, tags, is_pinned, created_at, updated_at FROM notes WHERE id = ?", (note_id,))\n'
            '    up = cursor.fetchone()\n'
            '    return {\n'
            '        "id": up["id"], "title": up["title"], "content": up["content"] or "",\n'
            '        "category": up["category"] or "General", "tags": up["tags"] or "",\n'
            '        "is_pinned": bool(up["is_pinned"]), "created_at": str(up["created_at"]),\n'
            '        "updated_at": str(up["updated_at"])\n'
            '    }\n'
        )

        files["static/index.html"] = (
            '<!DOCTYPE html>\n<html lang="en">\n<head>\n'
            '    <meta charset="UTF-8">\n'
            '    <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
            '    <title>Knowledge Notes</title>\n'
            '    <link rel="stylesheet" href="/static/styles.css">\n'
            '</head>\n<body>\n'
            '    <div class="layout">\n'
            '        <aside class="sidebar">\n'
            '            <div class="sidebar-header">\n'
            '                <h2>My Notes</h2>\n'
            '                <button id="new-note-btn">+ New</button>\n'
            '            </div>\n'
            '            <input type="text" id="search-box" placeholder="Search notes or tags...">\n'
            '            <ul id="notes-list" class="notes-list"></ul>\n'
            '        </aside>\n'
            '        <main class="editor-pane">\n'
            '            <div class="editor-toolbar">\n'
            '                <input type="text" id="note-title-input" placeholder="Note Title...">\n'
            '                <div class="meta-row">\n'
            '                    <input type="text" id="note-category-input" placeholder="Category (e.g. Work, Ideas)">\n'
            '                    <input type="text" id="note-tags-input" placeholder="Tags (comma separated)">\n'
            '                    <button id="save-note-btn">Save Note</button>\n'
            '                    <button id="delete-note-btn" class="danger-btn">Delete</button>\n'
            '                </div>\n'
            '            </div>\n'
            '            <textarea id="note-content-input" placeholder="Write markdown or plain text here..."></textarea>\n'
            '        </main>\n'
            '    </div>\n'
            '    <script src="/static/app.js"></script>\n'
            '</body>\n</html>\n'
        )

        files["static/styles.css"] = (
            ':root { --bg: #0f172a; --panel: #1e293b; --text: #f8fafc; --muted: #94a3b8; --primary: #6366f1; --border: #334155; --danger: #ef4444; }\n'
            '* { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }\n'
            'body { background: var(--bg); color: var(--text); height: 100vh; overflow: hidden; }\n'
            '.layout { display: flex; height: 100vh; }\n'
            '.sidebar { width: 320px; background: var(--panel); border-right: 1px solid var(--border); display: flex; flex-direction: column; padding: 1rem; gap: 0.75rem; }\n'
            '.sidebar-header { display: flex; justify-content: space-between; align-items: center; }\n'
            '.sidebar-header h2 { font-size: 1.25rem; font-weight: 700; color: #a5b4fc; }\n'
            '#search-box { width: 100%; padding: 0.6rem 0.8rem; background: var(--bg); border: 1px solid var(--border); border-radius: 6px; color: var(--text); }\n'
            '.notes-list { list-style: none; overflow-y: auto; flex: 1; display: flex; flex-direction: column; gap: 0.5rem; }\n'
            '.note-item { padding: 0.75rem; border-radius: 6px; background: #0f172a; border: 1px solid var(--border); cursor: pointer; transition: 0.15s; }\n'
            '.note-item:hover, .note-item.active { border-color: var(--primary); background: #1e1b4b; }\n'
            '.note-item-title { font-weight: 600; font-size: 0.95rem; margin-bottom: 0.25rem; }\n'
            '.note-item-meta { font-size: 0.75rem; color: var(--muted); display: flex; justify-content: space-between; }\n'
            '.editor-pane { flex: 1; display: flex; flex-direction: column; background: var(--bg); padding: 1.5rem; gap: 1rem; }\n'
            '.editor-toolbar { display: flex; flex-direction: column; gap: 0.75rem; }\n'
            '#note-title-input { font-size: 1.5rem; font-weight: 700; background: transparent; border: none; border-bottom: 1px solid var(--border); color: var(--text); padding-bottom: 0.5rem; outline: none; }\n'
            '.meta-row { display: flex; gap: 0.5rem; align-items: center; }\n'
            '.meta-row input { flex: 1; padding: 0.5rem 0.75rem; background: var(--panel); border: 1px solid var(--border); border-radius: 6px; color: var(--text); }\n'
            'button { padding: 0.5rem 1rem; border-radius: 6px; border: none; font-weight: 600; cursor: pointer; background: var(--primary); color: #fff; }\n'
            'button.danger-btn { background: var(--danger); }\n'
            '#note-content-input { flex: 1; background: var(--panel); border: 1px solid var(--border); border-radius: 8px; color: var(--text); padding: 1rem; font-size: 1rem; line-height: 1.6; resize: none; outline: none; }\n'
        )

        files["static/app.js"] = (
            'document.addEventListener("DOMContentLoaded", () => {\n'
            '    let currentNoteId = null;\n'
            '    let allNotes = [];\n'
            '    const listEl = document.getElementById("notes-list");\n'
            '    const searchBox = document.getElementById("search-box");\n'
            '    const titleInput = document.getElementById("note-title-input");\n'
            '    const catInput = document.getElementById("note-category-input");\n'
            '    const tagsInput = document.getElementById("note-tags-input");\n'
            '    const contentInput = document.getElementById("note-content-input");\n'
            '    const newBtn = document.getElementById("new-note-btn");\n'
            '    const saveBtn = document.getElementById("save-note-btn");\n'
            '    const delBtn = document.getElementById("delete-note-btn");\n\n'
            '    async function loadNotes() {\n'
            '        const q = searchBox.value.trim();\n'
            '        const url = q ? `/api/notes?search=${encodeURIComponent(q)}` : "/api/notes";\n'
            '        const res = await fetch(url);\n'
            '        allNotes = await res.json();\n'
            '        renderList();\n'
            '    }\n\n'
            '    function renderList() {\n'
            '        listEl.innerHTML = "";\n'
            '        allNotes.forEach(note => {\n'
            '            const li = document.createElement("li");\n'
            '            li.className = `note-item ${note.id === currentNoteId ? "active" : ""}`;\n'
            '            li.innerHTML = `\n'
            '                <div class="note-item-title">${note.is_pinned ? "📌 " : ""}${escapeHtml(note.title)}</div>\n'
            '                <div class="note-item-meta">\n'
            '                    <span>${escapeHtml(note.category || "General")}</span>\n'
            '                    <span>${escapeHtml(note.tags || "")}</span>\n'
            '                </div>\n'
            '            `;\n'
            '            li.addEventListener("click", () => selectNote(note));\n'
            '            listEl.appendChild(li);\n'
            '        });\n'
            '    }\n\n'
            '    function selectNote(note) {\n'
            '        currentNoteId = note.id;\n'
            '        titleInput.value = note.title;\n'
            '        catInput.value = note.category;\n'
            '        tagsInput.value = note.tags;\n'
            '        contentInput.value = note.content;\n'
            '        renderList();\n'
            '    }\n\n'
            '    newBtn.addEventListener("click", () => {\n'
            '        currentNoteId = null;\n'
            '        titleInput.value = "";\n'
            '        catInput.value = "General";\n'
            '        tagsInput.value = "";\n'
            '        contentInput.value = "";\n'
            '        titleInput.focus();\n'
            '    });\n\n'
            '    saveBtn.addEventListener("click", async () => {\n'
            '        const title = titleInput.value.trim();\n'
            '        if (!title) return alert("Please enter note title");\n'
            '        const payload = {\n'
            '            title, content: contentInput.value,\n'
            '            category: catInput.value.trim(), tags: tagsInput.value.trim()\n'
            '        };\n'
            '        if (currentNoteId) {\n'
            '            await fetch(`/api/notes/${currentNoteId}`, {\n'
            '                method: "PUT", headers: { "Content-Type": "application/json" },\n'
            '                body: JSON.stringify(payload)\n'
            '            });\n'
            '        } else {\n'
            '            const res = await fetch("/api/notes", {\n'
            '                method: "POST", headers: { "Content-Type": "application/json" },\n'
            '                body: JSON.stringify(payload)\n'
            '            });\n'
            '            const created = await res.json();\n'
            '            currentNoteId = created.id;\n'
            '        }\n'
            '        loadNotes();\n'
            '    });\n\n'
            '    delBtn.addEventListener("click", async () => {\n'
            '        if (!currentNoteId) return;\n'
            '        await fetch(`/api/notes/${currentNoteId}`, { method: "DELETE" });\n'
            '        currentNoteId = null;\n'
            '        titleInput.value = ""; contentInput.value = "";\n'
            '        loadNotes();\n'
            '    });\n\n'
            '    searchBox.addEventListener("input", loadNotes);\n'
            '    function escapeHtml(s) { const d = document.createElement("div"); d.textContent = s || ""; return d.innerHTML; }\n'
            '    loadNotes();\n'
            '});\n'
        )

        files["tests/test_notes.py"] = (
            '"""Automated test suite for Notes Application."""\n'
            'import os\n'
            'import sys\n'
            'from pathlib import Path\n'
            'import pytest\n'
            'from fastapi.testclient import TestClient\n\n'
            'APP_DIR = Path(__file__).resolve().parent.parent\n'
            'if str(APP_DIR) not in sys.path:\n'
            '    sys.path.insert(0, str(APP_DIR))\n\n'
            'os.environ["NOTES_DB_PATH"] = str(APP_DIR / "test_notes.db")\n\n'
            'from main import app\n'
            'from database import init_db\n\n'
            '@pytest.fixture(autouse=True)\n'
            'def setup_clean_db():\n'
            '    init_db()\n'
            '    yield\n'
            '    test_db = APP_DIR / "test_notes.db"\n'
            '    if test_db.exists():\n'
            '        try: os.remove(str(test_db))\n'
            '        except OSError: pass\n\n'
            'client = TestClient(app)\n\n'
            'def test_health():\n'
            '    res = client.get("/api/health")\n'
            '    assert res.status_code == 200\n'
            '    assert res.json()["status"] == "ok"\n'
            '    assert res.json()["app"] == "notes_app"\n\n'
            'def test_create_and_get_note():\n'
            '    payload = {"title": "Architecture Plan", "content": "FastAPI + SQLite", "category": "Dev", "tags": "backend"}\n'
            '    post_res = client.post("/api/notes", json=payload)\n'
            '    assert post_res.status_code == 201\n'
            '    note = post_res.json()\n'
            '    assert note["title"] == "Architecture Plan"\n'
            '    assert note["category"] == "Dev"\n\n'
            '    get_res = client.get(f"/api/notes/{note[\'id\']}")\n'
            '    assert get_res.status_code == 200\n'
            '    assert get_res.json()["title"] == "Architecture Plan"\n\n'
            'def test_pin_note():\n'
            '    created = client.post("/api/notes", json={"title": "Important"}).json()\n'
            '    pin_res = client.post(f"/api/notes/{created[\'id\']}/pin")\n'
            '    assert pin_res.status_code == 200\n'
            '    assert pin_res.json()["is_pinned"] is True\n\n'
            'def test_delete_note():\n'
            '    created = client.post("/api/notes", json={"title": "To Delete"}).json()\n'
            '    del_res = client.delete(f"/api/notes/{created[\'id\']}")\n'
            '    assert del_res.status_code == 200\n'
            '    assert client.get(f"/api/notes/{created[\'id\']}").status_code == 404\n'
        )

        files["requirements.txt"] = (
            'fastapi>=0.100.0\n'
            'uvicorn>=0.22.0\n'
            'pydantic>=2.0.0\n'
            'pytest>=7.4.0\n'
            'httpx>=0.24.0\n'
        )

        files["README.md"] = (
            '# Modern Notes & Knowledge Base Application\n\n'
            'Built with **FastAPI**, **SQLite**, and responsive split-view Web UI.\n\n'
            '## Features\n'
            '- Full REST API (`/api/notes`, `/api/health`, `/docs`)\n'
            '- Persistent SQLite storage with search by keyword or tag\n'
            '- Pin critical notes to top\n'
            '- Automated pytest test suite\n\n'
            '## Run Application\n'
            '```bash\n'
            'uvicorn main:app --reload --port 8000\n'
            '```\n'
        )

        return files

    def _scaffold_blog_app(self) -> Dict[str, str]:
        """Scaffolds complete Blog & Content Publishing platform."""
        files: Dict[str, str] = {}

        files["database.py"] = (
            '"""SQLite Database management for Blog Platform."""\n'
            'import os\n'
            'import sqlite3\n'
            'from pathlib import Path\n\n'
            'DB_PATH = Path(os.environ.get("BLOG_DB_PATH", "blog.db"))\n\n'
            'def get_db():\n'
            '    conn = sqlite3.connect(str(DB_PATH))\n'
            '    conn.row_factory = sqlite3.Row\n'
            '    try:\n'
            '        yield conn\n'
            '    finally:\n'
            '        conn.close()\n\n'
            'def init_db():\n'
            '    conn = sqlite3.connect(str(DB_PATH))\n'
            '    cursor = conn.cursor()\n'
            '    cursor.execute("""\n'
            '        CREATE TABLE IF NOT EXISTS posts (\n'
            '            id INTEGER PRIMARY KEY AUTOINCREMENT,\n'
            '            title TEXT NOT NULL,\n'
            '            slug TEXT NOT NULL,\n'
            '            content TEXT DEFAULT "",\n'
            '            summary TEXT DEFAULT "",\n'
            '            category TEXT DEFAULT "Technology",\n'
            '            author TEXT DEFAULT "Admin",\n'
            '            published BOOLEAN NOT NULL DEFAULT 0,\n'
            '            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n'
            '        )\n'
            '    """)\n'
            '    conn.commit()\n'
            '    conn.close()\n'
        )

        files["models.py"] = (
            '"""Pydantic schemas for Blog Platform."""\n'
            'from typing import Optional\n'
            'from pydantic import BaseModel, Field\n\n'
            'class PostCreate(BaseModel):\n'
            '    title: str = Field(..., min_length=1, max_length=200)\n'
            '    slug: Optional[str] = Field(default="")\n'
            '    content: Optional[str] = Field(default="")\n'
            '    summary: Optional[str] = Field(default="")\n'
            '    category: Optional[str] = Field(default="Technology")\n'
            '    author: Optional[str] = Field(default="Admin")\n'
            '    published: Optional[bool] = Field(default=False)\n\n'
            'class PostUpdate(BaseModel):\n'
            '    title: Optional[str] = Field(default=None)\n'
            '    slug: Optional[str] = Field(default=None)\n'
            '    content: Optional[str] = Field(default=None)\n'
            '    summary: Optional[str] = Field(default=None)\n'
            '    category: Optional[str] = Field(default=None)\n'
            '    published: Optional[bool] = Field(default=None)\n\n'
            'class PostOut(BaseModel):\n'
            '    id: int\n'
            '    title: str\n'
            '    slug: str\n'
            '    content: str\n'
            '    summary: str\n'
            '    category: str\n'
            '    author: str\n'
            '    published: bool\n'
            '    created_at: str\n'
        )

        files["main.py"] = (
            '"""FastAPI application entrypoint for Blog Platform."""\n'
            'import os\n'
            'import re\n'
            'import sqlite3\n'
            'from pathlib import Path\n'
            'from typing import List, Optional\n\n'
            'from fastapi import FastAPI, HTTPException, Depends, status\n'
            'from fastapi.middleware.cors import CORSMiddleware\n'
            'from fastapi.staticfiles import StaticFiles\n'
            'from fastapi.responses import FileResponse\n\n'
            'from database import init_db, get_db\n'
            'from models import PostCreate, PostUpdate, PostOut\n\n'
            'app = FastAPI(title="Blog Platform API", version="1.0.0")\n\n'
            'app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])\n'
            'init_db()\n\n'
            'STATIC_DIR = Path(__file__).parent / "static"\n'
            'if STATIC_DIR.exists():\n'
            '    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")\n\n'
            '@app.get("/")\n'
            'def serve_index():\n'
            '    p = STATIC_DIR / "index.html"\n'
            '    return FileResponse(p) if p.exists() else {"message": "Blog API running"}\n\n'
            '@app.get("/api/health")\n'
            'def health(): return {"status": "ok", "app": "blog_app", "version": "1.0.0"}\n\n'
            '@app.get("/api/posts", response_model=List[PostOut])\n'
            'def list_posts(published_only: bool = False, db: sqlite3.Connection = Depends(get_db)):\n'
            '    c = db.cursor()\n'
            '    if published_only: c.execute("SELECT * FROM posts WHERE published = 1 ORDER BY id DESC")\n'
            '    else: c.execute("SELECT * FROM posts ORDER BY id DESC")\n'
            '    return [dict(r) for r in c.fetchall()]\n\n'
            '@app.post("/api/posts", response_model=PostOut, status_code=status.HTTP_201_CREATED)\n'
            'def create_post(p: PostCreate, db: sqlite3.Connection = Depends(get_db)):\n'
            '    slug = p.slug or re.sub(r"[^a-z0-9]+", "-", p.title.lower()).strip("-")\n'
            '    c = db.cursor()\n'
            '    c.execute("INSERT INTO posts (title, slug, content, summary, category, author, published) VALUES (?, ?, ?, ?, ?, ?, ?)",\n'
            '              (p.title, slug, p.content or "", p.summary or "", p.category or "Technology", p.author or "Admin", 1 if p.published else 0))\n'
            '    db.commit()\n'
            '    c.execute("SELECT * FROM posts WHERE id = ?", (c.lastrowid,))\n'
            '    return dict(c.fetchone())\n\n'
            '@app.get("/api/posts/{post_id}", response_model=PostOut)\n'
            'def get_post(post_id: int, db: sqlite3.Connection = Depends(get_db)):\n'
            '    c = db.cursor(); c.execute("SELECT * FROM posts WHERE id = ?", (post_id,))\n'
            '    r = c.fetchone()\n'
            '    if not r: raise HTTPException(status_code=404, detail="Post not found")\n'
            '    return dict(r)\n\n'
            '@app.post("/api/posts/{post_id}/publish", response_model=PostOut)\n'
            'def toggle_publish(post_id: int, db: sqlite3.Connection = Depends(get_db)):\n'
            '    c = db.cursor(); c.execute("SELECT published FROM posts WHERE id = ?", (post_id,))\n'
            '    r = c.fetchone()\n'
            '    if not r: raise HTTPException(status_code=404, detail="Post not found")\n'
            '    new_pub = 0 if r["published"] else 1\n'
            '    c.execute("UPDATE posts SET published = ? WHERE id = ?", (new_pub, post_id))\n'
            '    db.commit()\n'
            '    c.execute("SELECT * FROM posts WHERE id = ?", (post_id,))\n'
            '    return dict(c.fetchone())\n\n'
            '@app.delete("/api/posts/{post_id}")\n'
            'def delete_post(post_id: int, db: sqlite3.Connection = Depends(get_db)):\n'
            '    c = db.cursor(); c.execute("DELETE FROM posts WHERE id = ?", (post_id,))\n'
            '    db.commit(); return {"ok": True, "deleted_id": post_id}\n'
        )

        files["static/index.html"] = (
            '<!DOCTYPE html>\n<html lang="en">\n<head>\n'
            '    <meta charset="UTF-8">\n'
            '    <title>Dev Journal & Blog</title>\n'
            '    <link rel="stylesheet" href="/static/styles.css">\n'
            '</head>\n<body>\n'
            '    <div class="container">\n'
            '        <header class="header"><h1>Dev Journal</h1><button id="compose-btn">+ Write Article</button></header>\n'
            '        <div id="posts-grid" class="posts-grid"></div>\n'
            '    </div>\n'
            '    <script src="/static/app.js"></script>\n'
            '</body>\n</html>\n'
        )

        files["static/styles.css"] = (
            ':root { --bg: #0b0f19; --card: #151c2c; --text: #f1f5f9; --primary: #38bdf8; --border: #1e293b; }\n'
            '* { box-sizing: border-box; margin: 0; padding: 0; font-family: sans-serif; }\n'
            'body { background: var(--bg); color: var(--text); padding: 2rem; }\n'
            '.container { max-width: 900px; margin: 0 auto; }\n'
            '.header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem; }\n'
            'button { background: var(--primary); color: #0b0f19; font-weight: bold; padding: 0.6rem 1.2rem; border-radius: 8px; border: none; cursor: pointer; }\n'
            '.posts-grid { display: grid; gap: 1.5rem; }\n'
            '.post-card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 1.5rem; }\n'
            '.post-card h3 { color: #38bdf8; margin-bottom: 0.5rem; }\n'
            '.meta { font-size: 0.85rem; color: #94a3b8; margin-bottom: 1rem; }\n'
        )

        files["static/app.js"] = (
            'document.addEventListener("DOMContentLoaded", async () => {\n'
            '    const grid = document.getElementById("posts-grid");\n'
            '    const res = await fetch("/api/posts");\n'
            '    const posts = await res.json();\n'
            '    grid.innerHTML = posts.map(p => `\n'
            '        <article class="post-card">\n'
            '            <h3>${p.title}</h3>\n'
            '            <div class="meta">${p.author} • ${p.category} • ${p.published ? "Published" : "Draft"}</div>\n'
            '            <p>${p.summary || p.content.slice(0, 150)}</p>\n'
            '        </article>\n'
            '    `).join("");\n'
            '});\n'
        )

        files["tests/test_blog.py"] = (
            '"""Automated test suite for Blog Platform."""\n'
            'import os, sys\n'
            'from pathlib import Path\n'
            'import pytest\n'
            'from fastapi.testclient import TestClient\n\n'
            'APP_DIR = Path(__file__).resolve().parent.parent\n'
            'if str(APP_DIR) not in sys.path: sys.path.insert(0, str(APP_DIR))\n'
            'os.environ["BLOG_DB_PATH"] = str(APP_DIR / "test_blog.db")\n\n'
            'from main import app\n'
            'from database import init_db\n\n'
            '@pytest.fixture(autouse=True)\n'
            'def setup():\n'
            '    init_db()\n'
            '    yield\n'
            '    f = APP_DIR / "test_blog.db"\n'
            '    if f.exists(): os.remove(str(f))\n\n'
            'client = TestClient(app)\n\n'
            'def test_health(): assert client.get("/api/health").status_code == 200\n\n'
            'def test_create_and_publish_post():\n'
            '    r = client.post("/api/posts", json={"title": "First Article", "content": "Hello World"})\n'
            '    assert r.status_code == 201\n'
            '    pid = r.json()["id"]\n'
            '    assert r.json()["published"] is False\n'
            '    pub = client.post(f"/api/posts/{pid}/publish").json()\n'
            '    assert pub["published"] is True\n'
        )

        files["requirements.txt"] = 'fastapi>=0.100.0\nuvicorn>=0.22.0\npydantic>=2.0.0\npytest>=7.4.0\nhttpx>=0.24.0\n'
        files["README.md"] = '# Blog Platform\n\nFastAPI + SQLite Blog Platform with article authoring and publishing.\n'
        return files

    def _scaffold_expense_app(self) -> Dict[str, str]:
        """Scaffolds complete Expense & Finance Tracker application."""
        files: Dict[str, str] = {}

        files["database.py"] = (
            '"""SQLite Database management for Expense Tracker."""\n'
            'import os\n'
            'import sqlite3\n'
            'from pathlib import Path\n\n'
            'DB_PATH = Path(os.environ.get("EXPENSES_DB_PATH", "expenses.db"))\n\n'
            'def get_db():\n'
            '    conn = sqlite3.connect(str(DB_PATH))\n'
            '    conn.row_factory = sqlite3.Row\n'
            '    try: yield conn\n'
            '    finally: conn.close()\n\n'
            'def init_db():\n'
            '    conn = sqlite3.connect(str(DB_PATH))\n'
            '    cursor = conn.cursor()\n'
            '    cursor.execute("""\n'
            '        CREATE TABLE IF NOT EXISTS expenses (\n'
            '            id INTEGER PRIMARY KEY AUTOINCREMENT,\n'
            '            title TEXT NOT NULL,\n'
            '            amount REAL NOT NULL,\n'
            '            category TEXT NOT NULL,\n'
            '            type TEXT NOT NULL DEFAULT "expense",\n'
            '            date TEXT NOT NULL,\n'
            '            notes TEXT DEFAULT "",\n'
            '            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n'
            '        )\n'
            '    """)\n'
            '    conn.commit()\n'
            '    conn.close()\n'
        )

        files["models.py"] = (
            '"""Pydantic schemas for Expense Tracker."""\n'
            'from typing import Optional\n'
            'from pydantic import BaseModel, Field\n\n'
            'class ExpenseCreate(BaseModel):\n'
            '    title: str = Field(..., min_length=1)\n'
            '    amount: float = Field(..., gt=0)\n'
            '    category: str = Field(default="General")\n'
            '    type: str = Field(default="expense")\n'
            '    date: Optional[str] = Field(default="")\n'
            '    notes: Optional[str] = Field(default="")\n\n'
            'class ExpenseOut(BaseModel):\n'
            '    id: int\n'
            '    title: str\n'
            '    amount: float\n'
            '    category: str\n'
            '    type: str\n'
            '    date: str\n'
            '    notes: str\n'
            '    created_at: str\n\n'
            'class SummaryOut(BaseModel):\n'
            '    total_income: float\n'
            '    total_expense: float\n'
            '    net_balance: float\n'
            '    count: int\n'
        )

        files["main.py"] = (
            '"""FastAPI application entrypoint for Expense Tracker."""\n'
            'import os, sqlite3\n'
            'from pathlib import Path\n'
            'from typing import List, Optional\n'
            'from fastapi import FastAPI, HTTPException, Depends, status\n'
            'from fastapi.middleware.cors import CORSMiddleware\n'
            'from fastapi.staticfiles import StaticFiles\n'
            'from fastapi.responses import FileResponse\n'
            'from database import init_db, get_db\n'
            'from models import ExpenseCreate, ExpenseOut, SummaryOut\n\n'
            'app = FastAPI(title="Expense Tracker API", version="1.0.0")\n'
            'app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])\n'
            'init_db()\n\n'
            'STATIC_DIR = Path(__file__).parent / "static"\n'
            'if STATIC_DIR.exists(): app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")\n\n'
            '@app.get("/")\n'
            'def serve(): p = STATIC_DIR / "index.html"; return FileResponse(p) if p.exists() else {"app": "Expense Tracker"}\n\n'
            '@app.get("/api/health")\n'
            'def health(): return {"status": "ok", "app": "expense_tracker", "version": "1.0.0"}\n\n'
            '@app.get("/api/summary", response_model=SummaryOut)\n'
            'def summary(db: sqlite3.Connection = Depends(get_db)):\n'
            '    c = db.cursor()\n'
            '    c.execute("SELECT type, SUM(amount) as s, COUNT(*) as c FROM expenses GROUP BY type")\n'
            '    rows = c.fetchall()\n'
            '    inc = sum(r["s"] for r in rows if r["type"] == "income")\n'
            '    exp = sum(r["s"] for r in rows if r["type"] == "expense")\n'
            '    cnt = sum(r["c"] for r in rows)\n'
            '    return {"total_income": inc, "total_expense": exp, "net_balance": inc - exp, "count": cnt}\n\n'
            '@app.get("/api/expenses", response_model=List[ExpenseOut])\n'
            'def list_expenses(db: sqlite3.Connection = Depends(get_db)):\n'
            '    c = db.cursor(); c.execute("SELECT * FROM expenses ORDER BY id DESC")\n'
            '    return [dict(r) for r in c.fetchall()]\n\n'
            '@app.post("/api/expenses", response_model=ExpenseOut, status_code=status.HTTP_201_CREATED)\n'
            'def create_expense(e: ExpenseCreate, db: sqlite3.Connection = Depends(get_db)):\n'
            '    import datetime\n'
            '    dt = e.date or datetime.date.today().isoformat()\n'
            '    c = db.cursor()\n'
            '    c.execute("INSERT INTO expenses (title, amount, category, type, date, notes) VALUES (?, ?, ?, ?, ?, ?)",\n'
            '              (e.title, e.amount, e.category, e.type, dt, e.notes or ""))\n'
            '    db.commit()\n'
            '    c.execute("SELECT * FROM expenses WHERE id = ?", (c.lastrowid,))\n'
            '    return dict(c.fetchone())\n\n'
            '@app.delete("/api/expenses/{item_id}")\n'
            'def delete_expense(item_id: int, db: sqlite3.Connection = Depends(get_db)):\n'
            '    c = db.cursor(); c.execute("DELETE FROM expenses WHERE id = ?", (item_id,))\n'
            '    db.commit(); return {"ok": True, "deleted_id": item_id}\n'
        )

        files["static/index.html"] = (
            '<!DOCTYPE html>\n<html lang="en">\n<head>\n'
            '    <meta charset="UTF-8">\n'
            '    <title>Expense Tracker</title>\n'
            '    <link rel="stylesheet" href="/static/styles.css">\n'
            '</head>\n<body>\n'
            '    <div class="container">\n'
            '        <h1>Personal Finance Tracker</h1>\n'
            '        <div class="kpi-row">\n'
            '            <div class="card kpi"><h3>Income</h3><p id="kpi-income">$0.00</p></div>\n'
            '            <div class="card kpi"><h3>Expenses</h3><p id="kpi-expense">$0.00</p></div>\n'
            '            <div class="card kpi"><h3>Net Balance</h3><p id="kpi-balance">$0.00</p></div>\n'
            '        </div>\n'
            '        <form id="tx-form" class="card form-card">\n'
            '            <input type="text" id="tx-title" placeholder="Description" required>\n'
            '            <input type="number" step="0.01" id="tx-amount" placeholder="Amount" required>\n'
            '            <select id="tx-type"><option value="expense">Expense</option><option value="income">Income</option></select>\n'
            '            <input type="text" id="tx-cat" placeholder="Category (Food, Rent, etc.)">\n'
            '            <button type="submit">Add Record</button>\n'
            '        </form>\n'
            '        <table class="card tx-table">\n'
            '            <thead><tr><th>Date</th><th>Title</th><th>Category</th><th>Amount</th><th>Action</th></tr></thead>\n'
            '            <tbody id="tx-body"></tbody>\n'
            '        </table>\n'
            '    </div>\n'
            '    <script src="/static/app.js"></script>\n'
            '</body>\n</html>\n'
        )

        files["static/styles.css"] = (
            ':root { --bg: #090d16; --card: #131b2e; --text: #f8fafc; --green: #10b981; --red: #f43f5e; --blue: #3b82f6; }\n'
            '* { box-sizing: border-box; margin: 0; padding: 0; font-family: sans-serif; }\n'
            'body { background: var(--bg); color: var(--text); padding: 2rem; }\n'
            '.container { max-width: 800px; margin: 0 auto; display: flex; flex-direction: column; gap: 1.5rem; }\n'
            '.kpi-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; }\n'
            '.card { background: var(--card); border: 1px solid #1e293b; border-radius: 10px; padding: 1.25rem; }\n'
            '.kpi p { font-size: 1.6rem; font-weight: bold; margin-top: 0.5rem; }\n'
            '#kpi-income { color: var(--green); } #kpi-expense { color: var(--red); } #kpi-balance { color: var(--blue); }\n'
            '.form-card { display: flex; gap: 0.5rem; flex-wrap: wrap; }\n'
            'input, select, button { padding: 0.6rem 0.8rem; border-radius: 6px; border: 1px solid #334155; background: #090d16; color: #fff; }\n'
            'button { background: var(--blue); border: none; font-weight: bold; cursor: pointer; }\n'
            '.tx-table { width: 100%; border-collapse: collapse; text-align: left; }\n'
            '.tx-table th, .tx-table td { padding: 0.75rem 1rem; border-bottom: 1px solid #1e293b; }\n'
        )

        files["static/app.js"] = (
            'document.addEventListener("DOMContentLoaded", () => {\n'
            '    async function load() {\n'
            '        const sumRes = await fetch("/api/summary");\n'
            '        const sum = await sumRes.json();\n'
            '        document.getElementById("kpi-income").textContent = `$${sum.total_income.toFixed(2)}`;\n'
            '        document.getElementById("kpi-expense").textContent = `$${sum.total_expense.toFixed(2)}`;\n'
            '        document.getElementById("kpi-balance").textContent = `$${sum.net_balance.toFixed(2)}`;\n'
            '        const listRes = await fetch("/api/expenses");\n'
            '        const list = await listRes.json();\n'
            '        const tbody = document.getElementById("tx-body");\n'
            '        tbody.innerHTML = list.map(item => `\n'
            '            <tr>\n'
            '                <td>${item.date}</td><td>${item.title}</td><td>${item.category}</td>\n'
            '                <td style="color:${item.type===\'income\'?\'#10b981\':\'#f43f5e\'}">${item.type===\'income\'?\'+\':\'-\'}$${item.amount.toFixed(2)}</td>\n'
            '                <td><button onclick="delItem(${item.id})">Delete</button></td>\n'
            '            </tr>\n'
            '        `).join("");\n'
            '    }\n'
            '    window.delItem = async (id) => { await fetch(`/api/expenses/${id}`, { method: "DELETE" }); load(); };\n'
            '    document.getElementById("tx-form").addEventListener("submit", async (e) => {\n'
            '        e.preventDefault();\n'
            '        const payload = {\n'
            '            title: document.getElementById("tx-title").value,\n'
            '            amount: parseFloat(document.getElementById("tx-amount").value),\n'
            '            type: document.getElementById("tx-type").value,\n'
            '            category: document.getElementById("tx-cat").value || "General"\n'
            '        };\n'
            '        await fetch("/api/expenses", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });\n'
            '        e.target.reset(); load();\n'
            '    });\n'
            '    load();\n'
            '});\n'
        )

        files["tests/test_expenses.py"] = (
            '"""Automated test suite for Expense Tracker."""\n'
            'import os, sys\n'
            'from pathlib import Path\n'
            'import pytest\n'
            'from fastapi.testclient import TestClient\n\n'
            'APP_DIR = Path(__file__).resolve().parent.parent\n'
            'if str(APP_DIR) not in sys.path: sys.path.insert(0, str(APP_DIR))\n'
            'os.environ["EXPENSES_DB_PATH"] = str(APP_DIR / "test_expenses.db")\n\n'
            'from main import app\n'
            'from database import init_db\n\n'
            '@pytest.fixture(autouse=True)\n'
            'def setup():\n'
            '    init_db()\n'
            '    yield\n'
            '    f = APP_DIR / "test_expenses.db"\n'
            '    if f.exists(): os.remove(str(f))\n\n'
            'client = TestClient(app)\n\n'
            'def test_health(): assert client.get("/api/health").status_code == 200\n\n'
            'def test_expense_and_summary():\n'
            '    client.post("/api/expenses", json={"title": "Salary", "amount": 5000.0, "type": "income", "category": "Work"})\n'
            '    client.post("/api/expenses", json={"title": "Groceries", "amount": 150.0, "type": "expense", "category": "Food"})\n'
            '    s = client.get("/api/summary").json()\n'
            '    assert s["total_income"] == 5000.0\n'
            '    assert s["total_expense"] == 150.0\n'
            '    assert s["net_balance"] == 4850.0\n'
        )

        files["requirements.txt"] = 'fastapi>=0.100.0\nuvicorn>=0.22.0\npydantic>=2.0.0\npytest>=7.4.0\nhttpx>=0.24.0\n'
        files["README.md"] = '# Expense Tracker\n\nFastAPI + SQLite Personal Finance Tracker.\n'
        return files

    def _scaffold_chat_app(self) -> Dict[str, str]:
        """Scaffolds complete Team Chat & Messaging application."""
        files: Dict[str, str] = {}
        files["database.py"] = (
            'import os, sqlite3; from pathlib import Path\n'
            'DB_PATH = Path(os.environ.get("CHAT_DB_PATH", "chat.db"))\n'
            'def get_db():\n'
            '    c = sqlite3.connect(str(DB_PATH)); c.row_factory = sqlite3.Row\n'
            '    try: yield c\n'
            '    finally: c.close()\n'
            'def init_db():\n'
            '    c = sqlite3.connect(str(DB_PATH))\n'
            '    c.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL, room TEXT NOT NULL DEFAULT \'general\', content TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")\n'
            '    c.commit(); c.close()\n'
        )
        files["models.py"] = (
            'from pydantic import BaseModel, Field\n'
            'class MessageCreate(BaseModel): username: str = Field(..., min_length=1); room: str = "general"; content: str = Field(..., min_length=1)\n'
            'class MessageOut(BaseModel): id: int; username: str; room: str; content: str; created_at: str\n'
        )
        files["main.py"] = (
            'import os, sqlite3; from pathlib import Path; from typing import List\n'
            'from fastapi import FastAPI, Depends, status; from fastapi.middleware.cors import CORSMiddleware; from fastapi.staticfiles import StaticFiles\n'
            'from database import init_db, get_db; from models import MessageCreate, MessageOut\n'
            'app = FastAPI(title="Chat API"); app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]); init_db()\n'
            'STATIC_DIR = Path(__file__).parent / "static"\n'
            'if STATIC_DIR.exists(): app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")\n'
            '@app.get("/api/health")\n'
            'def health(): return {"status": "ok", "app": "chat_app", "version": "1.0.0"}\n'
            '@app.get("/api/messages", response_model=List[MessageOut])\n'
            'def list_msgs(room: str = "general", db: sqlite3.Connection = Depends(get_db)):\n'
            '    c = db.cursor(); c.execute("SELECT * FROM messages WHERE room = ? ORDER BY id ASC", (room,))\n'
            '    return [dict(r) for r in c.fetchall()]\n'
            '@app.post("/api/messages", response_model=MessageOut, status_code=status.HTTP_201_CREATED)\n'
            'def send_msg(m: MessageCreate, db: sqlite3.Connection = Depends(get_db)):\n'
            '    c = db.cursor(); c.execute("INSERT INTO messages (username, room, content) VALUES (?, ?, ?)", (m.username, m.room, m.content))\n'
            '    db.commit(); c.execute("SELECT * FROM messages WHERE id = ?", (c.lastrowid,))\n'
            '    return dict(c.fetchone())\n'
        )
        files["static/index.html"] = '<!DOCTYPE html><html><head><title>Chat Room</title><link rel="stylesheet" href="/static/styles.css"></head><body><h1>Chat Room</h1><div id="msgs"></div><form id="f"><input id="u" placeholder="Name" value="Alice"><input id="m" placeholder="Message"><button>Send</button></form><script src="/static/app.js"></script></body></html>'
        files["static/styles.css"] = 'body{background:#0f172a;color:#fff;padding:2rem;font-family:sans-serif;}#msgs{height:300px;overflow-y:auto;border:1px solid #334155;padding:1rem;margin-bottom:1rem;}'
        files["static/app.js"] = 'document.getElementById("f").onsubmit=async(e)=>{e.preventDefault();await fetch("/api/messages",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({username:document.getElementById("u").value,content:document.getElementById("m").value})});document.getElementById("m").value="";load();};async function load(){const r=await fetch("/api/messages");const d=await r.json();document.getElementById("msgs").innerHTML=d.map(m=>`<div><b>${m.username}:</b> ${m.content}</div>`).join("");}load();'
        files["tests/test_chat.py"] = (
            'import os, sys; from pathlib import Path; from fastapi.testclient import TestClient\n'
            'APP_DIR = Path(__file__).resolve().parent.parent\n'
            'if str(APP_DIR) not in sys.path: sys.path.insert(0, str(APP_DIR))\n'
            'os.environ["CHAT_DB_PATH"] = str(APP_DIR / "test_chat.db")\n'
            'from main import app; from database import init_db\n'
            'init_db(); client = TestClient(app)\n'
            'def test_health(): assert client.get("/api/health").status_code == 200\n'
            'def test_send(): r = client.post("/api/messages", json={"username": "Alice", "content": "Hi"}); assert r.status_code == 201\n'
        )
        files["requirements.txt"] = 'fastapi>=0.100.0\nuvicorn>=0.22.0\npydantic>=2.0.0\npytest>=7.4.0\nhttpx>=0.24.0\n'
        files["README.md"] = '# Chat App\n\nFastAPI + SQLite Chat Room.\n'
        return files

    def _scaffold_contacts_app(self) -> Dict[str, str]:
        """Scaffolds complete Contact Directory application."""
        files: Dict[str, str] = {}
        files["database.py"] = (
            'import os, sqlite3; from pathlib import Path\n'
            'DB_PATH = Path(os.environ.get("CONTACTS_DB_PATH", "contacts.db"))\n'
            'def get_db():\n'
            '    c = sqlite3.connect(str(DB_PATH)); c.row_factory = sqlite3.Row\n'
            '    try: yield c\n'
            '    finally: c.close()\n'
            'def init_db():\n'
            '    c = sqlite3.connect(str(DB_PATH))\n'
            '    c.execute("CREATE TABLE IF NOT EXISTS contacts (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT NOT NULL, phone TEXT DEFAULT \'\', company TEXT DEFAULT \'\', category TEXT DEFAULT \'Personal\', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")\n'
            '    c.commit(); c.close()\n'
        )
        files["models.py"] = (
            'from pydantic import BaseModel, Field\n'
            'class ContactCreate(BaseModel): name: str = Field(..., min_length=1); email: str = Field(..., min_length=1); phone: str = ""; company: str = ""; category: str = "Personal"\n'
            'class ContactOut(BaseModel): id: int; name: str; email: str; phone: str; company: str; category: str; created_at: str\n'
        )
        files["main.py"] = (
            'import os, sqlite3; from pathlib import Path; from typing import List\n'
            'from fastapi import FastAPI, Depends, status; from fastapi.middleware.cors import CORSMiddleware; from fastapi.staticfiles import StaticFiles\n'
            'from database import init_db, get_db; from models import ContactCreate, ContactOut\n'
            'app = FastAPI(title="Contacts API"); app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]); init_db()\n'
            'STATIC_DIR = Path(__file__).parent / "static"\n'
            'if STATIC_DIR.exists(): app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")\n'
            '@app.get("/api/health")\n'
            'def health(): return {"status": "ok", "app": "contacts_app", "version": "1.0.0"}\n'
            '@app.get("/api/contacts", response_model=List[ContactOut])\n'
            'def list_contacts(db: sqlite3.Connection = Depends(get_db)):\n'
            '    c = db.cursor(); c.execute("SELECT * FROM contacts ORDER BY name ASC")\n'
            '    return [dict(r) for r in c.fetchall()]\n'
            '@app.post("/api/contacts", response_model=ContactOut, status_code=status.HTTP_201_CREATED)\n'
            'def add_contact(co: ContactCreate, db: sqlite3.Connection = Depends(get_db)):\n'
            '    c = db.cursor(); c.execute("INSERT INTO contacts (name, email, phone, company, category) VALUES (?, ?, ?, ?, ?)", (co.name, co.email, co.phone, co.company, co.category))\n'
            '    db.commit(); c.execute("SELECT * FROM contacts WHERE id = ?", (c.lastrowid,))\n'
            '    return dict(c.fetchone())\n'
            '@app.delete("/api/contacts/{cid}")\n'
            'def del_contact(cid: int, db: sqlite3.Connection = Depends(get_db)):\n'
            '    c = db.cursor(); c.execute("DELETE FROM contacts WHERE id = ?", (cid,)); db.commit(); return {"ok": True}\n'
        )
        files["static/index.html"] = '<!DOCTYPE html><html><head><title>Contacts</title><link rel="stylesheet" href="/static/styles.css"></head><body><h1>Contacts Directory</h1><ul id="list"></ul><script src="/static/app.js"></script></body></html>'
        files["static/styles.css"] = 'body{background:#0b0f19;color:#fff;padding:2rem;font-family:sans-serif;}'
        files["static/app.js"] = 'async function load(){const r=await fetch("/api/contacts");const d=await r.json();document.getElementById("list").innerHTML=d.map(c=>`<li>${c.name} (${c.email}) - ${c.company}</li>`).join("");}load();'
        files["tests/test_contacts.py"] = (
            'import os, sys; from pathlib import Path; from fastapi.testclient import TestClient\n'
            'APP_DIR = Path(__file__).resolve().parent.parent\n'
            'if str(APP_DIR) not in sys.path: sys.path.insert(0, str(APP_DIR))\n'
            'os.environ["CONTACTS_DB_PATH"] = str(APP_DIR / "test_contacts.db")\n'
            'from main import app; from database import init_db\n'
            'init_db(); client = TestClient(app)\n'
            'def test_health(): assert client.get("/api/health").status_code == 200\n'
            'def test_add(): r = client.post("/api/contacts", json={"name": "Alice", "email": "alice@example.com"}); assert r.status_code == 201\n'
        )
        files["requirements.txt"] = 'fastapi>=0.100.0\nuvicorn>=0.22.0\npydantic>=2.0.0\npytest>=7.4.0\nhttpx>=0.24.0\n'
        files["README.md"] = '# Contacts App\n\nFastAPI + SQLite Contact Directory.\n'
        return files

    def _scaffold_ecommerce_app(self) -> Dict[str, str]:
        """Scaffolds complete E-Commerce & Product Catalog application."""
        files: Dict[str, str] = {}
        files["database.py"] = (
            'import os, sqlite3; from pathlib import Path\n'
            'DB_PATH = Path(os.environ.get("SHOP_DB_PATH", "shop.db"))\n'
            'def get_db():\n'
            '    c = sqlite3.connect(str(DB_PATH)); c.row_factory = sqlite3.Row\n'
            '    try: yield c\n'
            '    finally: c.close()\n'
            'def init_db():\n'
            '    c = sqlite3.connect(str(DB_PATH))\n'
            '    c.execute("CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, description TEXT DEFAULT \'\', price REAL NOT NULL, stock INTEGER NOT NULL DEFAULT 0, category TEXT DEFAULT \'General\', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")\n'
            '    c.commit(); c.close()\n'
        )
        files["models.py"] = (
            'from pydantic import BaseModel, Field\n'
            'class ProductCreate(BaseModel): name: str = Field(..., min_length=1); description: str = ""; price: float = Field(..., gt=0); stock: int = 0; category: str = "General"\n'
            'class ProductOut(BaseModel): id: int; name: str; description: str; price: float; stock: int; category: str; created_at: str\n'
        )
        files["main.py"] = (
            'import os, sqlite3; from pathlib import Path; from typing import List\n'
            'from fastapi import FastAPI, Depends, status; from fastapi.middleware.cors import CORSMiddleware; from fastapi.staticfiles import StaticFiles\n'
            'from database import init_db, get_db; from models import ProductCreate, ProductOut\n'
            'app = FastAPI(title="Storefront API"); app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]); init_db()\n'
            'STATIC_DIR = Path(__file__).parent / "static"\n'
            'if STATIC_DIR.exists(): app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")\n'
            '@app.get("/api/health")\n'
            'def health(): return {"status": "ok", "app": "ecommerce_app", "version": "1.0.0"}\n'
            '@app.get("/api/products", response_model=List[ProductOut])\n'
            'def list_products(db: sqlite3.Connection = Depends(get_db)):\n'
            '    c = db.cursor(); c.execute("SELECT * FROM products ORDER BY id DESC")\n'
            '    return [dict(r) for r in c.fetchall()]\n'
            '@app.post("/api/products", response_model=ProductOut, status_code=status.HTTP_201_CREATED)\n'
            'def add_product(p: ProductCreate, db: sqlite3.Connection = Depends(get_db)):\n'
            '    c = db.cursor(); c.execute("INSERT INTO products (name, description, price, stock, category) VALUES (?, ?, ?, ?, ?)", (p.name, p.description, p.price, p.stock, p.category))\n'
            '    db.commit(); c.execute("SELECT * FROM products WHERE id = ?", (c.lastrowid,))\n'
            '    return dict(c.fetchone())\n'
            '@app.delete("/api/products/{pid}")\n'
            'def del_product(pid: int, db: sqlite3.Connection = Depends(get_db)):\n'
            '    c = db.cursor(); c.execute("DELETE FROM products WHERE id = ?", (pid,)); db.commit(); return {"ok": True}\n'
        )
        files["static/index.html"] = '<!DOCTYPE html><html><head><title>Storefront</title><link rel="stylesheet" href="/static/styles.css"></head><body><h1>Online Store</h1><div id="catalog"></div><script src="/static/app.js"></script></body></html>'
        files["static/styles.css"] = 'body{background:#0b0f19;color:#fff;padding:2rem;font-family:sans-serif;}#catalog{display:grid;grid-template-columns:repeat(auto-fill, minmax(200px, 1fr));gap:1rem;}'
        files["static/app.js"] = 'async function load(){const r=await fetch("/api/products");const d=await r.json();document.getElementById("catalog").innerHTML=d.map(p=>`<div style="border:1px solid #334155;padding:1rem;border-radius:8px;"><h3>${p.name}</h3><p>$${p.price.toFixed(2)}</p><p>Stock: ${p.stock}</p></div>`).join("");}load();'
        files["tests/test_ecommerce.py"] = (
            'import os, sys; from pathlib import Path; from fastapi.testclient import TestClient\n'
            'APP_DIR = Path(__file__).resolve().parent.parent\n'
            'if str(APP_DIR) not in sys.path: sys.path.insert(0, str(APP_DIR))\n'
            'os.environ["SHOP_DB_PATH"] = str(APP_DIR / "test_shop.db")\n'
            'from main import app; from database import init_db\n'
            'init_db(); client = TestClient(app)\n'
            'def test_health(): assert client.get("/api/health").status_code == 200\n'
            'def test_add_prod(): r = client.post("/api/products", json={"name": "Widget", "price": 19.99, "stock": 10}); assert r.status_code == 201\n'
        )
        files["requirements.txt"] = 'fastapi>=0.100.0\nuvicorn>=0.22.0\npydantic>=2.0.0\npytest>=7.4.0\nhttpx>=0.24.0\n'
        files["README.md"] = '# Storefront App\n\nFastAPI + SQLite Product Catalog.\n'
        return files

    def _scaffold_custom_app(self, arch: Dict[str, Any]) -> Dict[str, str]:
        """Scaffolds complete Custom Domain application."""
        slug = arch["slug"]
        table = arch["db_table"]
        name = arch["name"]
        files: Dict[str, str] = {}
        files["database.py"] = (
            f'import os, sqlite3; from pathlib import Path\n'
            f'DB_PATH = Path(os.environ.get("APP_DB_PATH", "{slug}.db"))\n'
            f'def get_db():\n'
            f'    c = sqlite3.connect(str(DB_PATH)); c.row_factory = sqlite3.Row\n'
            f'    try: yield c\n'
            f'    finally: c.close()\n'
            f'def init_db():\n'
            f'    c = sqlite3.connect(str(DB_PATH))\n'
            f'    c.execute("CREATE TABLE IF NOT EXISTS {table} (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, description TEXT DEFAULT \'\', category TEXT DEFAULT \'General\', status TEXT DEFAULT \'active\', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")\n'
            f'    c.commit(); c.close()\n'
        )
        files["models.py"] = (
            'from pydantic import BaseModel, Field\n'
            'class ItemCreate(BaseModel): name: str = Field(..., min_length=1); description: str = ""; category: str = "General"; status: str = "active"\n'
            'class ItemOut(BaseModel): id: int; name: str; description: str; category: str; status: str; created_at: str\n'
        )
        files["main.py"] = (
            f'import os, sqlite3; from pathlib import Path; from typing import List\n'
            f'from fastapi import FastAPI, Depends, status; from fastapi.middleware.cors import CORSMiddleware; from fastapi.staticfiles import StaticFiles\n'
            f'from database import init_db, get_db; from models import ItemCreate, ItemOut\n'
            f'app = FastAPI(title="{name} API"); app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]); init_db()\n'
            f'STATIC_DIR = Path(__file__).parent / "static"\n'
            f'if STATIC_DIR.exists(): app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")\n'
            f'@app.get("/api/health")\n'
            f'def health(): return {{"status": "ok", "app": "{slug}_app", "version": "1.0.0"}}\n'
            f'@app.get("/api/items", response_model=List[ItemOut])\n'
            f'def list_items(db: sqlite3.Connection = Depends(get_db)):\n'
            f'    c = db.cursor(); c.execute("SELECT * FROM {table} ORDER BY id DESC")\n'
            f'    return [dict(r) for r in c.fetchall()]\n'
            f'@app.post("/api/items", response_model=ItemOut, status_code=status.HTTP_201_CREATED)\n'
            f'def add_item(it: ItemCreate, db: sqlite3.Connection = Depends(get_db)):\n'
            f'    c = db.cursor(); c.execute("INSERT INTO {table} (name, description, category, status) VALUES (?, ?, ?, ?)", (it.name, it.description, it.category, it.status))\n'
            f'    db.commit(); c.execute("SELECT * FROM {table} WHERE id = ?", (c.lastrowid,))\n'
            f'    return dict(c.fetchone())\n'
            f'@app.delete("/api/items/{{item_id}}")\n'
            f'def del_item(item_id: int, db: sqlite3.Connection = Depends(get_db)):\n'
            f'    c = db.cursor(); c.execute("DELETE FROM {table} WHERE id = ?", (item_id,)); db.commit(); return {{"ok": True}}\n'
        )
        files["static/index.html"] = f'<!DOCTYPE html><html><head><title>{name}</title><link rel="stylesheet" href="/static/styles.css"></head><body><h1>{name}</h1><div id="list"></div><script src="/static/app.js"></script></body></html>'
        files["static/styles.css"] = 'body{background:#0b0f19;color:#fff;padding:2rem;font-family:sans-serif;}#list{display:flex;flex-direction:column;gap:0.75rem;}'
        files["static/app.js"] = 'async function load(){const r=await fetch("/api/items");const d=await r.json();document.getElementById("list").innerHTML=d.map(i=>`<div style="border:1px solid #334155;padding:1rem;border-radius:6px;"><b>${i.name}</b> (${i.category}) - ${i.status}</div>`).join("");}load();'
        files["tests/test_app.py"] = (
            f'import os, sys; from pathlib import Path; from fastapi.testclient import TestClient\n'
            f'APP_DIR = Path(__file__).resolve().parent.parent\n'
            f'if str(APP_DIR) not in sys.path: sys.path.insert(0, str(APP_DIR))\n'
            f'os.environ["APP_DB_PATH"] = str(APP_DIR / "test_{slug}.db")\n'
            f'from main import app; from database import init_db\n'
            f'init_db(); client = TestClient(app)\n'
            f'def test_health(): assert client.get("/api/health").status_code == 200\n'
            f'def test_create(): r = client.post("/api/items", json={{"name": "Test Entry", "description": "Automated test"}}); assert r.status_code == 201\n'
        )
        files["requirements.txt"] = 'fastapi>=0.100.0\nuvicorn>=0.22.0\npydantic>=2.0.0\npytest>=7.4.0\nhttpx>=0.24.0\n'
        files["README.md"] = f'# {name}\n\nFastAPI + SQLite production service.\n'
        return files
