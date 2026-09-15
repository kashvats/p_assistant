# Roadmap

## v0.7 — Evaluated self-improvement

- Assistant-core proposals created on dedicated Git branches.
- Isolated test/evaluation workspace before promotion.
- Automated unit test, lint and task benchmark runs.
- Before/after evaluation report with resource-cost comparison.
- Explicit promotion/merge step and deterministic rollback.
- Security-policy/approval core remains outside automatic promotion.
- Model-router benchmarking so specialist model choices are based on local hardware/task results rather than fixed assumptions.

## v0.8 — Connected personal layer

- Capability-scoped email/calendar/files/contact providers.
- Draft-first email workflow; sending requires explicit permission.
- Calendar conflict detection and proposal-first rescheduling.
- Connector audit log and token-scope inspection.
- Credential storage through OS keychain/secret service rather than config files.
- Optional tiny wake-word detector that wakes STT only after a local trigger.

## v0.9 — Security Guardian expansion

- Optional signed-hash/reputation provider interface.
- OS package/signature trust enrichment for more platforms.
- User-reviewed security allowlists with expiry/review dates.
- Better Windows scheduled-task and service change attribution.
- Optional high-value-folder canary files.
- Security event export compatible with common SIEM/log pipelines.
- Never perform offensive scanning or automatically disable protections.

## Later

- Authenticated LAN/mobile companion pairing.
- Accessibility-based desktop automation with strict per-app scopes.
- Optional local vision only on capable hardware.
- Signed plugin manifests and capability-scoped plugin permissions.
