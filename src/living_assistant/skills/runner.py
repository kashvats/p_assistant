from __future__ import annotations

import datetime as dt
import time
from typing import Any

from living_assistant.core.workspace import Workspace
from living_assistant.skills.adapters import PortableToolAdapter
from living_assistant.skills.evaluator import evaluate_condition, interpolate_variables
from living_assistant.skills.guards import SkillPermissionGuard, SkillPermissionViolation
from living_assistant.skills.manifest import SkillManifest
from living_assistant.skills.store import SkillStore
from living_assistant.tools.registry import ToolRegistry


class SkillExecutionError(Exception):
    pass


class SkillExecutor:
    """Executes declarative skill workflows with dry-run mutation suppression, step traces,
    condition evaluation, bounded iteration, and durable idempotency.
    """

    def __init__(
        self,
        tool_registry: ToolRegistry,
        skill_store: SkillStore,
        workspace: Workspace,
        approval_manager: Any = None,
        notifier: Any = None,
    ):
        self.tool_registry = tool_registry
        self.skill_store = skill_store
        self.workspace = workspace
        self.approval = approval_manager
        self.notifier = notifier
        self._cancelled_runs: set[str] = set()

    def cancel_execution(self, run_id: str):
        self._cancelled_runs.add(run_id)

    def _execute_single_tool_call(
        self,
        tool_name: str,
        resolved_args: dict[str, Any],
        adapter: PortableToolAdapter,
    ) -> Any:
        if tool_name == "files.list":
            p = resolved_args.get("path", ".")
            return adapter.files_list(p)
        elif tool_name == "files.read":
            p = resolved_args.get("path", "")
            return adapter.files_read(p)
        elif tool_name == "files.move":
            src = resolved_args.get("source", "")
            dst = resolved_args.get("destination", "")
            overwrite = bool(resolved_args.get("overwrite", False))
            return adapter.files_move(src, dst, overwrite=overwrite)
        elif tool_name == "files.write":
            p = resolved_args.get("path", "")
            content = resolved_args.get("content", "")
            return adapter.files_write(p, content)
        elif tool_name == "documents.extract":
            p = resolved_args.get("path", "")
            return adapter.documents_extract(p)
        elif tool_name == "notifications.show":
            title = resolved_args.get("title", "Notification")
            msg = resolved_args.get("message", "")
            return adapter.notifications_show(title, msg)
        elif tool_name == "briefings.get":
            return {
                "date": dt.date.today().isoformat(),
                "calendar_events": [],
                "pending_todos": [],
                "notes": "System operating normally. No pending alerts.",
            }
        elif tool_name == "calendar.list":
            return []
        else:
            tool_obj = self.tool_registry.get(tool_name)
            if not tool_obj:
                raise SkillExecutionError(f"Tool '{tool_name}' is not available in registry.")
            if hasattr(tool_obj, "func") and callable(tool_obj.func):
                return tool_obj.func(**resolved_args)
            return {"status": "invoked"}

    def execute(
        self,
        manifest: SkillManifest,
        inputs: dict[str, Any] | None = None,
        dry_run: bool = False,
        trigger: str = "manual",
        package_hash: str | None = None,
    ) -> dict[str, Any]:
        inputs = inputs or {}

        # Integrity verification: check approval and package hash
        lifecycle = self.skill_store.get_lifecycle(manifest.id)
        if lifecycle and lifecycle.get("state") == "ACTIVE":
            perm_hash = manifest.permissions.permission_hash()
            if not self.skill_store.is_approved(manifest.id, manifest.version, perm_hash, package_hash):
                raise SkillExecutionError(
                    f"Skill '{manifest.id}' has been modified or approval is invalid. Please re-activate."
                )

        guard = SkillPermissionGuard(manifest, self.workspace, self.approval)
        adapter = PortableToolAdapter(
            self.workspace,
            guard=guard,
            dry_run=dry_run,
            notifier=self.notifier,
            store=self.skill_store,
            skill_id=manifest.id,
        )

        run_id = self.skill_store.record_execution_start(
            skill_id=manifest.id,
            version=manifest.version,
            inputs=inputs,
            dry_run=dry_run,
            trigger=trigger,
        )
        adapter.run_id = run_id

        trace: list[dict[str, Any]] = []
        context: dict[str, Any] = {"inputs": inputs}
        outputs: dict[str, Any] = {}
        status = "COMPLETED"
        err_msg = None

        start_time = time.time()
        timeout = manifest.limits.timeout_seconds

        step_map = {s.id: s for s in manifest.workflow}
        idx = 0
        steps = manifest.workflow

        try:
            while idx < len(steps):
                step = steps[idx]

                # Check for user cancellation
                if run_id in self._cancelled_runs:
                    status = "CANCELLED"
                    err_msg = "Execution cancelled by user."
                    break

                # Overall timeout check
                if time.time() - start_time > timeout:
                    status = "FAILED"
                    err_msg = f"Execution timed out after {timeout} seconds."
                    break

                # Security check
                guard.check_tool_allowlist(step.tool)
                adapter.set_step_context(step.id)

                # Declarative condition check (when / condition)
                condition_expr = step.when or step.condition
                if condition_expr and not evaluate_condition(condition_expr, context):
                    trace.append({
                        "step_id": step.id,
                        "skipped": True,
                        "reason": f"Condition '{condition_expr}' evaluated to False.",
                    })
                    idx += 1
                    continue

                # Handle bounded iteration (for_each) vs single execution
                if step.for_each:
                    raw_collection = interpolate_variables(step.for_each, context)
                    if isinstance(raw_collection, list):
                        collection = raw_collection[:step.max_iterations]
                    elif raw_collection:
                        collection = [raw_collection]
                    else:
                        collection = []

                    iter_results = []
                    step_start = time.time()
                    for item in collection:
                        item_ctx = {**context, "item": item}
                        resolved_args = interpolate_variables(step.arguments, item_ctx)
                        res = self._execute_single_tool_call(step.tool, resolved_args, adapter)
                        iter_results.append(res)

                    trace.append({
                        "step_id": step.id,
                        "tool": step.tool,
                        "description": step.description,
                        "iteration_count": len(iter_results),
                        "duration_ms": round((time.time() - step_start) * 1000, 2),
                    })

                    if step.output_variable:
                        context[step.output_variable] = iter_results
                        context[step.id] = iter_results

                else:
                    # Single execution with retries
                    step_start = time.time()
                    resolved_args = interpolate_variables(step.arguments, context)
                    step_record = {
                        "step_id": step.id,
                        "tool": step.tool,
                        "description": step.description,
                        "started_at": dt.datetime.now().isoformat(timespec="seconds"),
                        "arguments": resolved_args,
                    }

                    step_result = None
                    last_exc = None
                    for attempt in range(step.retries + 1):
                        try:
                            step_result = self._execute_single_tool_call(step.tool, resolved_args, adapter)
                            last_exc = None
                            break
                        except Exception as exc:
                            last_exc = exc
                            if attempt < step.retries:
                                time.sleep(step.retry_delay_seconds)

                    if last_exc is not None:
                        if step.on_failure == "continue":
                            step_record["warning"] = f"Step failed but on_failure=continue: {last_exc}"
                            step_result = {"error": str(last_exc)}
                        elif step.on_failure == "fallback" and step.fallback_step_id:
                            step_record["fallback"] = f"Step failed; jumping to {step.fallback_step_id}"
                            trace.append(step_record)
                            if step.fallback_step_id in step_map:
                                idx = steps.index(step_map[step.fallback_step_id])
                                continue
                            else:
                                raise SkillExecutionError(f"Fallback step '{step.fallback_step_id}' not found.")
                        else:
                            raise last_exc

                    step_record["result"] = step_result
                    step_record["duration_ms"] = round((time.time() - step_start) * 1000, 2)
                    trace.append(step_record)

                    if step.output_variable:
                        context[step.output_variable] = step_result
                    context[step.id] = step_result

                idx += 1

            outputs = {
                "actions": adapter.recorded_actions,
                "context": {k: v for k, v in context.items() if k != "inputs"},
                "dry_run": dry_run,
            }

            # Record undo actions if executed live
            if not dry_run:
                for act in adapter.recorded_actions:
                    if "undo" in act:
                        self.skill_store.record_undo_action(run_id, "move", "files.move", act["undo"])

        except Exception as exc:
            status = "FAILED"
            err_msg = str(exc)
            trace.append({
                "step_id": "error",
                "error": err_msg,
                "timestamp": dt.datetime.now().isoformat(timespec="seconds"),
            })

        finally:
            self.skill_store.record_execution_finish(
                run_id=run_id,
                status=status,
                outputs=outputs,
                trace=trace,
                error=err_msg,
            )

        return {
            "run_id": run_id,
            "status": status,
            "skill_id": manifest.id,
            "version": manifest.version,
            "dry_run": dry_run,
            "outputs": outputs,
            "trace": trace,
            "error": err_msg,
        }
