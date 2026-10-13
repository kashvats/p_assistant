---
name: test-engineering
description: "Write and run automated tests and test plans that prove acceptance criteria - unit, integration and end-to-end - use for QA tasks."
---

# Test engineering

## When to use
A feature must be proven to work, or a QA task asks for tests.

## Steps
1. Turn each acceptance criterion into at least one test case (input, action, expected result), including one failure/edge case.
2. Write automated tests in the project's framework (pytest, node --test, etc.) in the project workspace.
3. Run them with the shell tool. Record the exact command and the real pass/fail output.
4. When a test fails, report the failing case precisely; do not change a test just to make it pass.

## Rules and checks
- A test that was not run is not evidence.
- Never weaken or delete existing tests to get a green result.
