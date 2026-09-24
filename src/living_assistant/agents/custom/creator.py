from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
import re
from typing import Any

from living_assistant.agents.custom.manifest import (
    AgentManifest,
    AgentLimits,
    AgentDelegationPolicy,
    AgentMemoryScope,
    AgentProvenance,
)
from living_assistant.agents.custom.package import AgentPackage
from living_assistant.agents.custom.store import AgentStore
from living_assistant.tools.registry import ToolRegistry


class AgentCreator:
    """Creates draft agent packages from natural language prompts or structured form inputs."""

    def __init__(
        self,
        tool_registry: ToolRegistry,
        store: AgentStore,
        skills_manager: Any = None,
        agents_dir: Path | None = None,
        model_manager: Any = None,
    ):
        self.tool_registry = tool_registry
        self.store = store
        self.skills_manager = skills_manager
        self.agents_dir = agents_dir or (Path.home() / ".living_assistant" / "agents")
        self.model_manager = model_manager

    def _slugify(self, text: str) -> str:
        s = text.lower().strip()
        s = re.sub(r"[^\w\s-]", "", s)
        s = re.sub(r"[\s_]+", "-", s)
        return s[:40] or "custom-agent"

    def _heuristic_agent_draft(self, prompt: str) -> dict[str, Any]:
        """Deterministic heuristic generator when offline or bootstrapping."""
        clean_text = prompt.strip()
        lower = clean_text.lower()

        # Infer role
        role = "assistant"
        if any(w in lower for w in ("research", "search", "paper", "investigate", "web")):
            role = "researcher"
        elif any(w in lower for w in ("file", "download", "folder", "organize", "pdf", "invoice")):
            role = "file_organizer"
        elif any(w in lower for w in ("plan", "milestone", "decompose", "strategy")):
            role = "planner"
        elif any(w in lower for w in ("security", "audit", "vulnerability", "cve")):
            role = "security_auditor"
        elif any(w in lower for w in ("code", "refactor", "bug", "patch", "git")):
            role = "coder"

        # Determine tools from available registry
        available_tools = set(self.tool_registry.names()) if hasattr(self.tool_registry, "names") else set()
        matched_tools = set()

        if role == "researcher":
            for t in ["web.search", "web.download", "files.read", "documents.extract"]:
                if t in available_tools:
                    matched_tools.add(t)
        elif role == "file_organizer":
            for t in ["files.list", "files.read", "files.write", "files.move", "documents.extract"]:
                if t in available_tools:
                    matched_tools.add(t)
        elif role == "planner":
            for t in ["tasks.plan", "tasks.list", "tasks.update", "files.read"]:
                if t in available_tools:
                    matched_tools.add(t)
        elif role == "coder":
            for t in ["files.read", "files.write", "git.status", "git.diff", "codebase.search"]:
                if t in available_tools:
                    matched_tools.add(t)
        else:
            for t in ["files.read", "files.list"]:
                if t in available_tools:
                    matched_tools.add(t)

        # Fallback if no available tools matched
        if not matched_tools and available_tools:
            matched_tools = {sorted(available_tools)[0]}

        # Check for skills
        matched_skills = []
        if self.skills_manager and hasattr(self.skills_manager, "list_skills"):
            try:
                for s in self.skills_manager.list_skills():
                    s_id = s.get("skill_id", "")
                    if s_id and s_id in lower:
                        matched_skills.append(s_id)
            except Exception:
                pass

        # Generate sensible name
        words = clean_text.split()[:4]
        title = " ".join(words).title()
        if not title:
            title = "Custom Agent"

        agent_id = self._slugify(title)

        system_prompt = (
            f"You are {title}, specialized as a {role}. "
            f"Your mission is: {clean_text}. "
            "Operate within your permitted tools, verify all outcomes, and communicate clearly."
        )

        return {
            "id": agent_id,
            "name": title,
            "description": clean_text,
            "role": role,
            "system_prompt": system_prompt,
            "capabilities": [role, "structured_reasoning"],
            "allowed_tools": sorted(matched_tools),
            "allowed_skills": matched_skills,
            "triggers": [agent_id, role],
        }

    def create_draft(
        self,
        prompt: str,
        form_data: dict[str, Any] | None = None,
    ) -> AgentPackage:
        now = dt.datetime.now().isoformat(timespec="seconds")

        if form_data:
            agent_data = dict(form_data)
            agent_id = agent_data.get("id") or self._slugify(agent_data.get("name", "custom-agent"))
            agent_data["id"] = agent_id
        else:
            agent_data = self._heuristic_agent_draft(prompt)
            agent_id = agent_data["id"]

        manifest = AgentManifest(
            schema_version="1.0.0",
            id=agent_id,
            name=agent_data.get("name", "Custom Agent"),
            description=agent_data.get("description", prompt),
            role=agent_data.get("role", "specialist"),
            version="1.0.0",
            system_prompt=agent_data.get("system_prompt", ""),
            capabilities=agent_data.get("capabilities", []),
            allowed_tools=agent_data.get("allowed_tools", []),
            allowed_skills=agent_data.get("allowed_skills", []),
            delegation_policy=AgentDelegationPolicy(
                can_delegate=agent_data.get("can_delegate", False),
                allowed_agents=agent_data.get("allowed_agents", []),
            ),
            memory_scope=AgentMemoryScope(),
            limits=AgentLimits(),
            provenance=AgentProvenance(
                created_by="user",
                created_at=now,
                prompt_used=prompt,
            ),
            triggers=agent_data.get("triggers", [agent_id]),
            examples=[
                {
                    "task": f"Perform task for {agent_data.get('name')}",
                    "expected_output_type": "text",
                }
            ],
        )

        agent_md = (
            f"# {manifest.name}\n\n"
            f"**Role:** {manifest.role}\n"
            f"**Created:** {now}\n\n"
            f"## Description\n{manifest.description}\n\n"
            f"## System Prompt\n```\n{manifest.system_prompt}\n```\n\n"
            f"## Allowed Capabilities\n"
            f"- Tools: {', '.join(manifest.allowed_tools) or 'None'}\n"
            f"- Skills: {', '.join(manifest.allowed_skills) or 'None'}\n"
        )

        pkg_root = self.agents_dir / agent_id
        pkg = AgentPackage(
            root=pkg_root,
            manifest=manifest,
            agent_md=agent_md,
            examples=manifest.examples,
        )
        pkg.save()

        # Register in AgentStore as DRAFT
        self.store.register_agent(
            manifest=manifest,
            agent_md=agent_md,
            initial_state="DRAFT",
            package_hash=pkg.deterministic_hash(),
        )

        return pkg
