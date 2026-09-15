# Living Assistant v0.7 Architecture

```text
                         User / Voice / API / Tray
                                  │
                                  ▼
                         ┌─────────────────┐
                         │  Orchestrator   │
                         └───────┬─────────┘
                                 │
                ┌────────────────┼────────────────┐
                │                │                │
        deterministic tools   specialists     personal layer
                │                │                │
                ▼                ▼                ▼
        files/projects/db    sleeping SLMs   calendar/routines
        browser/security                    focus/briefings
                │
                ▼
      ┌───────────────────────────────┐
      │ Evaluated Self-Improvement    │
      │ proposal → evaluate → promote │
      └───────────────┬───────────────┘
                      │
          ┌───────────┴───────────┐
          ▼                       ▼
    baseline worktree       candidate worktree
        @ BASE                @ candidate commit
          │                       │
          └────── measurements ───┘
                      │
                regression gates
                      │
                approval boundary
                      │
                      ▼
                 active checkout
```

## Nervous system

The daemon remains deterministic and low-resource. It monitors reminders, routines, projects, filesystem watches, security baselines and posture without keeping an LLM loaded.

## Model layer

One specialist model is normally active at a time. Roles can share the same physical SLM on small hardware. The model proposes and reasons; deterministic tools enforce workspace, security, DB and approval boundaries.

## Evaluation layer

`EvaluationStore` persists reusable suites and immutable evaluation reports in SQLite.

`EvaluationEngine` resolves a proposal, constructs an exact command plan, requests approval, creates isolated repository states, runs checks, records measurements, calculates gates and controls promotion/rollback.

### Git mode

```text
repo clean @ base SHA
   │
   ├── detached baseline worktree
   │
   └── candidate branch/worktree
             │
             └── exact proposal committed
```

The candidate branch survives worktree cleanup. Promotion verifies the branch tip still equals the candidate SHA and merges the SHA itself.

### Copy mode

Non-Git projects use bounded baseline/candidate copies under the assistant data directory. This has weaker reproducibility and no immutable commit identity, so Git mode is preferred.

## Approval boundaries

Separate approval classes include:

- `SELF_EVALUATION`: run exact local evaluation commands;
- `SELF_PROMOTION`: modify the active repository after a passing report;
- `SELF_PROMOTION_ROLLBACK`: create a Git revert;
- `SELF_EVALUATION_CLEANUP`: delete an isolated evaluation branch.

Approval for one class does not authorize another.

## Resource adaptation

Evaluation repetitions are profile-aware:

- lite: 1 measured run, no warmup;
- balanced: 3 measured runs, 1 warmup;
- power: 5 measured runs, 1 warmup.

An available-RAM floor is checked before evaluation starts.

## Security boundary

`security_policy.py`, `security_guardian.py`, `approval.py`, `improvements.py`, `evaluation.py`, `workspace.py`, `quarantine.py` and `assistant.yaml` are protected from automatic proposal application/promotion.

External content remains untrusted observation data. Evaluation commands are not taken as trusted merely because they appear in a proposal; the exact plan is approval-gated.
