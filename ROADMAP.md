# Roadmap

## v0.8 — Hardened Evaluation + Canary Operations

- Optional Docker/Podman evaluation provider when available.
- Read-only/network-disabled container modes for suitable test suites.
- Per-project canary start with health/SLO observation before replacing the normal process.
- Automatic rollback recommendation when canary health degrades.
- Benchmark history/trends across multiple candidate generations.
- Model/agent evaluation suites so specialist SLM choices can be measured on the user's hardware.

## v0.9 — Real Personal Connectors

- Gmail/mail provider implementation behind the existing connector boundary.
- Google/Microsoft calendar sync behind explicit OAuth scopes.
- Contact/file providers with least-privilege capabilities.
- Draft-before-send workflow by default.
- Scheduled briefings that combine local state with explicitly connected sources.

## v1.0 — Stable Personal Operator

- Native desktop shell/tray experience across Windows/macOS/Linux.
- Stable migration/versioning of local state.
- Signed/plugin capability manifests.
- Backup/restore tooling.
- Evaluation-driven release channel for the assistant itself.
- Long-running reliability and resource-budget tests on 8 GB and 32 GB reference systems.
