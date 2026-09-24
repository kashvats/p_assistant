# Node Registry

| Node ID | Type | Implementation Files | Responsibility |
| :--- | :--- | :--- | :--- |
| `NODE_SKILL_MANAGER` | service | `src/living_assistant/skills/package.py` | Package directory I/O, versioning, manifest loading, import/export. |
| `NODE_SKILL_STORE` | database | `src/living_assistant/skills/store.py` | SQLite lifecycle storage (`skill_lifecycle`, `skill_versions`, `skill_executions`). |
| `NODE_SKILL_CREATOR` | service | `src/living_assistant/skills/creator.py` | Natural-language prompt parsing to validated draft manifest & workflow. |
| `NODE_SKILL_GUARD` | security | `src/living_assistant/skills/guards.py` | Out-of-model permission enforcement (paths, tools, network, subprocess). |
| `NODE_PORTABLE_ADAPTER` | service | `src/living_assistant/skills/adapters.py` | Stable portable interfaces (`files.list`, `files.move`, dry-run, undo log). |
| `NODE_DOC_EXTRACTOR` | service | `src/living_assistant/skills/extractor.py` | Invoices & document extraction with confidence scoring. |
| `NODE_SKILL_RUNNER` | worker | `src/living_assistant/skills/runner.py` | Step-by-step workflow execution, retry safety, trace recording. |
| `NODE_SKILL_API` | api | `src/living_assistant/api_routes/skills.py` | REST API routes for draft creation, test, activate, rollback, export. |
| `NODE_SKILL_UI` | ui | `src/living_assistant/webui/src/main.js` | React dashboard tab for skills management. |
| `NODE_AGENT_MANAGER` | service | `src/living_assistant/agents/custom/manager.py` | Custom agent lifecycle orchestration, storage, snapshots, and execution coordination. |
| `NODE_AGENT_STORE` | database | `src/living_assistant/agents/custom/store.py` | SQLite persistence for agent lifecycles, versions, executions, actions, and memory. |
| `NODE_AGENT_CREATOR` | service | `src/living_assistant/agents/custom/creator.py` | Natural-language draft generation, heuristic role inference, and tool allowlisting. |
| `NODE_AGENT_EXECUTOR` | worker | `src/living_assistant/agents/custom/runner.py` | Bounded step execution, loop detection, outcome verification, and trace recording. |
| `NODE_AGENT_DELEGATION` | security | `src/living_assistant/agents/custom/delegation.py` | Controlled delegation, permission inheritance, depth bounding, and inference slot coordination. |
| `NODE_AGENT_MEMORY` | service | `src/living_assistant/agents/custom/memory.py` | Scoped memory isolation for working context, agent notes, and project knowledge. |
| `NODE_AGENT_API` | api | `src/living_assistant/api_routes/agents.py` | REST API endpoints for agent listing, drafting, activation, execution, export/import. |
| `NODE_AGENT_UI` | ui | `src/living_assistant/webui/src/main.js` | React dashboard tab for custom agent creation, inspection, and live execution. |
| `NODE_DIAGRAM_DESIGN` | adapter | `src/living_assistant/integrations/diagram_design.py` | Editorial diagram engine with deterministic IR extraction (Mermaid, Draw.io, Excalidraw), accessible SVG generation, and safety self-check across 41 diagram types. |
| `NODE_CYBERSECURITY_SKILLS` | adapter | `src/living_assistant/integrations/cybersecurity_skills.py` | Cybersecurity skills catalog adapter with 800+ defensive techniques, threat modeling, and multi-layered OWASP prompt injection auditing. |
| `NODE_GRAFT_MEMORY` | adapter | `src/living_assistant/integrations/graft.py` | Persistent local AI agent memory layer with verified recall, hybrid retrieval, graph exploration, and embedded SQLite FTS5 fallback. |
