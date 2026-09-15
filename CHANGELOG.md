# Changelog

## 0.3.0 — Desktop Operator

- Added optional clipboard read/write tools with explicit approval.
- Added optional cross-platform desktop screenshots with explicit approval.
- Added optional system tray process.
- Added optional Playwright browser snapshots and approval-gated click/fill operations.
- Browser automation disabled by default for the `lite` profile.
- Added Git status/diff/log tools and approval-gated branch/commit operations.
- File writes now return a unified diff; added non-mutating `preview_write_file`.
- Added project groups for multi-service applications.
- Added download quarantine for executable/script-like files and dangerous MIME types.
- Quarantine records source URL, file size and SHA-256; release requires approval.
- Expanded local dashboard with project groups, quarantine state and interactive approval cards.
- Added `/groups` and `/quarantine` API endpoints.
- Added `project test`, `group`, `git`, `desktop`, `quarantine` and `tray` CLI surfaces.
- Added v0.3 threat-model controls and tests.

## 0.2.0 — Nervous System

- Persistent process supervision and logs.
- Bounded automatic restart and health checks.
- Filesystem watches and native notifications.
- Persistent approval queue.
- User-confirmed reusable skills.
- Lightweight daemon behavior.
