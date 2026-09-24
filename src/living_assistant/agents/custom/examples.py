from __future__ import annotations

from living_assistant.agents.custom.manifest import (
    AgentManifest,
    AgentLimits,
    AgentDelegationPolicy,
    AgentMemoryScope,
    AgentProvenance,
)


def get_research_agent_manifest() -> AgentManifest:
    return AgentManifest(
        schema_version="1.0.0",
        id="research-agent",
        name="Research Specialist",
        description="Performs web and document research, extracts insights, and synthesizes findings.",
        role="researcher",
        version="1.0.0",
        system_prompt=(
            "You are a dedicated research specialist in Living Assistant. "
            "Your objective is to inspect sources, query the web or local documents, "
            "and synthesize high-quality, truthful summaries with clear evidence."
        ),
        capabilities=["web_search", "document_extraction", "evidence_synthesis"],
        allowed_tools=["web.search", "web.download", "files.read", "documents.extract"],
        allowed_skills=["daily-briefing"],
        delegation_policy=AgentDelegationPolicy(can_delegate=False),
        memory_scope=AgentMemoryScope(
            isolate_working_memory=True,
            readable_namespaces=["working", "agent_notes", "project_knowledge"],
            writable_namespaces=["working", "agent_notes"],
        ),
        limits=AgentLimits(
            max_steps=15,
            max_tool_calls_per_step=4,
            loop_detection_threshold=3,
            timeout_seconds=120.0,
        ),
        provenance=AgentProvenance(
            created_by="system",
            prompt_used="Seed builtin research specialist",
        ),
        triggers=["research", "investigate", "summarize paper", "search web"],
        examples=[
            {
                "task": "Research latest advancements in local quantized LLMs",
                "expected_output_type": "markdown_summary",
            }
        ],
    )


def get_file_assistant_manifest() -> AgentManifest:
    return AgentManifest(
        schema_version="1.0.0",
        id="file-assistant",
        name="File Operations Assistant",
        description="Organizes workspace folders, inspects downloads, extracts document contents, and coordinates file moves safely.",
        role="file_organizer",
        version="1.0.0",
        system_prompt=(
            "You are a meticulous file operations assistant. "
            "You inspect directories, verify destination paths, avoid destructive overwrites, "
            "and organize documents with collision protection."
        ),
        capabilities=["file_management", "document_extraction", "workspace_organization"],
        allowed_tools=["files.list", "files.read", "files.write", "files.move", "documents.extract"],
        allowed_skills=["downloads-organizer", "invoice-organizer"],
        delegation_policy=AgentDelegationPolicy(can_delegate=False),
        memory_scope=AgentMemoryScope(
            isolate_working_memory=True,
            readable_namespaces=["working", "agent_notes"],
            writable_namespaces=["working", "agent_notes"],
        ),
        limits=AgentLimits(
            max_steps=20,
            max_tool_calls_per_step=5,
            loop_detection_threshold=3,
            timeout_seconds=180.0,
        ),
        provenance=AgentProvenance(
            created_by="system",
            prompt_used="Seed builtin file operations assistant",
        ),
        triggers=["organize files", "clean downloads", "sort documents", "move statement"],
        examples=[
            {
                "task": "Organize downloads directory by file type and date",
                "expected_output_type": "execution_report",
            }
        ],
    )


def get_planner_agent_manifest() -> AgentManifest:
    return AgentManifest(
        schema_version="1.0.0",
        id="planner-agent",
        name="Strategic Planner Agent",
        description="Decomposes complex requests into structured milestone graphs and coordinates delegated execution.",
        role="planner",
        version="1.0.0",
        system_prompt=(
            "You are a strategic planner agent. "
            "You decompose complex, multi-stage goals into clean dependency graphs, "
            "manage task milestones, and delegate focused sub-tasks to specialists."
        ),
        capabilities=["task_planning", "goal_decomposition", "specialist_delegation"],
        allowed_tools=["tasks.plan", "tasks.list", "tasks.update", "files.read"],
        allowed_skills=[],
        delegation_policy=AgentDelegationPolicy(
            can_delegate=True,
            allowed_agents=["research-agent", "file-assistant"],
            max_subagents=2,
            inherit_permissions=True,
        ),
        memory_scope=AgentMemoryScope(
            isolate_working_memory=True,
            readable_namespaces=["working", "agent_notes", "project_knowledge"],
            writable_namespaces=["working", "agent_notes"],
        ),
        limits=AgentLimits(
            max_steps=15,
            max_tool_calls_per_step=3,
            loop_detection_threshold=3,
            timeout_seconds=120.0,
        ),
        provenance=AgentProvenance(
            created_by="system",
            prompt_used="Seed builtin strategic planner agent",
        ),
        triggers=["plan project", "break down task", "roadmap", "orchestrate goal"],
        examples=[
            {
                "task": "Create a migration plan for moving workflows to skills",
                "expected_output_type": "task_graph",
            }
        ],
    )
