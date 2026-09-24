# Architecture Decisions

> Record non-obvious architecture decisions and constraints that future agents should not repeatedly rediscover.

---

## ADR-001 — Dual-Engine AI: Jev (System One) + AirLLM (System Two)

**Status:** Active (implemented Sep 2026)

**Context:** AirLLM runs frontier models locally via disk-to-VRAM layer swapping.
It is high-intelligence but low-TPS. Using it for binary decisions (routing,
safety gating, loop-done checks) wastes 1–30 seconds per reflex.

**Decision:** All categorical and binary decisions are offloaded to Jev
(TypeSafe AI), a structured "System One" model with sub-100ms latency.
AirLLM exclusively generates text, code, and JSON payloads.

**Golden Rule:** AirLLM never makes a Yes/No or A/B/C decision. Jev never generates text.

**Affected files:**
- `src/living_assistant/core/typesafe.py` — JevClient (all primitives + mock)
- `src/living_assistant/agents/orchestrator.py` — routing, security gate, loop-breaker
- `src/living_assistant/learning/experience.py` — memory filter (context_for)
- `src/living_assistant/system/daemon.py` — semantic GC on hourly maintenance

**Full spec:** `JEV_ARCHITECTURE.md` in the repository root.

**Live API activation:** Set `TYPESAFE_API_KEY` env var. JevClient auto-switches.

---

## ADR-002 — No Autonomous Merges

**Status:** Active

**Decision:** The self-optimizing loop (AirLLM discovers patterns → Jev links
incidents → AirLLM writes patches) outputs proposals only. The human must
apply them. This prevents model collapse from the AI over-optimizing its own
`skills.py` or conflicting with existing lessons.
