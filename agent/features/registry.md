# Feature Registry

| Feature ID | Name | Objective | Primary Node | State | Dependencies | Mapped Tests |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `FEAT-19` | Custom Skill Creation and Execution System | End-to-end versioned skill creation, validation, out-of-model permission enforcement, portable execution, UI, and external collections. | `NODE_SKILL_MANAGER` | ACTIVE | `NODE_RUNTIME`, `NODE_TOOL_REGISTRY`, `NODE_APPROVAL_MANAGER`, `NODE_WORKSPACE` | `tests/test_custom_skills.py`, `tests/test_skills.py`, `tests/test_downloads_organizer_e2e.py` |
| `FEAT-20` | Custom Agent Creation and Management | Versioned agent definitions, natural-language creation, lifecycle management, orchestrator execution, controlled delegation, and scoped memory. | `NODE_AGENT_MANAGER` | ACTIVE | `NODE_ORCHESTRATOR`, `NODE_RUNTIME`, `NODE_SKILL_MANAGER`, `NODE_MEMORY_STORE` | `tests/test_custom_agents.py` |
