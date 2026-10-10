"""
Test Suite: Personal Assistant Director, Software Company Dynamic Roles & Permission Scoping.
Features Covered: F5 (Director), F6 (Software Company Roles & QA Gate), F7 (Specialists), F8 (Permissions & Model Routing).
Tiers Covered: Tier 1 (Features), Tier 2 (Boundaries), Tier 3 (Cross-Feature), Tier 4 (Real-World Cart Vertical Slice).
Mandatory Adversarial Tests: Scenarios (a) through (e).
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
import pytest

from living_assistant.core.workspace import Workspace, WorkspaceViolation
from living_assistant.core.approval import ApprovalManager, ApprovalStore
from living_assistant.tools.registry import ToolRegistry
from living_assistant.tools.base import Tool

from living_assistant.security.permissions import (
    TaskScopedPermissionEngine,
    TaskScope,
    PermissionDecision,
    PermissionDeniedViolation,
    IntegrityMode,
    TaskComplexity,
    LatencyCostPreference,
    DynamicModelRouter,
    ModelRouteRequest,
    VRAMLeaseManager,
    ROLE_CAPABILITY_MATRIX,
)
from living_assistant.security.security_policy import Risk

from living_assistant.agents.director import (
    PersonalAssistantDirector,
    ExecutionPlan,
    CompanyGoal,
    FunctionalSpec,
    DirectorResponse,
)

from living_assistant.agents.software_company.models import (
    CompanyPlan,
    DeveloperOutput,
    QAReport,
    QAFailureDetail,
    VerificationVerdict,
    CriteriaEvidence,
    TaskSpec,
    TaskNode,
    WorkflowStatus,
    LicenseVerdict,
    CompanyWorkflowResult,
    TaskBudget,
    GitHubCandidate,
    GitHubResearchReport,
    ToolOperatorReport,
    ToolExecutionStep,
)
from living_assistant.agents.software_company.roles import (
    RoleProfile,
    RoleRegistry,
    default_role_registry,
    ALL_ROLES,
)
from living_assistant.agents.software_company.workflow import (
    CompanyWorkflow,
    TestHarness,
    ForgedQAReportViolation,
    UnauthorizedCompletionViolation,
)


# =============================================================================
# Helper Fixtures & Mocks
# =============================================================================

@pytest.fixture
def mock_workspace(tmp_path: Path) -> Workspace:
    return Workspace([tmp_path])


@pytest.fixture
def approval_manager(tmp_path: Path) -> ApprovalManager:
    store = ApprovalStore(db_path=tmp_path / "approvals.sqlite")
    return ApprovalManager(interactive=False, store=store)


@pytest.fixture
def standard_tools() -> ToolRegistry:
    t_read = Tool("read_file", "Read file", {}, lambda path: "file-content")
    t_write = Tool("write_file", "Write file", {}, lambda path, content: "ok")
    t_edit = Tool("edit_file", "Edit file", {}, lambda path, old_str, new_str: "ok")
    t_list = Tool("list_files", "List files", {}, lambda path=".": [])
    t_search = Tool("search_files", "Search files", {}, lambda pattern="*": [])
    t_cmd = Tool("run_command", "Run command", {}, lambda command: "output")
    t_git_status = Tool("git_status", "Git status", {}, lambda: "clean")
    t_git_diff = Tool("git_diff", "Git diff", {}, lambda: "")
    return ToolRegistry([t_read, t_write, t_edit, t_list, t_search, t_cmd, t_git_status, t_git_diff])


# =============================================================================
# Tier 1: Functional Feature Tests (F5, F6, F7, F8)
# =============================================================================

def test_f5_director_intent_classification():
    director = PersonalAssistantDirector()

    # Canonical intent tests
    assert director.classify_intent("Remind me to call Mom tomorrow at 5pm") == "personal"
    assert director.classify_intent("Check CPU usage and system status") == "technical"
    assert director.classify_intent("Implement a FastAPI endpoint for user cart") == "coding"
    assert director.classify_intent("Search the web for python asyncio best practices") == "research"
    assert director.classify_intent("Download video from https://example.com/video") == "media"
    assert director.classify_intent("Take a screenshot of the active window") == "computer"
    assert director.classify_intent("Write a script to export sales and also remind me at 4pm") == "mixed"


def test_f5_director_directive_b4_spec_generation_and_approval(approval_manager: ApprovalManager):
    director = PersonalAssistantDirector(approval_manager=approval_manager)

    goal = CompanyGoal(
        goal="Implement Cart Checkout Service",
        requirements=["Calculate taxes", "Process payments", "Clear cart"],
    )

    # 1. Product Manager generates FunctionalSpec
    spec = director.generate_requirements_spec(goal)
    assert isinstance(spec, FunctionalSpec)
    assert "Cart Checkout" in spec.title
    assert len(spec.acceptance_criteria) >= 3
    assert goal.spec_status == "AWAITING_USER_APPROVAL"

    # 2. Register with ApprovalManager
    appr_id = director.request_spec_approval(goal)
    assert appr_id.startswith("appr-")
    assert goal.approval_id == appr_id

    # 3. User approval resolves approval
    res = approval_manager.store.resolve(appr_id, True)
    assert res["ok"] is True
    assert res["approval"]["status"] == "approved"


def test_f5_director_dual_mode_synthesis():
    director = PersonalAssistantDirector()

    plan = ExecutionPlan(
        intent="mixed",
        primary_domain="coding",
        domains_involved=["personal", "coding"],
        synthesis_instructions="Summarize both reminder and code output.",
    )

    action_results = [
        {"action": {"domain": "personal"}, "status": "success", "result": "Reminder set for 4pm."},
    ]
    company_result = {
        "status": "COMPLETED",
        "output": "Cart service created successfully.",
        "files_modified": ["src/cart.py"],
        "final_qa_report": {"status": "ACCEPTED", "passed": 5, "failed": 0},
    }

    # Deterministic synthesis fallback
    text = director.synthesize_response(plan, action_results, company_result)
    assert "Assistant Actions" in text
    assert "Reminder set for 4pm" in text
    assert "Software Engineering" in text
    assert "Cart service created successfully" in text
    assert "QA Verification: ACCEPTED" in text


def test_f6_role_catalogue_completeness():
    reg = default_role_registry
    roles = reg.list_roles()
    assert len(roles) >= 28, f"Expected 28 dynamic roles, found {len(roles)}"

    departments = {r.department for r in roles}
    expected_deps = {"executive", "design", "engineering", "quality", "security", "governance", "specialist"}
    assert expected_deps.issubset(departments)

    # Specific required roles
    for r in [
        "manager", "product", "ux_designer", "ui_designer", "design_system",
        "architect", "backend_dev", "frontend_dev", "database", "data_analyst",
        "ai_engineer", "devops", "qa_engineer", "performance", "accessibility",
        "security_lead", "appsec", "vapt", "security_auditor", "seo",
        "code_reviewer", "change_manager", "release_manager", "verifier",
        "tool_operator", "github_researcher", "web_researcher", "computer_operator",
    ]:
        assert reg.contains(r), f"Missing role: {r}"


def test_f6_role_tool_scoping(standard_tools: ToolRegistry):
    reg = default_role_registry

    # Manager cannot write or execute
    mgr_tools = reg.get_scoped_tools("manager", standard_tools)
    assert "read_file" in mgr_tools.names()
    assert "write_file" not in mgr_tools.names()
    assert "run_command" not in mgr_tools.names()

    # QA engineer has write_file and run_command
    qa_tools = reg.get_scoped_tools("qa_engineer", standard_tools)
    assert "write_file" in qa_tools.names()
    assert "run_command" in qa_tools.names()

    # GitHub researcher has read_file only, no mutations
    gh_tools = reg.get_scoped_tools("github_researcher", standard_tools)
    assert "read_file" in gh_tools.names()
    assert "write_file" not in gh_tools.names()
    assert "run_command" not in gh_tools.names()


def test_f6_evidence_based_qa_report(mock_workspace: Workspace):
    harness = TestHarness(mock_workspace)

    # Run against a mock/simple passing command
    report = harness.run_tests(
        task_id="task_001",
        test_command="python -c \"import sys; sys.exit(0)\"",
    )
    assert report.status == "ACCEPTED"
    assert report.exit_code == 0
    assert report.generated_by_harness is True
    assert len(report.log_hash) == 64  # SHA-256


def test_f7_specialist_tool_operator_pipeline():
    steps = [
        ToolExecutionStep(step_number=1, tool_name="search_files", arguments={"pattern": "*.py"}, output=["main.py"]),
        ToolExecutionStep(step_number=2, tool_name="read_file", arguments={"path": "main.py"}, output="code"),
    ]
    report = ToolOperatorReport(
        task_id="task_tool_01",
        action_sequence="search -> read",
        total_steps=2,
        successful_steps=2,
        steps=steps,
        status="SUCCESS",
    )
    assert report.status == "SUCCESS"
    assert len(report.steps) == 2


def test_f7_specialist_github_researcher_license_audit():
    cand1 = GitHubCandidate(
        repo_url="https://github.com/fastapi/fastapi",
        name="fastapi",
        license_spdx="MIT",
        health_score=0.95,
        recommendation=LicenseVerdict.REUSE,
        justification="Permissive MIT license with strong health.",
    )
    cand2 = GitHubCandidate(
        repo_url="https://github.com/bad/gpl-tool",
        name="gpl-tool",
        license_spdx="AGPL-3.0",
        health_score=0.5,
        recommendation=LicenseVerdict.REJECT,
        justification="Incompatible copyleft license for closed-source embedding.",
    )
    report = GitHubResearchReport(
        task_id="task_gh_01",
        query="API framework",
        candidates=[cand1, cand2],
        chosen_recommendation=cand1,
        license_audit_passed=True,
        summary="Evaluated 2 candidates; fastapi recommended for direct consumption.",
    )
    assert report.chosen_recommendation.recommendation == LicenseVerdict.REUSE
    assert cand2.recommendation == LicenseVerdict.REJECT


def test_f8_permission_engine_evaluation(mock_workspace: Workspace):
    engine = TaskScopedPermissionEngine(mock_workspace)

    scope = TaskScope(
        task_id="task_dev_01",
        role="backend_dev",
        target_paths=["src/api.py"],
        frozen_paths=["tests/test_api.py"],
    )

    # 1. Allowed write in target path
    d1 = engine.evaluate("backend_dev", scope, "write_file", {"path": "src/api.py", "content": "code"})
    assert d1.allowed is True

    # 2. Blocked write outside target paths
    d2 = engine.evaluate("backend_dev", scope, "write_file", {"path": "src/other.py", "content": "code"})
    assert d2.allowed is False
    assert "outside task" in d2.reason


def test_f8_dynamic_model_routing_and_vram_lease():
    lease_mgr = VRAMLeaseManager(total_vram_mb=4096)
    router = DynamicModelRouter(lease_manager=lease_mgr)

    # 1. Frontier reasoning for manager
    req_mgr = ModelRouteRequest(task_description="Decompose project", role="manager", complexity=TaskComplexity.HIGH)
    res_mgr = router.route(req_mgr)
    assert res_mgr.tier == "frontier_reasoning"

    # 2. Primary coding for backend dev
    req_dev = ModelRouteRequest(task_description="Implement endpoint", role="backend_dev", complexity=TaskComplexity.MEDIUM)
    res_dev = router.route(req_dev)
    assert res_dev.tier == "primary_coding"

    # 3. Offline forced local
    req_local = ModelRouteRequest(task_description="Simple parsing", role="tool_operator", force_local=True)
    res_local = router.route(req_local)
    assert res_local.tier == "local_edge"

    # 4. Directive B6: VRAM Lease test
    lease1 = lease_mgr.acquire_lease(requested_mb=3000)
    assert lease1 is not None
    # Cannot acquire second 2048MB lease with 3000MB active out of 4096MB
    lease2 = lease_mgr.acquire_lease(requested_mb=2048)
    assert lease2 is None
    lease_mgr.release_lease(lease1.lease_id)
    # Now can acquire
    lease3 = lease_mgr.acquire_lease(requested_mb=2048)
    assert lease3 is not None


# =============================================================================
# Tier 2: Boundary & Edge Case Tests
# =============================================================================

def test_f5_empty_prompt_handling():
    director = PersonalAssistantDirector()
    plan = director.route_request("")
    assert plan.intent == "personal"
    assert "conversational" in plan.rationale.lower()


def test_f5_ambiguous_intent_fallback():
    director = PersonalAssistantDirector()
    plan = director.route_request("Hello there")
    assert plan.intent == "personal"


def test_f6_qa_remediation_loop_max_3_cycles(mock_workspace: Workspace):
    # Test harness simulating 3 failures, then passing on cycle 3
    cycle_counter = [0]

    class FlakyHarness:
        def run_tests(self, task_id, test_command="pytest", test_paths=None, timeout_seconds=120.0):
            cycle_counter[0] += 1
            if cycle_counter[0] <= 2:
                return QAReport(
                    task_id=task_id,
                    status="REJECTED",
                    total_tests=3,
                    passed=2,
                    failed=1,
                    failures=[QAFailureDetail(test_name="test_fail", error_message="Assertion failed")],
                    feedback="Failed assertion",
                    exit_code=1,
                    log_hash=f"hash_fail_{cycle_counter[0]}",
                    generated_by_harness=True,
                )
            return QAReport(
                task_id=task_id,
                status="ACCEPTED",
                total_tests=3,
                passed=3,
                failed=0,
                feedback="All tests pass",
                exit_code=0,
                log_hash="hash_pass_3",
                generated_by_harness=True,
            )

    wf = CompanyWorkflow(
        workspace=mock_workspace,
        tool_registry=ToolRegistry([]),
        test_harness=FlakyHarness(),
        contractor_executor=lambda t, c, r: {"ok": True, "output": "fixed"},
        budget=TaskBudget(max_remediation_cycles=3),
    )

    res = wf.run_workflow(goal="Fix failing code")
    assert res.status == WorkflowStatus.COMPLETED
    assert res.remediation_cycles == 2
    assert len(res.qa_reports) == 3


def test_f6_max_remediation_exceeded_escalates_to_human(mock_workspace: Workspace):
    class AlwaysFailingHarness:
        def run_tests(self, task_id, test_command="pytest", test_paths=None, timeout_seconds=120.0):
            return QAReport(
                task_id=task_id,
                status="REJECTED",
                total_tests=1,
                passed=0,
                failed=1,
                failures=[QAFailureDetail(test_name="test_hard", error_message="Unfixable bug")],
                feedback="Unfixable bug",
                exit_code=1,
                log_hash="hash_unfixable",
                generated_by_harness=True,
            )

    wf = CompanyWorkflow(
        workspace=mock_workspace,
        tool_registry=ToolRegistry([]),
        test_harness=AlwaysFailingHarness(),
        contractor_executor=lambda t, c, r: {"ok": True, "output": "tried"},
        budget=TaskBudget(max_remediation_cycles=3),
    )

    res = wf.run_workflow(goal="Bug that cannot be fixed")
    assert res.status == WorkflowStatus.ESCALATED_TO_HUMAN
    assert res.escalated_to_human is True
    assert res.verdict is None
    assert len(res.qa_reports) == 4  # Initial + 3 remediation cycles


def test_f8_sensitive_file_approval_interception(mock_workspace: Workspace):
    engine = TaskScopedPermissionEngine(mock_workspace)
    scope = TaskScope(task_id="t1", role="backend_dev")

    # .env write requires user approval
    d = engine.evaluate("backend_dev", scope, "write_file", {"path": ".env", "content": "SECRET=1"})
    assert d.requires_approval is True
    assert d.risk == Risk.DESTRUCTIVE


def test_f8_destructive_command_blocking(mock_workspace: Workspace):
    engine = TaskScopedPermissionEngine(mock_workspace)
    scope = TaskScope(task_id="t1", role="backend_dev")

    d = engine.evaluate("backend_dev", scope, "run_command", {"command": "rm -rf /"})
    assert d.allowed is False
    assert d.risk == Risk.DESTRUCTIVE


# =============================================================================
# Tier 3: Cross-Feature Integration Tests
# =============================================================================

def test_tier3_director_to_software_company_dispatch(mock_workspace: Workspace, approval_manager: ApprovalManager):
    class MockHarness:
        def run_tests(self, task_id, test_command="pytest", test_paths=None, timeout_seconds=120.0):
            return QAReport(
                task_id=task_id,
                status="ACCEPTED",
                total_tests=5,
                passed=5,
                failed=0,
                feedback="All tests passed cleanly.",
                exit_code=0,
                log_hash="hash_e2e_accepted_12345",
                commit_sha="sha_clean_baseline",
                generated_by_harness=True,
            )

    wf = CompanyWorkflow(
        workspace=mock_workspace,
        tool_registry=ToolRegistry([]),
        test_harness=MockHarness(),
        contractor_executor=lambda t, c, r: {"ok": True, "output": "Cart logic implemented"},
    )

    director = PersonalAssistantDirector(
        software_company=wf,
        approval_manager=approval_manager,
    )

    # Execute with auto_approve_spec=True
    resp = director.execute(
        user_prompt="Implement a shopping cart module",
        auto_approve_spec=True,
    )

    assert isinstance(resp, DirectorResponse)
    assert resp.plan.intent == "coding"
    assert resp.domain_results["company_task"]["status"] == WorkflowStatus.COMPLETED
    assert "Software Engineering" in resp.answer
    assert "QA Verification: ACCEPTED" in resp.answer


# =============================================================================
# Tier 4: Real-World Workload Scenario ("Implement Cart" Thin Vertical Slice)
# =============================================================================

def test_tier4_end_to_end_cart_vertical_slice(mock_workspace: Workspace):
    """
    Phase B Directives B1-B7 Thin Vertical Slice:
    Requirements -> Spec Approval -> Manager -> Backend Leaf -> Frozen Tests ->
    Harness QA Rejection -> Remediation Fix -> QA Accept -> Final Verifier -> COMPLETED.
    """
    root = mock_workspace.roots[0]
    cart_dir = root / "src" / "living_assistant" / "cart"
    cart_dir.mkdir(parents=True, exist_ok=True)
    tests_dir = root / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)

    test_cart_file = tests_dir / "test_cart.py"

    # Step 1: Pre-freeze QA tests (Directive B2)
    test_cart_file.write_text(
        "def test_cart_math():\n    assert 1 + 1 == 2\n",
        encoding="utf-8",
    )

    harness_calls = [0]

    class CartHarness:
        def run_tests(self, task_id, test_command="pytest", test_paths=None, timeout_seconds=120.0):
            harness_calls[0] += 1
            if harness_calls[0] == 1:
                # First run: deliberate failure (Directive B2 & B3)
                return QAReport(
                    task_id=task_id,
                    status="REJECTED",
                    total_tests=5,
                    passed=4,
                    failed=1,
                    failures=[QAFailureDetail(test_name="test_invalid_quantity", error_message="ValueError not raised on quantity <= 0")],
                    feedback="Quantity validation failed: negative quantity accepted.",
                    test_command="pytest tests/test_cart.py",
                    exit_code=1,
                    log_hash="hash_cart_fail_4e81b1",
                    commit_sha="sha_cart_dirty",
                    generated_by_harness=True,
                )
            # Second run: remediation passes
            return QAReport(
                task_id=task_id,
                status="ACCEPTED",
                total_tests=5,
                passed=5,
                failed=0,
                feedback="All cart tests passed including edge case validations.",
                test_command="pytest tests/test_cart.py",
                exit_code=0,
                log_hash="hash_cart_pass_4e81b2",
                commit_sha="sha_cart_clean",
                generated_by_harness=True,
            )

    def mock_cart_contractor(prompt, context, tools):
        # Developer implements models and service
        (cart_dir / "models.py").write_text("class CartItem:\n    pass\n", encoding="utf-8")
        (cart_dir / "service.py").write_text("class CartService:\n    pass\n", encoding="utf-8")
        return {"ok": True, "output": "Created CartItem and CartService"}

    wf = CompanyWorkflow(
        workspace=mock_workspace,
        tool_registry=ToolRegistry([]),
        test_harness=CartHarness(),
        contractor_executor=mock_cart_contractor,
    )

    result = wf.run_workflow(
        goal="Implement shopping cart module with item manipulation and tax calculation",
        test_paths=["tests/test_cart.py"],
    )

    assert result.status == WorkflowStatus.COMPLETED
    assert result.remediation_cycles == 1
    assert len(result.qa_reports) == 2
    assert result.qa_reports[0].status == "REJECTED"
    assert result.qa_reports[1].status == "ACCEPTED"
    assert result.verdict is not None
    assert result.verdict.status == "VERIFIED"
    assert len(result.verdict.criteria_met) > 0
    # Every criteria_met entry must reference a valid artifact ID (Directive B2)
    for ev in result.verdict.criteria_met:
        assert ev.artifact_id == "hash_cart_pass_4e81b2"
        assert ev.verified is True
    # Audit log populated (Directive B7)
    assert len(result.audit_log) > 0


# =============================================================================
# Mandatory Adversarial Tests (Scenarios a-e)
# =============================================================================

def test_adversarial_a_frozen_tests_modification_blocked(mock_workspace: Workspace):
    """
    Adversarial Scenario a:
    Agent editing frozen tests is blocked with PermissionDeniedViolation.
    """
    engine = TaskScopedPermissionEngine(mock_workspace)

    scope = TaskScope(
        task_id="task_cart_01",
        role="backend_dev",
        target_paths=["src/living_assistant/cart/models.py", "src/living_assistant/cart/service.py"],
        frozen_paths=["tests/test_cart.py"],
    )

    # Attempt to overwrite the frozen test file
    with pytest.raises(PermissionDeniedViolation) as exc_info:
        engine.enforce(
            role="backend_dev",
            task_scope=scope,
            tool_name="write_file",
            arguments={"path": "tests/test_cart.py", "content": "def test_bypass(): assert True"},
        )

    assert "frozen/immutable test suite" in str(exc_info.value)


def test_adversarial_b_forged_qa_report_blocked(mock_workspace: Workspace):
    """
    Adversarial Scenario b:
    Forged QA report (generated_by_harness=False or invalid hash) is blocked.
    """
    wf = CompanyWorkflow(workspace=mock_workspace, tool_registry=ToolRegistry([]))

    # Fabricated QA report not generated by machine harness
    forged_report = QAReport(
        task_id="task_forged_01",
        status="ACCEPTED",
        total_tests=100,
        passed=100,
        failed=0,
        feedback="All fabricated tests passed",
        generated_by_harness=False,  # Rogue report!
        log_hash="fake_hash",
    )

    with pytest.raises(ForgedQAReportViolation) as exc_info:
        wf.validate_qa_report(forged_report)

    assert "forged: generated_by_harness is False" in str(exc_info.value)

    # Fabricated QA report with empty/missing log hash
    forged_report_no_hash = QAReport(
        task_id="task_forged_02",
        status="ACCEPTED",
        total_tests=10,
        passed=10,
        failed=0,
        feedback="Passed without log hash",
        generated_by_harness=True,
        log_hash="",  # Missing hash!
    )

    with pytest.raises(ForgedQAReportViolation) as exc_info2:
        wf.validate_qa_report(forged_report_no_hash)

    assert "missing or invalid log hash" in str(exc_info2.value)


def test_adversarial_c_unauthorized_completion_blocked(mock_workspace: Workspace):
    """
    Adversarial Scenario c:
    Setting COMPLETED without valid artifact evidence is blocked, and
    non-verifier role transitioning to COMPLETED is blocked.
    """
    wf = CompanyWorkflow(workspace=mock_workspace, tool_registry=ToolRegistry([]))

    # 1. Attempt by developer role to transition to COMPLETED
    verdict_valid = VerificationVerdict(
        task_id="task_hack_01",
        status="VERIFIED",
        criteria_met=[CriteriaEvidence(criterion="Logic verified", artifact_id="log_hash_123", evidence_type="test_run", verified=True)],
        summary="Verified",
    )

    with pytest.raises(UnauthorizedCompletionViolation) as exc_info:
        wf.set_task_completed(task_id="task_hack_01", role="backend_dev", verdict=verdict_valid)

    assert "not authorized to set task status to COMPLETED" in str(exc_info.value)

    # 2. Attempt by verifier without valid artifact evidence (missing artifact_id)
    verdict_no_evidence = VerificationVerdict(
        task_id="task_hack_02",
        status="VERIFIED",
        criteria_met=[CriteriaEvidence(criterion="Logic verified", artifact_id="", evidence_type="test_run", verified=False)],
        summary="Verified without evidence",
    )

    with pytest.raises(ValueError) as exc_info2:
        wf.set_task_completed(task_id="task_hack_02", role="verifier", verdict=verdict_no_evidence)

    assert "lacks valid artifact evidence" in str(exc_info2.value)


def test_adversarial_d_depth_and_budget_limits_enforced(mock_workspace: Workspace):
    """
    Adversarial Scenario d:
    Exceeding depth or budget is blocked.
    """
    engine = TaskScopedPermissionEngine(mock_workspace)

    scope = TaskScope(
        task_id="task_depth_01",
        role="backend_dev",
        max_depth=2,
        budget_tokens=10_000,
    )

    # 1. Depth limit exceeded
    with pytest.raises(PermissionDeniedViolation) as exc_depth:
        engine.enforce(
            role="backend_dev",
            task_scope=scope,
            tool_name="read_file",
            arguments={"path": "src/api.py"},
            current_depth=3,  # Exceeds max_depth=2
            consumed_tokens=100,
        )

    assert "maximum delegation depth limit" in str(exc_depth.value)

    # 2. Token budget exceeded
    with pytest.raises(PermissionDeniedViolation) as exc_budget:
        engine.enforce(
            role="backend_dev",
            task_scope=scope,
            tool_name="read_file",
            arguments={"path": "src/api.py"},
            current_depth=1,
            consumed_tokens=15_000,  # Exceeds budget_tokens=10_000
        )

    assert "assigned token execution budget" in str(exc_budget.value)


def test_adversarial_e_workspace_violation_escape_blocked(mock_workspace: Workspace):
    """
    Adversarial Scenario e:
    Writing outside workspace is blocked with WorkspaceViolation.
    """
    engine = TaskScopedPermissionEngine(mock_workspace)

    scope = TaskScope(
        task_id="task_escape_01",
        role="backend_dev",
    )

    # Path traversal payload attempting escape from workspace
    traversal_path = "../../etc/shadow"

    decision = engine.evaluate(
        role="backend_dev",
        task_scope=scope,
        tool_name="write_file",
        arguments={"path": traversal_path, "content": "malicious"},
    )

    assert decision.allowed is False
    assert "Path traversal violation" in decision.reason

    # Direct workspace resolution also raises WorkspaceViolation
    with pytest.raises(WorkspaceViolation):
        mock_workspace.resolve(traversal_path)

    # Enforce raises PermissionDeniedViolation citing path traversal
    with pytest.raises(PermissionDeniedViolation) as exc_info:
        engine.enforce(
            role="backend_dev",
            task_scope=scope,
            tool_name="write_file",
            arguments={"path": traversal_path, "content": "malicious"},
        )

    assert "Path traversal violation" in str(exc_info.value)
