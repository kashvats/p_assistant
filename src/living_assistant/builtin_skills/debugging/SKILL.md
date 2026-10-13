---
name: debugging
description: "Find and fix the root cause of a bug or failing test by reproducing it, narrowing it down and verifying the fix - use when something is broken."
---

# Debugging

## When to use
A program crashes, a test fails, or the output is wrong.

## Steps
1. Reproduce it: run the failing command and read the full error.
2. Form one hypothesis at a time from the error and the code; check it by reading code or adding a print, not by guessing.
3. Fix the root cause with the smallest change.
4. Re-run the failing command and the related tests; record the before and after output.

## Rules and checks
- Do not hide errors (broad try/except, skipping tests) to make symptoms disappear.
- If you cannot reproduce it, say so and what you tried.
