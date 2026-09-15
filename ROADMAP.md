# Roadmap after v0.9

The core personal-agent architecture, defensive guardian, evaluated improvement/canary pipeline and past-mistake learning engine are now implemented. The next milestone should be **real-machine validation leading to v1.0**, not another architecture-heavy release.

Recommended v1.0 work:

- run v0.9 daily on Windows/Ubuntu/macOS hardware and collect real failure patterns;
- tune experience confidence/decay from observed behavior;
- polished installer/updater and first-run model/profile setup;
- native desktop task timeline and approval UX;
- connector plugins for email/calendar/cloud files;
- backup/restore/export controls for assistant state;
- release migration tests and crash recovery;
- signed release artifacts where practical.

# Roadmap

## Current: v0.8 — Hardened Evaluation + Canary Operations

The core local assistant now has sleeping specialist agents, project supervision, desktop/browser/voice foundations, personal operating features, defensive endpoint monitoring, measured self-improvement, optional container-restricted evaluation and canary gates.

## v0.9 — Real-world integration & UX hardening

- Production Gmail/Outlook and Google/Microsoft calendar provider implementations.
- Native desktop approval/task center instead of the minimal Tk/web UI.
- Better project templates for Python/Node/Java/Docker stacks.
- Canary adapters for multi-service Compose applications.
- Signed connector/plugin manifests and granular capability permissions.
- Improved secrets provider/keychain integration.
- Structured audit export and backup/restore of assistant state.

## Later

- Optional wake word on capable systems.
- Dedicated VM execution provider for genuinely untrusted code.
- Multi-machine/remote worker architecture with explicit pairing.
- Evaluation datasets for choosing the best local specialist model per hardware profile.
