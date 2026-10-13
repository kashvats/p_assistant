---
name: automation-integration
description: "Connect systems and automate workflows: scripts, schedules, webhooks, file and API integrations - use for integration and automation tasks."
---

# Automation integration

## When to use
Work should happen automatically, or two systems must exchange data.

## Steps
1. Describe the trigger, the input, each step, and the output; note what happens on failure.
2. Implement as a small script or module with logging and clear error messages.
3. Make steps safe to re-run (idempotent): check before creating, never duplicate.
4. Test with a dry run or sample data first and record the result.

## Rules and checks
- Anything that sends messages, spends money or deletes data needs the user's approval.
- Credentials from environment variables or the system's secret store only.
