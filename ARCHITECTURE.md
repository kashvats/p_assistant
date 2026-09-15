# Living Assistant v0.2 Architecture

```text
User / CLI / localhost API / future voice
                  │
                  ▼
            Orchestrator SLM
       plan / tool / delegate / stop
             │              │
             │              └────► sleeping specialist role
             │                      coder / researcher / security
             │                      database / planner / general
             ▼
      Deterministic Policy Engine
    block / allow / request approval
             │
  ┌──────────┼────────────────────────────────────────────┐
  ▼          ▼           ▼          ▼         ▼           ▼
files      shell      projects     web        DB       security
             │
             ▼
     Persistent Process Registry
             ▲
             │
   ┌─────────┴─────────────────────────────────────────────┐
   │              Nervous System (no LLM)                 │
   │ process supervisor | reminders | watches | ports     │
   │ resources | health checks | event store | notify     │
   └───────────────────────────────────────────────────────┘
```

## Resource rule

Only one model should normally be resident. A role may map to the same physical SLM under the lite profile. The model manager unloads a previous model before activating a different one, and the resource manager can refuse a new model load under severe RAM pressure.

## Persistence

Platform-specific application data stores:

- `assistant.sqlite3`: memory, todos, events, approval queue.
- `projects.json`: explicit project registrations and restart policy.
- `managed_processes.json`: commands/PIDs/log metadata for supervised processes.
- `watches.json`: explicitly configured filesystem watches.
- `skills.json`: explicitly confirmed prompt skills.
- `logs/`: supervised process logs.

Secrets remain in environment variables and are not intentionally written to these stores.

## Approval queue

For noninteractive calls, a protected action creates a pending approval keyed by a hash of action + reason + risk. Approving it does not execute the action by itself. When the caller retries the same operation, one matching approved token is consumed. This prevents stale approval IDs from becoming arbitrary execution handles.

## Safe recovery

Auto-restart is allowed only when:

1. the user registered/started that exact command,
2. the process record has `auto_restart=true`,
3. desired state is still `running`,
4. restart attempts remain under `max_restarts`.

The nervous system cannot invent a new recovery command.

## Skills

Skills are user-confirmed prompt additions selected by trigger text. They can influence model reasoning but cannot alter deterministic policy or tool boundaries.
