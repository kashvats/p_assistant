# Living Assistant v0.5 Architecture

```text
                   ┌─────────────────────────────────────┐
                   │ User / CLI / Tray / Local API       │
                   │ Voice / Browser / Approval Window   │
                   └─────────────────┬───────────────────┘
                                     │
                           intent / approved sensor
                                     │
                   ┌─────────────────▼───────────────────┐
                   │            Orchestrator             │
                   │ tools first • smallest useful SLM   │
                   └──────────┬──────────────┬───────────┘
                              │              │
                    deterministic tools      │ specialist handoff
                              │              │
              ┌───────────────▼──────┐  ┌────▼──────────────┐
              │ Policy / Approvals   │  │ one active SLM     │
              │ outside the model    │  │ normally at a time │
              └───────────────┬──────┘  └───────────────────┘
                              │
  ┌───────────────────────────▼─────────────────────────────────────┐
  │ files • shell • git • DB • web • browser • desktop • voice    │
  │ projects • security • quarantine • improvement proposals       │
  │ calendar • todos • sessions • briefing • personal state        │
  └─────────────────────────────────────────────────────────────────┘

                        PERSONAL OPERATING LAYER
  ┌─────────────────────────────────────────────────────────────────┐
  │ Local calendar        Session history       Connector metadata   │
  │ Todos/reminders       Quiet hours/focus     Morning/evening brief│
  │ Daily/weekly routines Notification queue    Retention/redaction  │
  └──────────────────────────────┬──────────────────────────────────┘
                                 │
                         LOW-RESOURCE NERVOUS SYSTEM
  ┌──────────────────────────────▼──────────────────────────────────┐
  │ project crashes • health checks • file watches • local ports   │
  │ reminders • daily/weekly routines • briefings • queue flush    │
  │ session retention maintenance                                  │
  │                  NO LLM REMAINS LOADED WHILE IDLE              │
  └─────────────────────────────────────────────────────────────────┘
```

## Sleeping agents

Roles are separated from physical model residency. On low/moderate hardware, general/coder/research/security/database/planner roles may share the same quantized SLM with different system prompts. `ModelManager` unloads the old physical model when switching when necessary.

## Personal state and notifications

`PersonalState` persists focus mode and quiet hours. `Notifier` checks this state before native notification delivery. Non-urgent notifications produced during quiet time are stored in a bounded local queue and later flushed; the producer can safely mark a reminder delivered because the queue is durable.

## Calendar and briefings

`CalendarStore` is a local SQLite calendar independent of any cloud provider. `BriefingEngine` combines local calendar events, due/overdue todos, managed-process state, pending approvals and selected recent events. Scheduled briefings are deterministic and do not require model inference.

## Session continuity

`SessionStore` keeps bounded local chat history with configurable retention. The orchestrator receives only a small recent window for a named session. Common credential shapes are redacted before storage. Old assistant text is context, never policy authority.

## Routines

Routines support:

- event triggers;
- interval triggers;
- daily `HH:MM` triggers;
- weekly weekday + `HH:MM` triggers.

`notify` and `todo` actions need no LLM. Model-waking prompt routines are disabled by default; even when enabled, the daemon will not wake a model during focus/quiet mode.

## Connector boundary

`ConnectorRegistry` stores only provider metadata, capability names and an optional environment-variable prefix. It deliberately does not store passwords/tokens. Vendor-specific mail/calendar/files connectors can be added later without changing the orchestrator architecture.

## Sensors, browser and self-improvement

Microphone, clipboard and screenshots remain approval-gated sensitive sensors. Browser profiles remain isolated from the user's normal browser. Self-improvement remains an exact proposal/diff/hash/backup/approval pipeline; deterministic security-policy core files are excluded from automatic application.

## Trust boundary

The LLM is **not** the security boundary. Workspace checks, SQL policy, shell risk, approvals, notification behavior, session retention, browser scope, quarantine and self-modification rules are deterministic code.
