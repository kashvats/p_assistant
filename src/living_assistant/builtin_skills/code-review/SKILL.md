---
name: code-review
description: Review code or a change for bugs, security problems and readability, and suggest concrete fixes - use for "review this", "what's wrong with this code", or before merging.
---

# Code review

## When to use
The user shares code, a file, a diff or a project folder and wants it reviewed or checked for bugs.

## Steps
1. Read the code (and the files it calls if needed) before commenting. For a project, start with the files the user names.
2. Look for, in this order: bugs that give wrong results or crash, security problems (injection, secrets in code, unsafe input handling), missing error handling at boundaries, then readability and duplication.
3. Report findings most severe first. For each: file and line, what goes wrong with a concrete example input, and the fix (a small code snippet).
4. End with what is good about the code, briefly.
5. Offer to apply the fixes; file changes ask for approval.

## Rules and checks
- Only report problems you can explain with a concrete failing case; mark guesses as "possible".
- Do not rewrite working code just for style.
