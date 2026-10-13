---
name: project-planning
description: "Break a project request into a specification and a dependency-ordered plan of small, verifiable tasks assigned to departments - use when directing a project or planning multi-step work."
---

# Project planning

## When to use
You lead a project (Project Director, department head) or must turn a request into work others can do.

## Steps
1. Restate the goal in one sentence. List the requirements you can see, the assumptions you are making, and the open questions only the user can answer.
2. Look at what already exists in the project workspace before planning new work.
3. Split the work into tasks that one person can finish in one sitting (roughly 1-3 files or one clear result). Each task gets: a short key, a title, a self-contained description, the department that owns it, the tasks it depends on, 1-4 acceptance criteria that can be checked, and the files it should produce.
4. Order by dependency: design before build, build before test. Mark tasks with no dependency between them as parallel.
5. Keep the plan as small as the request allows. A one-file request needs one or two tasks, not ten.

## Rules and checks
- Acceptance criteria must be checkable by someone else ("`python app.py` prints the total", "the README explains setup"), never "works well".
- No circular dependencies; every dependency must name a task in the plan.
- Do not invent requirements the user did not ask for; put them under assumptions.
