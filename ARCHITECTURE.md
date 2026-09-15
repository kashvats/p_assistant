# Living Assistant v0.6 Architecture

```text
                  ┌──────────────────────────────────────┐
                  │ User / CLI / Tray / Local API        │
                  │ Voice / Browser / Approval Window    │
                  └─────────────────┬────────────────────┘
                                    │
                             intent / event
                                    │
                  ┌─────────────────▼────────────────────┐
                  │            Orchestrator              │
                  │ tools first • smallest useful SLM    │
                  └───────────┬─────────────┬────────────┘
                              │             │
                     deterministic tools    │ specialist handoff
                              │             │
              ┌───────────────▼──────┐ ┌────▼──────────────┐
              │ Policy / Approvals   │ │ one active SLM     │
              │ outside model        │ │ normally at a time │
              └───────────────┬──────┘ └───────────────────┘
                              │
  ┌───────────────────────────▼─────────────────────────────────────┐
  │ files • shell • git • DB • web • browser • desktop • voice    │
  │ projects • calendar • sessions • quarantine • improvements     │
  └───────────────────────────┬─────────────────────────────────────┘
                              │
                    SECURITY GUARDIAN LAYER
  ┌───────────────────────────▼─────────────────────────────────────┐
  │ startup/persistence baseline       listener baseline            │
  │ protected-file hashes              process triage/ancestry      │
  │ firewall/AV/encryption posture     quarantine provenance        │
  │ persistent deduplicated findings  approval-gated containment   │
  └───────────────────────────┬─────────────────────────────────────┘
                              │
                     PERSONAL OPERATING LAYER
  ┌───────────────────────────▼─────────────────────────────────────┐
  │ calendar • todos • quiet/focus • briefings • routines          │
  │ sessions • notification queue • connector metadata             │
  └───────────────────────────┬─────────────────────────────────────┘
                              │
                    LOW-RESOURCE NERVOUS SYSTEM
  ┌───────────────────────────▼─────────────────────────────────────┐
  │ project crashes • health checks • file watches • reminders     │
  │ security scans • posture cache • routine/briefing scheduler    │
  │ session retention • notification severity/quiet-hours policy   │
  │                    NO LLM WHILE IDLE                           │
  └─────────────────────────────────────────────────────────────────┘
```

## Security trust model

The LLM is **not** allowed to decide what is trusted. The Security Guardian is deterministic code. It records observations and creates findings; it does not convert a heuristic into a malware verdict.

Three reference types exist:

1. **Startup/persistence baseline** — normalized startup objects plus hashes for selected startup files.
2. **Listener baseline** — local address/port + process/executable identity for listening services.
3. **Integrity baselines** — bounded SHA-256 snapshots of explicitly selected paths.

By default these baselines are **not automatically initialized**. `organism security initialize` is an explicit known-good-state operation. Agent/API baseline mutations require approval because resetting a reference can hide a previous change.

## Findings

`SecurityGuardian` stores findings in SQLite with:

- stable fingerprint;
- kind and severity;
- first/last seen;
- occurrence count;
- open/resolved status;
- structured details.

Repeated polls update an existing finding instead of emitting endless new alerts. If a resolved condition returns, the finding can reopen and alert again.

## Process triage

Process scoring is intentionally explainable. Current signals include temporary/download execution locations, temporary executables opening listeners, encoded PowerShell and selected Office → script-host/LOLBin ancestry.

Only scores above a configured threshold become automatic findings. On-demand inspection can show lower-scoring signals. A score is not proof of maliciousness.

Containment is narrower than observation:

- current-user-owned process only;
- protected critical-process denylist;
- explicit approval;
- graceful terminate only;
- no automatic file deletion or force-kill.

## Posture

Live posture can inspect firewall, endpoint protection and disk encryption using OS-native read-only commands. Slow update/package checks are on-demand. The daemon refreshes normal posture on a slower cadence and stores a cached snapshot used by the dashboard.

Unknown/unavailable tools are not automatically treated as compromise. Only positively identified disabled/off states produce protection findings.

## Quarantine

Downloads first land in a private quarantine location when type/risk rules require it. Persistent provenance strips URL userinfo/query/fragment so signed URLs and tokens are not stored. Quarantined executables are never auto-run. Release remains explicit.

## Personal/privacy layer

Quiet/focus behavior, sessions, reminders and briefings remain independent of security findings. Startup commands and process command lines are redacted for common credential forms before security persistence. Session history uses its own bounded redaction/retention controls.

## Model/resource layer

Security monitoring does not wake an SLM. A security specialist model may be invoked only when the user asks for interpretation or a finding/routine explicitly needs reasoning and policy permits it. ModelManager still keeps normally one physical local model active at a time.
