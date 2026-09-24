from __future__ import annotations

from collections import Counter
import datetime as dt
import hashlib
import json
import time
from typing import Any

from living_assistant.agents.custom.delegation import AgentDelegationCoordinator, DelegationViolation
from living_assistant.agents.custom.manifest import AgentManifest
from living_assistant.agents.custom.memory import AgentScopedMemory
from living_assistant.agents.custom.store import AgentStore
from living_assistant.tools.registry import ToolRegistry


class AgentExecutionError(RuntimeError):
    pass


class AgentExecutor:
    """Runs a custom agent with strict bounding, scoped memory, and loop detection."""

    def __init__(
        self,
        tool_registry: ToolRegistry,
        agent_store: AgentStore,
        skills_manager: Any = None,
        model_manager: Any = None,
        delegation_coordinator: AgentDelegationCoordinator | None = None,
        system_memory: Any = None,
    ):
        self.tool_registry = tool_registry
        self.agent_store = agent_store
        self.skills_manager = skills_manager
        self.model_manager = model_manager
        self.delegation_coordinator = delegation_coordinator or AgentDelegationCoordinator()
        self.system_memory = system_memory

    def execute(
        self,
        manifest: AgentManifest,
        task: str,
        context: str = "",
        inputs: dict[str, Any] | None = None,
        dry_run: bool = False,
        package_hash: str | None = None,
        session_id: str | None = None,
        depth: int = 0,
        parent_run_id: str | None = None,
    ) -> dict[str, Any]:
        start_time = time.time()
        lifecycle = self.agent_store.get_lifecycle(manifest.id)
        current_state = lifecycle.get("state", "DRAFT") if lifecycle else "DRAFT"

        # Permission and lifecycle validation
        if current_state == "ACTIVE":
            perm_hash = manifest.permission_hash()
            if not self.agent_store.is_approved(manifest.id, manifest.version, perm_hash, package_hash):
                raise PermissionError(
                    f"Agent '{manifest.id}' has been modified on disk since approval or approval is invalid. Please re-activate."
                )
        elif current_state == "DRAFT":
            if not dry_run:
                raise PermissionError(
                    f"Agent '{manifest.id}' is in DRAFT state. Must be activated before live execution or run with dry_run=True."
                )
        else:
            raise PermissionError(f"Agent '{manifest.id}' is {current_state} and cannot be executed.")

        # Scoped memory setup
        scoped_mem = AgentScopedMemory(
            agent_id=manifest.id,
            scope=manifest.memory_scope,
            store=self.agent_store,
            system_memory=self.system_memory,
        )

        run_id = self.agent_store.record_execution_start(
            agent_id=manifest.id,
            version=manifest.version,
            task=task,
            inputs=inputs,
            dry_run=dry_run,
        )

        # Build allowed tools map
        allowed_tool_names = set(manifest.allowed_tools)
        available_tools: dict[str, Any] = {}
        for name in allowed_tool_names:
            tool_obj = self.tool_registry.get(name) if hasattr(self.tool_registry, "get") else None
            if tool_obj:
                available_tools[name] = tool_obj

        trace: list[dict[str, Any]] = []
        call_signatures: Counter[str] = Counter()
        step_count = 0
        total_tool_calls = 0
        status = "COMPLETED"
        error_msg = None
        final_output = ""

        try:
            # Memory working context
            scoped_mem.write("working", "task", task)
            scoped_mem.write("working", "started_at", dt.datetime.now().isoformat())

            # Execution loop bounded by max_steps and timeout
            timeout_at = start_time + manifest.limits.timeout_seconds
            is_done = False

            while step_count < manifest.limits.max_steps and not is_done:
                if time.time() > timeout_at:
                    status = "FAILED"
                    error_msg = f"Agent execution exceeded timeout of {manifest.limits.timeout_seconds} seconds."
                    break

                step_count += 1
                step_record = {
                    "step": step_count,
                    "timestamp": dt.datetime.now().isoformat(timespec="seconds"),
                    "actions": [],
                }

                # If LLM model manager is active, query model with scoped tools
                if self.model_manager and not dry_run:
                    # Model-driven execution loop
                    mem_context = scoped_mem.get_prompt_context()
                    full_system = f"{manifest.system_prompt}\n\n{mem_context}"
                    model_name = manifest.model_preference.model_name or "orchestrator"
                    messages = [
                        {"role": "system", "content": full_system},
                        {"role": "user", "content": f"Task: {task}\nContext: {context}"},
                    ]
                    # Acquire inference slot via delegation coordinator
                    with self.delegation_coordinator._inference_lock:
                        response = self.model_manager.provider.chat(
                            model_name,
                            messages,
                            options={"num_ctx": manifest.model_preference.context_tokens},
                        )
                    resp_content = response.get("message", {}).get("content", "")
                    final_output = resp_content
                    step_record["output"] = resp_content
                    is_done = True
                else:
                    # Deterministic tool execution simulation / dry-run
                    # If agent has allowed skills and skill manager, invoke skill if matching
                    for skill_id in manifest.allowed_skills:
                        if self.skills_manager and skill_id in task.lower():
                            act_id = self.agent_store.record_action(
                                run_id=run_id,
                                agent_id=manifest.id,
                                action_type="skill_invocation",
                                target_name=skill_id,
                                arguments={"inputs": inputs or {}},
                                parent_run_id=parent_run_id,
                                step_number=step_count,
                            )
                            skill_res = self.skills_manager.execute_skill(
                                skill_id,
                                inputs=inputs or {},
                                dry_run=dry_run,
                            )
                            step_record["actions"].append({
                                "action_id": act_id,
                                "type": "skill_invocation",
                                "skill": skill_id,
                                "result": skill_res,
                            })
                            total_tool_calls += 1

                    # Execute declared tools that match task
                    for t_name, tool_obj in available_tools.items():
                        # Determine simple argument signature for matching
                        sig = f"{t_name}::{json.dumps(inputs or {}, sort_keys=True)}"
                        call_signatures[sig] += 1

                        # Loop detection check
                        if call_signatures[sig] > manifest.limits.loop_detection_threshold:
                            step_record["warning"] = f"Loop detected: tool '{t_name}' called repeatedly with identical arguments."
                            is_done = True
                            break

                        if total_tool_calls >= manifest.limits.aggregate_tool_limit:
                            step_record["warning"] = "Aggregate tool call limit reached."
                            is_done = True
                            break

                        total_tool_calls += 1
                        act_id = self.agent_store.record_action(
                            run_id=run_id,
                            agent_id=manifest.id,
                            action_type="tool_call",
                            target_name=t_name,
                            arguments=inputs or {},
                            parent_run_id=parent_run_id,
                            step_number=step_count,
                        )
                        res = {"simulated": True, "dry_run": dry_run, "status": "invoked", "tool": t_name}
                        if not dry_run and hasattr(tool_obj, "handler"):
                            try:
                                res = tool_obj.handler(**(inputs or {}))
                            except Exception as e:
                                res = {"error": str(e)}
                        step_record["actions"].append({
                            "action_id": act_id,
                            "tool": t_name,
                            "result": res,
                        })

                    final_output = f"Completed agent task: {task} using {len(available_tools)} tools."
                    is_done = True

                trace.append(step_record)

        except Exception as exc:
            status = "FAILED"
            error_msg = str(exc)
            trace.append({
                "step": step_count + 1,
                "error": error_msg,
                "timestamp": dt.datetime.now().isoformat(timespec="seconds"),
            })

        duration_ms = round((time.time() - start_time) * 1000, 2)
        self.agent_store.record_execution_finish(
            run_id=run_id,
            status=status,
            steps_taken=step_count,
            tool_call_count=total_tool_calls,
            trace=trace,
            output_text=final_output,
            error=error_msg,
        )

        return {
            "run_id": run_id,
            "agent_id": manifest.id,
            "version": manifest.version,
            "status": status,
            "dry_run": dry_run,
            "steps_taken": step_count,
            "tool_call_count": total_tool_calls,
            "output": final_output,
            "trace": trace,
            "error": error_msg,
            "duration_ms": duration_ms,
        }
