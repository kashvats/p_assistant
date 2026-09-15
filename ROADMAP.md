# Roadmap

## v0.6 — Security guardian

- OS-specific startup/persistence inventory for Windows, Linux and macOS.
- File-integrity baselines for explicitly selected sensitive folders.
- Network baseline learning with false-positive controls.
- Richer process ancestry/signature metadata.
- Optional file/hash reputation provider interface.
- Quarantine restore with provenance and scan status.
- Security posture report covering updates/firewall/AV/disk-encryption signals where safely queryable.
- Never disable security protections or perform offensive scanning against third parties.

## v0.7 — Evaluated self-improvement

- Git branch creation for assistant-core proposals.
- Isolated evaluation sandbox.
- Automatic unit tests/lint/benchmark before review.
- Before/after result report and explicit promotion step.
- Deterministic rollback.
- No candidate may replace the running security boundary before explicit approval.

## v0.8 — Connected personal layer

- Capability-scoped provider implementations for email/calendar/files/contact systems.
- Draft-first email behavior; send requires explicit permission.
- Calendar conflict detection and proposal-first rescheduling.
- Connector audit logs and token-scope inspection.
- Optional wake-word detector using a tiny dedicated local model.

## Later

- Authenticated LAN/mobile companion pairing.
- Accessibility-based desktop automation with strict per-app scopes.
- Optional local vision only on capable hardware.
- Signed plugin manifests and capability-scoped plugin permissions.
