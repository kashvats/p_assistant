# Living Assistant — Capabilities Status Inventory

**Generated:** 2026-09-24
**Operating Environment:** Windows (Portable to Ubuntu/Linux)
**Target Hardware Constraints:** 4 GB VRAM / 32 GB RAM (Strict single-resident inference model)
**Live Tool Surface:** 154 Active Tools | **FastAPI Endpoints:** 149 Verified Routes

---

## 🟢 1. WORKING CAPABILITIES (Verified & Operational)

### A. Orchestration, Reasoning & Specialists
- **Central ReAct Orchestrator (`src/living_assistant/agents/orchestrator.py`):**
  - **Dynamic Tool Routing:** Uses BM25 lexical ranking and fuzzy matching over tool schemas to dynamically expose compact tool sets per turn, preventing context blowout on local models.
  - **Dynamic Capability Discovery (`tool_catalog_search`):** Internal tool allowing model to search and expose unmapped tools mid-run.
  - **Step Ceiling & Telemetry:** Configurable step ceilings (`max_tool_steps`), character-bounded session history, and latency/token telemetry.
- **Specialist Router (`src/living_assistant/agents/agents.py`):**
  - 6 specialist roles with bounded concurrency semaphore and hardware resource checking:
    1. `general` — practical assistance & routing.
    2. `coder` — code analysis, AST patching, test verification.
    3. `researcher` — fact verification, citations, evidence extraction.
    4. `security` — process triage, network containment, vulnerability analysis.
    5. `database` — SQL queries, schema inspection, integrity checks.
    6. `planner` — milestone decomposition and DAG planning.

### B. Custom Skills Workflow System (`FEAT-19`)
- **Restricted AST Condition Evaluator (`src/living_assistant/skills/evaluator.py`):**
  - Declarative step `when` conditions evaluated safely via Python `ast` visitor without `eval`. Function calls, lambdas, and statements prohibited.
  - DAG cycle validator and typed recursive variable interpolation (`{{var}}`).
- **Cryptographic Package Snapshots (`src/living_assistant/skills/package.py`):**
  - Bundles located in `~/.living_assistant/skills/<id>/` (`manifest.json`, `SKILL.md`, `examples/`, `tests/`).
  - Deterministic SHA-256 package hashing. Immutable version snapshots created under `_snapshots/` upon activation.
  - Zip export and safe zip import (zip-slip prevention, 10MB uncompressed limit).
- **Crash Recovery & Conflict-Aware Undo (`src/living_assistant/skills/store.py`, `adapters.py`):**
  - Durable action logging in SQLite (`skill_action_records`) tracking planned, started, succeeded, and failed actions.
  - Mid-workflow crash recovery via `reconcile_execution()`.
  - Conflict-aware file rollback via `undo_execution()` (checks post-run modifications and destination occupancy).
- **Out-of-Model Security Guard (`src/living_assistant/skills/guards.py`):**
  - Deterministic workspace boundary confinement; raises `SkillPermissionViolation`.
  - Hard denial for policy files (`security_policy.py`, `approval.py`, `.git/`).
- **Document & Invoice Extraction (`src/living_assistant/skills/extractor.py`):**
  - Docling integration with native text/PDF/HTML fallback. Mathematical invoice validation (`subtotal + tax == total`).
- **Built-in Working Reference Skills:**
  1. `daily-briefing` — Combines calendar, pending todos, and system status into morning/evening reports.
  2. `downloads-organizer` — Scans downloads folder, extracts metadata, categorizes with collision avoidance.
  3. `invoice-organizer` — Extracts invoice amounts, validates math, categorizes by vendor/month.

### C. Custom Agent Creation & Governance (`FEAT-20`)
- **Versioned Agent Manifest Schema (`src/living_assistant/agents/custom/manifest.py`):**
  - `AgentManifest`, `AgentLimits`, `AgentDelegationPolicy`, `AgentMemoryScope`, `AgentModelPreference`.
  - Deterministic cryptographic permission hashing (`permission_hash()`).
- **Agent Package Bundles (`src/living_assistant/agents/custom/package.py`):**
  - Bundles stored in `~/.living_assistant/agents/<id>/` (`AGENT.md`, `manifest.json`, `examples/`, `tests/`).
  - Deterministic SHA-256 package hashing, immutable snapshots, zip export/import.
- **SQLite Agent Lifecycle & Metrics Store (`src/living_assistant/agents/custom/store.py`):**
  - Tables: `agent_lifecycle`, `agent_versions`, `agent_executions`, `agent_action_records`, `agent_memory_entries`.
  - State machine: `DRAFT`, `ACTIVE`, `DISABLED`, `ARCHIVED`.
  - Live disk tampering detection: automatically demotes tampered active agents to `DRAFT`.
- **Scoped Memory Namespaces (`src/living_assistant/agents/custom/memory.py`):**
  - Read/write access isolation across `working` (per-run volatile), `agent_notes` (per-agent persistent SQLite), `project_knowledge`, and `user_memory`.
  - Unauthorized namespace access raises `MemoryScopeViolation`.
- **Controlled Delegation Coordinator (`src/living_assistant/agents/custom/delegation.py`):**
  - Enforces permission inheritance (child agent cannot exceed parent tools or skills).
  - Recursion depth limit enforcement (`max_delegation_depth`).
  - Yields inference locks during delegation to maintain single-resident 4GB VRAM constraint.
- **Natural-Language Agent Creator (`src/living_assistant/agents/custom/creator.py`):**
  - Automatically infers role, capabilities, tools, and skills from natural-language descriptions with heuristic fallback.
- **Bounded Executor & Loop Detector (`src/living_assistant/agents/custom/runner.py`):**
  - Trips loop detection warning if duplicate tool calls exceed `loop_detection_threshold: 3`.
  - Bounded by step limits, timeout seconds, and aggregate tool call limits.
- **Built-in Working Reference Agents:**
  1. `research-agent` (Role: `researcher`) — Web search, document extraction, evidence synthesis.
  2. `file-assistant` (Role: `file_organizer`) — Directory scanning, document parsing, collision-protected moves.
  3. `planner-agent` (Role: `planner`) — Milestone planning with authorized delegation to research and file assistants.

### D. Core Tool Suites (154 Active Tools Registered in Runtime)
1. **Filesystem Operations:** `read_file`, `write_file`, `preview_write_file`, `list_files`, `search_files` (regex, binary check, type filters). Confinement strictly inside workspace roots.
2. **Command & Process Execution:** `run_command` (size-capped, security policy classified, approval gated), `start_process`, `stop_managed_process`, `restart_managed_process`, `list_managed_processes`, `tail_process_log`.
3. **Git & Version Control:** `git_status`, `git_diff` (with automated secret/token redaction), `git_log`, `git_commit`, `git_create_branch`.
4. **Web & Browser Automation:** `web_search` (Serper + scraper fallback + search budget), `web_fetch`, `download_url`, `download_image`, `image_search`. Full Playwright sessions: `browser_session_start`, `browser_session_navigate`, `browser_session_interact`, `browser_session_snapshot`, `browser_session_close`.
5. **Desktop & Screen Intelligence:** `desktop_accessibility_tree`, `desktop_analyze_screen`, `desktop_windows`, `desktop_monitors`, `desktop_status`, `desktop_click`, `desktop_move_mouse`, `desktop_type_text`, `desktop_hotkey`, `take_desktop_screenshot`, `clipboard_read`, `clipboard_write`.
6. **Database Operations:** `db_query`, `mongo_find` (read-only default, table allowlists, sensitive column redaction).
7. **Defensive Security & Guardian:** `local_security_audit`, `antivirus_status`, `antivirus_quick_scan`, `security_posture`, `security_findings`, `security_process_inspect`, `security_process_triage`, `security_contain_process`, `security_network_activity`, `security_network_isolate`, `security_network_restore`, `security_dns_summary`, `security_yara_scan`, `security_file_signature`, `security_reputation_file`, `security_reputation_process`, `security_integrity_check`, `quarantine_list`, `quarantine_release`.
8. **Planning, Memory & Personal State:** `plan_add_task`, `plan_complete_task`, `plan_fail_task`, `plan_get_ready`, `plan_clear` (DAG task graph), `remember`, `memory_search` (FTS5 indexed), `session_list`, `session_search`, `query_run_history`, `record_experience`, `verify_experience`, `search_experience`, `calendar_add`, `calendar_list`, `todo_add`, `todo_list`, `focus_start`, `focus_stop`, `daily_briefing`, `notify`.
9. **Self-Improvement & Canaries:** `propose_improvement` (AST syntax & import checked), `evaluate_improvement`, `get_improvement_evaluation`, `list_improvements`, `apply_improvement` (conflict-aware), `rollback_improvement`, `run_improvement_canary`.
10. **Custom Skill & Agent Tools:** `create_skill_draft`, `list_active_skills`, `execute_skill`, `agent_list`, `agent_get_info`, `agent_create_draft`, `agent_activate`, `agent_execute`.

### E. Integrated External Components
- **`browser-use` (`EXT-01`):** Web agent automation adapter with sandboxed browser execution.
- **`OpenViking` (`EXT-02`):** Repository indexing, graph queries, caller/callee tracing, and ADR management.
- **`agentmemory` (`EXT-03`):** Persistent key-value agent memory with vector similarity search.
- **`codebase-memory-mcp` (`EXT-04`):** AST knowledge graph codebase index and architectural decision recording.

### F. Foundational System Integrations
- **`psutil` & GPU Resource Governor (`SYS-01`):** Real-time process/RAM/CPU snapshots, load averaging, and unified GPU abstraction (`NvidiaSmiBackend`, `AppleMlxBackend`, `FallbackGPUBackend`) with interactive session throttling.
- **`platformdirs` + `uv` (`SYS-02`):** OS-standard directories across Windows/Linux/macOS with isolated virtual environment management.
- **`keyring` (`SYS-03`):** OS Credential Manager integration with fallback credential vault.
- **`DiskCache` (`SYS-04`):** Persistent SQLite-backed caching for embeddings, document parsing, and expensive reads.
- **`Watchdog` (`SYS-05`):** Debounced filesystem events preventing event flood.

### G. Client & Management Interfaces
- **Web UI Dashboard (React SPA):** Multi-page interface with Overview, Models, Chat, Skills, Agents, Approvals, Calendar & Todos, Security, and Activity tabs.
- **CLI Commands (`organism`):** Complete suites for `agent`, `skill`, `chat`, `models`, `security`, `todo`, `calendar`, `routine`, `improve`, `quarantine`, `desktop`, `browser`, `voice`.
- **FastAPI Local Backend:** 149 verified endpoints without route collisions.

---

## 🔴 2. NOT WORKING / PENDING / NOT YET IMPLEMENTED

### A. External Components Pending Implementation
These repositories/modules are referenced in project plans or cloned under `external-components/` but have not yet been wired into the runtime:
- [ ] **`EXT-05` · `diagram-design`:** Automated Mermaid/SVG visualization generator and architecture diagram tooling.
- [ ] **`EXT-06` · `Anthropic-Cybersecurity-Skills`:** Sandboxed audit rules, threat modeling, and defensive skill adapters.
- [ ] **`EXT-07` · `Graft`:** Persistent coding agent with isolated worktree branching and multi-step patch refinement.
- [ ] **`EXT-08` · `openmontage`:** Multi-modal asset orchestration and media processing bindings.
- [ ] **`EXT-09` · `Edge0`:** Local-first edge model execution pipelines and quantized model fallback.
- [ ] **`EXT-10` · `agency-agents`:** Multi-agent persona definitions and specialized agent workflow execution.
- [ ] **`EXT-11` · `scientific-agent-skills`:** Analytical and data synthesis specialist tooling.
- [ ] **`EXT-12` · `awesome-harness-engineering`:** Agent evaluation harnesses, stress test fixtures, and safety verification benches.
- [ ] **`EXT-13` · `awesome-ai-agent-tools`:** Curated tool catalog and dynamic capability registry.

### B. Foundational System Integrations Pending Implementation
- [ ] **`SYS-06` · `APScheduler`:** Persistent cron reminders, scheduled recurring workflows, and missed-run recovery after system sleep/reboot (currently handled via simple in-process interval routines).
- [ ] **`SYS-07` · `Trafilatura`:** Dedicated web article and documentation extraction library (currently handled by Docling and native regex/scraper fallback).

---

## ⚠️ 3. OPERATIONAL CONSTRAINTS & HARDWARE LIMITATIONS

1. **Hardware Ceiling (4 GB VRAM / 32 GB RAM):**
   - Concurrent local LLM inference is strictly forbidden. The system utilizes single-resident model leasing. Background tasks or delegated agents must acquire the inference semaphore sequentially.
2. **AirLLM Layer Streaming:**
   - 70B+ models execute via layer-by-layer disk streaming, resulting in significantly higher latency (~1-3 tokens/sec) than native VRAM-resident models (e.g. 7B/8B Q4 quantized models).
3. **Git Remote Push:**
   - Disabled per explicit user instruction. All changes remain local until user requests remote push.
4. **Root Traversal & System Policy Protections:**
   - Any tool or agent attempting to write or read outside allowed workspace roots or touch protected security files (`security_policy.py`, `approval.py`, `.git/`) is rejected with `SkillPermissionViolation` / `WorkspaceViolation`.

---

## 📊 Summary Scorecard

| Category | Working / Verified | Pending / Not Implemented |
| :--- | :---: | :---: |
| **Critical Bugs (`BUG-01` to `BUG-28`)** | 28 / 28 (100%) | 0 |
| **Broken Feature Repairs (`BROKEN-01` to `BROKEN-15`)** | 15 / 15 (100%) | 0 |
| **Incomplete Feature Completions (`INCOMPLETE-01` to `INCOMPLETE-18`)** | 18 / 18 (100%) | 0 |
| **Core Custom Features (`FEAT-01` to `FEAT-20`)** | 20 / 20 (100%) | 0 |
| **External Component Adapters (`EXT-01` to `EXT-13`)** | 4 / 13 (31%) | 9 |
| **System Utility Integrations (`SYS-01` to `SYS-07`)** | 5 / 7 (71%) | 2 |
| **Active Registered Runtime Tools** | 154 | — |
| **FastAPI REST Endpoints** | 149 | — |
| **Automated Verification Test Suite** | 40 / 40 Passed | 0 Failing |
