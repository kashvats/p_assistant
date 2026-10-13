---
name: security-review
description: "Review software for security weaknesses - injection, auth, secrets, unsafe input, dependencies - and give concrete fixes - use for security tasks and before delivery."
---

# Security review

## When to use
Before a delivery, or when a task asks for a security check.

## Steps
1. Read the code paths that take outside input: forms, APIs, files, command lines.
2. Check: injection (SQL, shell, HTML), authentication and authorization, secrets in code or logs, unsafe file paths, error messages that leak internals, and outdated or unnecessary dependencies.
3. For each finding give file and line, a concrete attack example, severity, and the fix.
4. Re-check after fixes are applied.

## Rules and checks
- Only report issues with a concrete exploit path; mark theoretical ones as low.
- Never test against systems the user does not own.
