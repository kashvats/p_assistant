# Living Assistant — Custom Agents Guide (FEAT-20)

This guide documents the architecture, lifecycle, security boundaries, and operational workflows for the Custom Agent Creation and Management System in Living Assistant.

---

## 1. Overview & Core Tenets

The Custom Agents system allows users and developers to create, inspect, execute, and govern specialized autonomous agents alongside the core Orchestrator and SpecialistRouter:
- **Portability:** Seamless operation across Windows and Ubuntu/Linux environments.
- **Strict Out-of-Model Governance:** Execution bounds (maximum steps, timeouts, aggregate tool call limits) and permission inheritance are enforced deterministically by `AgentExecutor` and `AgentDelegationCoordinator`, never relying on LLM self-restraint.
- **Hardware-Aware Single-Resident Inference:** Runs reliably on 4 GB VRAM / 32 GB RAM hardware. Child delegations coordinate inference slots so that only one model is actively loaded at any time.
- **Cryptographic Approval Snapshots:** Active agents are bound to SHA-256 hashes of their manifest and bundle files. Disk tampering immediately revokes active status and drops the agent to `DRAFT`.
- **Scoped Memory Namespaces:** Volatile working context and persistent agent notes are isolated from unrelated agents and sensitive system memory.

---

## 2. Agent Package Structure

Custom agent definitions reside in `~/.living_assistant/agents/<agent-id>/`:

```
agents/<agent-id>/
├── AGENT.md            # Human-readable prompt, role description, and guidelines
├── manifest.json       # Versioned contract, capabilities, limits, tools, memory scopes
├── examples/           # Sample tasks and expected output types
│   └── default.json
└── tests/              # Declarative test assertions
    └── test_cases.json
```

---

## 3. Agent Manifest Schema (`manifest.json`)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "schema_version": "1.0.0",
  "id": "research-agent",
  "name": "Research Specialist",
  "description": "Performs web and document research, extracts insights, and synthesizes findings.",
  "role": "researcher",
  "version": "1.0.0",
  "system_prompt": "You are a research specialist...",
  "capabilities": [
    "web_search",
    "document_extraction",
    "evidence_synthesis"
  ],
  "allowed_tools": [
    "web.search",
    "web.download",
    "files.read",
    "documents.extract"
  ],
  "allowed_skills": [
    "daily-briefing"
  ],
  "delegation_policy": {
    "can_delegate": false,
    "allowed_agents": [],
    "max_subagents": 2,
    "inherit_permissions": true
  },
  "memory_scope": {
    "isolate_working_memory": true,
    "readable_namespaces": ["working", "agent_notes", "project_knowledge"],
    "writable_namespaces": ["working", "agent_notes"]
  },
  "limits": {
    "max_steps": 15,
    "max_tool_calls_per_step": 4,
    "loop_detection_threshold": 3,
    "timeout_seconds": 120.0,
    "max_delegation_depth": 2,
    "aggregate_tool_limit": 50
  }
}
```

---

## 4. Built-in Reference Agents

The system automatically seeds three pre-approved reference agents:

1. **`research-agent` (Role: `researcher`):**
   - Focus: Web searching, downloading articles, reading documents, and synthesizing factual briefings.
   - Tools: `web.search`, `web.download`, `files.read`, `documents.extract`.
   - Memory: Scoped read of `project_knowledge`, isolated write to `agent_notes`.

2. **`file-assistant` (Role: `file_organizer`):**
   - Focus: Directory inspection, document extraction, collision-protected file moves, and downloads organization.
   - Tools: `files.list`, `files.read`, `files.write`, `files.move`, `documents.extract`.
   - Skills: `downloads-organizer`, `invoice-organizer`.

3. **`planner-agent` (Role: `planner`):**
   - Focus: Strategic task decomposition, milestone tracking, and delegating subtasks to specialists.
   - Tools: `tasks.plan`, `tasks.list`, `tasks.update`, `files.read`.
   - Delegation: Authorized to delegate subtasks to `research-agent` and `file-assistant`.

---

## 5. Controlled Delegation & Security

When an agent delegates a task to another agent:
1. **Delegation Authorization:** The parent agent's `delegation_policy.can_delegate` must be `true`.
2. **Target Whitelist:** If `allowed_agents` is non-empty, the target agent must be in the list.
3. **Depth Limits:** Total delegation depth cannot exceed `parent.limits.max_delegation_depth`.
4. **Permission Inheritance:** Child agents cannot exceed the parent's allowed tools or allowed skills (`DelegationViolation`).
5. **Inference Slot Coordination:** During delegation, the parent yields its inference lock to allow the child agent to run within the single-resident 4GB VRAM constraint.

---

## 6. Execution Lifecycle & Safety Guards

- **DRAFT Mode:** Newly created or edited agents can only be executed with `dry_run=True`.
- **ACTIVE Mode:** Requires formal activation via `activate_agent()`, which creates an immutable snapshot under `_snapshots/<id>/<version>_<hash>/` and records the approved package hash in SQLite.
- **Tampering Invalidation:** If any file in an active agent package is modified on disk, the SHA-256 hash check fails on the next execution, automatically demoting the agent to `DRAFT`.
- **Loop Detection:** If an agent calls the exact same tool with identical arguments more than `loop_detection_threshold` times, execution is immediately halted with a loop detection warning.

---

## 7. CLI & API Reference

### CLI Commands (`organism agent`)
```bash
# List all custom agents
organism agent list

# Inspect detailed agent specifications and history
organism agent info research-agent

# Draft an agent from a natural-language description
organism agent draft "Create an agent that audits python files for security vulnerabilities"

# Activate an agent after review (creates snapshot)
organism agent activate research-agent

# Run agent in safe dry-run simulation mode
organism agent test research-agent "Find papers on speculative decoding"

# Execute agent live
organism agent run research-agent "Find papers on speculative decoding"

# Export agent package to zip
organism agent export research-agent research-agent.zip

# Import agent package from zip
organism agent import research-agent.zip
```

### REST API Endpoints
- `GET /agents`: List registered agents (with state filter).
- `GET /agents/{id}`: Detailed manifest, history, and version records.
- `POST /agents/draft`: Create agent draft from natural-language description or form.
- `PUT /agents/{id}`: Update manifest and `AGENT.md`.
- `POST /agents/{id}/activate`: Create snapshot and approve package hash.
- `POST /agents/{id}/disable`: Disable agent.
- `POST /agents/{id}/execute`: Execute agent task (with `dry_run` support).
- `GET /agents/{id}/export`: Export agent bundle as a zip file.
- `POST /agents/import`: Import agent bundle from base64 zip.
