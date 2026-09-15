# Living Assistant v0.3 Architecture

```text
                     User / Tray / Local API
                              │
                              ▼
                    ┌──────────────────┐
                    │   Orchestrator   │
                    └───────┬──────────┘
                            │
          ┌─────────────────┼──────────────────┐
          │                 │                  │
          ▼                 ▼                  ▼
  Deterministic tools   Specialist router   Learned skills
          │                 │
          │            one active SLM
          │                 │
          │       coder / DB / security /
          │       research / planner / general
          │
┌─────────┴─────────────────────────────────────────────┐
│ Policy boundary                                      │
│ workspace roots • approvals • SQL read-only          │
│ shell deny rules • browser approval • quarantine     │
└─────────┬─────────────────────────────────────────────┘
          │
 ┌────────┼───────────┬───────────┬──────────────┐
 ▼        ▼           ▼           ▼              ▼
files    shell      browser      git          desktop
          │                                      │
      projects/groups                     clipboard/screen

                 Low-resource nervous system
 ┌───────────────────────────────────────────────────────┐
 │ reminders • watches • port changes • process crashes │
 │ health checks • bounded restart • notifications      │
 │                         NO LLM                        │
 └───────────────────────────────────────────────────────┘
```

## Model lifecycle

The orchestrator and specialists use a model manager. When the selected physical model changes, the old model is unloaded. The daemon/tray event loop does not require a language model.

## Project groups

A project group is a deterministic ordered list of registered projects. Each project carries its own start command, test command, restart policy and optional health URL. The group controller validates every start command through the deterministic command policy, asks for one approval for the exact plan, and then launches each registered service.

## Coding workflow

Preferred coding path:

```text
inspect files → git status → plan → preview/write diff → tests → git diff → report
```

Substantial changes can use an approval-gated new branch. Commit is also approval-gated and only commits already-staged content; the Git tool does not silently stage everything.

## Desktop trust boundary

Clipboard contents and screen captures are high-value sources of accidental secret disclosure. They are therefore approval-gated even though the actions occur locally. The base package does not require desktop packages; they are an optional extra.

## Browser trust boundary

The Playwright controller launches an isolated browser context rather than attaching to the user's everyday browser profile. Page snapshots are observations, not instructions. Click/fill actions require approval. Browser-managed downloads are disabled; downloads go through the explicit web download/quarantine path instead.

## Download quarantine

Potentially executable files are stored outside approved project workspaces in the local application data quarantine folder. Metadata includes source URL and SHA-256. Release into a workspace requires approval and never implies execution.

## Why deterministic controls live outside the LLM

Prompts are guidance, not enforcement. A compromised website, README, log, database row or model output must not be able to relax security rules. The policy, workspace resolver, approval store, DB read-only check, quarantine and process supervision are normal code paths outside model reasoning.
