---
name: devops-setup
description: "Make software installable, runnable and testable: dependency files, run scripts, environment config, CI steps - use for infrastructure and developer-experience tasks."
---

# Devops setup

## When to use
A project needs a way to install, run, test or package it.

## Steps
1. Write the dependency file the stack uses (requirements.txt/pyproject, package.json) with pinned versions.
2. Add one obvious way to run it and one to test it (README commands, a script, or a Makefile).
3. Put configuration in environment variables with a documented `.env.example`; never commit secrets.
4. Verify on this machine: install and run the commands, and record their output.

## Rules and checks
- Do not install system-wide software or change system settings; ask the user instead.
- Commands must work on the user's OS (Windows here unless told otherwise).
