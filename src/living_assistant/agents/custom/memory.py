from __future__ import annotations

from typing import Any
from living_assistant.agents.custom.manifest import AgentMemoryScope
from living_assistant.agents.custom.store import AgentStore


class MemoryScopeViolation(PermissionError):
    pass


class AgentScopedMemory:
    """Provides isolated, scope-checked memory access for a specific agent execution."""

    def __init__(
        self,
        agent_id: str,
        scope: AgentMemoryScope,
        store: AgentStore,
        system_memory: Any = None,
    ):
        self.agent_id = agent_id
        self.scope = scope
        self.store = store
        self.system_memory = system_memory
        self._working_memory: dict[str, Any] = {}

    def _check_read(self, namespace: str):
        if namespace not in self.scope.readable_namespaces:
            raise MemoryScopeViolation(
                f"Agent '{self.agent_id}' does not have read access to namespace '{namespace}'. "
                f"Readable namespaces: {self.scope.readable_namespaces}"
            )

    def _check_write(self, namespace: str):
        if namespace not in self.scope.writable_namespaces:
            raise MemoryScopeViolation(
                f"Agent '{self.agent_id}' does not have write access to namespace '{namespace}'. "
                f"Writable namespaces: {self.scope.writable_namespaces}"
            )

    def read(self, namespace: str, key: str) -> Any | None:
        self._check_read(namespace)
        if namespace == "working":
            return self._working_memory.get(key)
        elif namespace == "agent_notes":
            return self.store.get_memory(namespace, self.agent_id, key)
        elif namespace in ("project_knowledge", "user_memory") and self.system_memory:
            if hasattr(self.system_memory, "get"):
                return self.system_memory.get(key)
            return None
        return self.store.get_memory(namespace, self.agent_id, key)

    def write(self, namespace: str, key: str, value: Any) -> None:
        self._check_write(namespace)
        if namespace == "working":
            self._working_memory[key] = value
        elif namespace == "agent_notes":
            self.store.set_memory(namespace, self.agent_id, key, value)
        elif namespace in ("project_knowledge", "user_memory") and self.system_memory:
            if hasattr(self.system_memory, "set"):
                self.system_memory.set(key, value)
            else:
                self.store.set_memory(namespace, self.agent_id, key, value)
        else:
            self.store.set_memory(namespace, self.agent_id, key, value)

    def list_keys(self, namespace: str) -> list[str]:
        self._check_read(namespace)
        if namespace == "working":
            return list(self._working_memory.keys())
        elif namespace == "agent_notes":
            return list(self.store.list_memory(namespace, self.agent_id).keys())
        return []

    def get_prompt_context(self) -> str:
        """Render readable memory into an LLM context block."""
        blocks: list[str] = []
        if "agent_notes" in self.scope.readable_namespaces:
            notes = self.store.list_memory("agent_notes", self.agent_id)
            if notes:
                items = [f"- {k}: {v}" for k, v in notes.items()]
                blocks.append("[AGENT PERSISTENT NOTES]\n" + "\n".join(items[:20]))

        if "working" in self.scope.readable_namespaces and self._working_memory:
            items = [f"- {k}: {v}" for k, v in self._working_memory.items()]
            blocks.append("[WORKING CONTEXT]\n" + "\n".join(items[:20]))

        return "\n\n".join(blocks)
