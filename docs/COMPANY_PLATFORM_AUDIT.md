# Multi-company platform — audit and plan (2026-10-12)

Audit of the existing assistant before building the multi-company platform. Status labels:
**tested** (covered by tests and seen working in the app), **unverified** (code exists, not proven end to end),
**partial**, **missing**, **unsuitable** (exists but not fit for this purpose).

## Reused as-is

| Component | Where | Status | Role in the platform |
|---|---|---|---|
| Agent runtime (tool loop, streaming, tool routing, approvals) | `agents/orchestrator.py` | tested | Every employee turn runs through it (no second assistant) |
| Tool registry + permission gates (workspace scoping, approvals, shell policy) | `tools/*`, `core/approval.py`, `core/workspace.py` | tested | Employees use the same tools and the same approval rules |
| Skill library (SKILL.md, install/learn, per-skill instructions) | `skills/library.py` | tested | Employee skill portfolios point at real SKILL.md skills |
| Agents, templates, teams, `team_ask` | `experts/` | tested | Employee turns reuse `run_member`-style execution with live events |
| Event bus + activity stream | `core/event_bus.py`, `/activity/stream` | tested | Project/task events for the command center |
| Workspace snapshots (now per project/file) | `system/workspace_snapshots.py` | tested | Recovery points before employee file changes |
| Goal runner (long-running rounds, resume after restart) | `system/goal_runner.py` | tested | Pattern for resumable background execution |

## Existing pieces judged unsuitable

| Component | Finding |
|---|---|
| `agents/software_company/*` (`build_software_project`) | Writes canned project templates (archetype scaffolds, Todo-style) instead of agents doing the work; workflow is in-memory, no persistent employees, tasks or evidence. Kept for compatibility, not used by the platform. |
| `agents/task_graph.py` | Minimal SQLite task list without owners, dependencies or state rules. |
| `agents/custom` (manifest agents) | Works for single agents; no departments/companies. Superseded for this purpose by `experts/` + `companies/`. |

## Missing (built now)

Companies, departments, employees with reporting lines and skill portfolios, company/department/individual skill
libraries, projects with authorized companies and a workspace, project teams, hierarchical tasks with dependencies and
enforced states, evidence-based verification, scheduler, control centers.

## Hardware constraint that shapes the design

One local model (Qwen3-30B-A3B, ~18 GB of 32 GB RAM, ~13 tokens/s) serves every agent. "Employees" are therefore
logical identities (role, skills, reporting line, memory boundary, assignments) that share that backend; the
scheduler runs **one employee turn at a time by default** (configurable). Parallelism is in the plan (tasks that can
run in parallel are marked and scheduled as soon as their dependencies are met), not in simultaneous model calls.

## What was built (2026-10-12)

| Piece | Where | Status |
|---|---|---|
| Persistent store: companies, departments, employees, skill portfolios, projects, tasks, dependencies, records (spec/plan/report), audit events | `companies/store.py` | tested |
| Task state machine (draft → ready → assigned → in progress → review → verification → completed; blocked / failed / needs user input / cancelled); completion only through verification by a different employee with passing evidence | `CompanyStore.transition`, `complete_task` | tested |
| Templates: Software Development Company (14 departments incl. executive office, 22 employees), Research & Content Studio, Office Operations; improvised companies drafted by the model, always given a planner and a verifier | `companies/templates.py`, `CompanyEngine.create_from_description` | tested (model drafting: unit-tested with a fake model only) |
| Operational skills (19 SKILL.md) assigned per employee as core / specialist / supporting; missing skills shown as "learning" | `builtin_skills/` | tested (all load) |
| Planning by the Project Director: spec + plan JSON, validated (unknown departments/dependencies, cycles, paths outside the workspace, missing acceptance criteria) with up to 3 attempts; automatic final end-to-end check task | `CompanyEngine.plan`, `validate_plan` | tested; live run done |
| Scheduler: dependency-aware, one employee turn at a time by default, restart recovery, approval waits | `CompanyEngine.tick`, `start` | tested |
| Evidence: tool calls, files with hashes, deliverable checks, file writes must stay inside the project folder | `collect_evidence` | tested |
| Independent verification: a verifier from Review & Verification (else QA, else anyone else) re-checks every task; a pass without inspecting anything is rejected | `CompanyEngine.verify` | tested |
| Modes: supervised (plan approval), balanced, autonomous (more retries); approvals are never bypassed | `MAX_ATTEMPTS`, `approve_plan` | tested |
| Control centers: companies overview, org chart with skills and workload, project command center (board, task evidence, verification, live timeline, spec/plan/report) | `webui/src/companies_view.js` | checked in the app |
| Chat tools: company_list, company_create, project_start, project_status, project_approve_plan, project_control | `companies/tools.py` | registered; not yet driven from chat |

| Project scope: during an employee's turn every workspace path resolves inside the project folder and anything outside is refused | `core/scope.py`, `Workspace.resolve` | tested |
| Role tool sets: workers get file + shell + web read tools, verifiers read + run only; excluded tools are hard-blocked even when named by the model | `WORKER_TOOLS`, `VERIFIER_TOOLS`, orchestrator `excluded_set` | tested |
| Opt-in "trust commands" per project: ordinary execute/write commands inside the project folder run without asking; network/installs, system, privileged and destructive commands still ask | `tools/shell.py` | tested |
| Product blueprints (blueprint-ecommerce, blueprint-blog) + a runnable stack recipe (web-app-python: Flask + SQLite + pytest in a project venv) given to the director when a request matches | `builtin_skills/`, `CompanyEngine.blueprint_for` | tested (matching); live build in progress |
| Improve an existing project: a project can target a registered project / workspace folder; evidence counts only files changed during the task; no report file is added to the user's project | `start_project(folder=...)` | tested |

Known limits: the small local model (Qwen3-30B-A3B) needs retries and is slow (one employee turn at a time); package
installs always ask the user; Flask/pytest are not installed system-wide, so web projects create their own venv.

## Build order

1. `companies/store.py` — persistent entities and lifecycle (SQLite, versioned config, audit events).
2. `companies/templates/` — Software Development Company (full hierarchy from the spec) and Research Company templates;
   companies can also be created blank or drafted by the model from a description.
3. Operational skills (SKILL.md) for the company's disciplines, assigned per employee as core/specialist/supporting;
   department and company libraries with access checks; loadability validation.
4. `companies/engine.py` — project intake → specification → plan (Project Director) → task graph validation →
   scheduler → employee execution through the orchestrator → independent verification → report.
5. API + Companies / Company / Project command-center pages, all from persisted state and events.
6. Tests for every rule (state transitions, dependencies, cycles, isolation, false completion, restart recovery).
