---
name: requirements-analysis
description: "Turn a vague request into clear requirements, user stories and testable acceptance criteria - use for product/feature definition and scoping."
---

# Requirements analysis

## When to use
A request is broad ("build me an app for X") and someone must decide exactly what will be delivered.

## Steps
1. Identify the users and the main job they need done.
2. Write the must-have requirements as short user stories: "As a <user>, I can <action> so that <benefit>".
3. For each story write acceptance criteria in Given/When/Then form or as a checkable statement.
4. List what is explicitly out of scope, and the assumptions you made.
5. Write the result to the file you were asked for (for example `docs/requirements.md`).

## Rules and checks
- Prefer the smallest scope that solves the stated problem.
- Every requirement must be testable; rewrite any that are not.
- Mark anything you guessed as an assumption so the user can correct it.
