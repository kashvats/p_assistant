# Changelog

## 0.6.0

- Added cross-platform Security Guardian with persistent startup/persistence and listening-service baselines.
- Baselines are **not silently initialized** by default; `organism security initialize` requires an explicit known-good-state decision.
- Added common Linux/macOS persistence-file hashing so edits to existing startup files can be detected.
- Added protected-file integrity baselines with added/changed/removed detection and bounded hashing.
- Added deterministic process triage, ancestry inspection, connection metadata and configurable automatic alert threshold.
- Added established network-activity summary without offensive scanning.
- Added firewall, antivirus/endpoint-protection and disk-encryption posture checks plus optional update posture.
- Added persistent deduplicated security findings with severity, status, count, first/last seen and reopen behavior.
- Added approval-gated containment for non-critical current-user-owned processes.
- Added executable SHA-256 plus OS signature/package ownership inspection when supported.
- Added richer quarantine provenance, scan history and release history; signed URL queries are stripped before persistence.
- Quarantine release now verifies the current SHA-256 still matches the registered artifact, blocking post-registration tampering.
- Integrity baselines record symlink metadata without hashing through nested symlinks outside the selected tree.
- Startup/persistence text is redacted for common token/password patterns before storage.
- Security baseline changes and finding resolution through agent/API paths require explicit approval.
- Dashboard Security Guardian uses cached posture instead of repeatedly invoking OS security commands.
- Security desktop notifications honor a minimum severity threshold.
- Added Security Guardian/quarantine/workspace modules to the self-improvement protected-core list.
- Expanded regression suite to 61 passing tests.

## 0.5.0

- Added local calendar, deterministic briefings, quiet/focus mode, clock routines, local session continuity, approval UI and connector metadata registry.

## 0.4.0

- Added push-to-talk voice, routines, reviewable self-improvement and persistent isolated browser sessions.

## 0.3.0

- Added Git-aware coding tools, project groups, desktop sensors, browser automation and download quarantine.

## 0.2.0

- Added persistent process supervision, filesystem watches, notifications, approvals and user-confirmed skills.

## 0.1.0

- Initial local-first orchestrator, sleeping specialist agents, tools, memory and hardware profiles.
