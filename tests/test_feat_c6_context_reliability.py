"""
Automated Test Suite for C6: Context and Reliability.
Tests:
- Oversized context is trimmed within budget (usable_context = runtime_limit - reserved_output - safety_margin).
- Invalid structured output is repaired or rejected (schema validation).
- Personal memory never enters company context (strict boundary check).
- Extended B2 verification checks (lint, syntax, typecheck).
- Cloud escalation approval gate.
"""

from __future__ import annotations

from pathlib import Path
import pytest
from pydantic import BaseModel, Field

from living_assistant.agents.software_company.context_builder import (
    BuiltContext,
    CloudEscalationGatekeeper,
    ContextBuilder,
    ContextItem,
    ExtendedVerifier,
    OutputSchemaValidator,
    TaskPolicy,
    TokenBudgetConfig,
)
from living_assistant.core.approval import ApprovalManager, ApprovalStore
from living_assistant.core.workspace import Workspace


class SamplePlanSchema(BaseModel):
    task_id: str
    goal: str
    steps: list[str] = Field(default_factory=list)


def test_c6_token_budget_calculation_and_context_trimming():
    """Verify usable_context = runtime_limit - reserved_output - safety_margin, and oversized items are trimmed."""
    config = TokenBudgetConfig(runtime_limit=1000, reserved_output=200, safety_margin=100)
    assert config.usable_context == 700

    builder = ContextBuilder(config)

    items = [
        ContextItem(source="spec", content="Short spec", inclusion_reason="core goal"),
        # Massive item exceeding budget
        ContextItem(source="code", content="x = 1\n" * 2000, inclusion_reason="historical codebase"),
    ]

    built = builder.build_context(policy=TaskPolicy.CODING, candidate_items=items)
    assert built.total_tokens <= config.usable_context
    assert len(built.discarded_items) >= 1
    assert any("DISCARDED" in d["reason"] for d in built.discarded_items)


def test_c6_personal_memory_never_enters_company_context():
    """Verify personal memory boundaries are strictly maintained; personal markers are filtered."""
    builder = ContextBuilder()

    items = [
        ContextItem(source="spec", content="Implement authentication endpoint", inclusion_reason="spec"),
        ContextItem(source="personal", content="Remember that user's private key is sk-12345", inclusion_reason="note"),
        ContextItem(source="personal", content="Set a personal reminder to buy milk", inclusion_reason="reminder"),
    ]

    built = builder.build_context(policy=TaskPolicy.CODING, candidate_items=items, disallow_personal_memory=True)
    assert len(built.items) == 1
    assert built.items[0].source == "spec"
    assert len(built.discarded_items) == 2
    for d in built.discarded_items:
        assert "personal memory boundary" in d["reason"].lower()


def test_c6_structured_output_validation_repair_and_rejection():
    """Verify structured output validator parses json in code fences, repairs minor flaws, and rejects invalid schemas."""
    # 1. Valid with code fence
    valid_fenced = """Here is the plan:
```json
{
  "task_id": "t1",
  "goal": "Write code",
  "steps": ["step1", "step2"]
}
```
"""
    ok, inst, err = OutputSchemaValidator.validate_or_repair(valid_fenced, SamplePlanSchema)
    assert ok is True
    assert inst.task_id == "t1"
    assert inst.steps == ["step1", "step2"]

    # 2. Repairable extra prose wrapping JSON object
    prose_wrapped = 'Leading analysis... {"task_id": "t2", "goal": "Repair", "steps": []} Trailing notes...'
    ok, inst, err = OutputSchemaValidator.validate_or_repair(prose_wrapped, SamplePlanSchema)
    assert ok is True
    assert inst.task_id == "t2"

    # 3. Invalid schema fields (missing required task_id)
    invalid_schema = '{"goal": "Missing task_id"}'
    ok, inst, err = OutputSchemaValidator.validate_or_repair(invalid_schema, SamplePlanSchema)
    assert ok is False
    assert "Schema validation error" in err


def test_c6_extended_b2_verifier_and_cloud_escalation(tmp_path: Path):
    """Verify extended verifier AST check and cloud escalation approval gate."""
    ws_dir = tmp_path / "extended_ws"
    ws_dir.mkdir()
    (ws_dir / "valid.py").write_text("def test(): pass\n", encoding="utf-8")

    ws = Workspace([ws_dir])
    verifier = ExtendedVerifier(workspace=ws)
    res = verifier.run_extended_verification()
    assert res["lint_passed"] is True

    # Cloud escalation approval gate check
    db_file = tmp_path / "escalation.sqlite3"
    app_store = ApprovalStore(db_path=db_file)
    app_mgr = ApprovalManager(store=app_store, interactive=False)

    gate = CloudEscalationGatekeeper(approval_manager=app_mgr)
    req_res = gate.request_cloud_escalation(
        task_id="task_cloud_1",
        target_cloud_model="anthropic:claude-3-7-sonnet",
        reason="Complex architectural refactoring",
    )
    assert req_res["requires_approval"] is True
    assert req_res["allowed"] is False
    assert req_res["status"] == "PENDING_APPROVAL"
