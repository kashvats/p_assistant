from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

from living_assistant.core.approval import ApprovalManager
from living_assistant.learning.eval_engine import EvaluationEngine
from living_assistant.learning.improvements import ImprovementEngine
from living_assistant.security.security_utils import redact_secrets

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.IGNORECASE | re.DOTALL)


class AutonomousRepairLoop:
    """Bounded repair/evaluate loop for failed improvement evaluations.

    The loop never applies or promotes code. It creates new reviewable proposals and
    evaluates them using the exact plan of the failed evaluation. A single explicit
    approval authorizes only the bounded repair operation; individual evaluation
    calls use an in-process, object-identity capability that cannot be supplied via
    the JSON tool interface.
    """

    def __init__(
        self,
        improvements: ImprovementEngine,
        evaluations: EvaluationEngine,
        approval: ApprovalManager,
        repairer: Callable[[str, str], Any],
        config: dict | None = None,
    ):
        self.improvements = improvements
        self.evaluations = evaluations
        self.approval = approval
        self.repairer = repairer
        repair_cfg = ((config or {}).get("self_improvement", {}) or {}).get("repair", {}) or {}
        self.enabled = bool(repair_cfg.get("enabled", True))
        self.default_max_cycles = max(1, min(int(repair_cfg.get("max_cycles", 3)), 8))
        self.max_cycles_limit = max(1, min(int(repair_cfg.get("max_cycles_limit", 5)), 8))
        self.max_context_chars = max(4_000, min(int(repair_cfg.get("max_context_chars", 24_000)), 80_000))
        self.authorization_ttl_seconds = max(300, min(int(repair_cfg.get("authorization_ttl_seconds", 7_200)), 43_200))

    @staticmethod
    def _repair_payload(value: Any) -> dict:
        if isinstance(value, dict) and isinstance(value.get("new_content"), str):
            return value
        answer = value.get("answer") if isinstance(value, dict) else value
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError("Repair agent returned no usable response.")
        text = answer.strip()
        match = _JSON_FENCE_RE.match(text)
        if match:
            text = match.group(1).strip()
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start < 0 or end <= start:
                raise ValueError("Repair agent must return JSON containing new_content, title, and rationale.")
            try:
                payload = json.loads(text[start : end + 1])
            except json.JSONDecodeError as exc:
                raise ValueError("Repair agent returned malformed JSON.") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("new_content"), str):
            raise ValueError("Repair agent response must contain a string new_content field.")
        payload.setdefault("title", "Autonomous repair candidate")
        payload.setdefault("rationale", "Repair candidate generated from a failed isolated evaluation.")
        return payload

    def _failure_context(self, evaluation: dict, proposal: dict, target_path: str) -> str:
        result = {
            "evaluation_id": evaluation.get("id"),
            "status": evaluation.get("status"),
            "verdict": evaluation.get("verdict"),
            "error": evaluation.get("error"),
            "result": evaluation.get("result", {}),
        }
        cross_file = self.improvements.context(target_path, max_files=6, max_chars_per_file=3_000)
        payload = {
            "failed_evaluation": result,
            "candidate_that_failed": proposal.get("proposed_content", ""),
            "cross_file_context": cross_file,
        }
        return redact_secrets(json.dumps(payload, sort_keys=True, default=str), self.max_context_chars)

    @staticmethod
    def _plan_arguments(plan: dict) -> dict:
        return {
            "project_path": plan.get("project_path"),
            "test_commands": list(plan.get("test_commands") or []),
            "lint_commands": list(plan.get("lint_commands") or []),
            "benchmark_commands": list(plan.get("benchmark_commands") or []),
            "repetitions": plan.get("repetitions"),
            "max_latency_regression_pct": plan.get("max_latency_regression_pct"),
            "max_memory_regression_pct": plan.get("max_memory_regression_pct"),
            "execution_provider": plan.get("execution_provider"),
            "sandbox_image": plan.get("sandbox_image"),
            "sandbox_network": plan.get("sandbox_network"),
        }

    def run(self, failed_evaluation_id: str, max_cycles: int | None = None) -> dict:
        if not self.enabled:
            return {"ok": False, "error": "Autonomous repair is disabled in config."}
        failed = self.evaluations.store.get(failed_evaluation_id)
        if not failed:
            return {"ok": False, "error": "Unknown evaluation id."}
        if failed.get("verdict") == "passed":
            return {"ok": False, "error": "The supplied evaluation already passed; repair is unnecessary."}
        if failed.get("status") not in {"completed", "error"}:
            return {"ok": False, "error": "Repair requires a completed failed/error evaluation."}

        original = self.improvements.store.get(str(failed.get("proposal_id") or ""))
        if not original:
            return {"ok": False, "error": "The proposal for this evaluation no longer exists."}
        if original.get("status") != "pending":
            return {"ok": False, "error": f"Proposal is {original.get('status')}; repair only operates on pending candidates."}

        cycles = self.default_max_cycles if max_cycles is None else int(max_cycles)
        cycles = max(1, min(cycles, self.max_cycles_limit))
        plan = dict(failed.get("config") or {})
        if not plan:
            return {"ok": False, "error": "Failed evaluation is missing its immutable evaluation plan."}

        # Re-resolve the stored plan through the normal safety checks before asking
        # for approval. This prevents old/tampered evaluation metadata from becoming
        # a command-execution capability.
        try:
            checked_plan = self.evaluations._resolve_plan(
                original,
                None,
                plan.get("project_path"),
                list(plan.get("test_commands") or []),
                list(plan.get("lint_commands") or []),
                list(plan.get("benchmark_commands") or []),
                plan.get("repetitions"),
                plan.get("max_latency_regression_pct"),
                plan.get("max_memory_regression_pct"),
                plan.get("execution_provider"),
                plan.get("sandbox_image"),
                plan.get("sandbox_network"),
            )
        except Exception as exc:
            return {"ok": False, "error": f"Stored repair evaluation plan is no longer valid: {exc}"}

        approval_summary = {
            "failed_evaluation_id": failed_evaluation_id,
            "target": checked_plan["target_path"],
            "project": checked_plan["project_path"],
            "tests": checked_plan["test_commands"],
            "lint": checked_plan["lint_commands"],
            "benchmarks": checked_plan["benchmark_commands"],
            "execution_provider": checked_plan["execution_provider"],
            "sandbox_image": checked_plan.get("sandbox_image"),
            "max_cycles": cycles,
        }
        action = "Run bounded autonomous repair loop: " + json.dumps(approval_summary, sort_keys=True, separators=(",", ":"))
        reason = (
            "May generate up to the approved number of new pending proposals and run the exact listed isolated "
            "evaluation plan for each candidate. It never applies or promotes a candidate automatically."
        )
        req = self.approval.request(action, reason, "SELF_REPAIR")
        if not req.get("allowed"):
            return {"ok": False, "approval_required": True, **req, "plan": approval_summary}

        authorization = self.evaluations._create_repair_authorization(
            checked_plan,
            max_uses=cycles,
            ttl_seconds=self.authorization_ttl_seconds,
        )
        attempts: list[dict] = []
        current_evaluation = failed
        current_proposal = original

        for cycle in range(1, cycles + 1):
            context = self._failure_context(current_evaluation, current_proposal, checked_plan["target_path"])
            task = (
                "Repair the failed candidate described in the context. Return JSON only with keys new_content, title, "
                "and rationale. new_content must be the complete replacement file, preserve unrelated existing "
                "functions/classes/methods, and address the observed test/lint/benchmark failure. Do not include "
                "markdown fences or commentary outside the JSON object."
            )
            try:
                raw = self.repairer(task, context)
                payload = self._repair_payload(raw)
            except Exception as exc:
                attempts.append({"cycle": cycle, "stage": "repair_generation", "ok": False, "error": redact_secrets(exc, 1200)})
                continue

            proposed = self.improvements.propose(
                checked_plan["target_path"],
                payload["new_content"],
                str(payload.get("title") or "Autonomous repair candidate")[:300],
                str(payload.get("rationale") or "Repair generated from failed evaluation.")[:4000],
                tests=list(checked_plan.get("test_commands") or []),
            )
            if not proposed.get("id"):
                attempts.append({
                    "cycle": cycle,
                    "stage": "proposal",
                    "ok": False,
                    "error": redact_secrets(proposed.get("error") or "Repair proposal was rejected.", 1200),
                    "ast_guard": bool(proposed.get("ast_guard")),
                })
                current_evaluation = {
                    "id": None,
                    "status": "error",
                    "verdict": "error",
                    "error": proposed.get("error") or "Repair proposal was rejected.",
                    "result": proposed,
                }
                continue

            evaluated = self.evaluations.evaluate(
                proposed["id"],
                **self._plan_arguments(checked_plan),
                _repair_authorization=authorization,
            )
            attempt = {
                "cycle": cycle,
                "stage": "evaluation",
                "ok": bool(evaluated.get("ok")),
                "proposal_id": proposed["id"],
                "evaluation_id": evaluated.get("id"),
                "status": evaluated.get("status"),
                "verdict": evaluated.get("verdict"),
            }
            if evaluated.get("error"):
                attempt["error"] = redact_secrets(evaluated["error"], 1200)
            attempts.append(attempt)

            if evaluated.get("ok") and evaluated.get("verdict") == "passed":
                return {
                    "ok": True,
                    "repaired": True,
                    "source_evaluation_id": failed_evaluation_id,
                    "proposal_id": proposed["id"],
                    "evaluation_id": evaluated.get("id"),
                    "cycles_used": cycle,
                    "attempts": attempts,
                    "applied": False,
                    "promoted": False,
                    "message": "Repair candidate passed isolated evaluation and remains pending for human-controlled promotion/apply.",
                }
            current_evaluation = evaluated
            current_proposal = proposed

        return {
            "ok": False,
            "repaired": False,
            "source_evaluation_id": failed_evaluation_id,
            "cycles_used": cycles,
            "attempts": attempts,
            "applied": False,
            "promoted": False,
            "error": f"No repair candidate passed after {cycles} cycle(s).",
        }
