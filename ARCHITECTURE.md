# Architecture

```text
┌──────────────────────────────────────────────────────────┐
│ User / Local API / Future Voice / Future Desktop UI     │
└────────────────────────┬─────────────────────────────────┘
                         │
                   Intent / Event
                         │
┌────────────────────────▼─────────────────────────────────┐
│ Orchestrator                                              │
│ plan → choose tool/agent → policy check → observe → stop │
└──────────────┬───────────────────────────┬───────────────┘
               │                           │
       deterministic tools          Specialist Router
               │                           │
    ┌──────────▼─────────┐        ┌────────▼────────┐
    │ Policy / Approvals │        │ one active SLM │
    └──────────┬─────────┘        └───────┬─────────┘
               │                          │
 ┌─────────────▼────────────────┐  coder/research/security/
 │ files/shell/projects/web/db  │  database/planner personas
 └──────────────────────────────┘
               ▲
               │
┌──────────────┴───────────────────────────────────────────┐
│ Nervous System: reminders, resource checks, port changes │
│ deterministic, low-resource, no always-on LLM            │
└──────────────────────────────────────────────────────────┘
```

## Why personas before many physical models?

On a laptop, model weight residency is usually more expensive than a specialist prompt. A 0.8B/2B/4B base model can serve multiple roles using role prompts. If later benchmarks prove a dedicated coder/security model is better on the available hardware, the role can point to a different runtime model without changing the agent architecture.

## Trust boundary

The model is not the security boundary. `PolicyEngine` is.

External text is always observation data, never authority. The model may propose actions; tools enforce roots, query type, timeout, approval, and explicit deny rules.
