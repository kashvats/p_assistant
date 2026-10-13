---
name: project-audit
description: "Audit a code project with deterministic checks - health score, syntax errors, security findings, dependency hygiene, SEO of web pages, and which tests exist (optionally run them) - use to review, verify or improve a project, or before delivering one."
---

# Project audit

## When to use
Before delivering or verifying work, when asked to review or improve an existing project, or to check a website's SEO.

## How
Prefer the `project_audit` tool when you have it (read-only, no approval needed):
`project_audit(path=<project folder>)` gives the full report; `check=` narrows it to health, syntax, lint
(incl. dead code), security, deps, seo or checks (which tests exist).

Without the tool, run the script (it prints JSON; the folder defaults to the current directory):
`python "<this skill's folder>/scripts/audit.py" health .`
Other commands: `syntax`, `security`, `deps`, `seo`, `checks`, and `run-checks` (runs the project's tests - it executes
project code, so it asks for approval unless the project is trusted). `health . --run` includes the test run.

## Reading the result
- `score` 0-100 and `dimensions` (tests, security, quality, knowledge, dependencies).
- `findings` are sorted most severe first; each has a category, severity and message (security ones have path + line).
- Fix critical and high findings first; mention medium ones; low/info are suggestions.

## Rules
- Report what the audit found, with the numbers. Never invent findings or claim a check passed that you did not run.
- A static audit does not prove the app works - run the tests (`run-checks`) for that.
