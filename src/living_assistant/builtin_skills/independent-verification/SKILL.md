---
name: independent-verification
description: "Independently verify someone else's work against its acceptance criteria using real evidence (files, commands, test output) and give a pass/fail verdict - use when verifying or reviewing a deliverable."
---

# Independent verification

## When to use
You are the verifier for a task you did not do.

## Steps
1. Read the task's acceptance criteria and the worker's report, but trust nothing in the report until you have checked it yourself.
2. Open every file the worker says it produced; confirm it exists and contains what the criteria need.
3. Where a criterion can be executed (a program runs, a test passes), run it yourself with the shell tool and read the real output.
4. Check each criterion separately and record: criterion, what you did, what you saw, pass or fail.
5. Verdict: pass only if every criterion passed. Otherwise fail with the exact problems and what would fix them.

## Rules and checks
- Never pass work you could not check; "could not verify" is a fail with a reason.
- Do not fix the work yourself; report what is wrong.
