---
name: backend-development
description: "Implement server-side code, business logic, data access and APIs that actually run, with input validation and error handling - use for backend implementation tasks."
---

# Backend development

## When to use
A task asks for server code, a CLI, business logic, a service or data access.

## Steps
1. Read the architecture/API contract and existing code before writing anything.
2. Implement in small files with clear functions; validate input at the boundaries.
3. Handle errors explicitly; return useful messages without leaking internals.
4. Run it: start the program or run its tests with the shell tool and fix what fails. Record the command and its real output.
5. Report the files you changed and the exact commands that prove it works.

## Rules and checks
- Never claim it runs unless you ran it and saw the output.
- No hardcoded secrets; read them from environment variables.
- Use parameterized queries for databases.
