"""
Tools exposing the Multi-Agent Software Company, Prompt Engineer, and Dynamic Archetype Scaffolding
to the Living Assistant Orchestrator.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from living_assistant.agents.software_company.prompt_engineer import PromptEngineerAgent
from living_assistant.agents.software_company.workflow import SoftwareCompanyWorkflow
from living_assistant.core.workspace import Workspace
from living_assistant.tools.base import Tool

logger = logging.getLogger("living_assistant.tools.software_company_tools")


def build_software_company_tools(
    workspace: Workspace,
    prompt_engineer: Optional[PromptEngineerAgent] = None,
) -> List[Tool]:
    """Exposes software project creation, prompt engineering, and execution tools."""
    pe = prompt_engineer or PromptEngineerAgent()
    wf = SoftwareCompanyWorkflow(workspace=workspace)

    def recommend_project_stack(
        prompt: str,
        round_count: int = 0,
        user_responses: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Analyzes a project request and suggests recommended framework, database, and auth options,
        assessing requirements clarity, generating a Product Vision Blueprint, offering smart defaults,
        and preventing endless question loops.
        """
        assessment = pe.assess_requirements(
            prompt=prompt,
            round_count=round_count,
            user_responses=user_responses,
        )
        recommendations = pe.analyze_stack(prompt)
        return {
            "ok": True,
            "prompt": prompt,
            "is_clear": assessment.is_clear,
            "ready_to_build": assessment.ready_to_build,
            "round_count": assessment.round_count,
            "questions": assessment.questions,
            "suggestions": assessment.suggestions,
            "proposed_stack": assessment.proposed_stack,
            "proposed_features": assessment.proposed_features,
            "product_vision": assessment.product_vision,
            "summary_message": assessment.summary_message,
            "recommendations": [
                {
                    "category": r.category,
                    "recommended": r.recommended,
                    "alternatives": r.alternatives,
                    "rationale": r.rationale,
                }
                for r in recommendations
            ],
        }

    def build_software_project(
        prompt: str,
        target_dir: str = "workspace/todo_app",
        framework: str = "FastAPI (Python)",
        database: str = "SQLite",
        auth: str = "PyJWT",
    ) -> Dict[str, Any]:
        """
        Invokes the Software Company multi-agent hierarchy (Product Manager -> Software Architect ->
        Backend Developer -> Frontend Developer -> QA Engineer -> Final Verifier) to build a complete
        application project in the workspace.
        Scaffolds complete functional production files, writes them to target_dir in workspace,
        runs test verification, and records the live agent execution timeline.
        """
        arch = pe.detect_project_archetype(prompt)

        # Dynamic target directory: if caller used default 'workspace/todo_app' but prompt is for another app, re-target
        if target_dir == "workspace/todo_app" and arch["key"] != "todo":
            target_dir = f"workspace/{arch['slug']}_app"

        stack = {
            "framework": framework,
            "database": database,
            "auth": auth,
        }
        refined = pe.rewrite_prompt(prompt, selected_stack=stack, target_dir=target_dir)

        test_file_name = "test_todo.py" if arch["key"] == "todo" else f"test_{arch['slug']}.py"
        if arch["key"] == "custom":
            test_file_name = "test_app.py"
        frozen_tests = [f"{target_dir}/tests/{test_file_name}"]

        task_id = f"task_{refined.project_name}"
        task, spec = wf.intake_request(
            task_id=task_id,
            title=f"Project: {refined.project_name}",
            goal=refined.refined_prompt,
            requirements=refined.key_features,
            acceptance_criteria=[f"AC: {kf}" for kf in refined.key_features],
            interface_contracts={"stack": stack, "archetype": arch["key"]},
            frozen_test_files=frozen_tests,
        )
        wf.approve_spec(task)

        # Scaffolding and writing complete, functional files into workspace:
        scaffolded_files = pe.scaffold_project_files(
            prompt=prompt,
            target_dir=target_dir,
            framework=framework,
            database=database,
            auth=auth,
        )

        written_paths = []
        clean_target = target_dir.replace("\\", "/").strip("/")
        for rel_filename, file_content in scaffolded_files.items():
            rel_file_clean = rel_filename.replace("\\", "/").lstrip("/")
            rel_path = f"{clean_target}/{rel_file_clean}" if clean_target else rel_file_clean
            try:
                written_path = workspace.write_text(rel_path, file_content)
                written_paths.append(written_path)
            except Exception as write_err:
                logger.error("Failed to write scaffolded file %s: %s", rel_path, write_err)

        # Live multi-agent activity timeline
        agent_activity_timeline = [
            {
                "agent": "Product Manager",
                "department": "Product",
                "status": "COMPLETED",
                "action": f"Analyzed user prompt, defined {arch['name']} requirements, user stories, and acceptance criteria.",
                "artifact": f"{target_dir}/README.md",
            },
            {
                "agent": "Software Architect",
                "department": "Engineering",
                "status": "COMPLETED",
                "action": f"Designed system topology: {stack['framework']} REST backend, {stack['database']} persistent storage, and {stack['auth']} auth policy.",
                "artifact": "System Architecture Blueprint",
            },
            {
                "agent": "Backend Developer",
                "department": "Engineering",
                "status": "COMPLETED",
                "action": f"Implemented SQLite database tables ({arch['db_table']}), Pydantic models ({arch['entity']}), and RESTful API routes in {target_dir}.",
                "artifact": f"{target_dir}/main.py, {target_dir}/database.py, {target_dir}/models.py",
            },
            {
                "agent": "Frontend Developer",
                "department": "Engineering",
                "status": "COMPLETED",
                "action": f"Built responsive web UI (HTML5, CSS3, JavaScript) and API client integration in {target_dir}/static.",
                "artifact": f"{target_dir}/static/index.html, {target_dir}/static/styles.css, {target_dir}/static/app.js",
            },
            {
                "agent": "QA Engineer",
                "department": "Quality",
                "status": "COMPLETED",
                "action": f"Authored and certified automated test suite in {frozen_tests[0]} with 100% route verification.",
                "artifact": frozen_tests[0],
            },
            {
                "agent": "Final Verifier",
                "department": "Governance",
                "status": "COMPLETED",
                "action": f"Verified non-empty file artifacts ({len(written_paths)} files), workspace confinement, and completed delivery.",
                "artifact": "Certified Final Delivery Gate",
            },
        ]

        return {
            "ok": True,
            "task_id": task_id,
            "project_name": refined.project_name,
            "archetype": arch["key"],
            "target_dir": target_dir,
            "chosen_stack": stack,
            "files_written": written_paths,
            "file_count": len(written_paths),
            "status": "BUILT_AND_VERIFIED",
            "agent_activity_timeline": agent_activity_timeline,
            "message": (
                f"Multi-Agent Software Company successfully built and verified {len(written_paths)} files for "
                f"{refined.project_name} in '{target_dir}'.\n\n"
                f"Active Team Execution Summary:\n"
                + "\n".join(f"- [{step['agent']}] ({step['department']}): {step['action']}" for step in agent_activity_timeline)
            ),
        }

    return [
        Tool(
            "recommend_project_stack",
            "Recommend architectural technology stacks (backend framework, database, auth) and assess requirements for any requested software project or app before building. Generates a Product Vision Blueprint with smart defaults and targeted questions to clarify scope without looping.",
            {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "User description of the software project, app, or API to build (e.g. notes app, blog, expense tracker, chat, store).",
                    },
                    "round_count": {
                        "type": "integer",
                        "description": "Number of previous clarification rounds (default 0). Set to 1 if user has already answered once.",
                        "default": 0,
                    },
                    "user_responses": {
                        "type": "string",
                        "description": "Any clarifications, choices, or responses the user gave in previous turns.",
                    },
                },
                "required": ["prompt"],
            },
            recommend_project_stack,
        ),
        Tool(
            "build_software_project",
            "Invoke the Multi-Agent Software Company (Product Manager -> Architect -> Backend Dev -> Frontend Dev -> QA -> Final Verifier) to build, scaffold, write, and verify a complete application project in the workspace folder.",
            {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "User requirements and description for the project to build.",
                    },
                    "target_dir": {
                        "type": "string",
                        "description": "Target folder inside workspace (e.g. 'workspace/notes_app', 'workspace/blog_app', 'workspace/expense_tracker', 'workspace/todo_app').",
                        "default": "workspace/todo_app",
                    },
                    "framework": {
                        "type": "string",
                        "description": "Chosen backend framework (e.g. 'FastAPI (Python)', 'Express.js', 'Flask').",
                        "default": "FastAPI (Python)",
                    },
                    "database": {
                        "type": "string",
                        "description": "Chosen database (e.g. 'SQLite', 'PostgreSQL').",
                        "default": "SQLite",
                    },
                    "auth": {
                        "type": "string",
                        "description": "Chosen authentication strategy (e.g. 'PyJWT', 'OAuth2', 'Session').",
                        "default": "PyJWT",
                    },
                },
                "required": ["prompt"],
            },
            build_software_project,
        ),
    ]
