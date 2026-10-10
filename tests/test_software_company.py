"""
Comprehensive test suite for the Software Company multi-agent hierarchy and dynamic roles.
Covers:
1. Profile loading and validation of all YAML profiles.
2. Hierarchical DAG execution (parent/child, depth <= 3, dependency resolution, budget, cancellation).
3. Task-scoped tool permissions and workspace confinement.
4. QA rejection gate (failing tests emit REJECTED, block completion, trigger remediation loop).
5. FinalVerifier completion gate (only FinalVerifier can set task to COMPLETED, requires valid evidence).
6. End-to-End Thin Vertical Slice ("Implement Cart").
7. Adversarial hardening tests (frozen test protection, forged report blocking, depth limits, evidence validation).
"""

from __future__ import annotations

from pathlib import Path
import pytest

from living_assistant.agents.software_company.models import (
    CompanyPlan,
    CompanyTask,
    ExecutionBudget,
    QAReport,
    RoleProfile,
    TaskNode,
    TaskSpec,
    VerificationVerdict,
)
from living_assistant.agents.software_company.profiles import (
    ProfileLoader,
    ProfileNotFoundError,
    ProfileValidationError,
)
from living_assistant.agents.software_company.task_graph import (
    BudgetExceededError,
    HierarchicalTaskGraph,
    MaxDepthExceededError,
    TaskGraphError,
)
from living_assistant.agents.software_company.workflow import (
    FrozenTestViolationError,
    QARejectionError,
    QARetryLimitExceededError,
    QARunnerHarness,
    SoftwareCompanyWorkflow,
    SpecNotApprovedError,
    TaskScopedToolFactory,
    VerificationError,
)
from living_assistant.core.workspace import Workspace, WorkspaceViolation
from living_assistant.tools.registry import ToolRegistry


# ============================================================================
# 1. PROFILE LOADING & VALIDATION
# ============================================================================

def test_profile_loading_all_yaml_profiles():
    """Verify all 9 YAML profiles load, parse, and validate correctly."""
    loader = ProfileLoader()
    expected_profiles = [
        "manager",
        "backend_dev",
        "frontend_dev",
        "qa_engineer",
        "verifier",
        "tool_operator",
        "github_researcher",
        "product",
        "architect",
    ]

    all_profiles = loader.load_all_profiles()
    for role_id in expected_profiles:
        assert role_id in all_profiles, f"Expected profile '{role_id}' to be loaded."
        profile = all_profiles[role_id]
        assert profile.role_id == role_id
        assert bool(profile.name)
        assert bool(profile.description)
        assert bool(profile.tier)
        assert bool(profile.model_tier)
        assert isinstance(profile.allowed_tools, list) and len(profile.allowed_tools) > 0
        assert bool(profile.prompt_template)
        assert isinstance(profile.constraints, list) and len(profile.constraints) > 0

    # Caching verification
    cached = loader.get_profile("manager")
    assert cached is all_profiles["manager"]


def test_profile_not_found_raises_error():
    """Verify requesting an unknown role profile raises ProfileNotFoundError."""
    loader = ProfileLoader()
    with pytest.raises(ProfileNotFoundError):
        loader.load_profile("nonexistent_unknown_agent_role")


def test_profile_validation_missing_required_fields():
    """Verify validation fails if required fields are missing."""
    loader = ProfileLoader()
    invalid_data = {
        "role_id": "test_role",
        # 'name' missing
        "description": "incomplete",
        "tier": "engineering",
    }
    with pytest.raises(ProfileValidationError) as exc:
        loader.validate_profile(invalid_data)
    assert "missing required fields" in str(exc.value)


# ============================================================================
# 2. HIERARCHICAL DAG EXECUTION
# ============================================================================

def test_hierarchical_dag_parent_child_relationships():
    """Verify parent/child hierarchy, depth calculation, and descendant traversal."""
    graph = HierarchicalTaskGraph(max_depth=3)

    root = graph.add_node(node_id="root", title="Root", role="manager", parent_id=None)
    assert root.depth == 0

    child = graph.add_node(node_id="child_1", title="Child 1", role="backend_dev", parent_id="root")
    assert child.depth == 1

    grandchild = graph.add_node(node_id="grandchild_1", title="Grandchild 1", role="backend_dev", parent_id="child_1")
    assert grandchild.depth == 2

    # Verify relationships
    children = graph.get_children("root")
    assert len(children) == 1
    assert children[0].id == "child_1"

    descendants = graph.get_descendants("root")
    descendant_ids = [d.id for d in descendants]
    assert descendant_ids == ["child_1", "grandchild_1"]
    assert graph.get_max_depth() == 2


def test_hierarchical_dag_max_depth_enforced():
    """Verify adding nodes exceeding max_depth (<= 3) raises MaxDepthExceededError."""
    graph = HierarchicalTaskGraph(max_depth=3)

    graph.add_node(node_id="d0", title="Depth 0", role="manager", parent_id=None)
    graph.add_node(node_id="d1", title="Depth 1", role="architect", parent_id="d0")
    graph.add_node(node_id="d2", title="Depth 2", role="backend_dev", parent_id="d1")
    graph.add_node(node_id="d3", title="Depth 3", role="backend_dev", parent_id="d2")

    # Depth 4 exceeds max_depth of 3
    with pytest.raises(MaxDepthExceededError):
        graph.add_node(node_id="d4", title="Depth 4", role="backend_dev", parent_id="d3")


def test_hierarchical_dag_dependency_resolution():
    """
    Verify dependency resolution:
    1. Sibling dependency must be completed.
    2. Parent integration task is NOT ready until ALL its child nodes are completed.
    """
    graph = HierarchicalTaskGraph(max_depth=3)

    # Root integration task
    root = graph.add_node(node_id="integration", title="Integration Task", role="manager", parent_id=None)

    # Subtasks
    b1 = graph.add_node(node_id="task_backend", title="Backend Logic", role="backend_dev", parent_id="integration")
    f1 = graph.add_node(
        node_id="task_frontend",
        title="Frontend Logic",
        role="frontend_dev",
        parent_id="integration",
        dependencies=["task_backend"],  # Frontend depends on backend
    )

    # Initially, only task_backend is ready (frontend depends on backend; integration depends on children)
    ready = graph.get_ready_nodes()
    ready_ids = [r.id for r in ready]
    assert ready_ids == ["task_backend"]

    # Mark backend completed
    graph.update_node_status("task_backend", status="completed")

    # Now task_frontend is ready, but integration is still NOT ready (frontend is still pending)
    ready = graph.get_ready_nodes()
    ready_ids = [r.id for r in ready]
    assert ready_ids == ["task_frontend"]

    # Mark frontend completed
    graph.update_node_status("task_frontend", status="completed")

    # Now that all children are completed, integration task becomes ready
    ready = graph.get_ready_nodes()
    ready_ids = [r.id for r in ready]
    assert ready_ids == ["integration"]


def test_hierarchical_dag_budget_and_step_counting():
    """Verify execution steps and token consumption update budget and enforce limits."""
    budget = ExecutionBudget(max_steps=3, token_cap=500)
    graph = HierarchicalTaskGraph(budget=budget)

    node = graph.add_node(node_id="step_task", title="Step Task", role="backend_dev")

    graph.record_step(node.id, tokens=100)
    assert budget.current_steps == 1
    assert budget.tokens_used == 100

    graph.record_step(node.id, tokens=150)
    assert budget.current_steps == 2
    assert budget.tokens_used == 250

    graph.record_step(node.id, tokens=100)
    assert budget.current_steps == 3
    assert budget.tokens_used == 350

    # Step 4 exceeds max_steps=3
    with pytest.raises(BudgetExceededError):
        graph.record_step(node.id, tokens=50)


def test_hierarchical_dag_cancellation_kill_switch():
    """Verify cancelling a node cascades cancellation to all descendants."""
    graph = HierarchicalTaskGraph(max_depth=3)

    graph.add_node(node_id="parent_task", title="Parent", role="manager")
    graph.add_node(node_id="child_task_1", title="Child 1", role="backend_dev", parent_id="parent_task")
    graph.add_node(node_id="child_task_2", title="Child 2", role="frontend_dev", parent_id="parent_task")
    graph.add_node(node_id="leaf_task", title="Leaf", role="backend_dev", parent_id="child_task_1")

    # Trigger kill-switch on parent
    cancelled = graph.cancel_task("parent_task", reason="User emergency stop")
    assert set(cancelled) == {"parent_task", "child_task_1", "child_task_2", "leaf_task"}

    assert graph.is_cancelled("parent_task")
    assert graph.is_cancelled("child_task_1")
    assert graph.is_cancelled("leaf_task")

    # Check output result records cancellation reason
    leaf = graph.get_node("leaf_task")
    assert leaf.output_result.get("cancellation_reason") == "User emergency stop"


# ============================================================================
# 3. TASK-SCOPED TOOL PERMISSIONS & WORKSPACE CONFINEMENT
# ============================================================================

def test_task_scoped_tools_backend_cannot_access_unallowed_tools(tmp_path: Path):
    """Verify backend_dev cannot invoke tools outside its profile."""
    workspace = Workspace([tmp_path])
    loader = ProfileLoader()
    backend_profile = loader.get_profile("backend_dev")

    registry = TaskScopedToolFactory.create_registry(
        profile=backend_profile,
        workspace=workspace,
    )

    # Allowed tools should be present
    assert "read_file" in registry.names()
    assert "write_file" in registry.names()
    assert "run_command" in registry.names()

    # Tools reserved for verifier or manager should NOT be present
    assert "certify_completion" not in registry.names()
    assert "verify_evidence" not in registry.names()
    assert "cancel_task" not in registry.names()
    assert "decompose_task" not in registry.names()


def test_task_scoped_tools_workspace_confinement(tmp_path: Path):
    """Verify file tools reject paths outside the authorized workspace."""
    workspace_dir = tmp_path / "sandbox"
    workspace_dir.mkdir()
    outside_dir = tmp_path / "forbidden"
    outside_dir.mkdir()

    workspace = Workspace([workspace_dir])
    loader = ProfileLoader()
    backend_profile = loader.get_profile("backend_dev")

    registry = TaskScopedToolFactory.create_registry(
        profile=backend_profile,
        workspace=workspace,
    )

    write_tool = registry.get("write_file")
    assert write_tool is not None

    # Write inside workspace succeeds
    res = write_tool.handler(path="allowed.txt", content="hello")
    assert res["ok"] is True
    assert (workspace_dir / "allowed.txt").read_text() == "hello"

    # Write outside workspace is blocked
    outside_path = str(outside_dir / "escaped.txt")
    with pytest.raises(WorkspaceViolation):
        write_tool.handler(path=outside_path, content="escape attempt")


# ============================================================================
# 4. FROZEN TEST PROTECTION & QA REJECTION GATE
# ============================================================================

def test_frozen_test_protection_blocks_developer_modifications(tmp_path: Path):
    """Verify developer workers are strictly blocked from writing or editing frozen test files."""
    workspace = Workspace([tmp_path])
    loader = ProfileLoader()
    backend_profile = loader.get_profile("backend_dev")

    frozen_file = "tests/fixtures/test_frozen_cart.py"
    registry = TaskScopedToolFactory.create_registry(
        profile=backend_profile,
        workspace=workspace,
        frozen_test_files=[frozen_file],
    )

    write_tool = registry.get("write_file")
    edit_tool = registry.get("edit_file")

    with pytest.raises(FrozenTestViolationError):
        write_tool.handler(path=frozen_file, content="def test_tampered(): pass")

    with pytest.raises(FrozenTestViolationError):
        edit_tool.handler(path=frozen_file, old_str="assert", new_str="pass")


def test_qa_rejection_blocks_completion_and_triggers_remediation(tmp_path: Path):
    """Verify QA REJECTED status blocks completion, triggers remediation loop, then accepts."""
    workspace = Workspace([tmp_path])
    workflow = SoftwareCompanyWorkflow(workspace=workspace, max_retries=3)

    task, spec = workflow.intake_request(
        task_id="task_qa_test",
        title="Cart QA Test",
        goal="Test remediation loop",
        requirements=["Add item"],
        acceptance_criteria=["Item count updates correctly"],
        interface_contracts={},
        frozen_test_files=[],
    )
    workflow.approve_spec(task)

    # Stateful test runner that fails on attempt 1 and passes on attempt 2
    attempt = {"count": 0}

    def flaky_qa_suite():
        attempt["count"] += 1
        if attempt["count"] == 1:
            return {
                "total": 2,
                "passed": 1,
                "failed": 1,
                "failures": [{"test": "test_count", "error": "AssertionError: expected 1 got 0"}],
                "output": "FAILED test_count",
            }
        return {
            "total": 2,
            "passed": 2,
            "failed": 0,
            "failures": [],
            "output": "PASSED all tests",
        }

    remediation_calls = []

    def developer_remediation(t: CompanyTask, r: QAReport):
        remediation_calls.append(r.report_id)

    report = workflow.run_qa_remediation_loop(
        task=task,
        qa_suite_fn=flaky_qa_suite,
        developer_remediation_fn=developer_remediation,
    )

    assert report.status == "ACCEPTED"
    assert report.passed == 2
    assert len(remediation_calls) == 1
    assert task.budget.current_retries == 1
    assert len(task.qa_reports) == 2
    assert task.qa_reports[0].status == "REJECTED"
    assert task.qa_reports[1].status == "ACCEPTED"


def test_qa_retry_limit_exceeded_escalates(tmp_path: Path):
    """Verify exceeding QA retry limit (max 3 retries) raises QARetryLimitExceededError."""
    workspace = Workspace([tmp_path])
    workflow = SoftwareCompanyWorkflow(workspace=workspace, max_retries=2)

    task, spec = workflow.intake_request(
        task_id="task_retry_limit",
        title="Broken Feature",
        goal="Feature that always fails QA",
        requirements=["Impossible req"],
        acceptance_criteria=["Criterion 1"],
        interface_contracts={},
        frozen_test_files=[],
    )
    workflow.approve_spec(task)

    def always_failing_suite():
        return {
            "total": 1,
            "passed": 0,
            "failed": 1,
            "failures": [{"test": "test_impossible", "error": "Always fails"}],
            "output": "FAILED",
        }

    def noop_remediation(t, r):
        pass

    with pytest.raises(QARetryLimitExceededError):
        workflow.run_qa_remediation_loop(
            task=task,
            qa_suite_fn=always_failing_suite,
            developer_remediation_fn=noop_remediation,
        )


# ============================================================================
# 5. FINAL VERIFIER COMPLETION GATE
# ============================================================================

def test_only_final_verifier_can_transition_to_completed():
    """Verify non-verifier roles cannot mark a CompanyTask COMPLETED."""
    task = CompanyTask(id="task_gate", title="Gate Test")
    task.register_artifact("art_1", {"code": "done"})

    verdict = VerificationVerdict(
        verdict_id="v1",
        status="VERIFIED",
        criteria_met=[{"criterion": "C1", "artifact_id": "art_1"}],
        verified_by="verifier",
    )

    # Manager cannot complete
    with pytest.raises(PermissionError):
        task.complete(verdict, caller_role="manager")

    # Backend dev cannot complete
    with pytest.raises(PermissionError):
        task.complete(verdict, caller_role="backend_dev")

    # QA engineer cannot complete
    with pytest.raises(PermissionError):
        task.complete(verdict, caller_role="qa_engineer")

    # Direct status change to COMPLETED is blocked
    with pytest.raises(PermissionError):
        task.set_status("COMPLETED", caller_role="manager")

    # Verifier succeeds
    task.complete(verdict, caller_role="verifier")
    assert task.status == "COMPLETED"


def test_final_verifier_blocks_completed_without_valid_evidence():
    """Verify completion is rejected if criteria reference non-existent artifacts."""
    task = CompanyTask(id="task_evidence", title="Evidence Test")

    # Criteria references 'missing_artifact' which is not registered in task.artifacts
    verdict = VerificationVerdict(
        verdict_id="v_bad",
        status="VERIFIED",
        criteria_met=[{"criterion": "C1", "artifact_id": "missing_artifact"}],
        verified_by="verifier",
    )

    with pytest.raises(ValueError) as exc:
        task.complete(verdict, caller_role="verifier")
    assert "missing or invalid artifact ID" in str(exc.value)


def test_final_verifier_blocks_completed_when_qa_rejected(tmp_path: Path):
    """Verify workflow verify_and_complete rejects if latest QA report is REJECTED."""
    workspace = Workspace([tmp_path])
    workflow = SoftwareCompanyWorkflow(workspace=workspace)

    task = CompanyTask(id="task_qa_reject_gate", title="Gate Check")
    task.register_artifact("art_1", {"test": "data"})
    # QA report marked REJECTED
    rejected_report = QAReport(
        report_id="rep_fail",
        status="REJECTED",
        total_tests=1,
        passed=0,
        failed=1,
    )
    task.qa_reports.append(rejected_report)

    with pytest.raises(VerificationError) as exc:
        workflow.verify_and_complete(task, criteria_artifact_map={"C1": "art_1"})
    assert "Latest QA report is not ACCEPTED" in str(exc.value)


# ============================================================================
# 6. END-TO-END THIN VERTICAL SLICE ("IMPLEMENT CART")
# ============================================================================

def test_e2e_implement_cart_vertical_slice(tmp_path: Path):
    """
    End-to-End Thin Vertical Slice:
    1. Product intake & spec generation for Shopping Cart feature.
    2. User explicitly approves spec.
    3. Manager decomposes into hierarchical DAG:
       - Cart Integration Task (manager, depth 0)
       - Backend Logic (backend_dev, depth 1, child of integration)
       - Frontend Contract (frontend_dev, depth 1, child of integration)
    4. Developers execute and produce genuine implementations:
       - CartService (add, remove, total, checkout)
       - CartUIContract (items, state management, checkout call)
    5. Independent QA Harness executes tests and emits certified QAReport.
    6. FinalVerifier validates criteria against artifacts and marks task COMPLETED.
    """
    workspace = Workspace([tmp_path])
    workflow = SoftwareCompanyWorkflow(workspace=workspace)
    graph = HierarchicalTaskGraph(max_depth=3)

    # Step 1: Intake & Spec
    frozen_test_path = "tests/fixtures/test_frozen_cart.py"
    task, spec = workflow.intake_request(
        task_id="task_cart_001",
        title="Shopping Cart Feature",
        goal="Implement shopping cart with add_item, remove_item, get_total, and checkout endpoints/logic plus UI contract.",
        requirements=[
            "Support adding items with item_id, price, and quantity.",
            "Support removing items by item_id.",
            "Compute total cart price with tax calculation.",
            "Provide checkout method returning order confirmation.",
            "Frontend contract matches backend interfaces.",
        ],
        acceptance_criteria=[
            "AC1: Item addition updates cart total and item list.",
            "AC2: Item removal removes item and recalculates total.",
            "AC3: Checkout returns confirmation dictionary.",
            "AC4: Frontend UI contract synchronizes with cart state.",
            "AC5: QA test suite passes with zero failures.",
        ],
        interface_contracts={
            "backend": {
                "methods": ["add_item", "remove_item", "get_total", "checkout"],
                "types": {"item_id": "str", "price": "float", "quantity": "int"},
            },
            "frontend": {
                "events": ["on_item_added", "on_item_removed", "on_checkout"],
                "state": ["items", "total_price", "is_checking_out"],
            },
        },
        frozen_test_files=[frozen_test_path],
    )

    # Step 2: User Approval Gate
    assert not spec.approved_by_user
    workflow.approve_spec(task)
    assert spec.approved_by_user

    # Step 3: Manager Decomposition
    plan = workflow.decompose_task(task, graph)
    assert len(plan.nodes) == 3
    assert graph.get_max_depth() == 1

    # Step 4: Worker Implementation
    class CartService:
        """Genuine in-memory Cart implementation."""
        def __init__(self, tax_rate: float = 0.05):
            self.items: dict[str, dict[str, Any]] = {}
            self.tax_rate = tax_rate

        def add_item(self, item_id: str, name: str, price: float, quantity: int = 1) -> dict[str, Any]:
            if quantity <= 0:
                raise ValueError("Quantity must be positive.")
            if item_id in self.items:
                self.items[item_id]["quantity"] += quantity
            else:
                self.items[item_id] = {"item_id": item_id, "name": name, "price": price, "quantity": quantity}
            return self.items[item_id]

        def remove_item(self, item_id: str) -> bool:
            if item_id in self.items:
                del self.items[item_id]
                return True
            return False

        def get_total(self) -> float:
            subtotal = sum(i["price"] * i["quantity"] for i in self.items.values())
            return round(subtotal * (1.0 + self.tax_rate), 2)

        def checkout(self) -> dict[str, Any]:
            total = self.get_total()
            count = sum(i["quantity"] for i in self.items.values())
            order = {"status": "CONFIRMED", "item_count": count, "total_paid": total}
            self.items.clear()
            return order

    class CartUIContract:
        """Genuine Frontend Cart Contract."""
        def __init__(self, cart_service: CartService):
            self.service = cart_service
            self.view_items: list[dict[str, Any]] = []

        def sync(self):
            self.view_items = list(self.service.items.values())

        def handle_add_click(self, item_id: str, name: str, price: float, quantity: int = 1):
            self.service.add_item(item_id, name, price, quantity)
            self.sync()

        def handle_checkout_click(self) -> dict[str, Any]:
            order = self.service.checkout()
            self.sync()
            return order

    cart = CartService()
    ui = CartUIContract(cart)

    def worker_dispatch(node: TaskNode, registry: ToolRegistry) -> dict[str, Any]:
        if node.role == "backend_dev":
            # Write backend implementation to workspace
            write_tool = registry.get("write_file")
            write_tool.handler(path="src/cart_service.py", content="# CartService Implementation")
            return {
                "artifacts": {
                    "cart_backend_code": {
                        "class": "CartService",
                        "methods": ["add_item", "remove_item", "get_total", "checkout"],
                        "instance": cart,
                    }
                }
            }
        elif node.role == "frontend_dev":
            write_tool = registry.get("write_file")
            write_tool.handler(path="src/cart_ui.py", content="# CartUI Contract Implementation")
            return {
                "artifacts": {
                    "cart_frontend_contract": {
                        "class": "CartUIContract",
                        "events": ["handle_add_click", "handle_checkout_click"],
                        "instance": ui,
                    }
                }
            }
        elif node.role == "manager":
            return {"artifacts": {"cart_integration_artifact": {"status": "integrated"}}}
        return {}

    workflow.execute_all_nodes(task, graph, worker_dispatch)
    assert graph.is_all_completed()
    assert "cart_backend_code" in task.artifacts
    assert "cart_frontend_contract" in task.artifacts

    # Step 5: Independent QA Harness Execution
    def real_cart_qa_tests() -> dict[str, Any]:
        # Genuine assertions exercising the actual implementation
        cart.add_item("item-1", "Coffee", 10.0, 2)
        assert cart.get_total() == 21.0  # 20 + 5% tax

        ui.sync()
        assert len(ui.view_items) == 1

        cart.add_item("item-2", "Cookie", 5.0, 1)
        assert cart.get_total() == 26.25  # 25 + 5% tax

        cart.remove_item("item-2")
        assert cart.get_total() == 21.0

        confirmation = ui.handle_checkout_click()
        assert confirmation["status"] == "CONFIRMED"
        assert confirmation["total_paid"] == 21.0
        assert len(ui.view_items) == 0

        return {
            "total": 5,
            "passed": 5,
            "failed": 0,
            "failures": [],
            "output": "Cart unit & integration test suite passed 5/5.",
        }

    qa_report = workflow.run_qa_remediation_loop(task, real_cart_qa_tests)
    assert qa_report.status == "ACCEPTED"
    assert qa_report.passed == 5
    assert "qa_report_artifact" in task.artifacts

    # Step 6: FinalVerifier Certification
    criteria_map = {
        "AC1: Item addition updates cart total and item list.": "cart_backend_code",
        "AC2: Item removal removes item and recalculates total.": "cart_backend_code",
        "AC3: Checkout returns confirmation dictionary.": "cart_backend_code",
        "AC4: Frontend UI contract synchronizes with cart state.": "cart_frontend_contract",
        "AC5: QA test suite passes with zero failures.": "qa_report_artifact",
    }

    verdict = workflow.verify_and_complete(task, criteria_map)
    assert verdict.status == "VERIFIED"
    assert verdict.verified_by == "verifier"
    assert task.status == "COMPLETED"
    assert len(task.audit_log) > 0


# ============================================================================
# 7. ADVERSARIAL HARDENING TESTS
# ============================================================================

def test_adversarial_agent_editing_frozen_tests_blocked(tmp_path: Path):
    """Adversarial check: modifying frozen tests is blocked."""
    workspace = Workspace([tmp_path])
    loader = ProfileLoader()
    profile = loader.get_profile("backend_dev")

    registry = TaskScopedToolFactory.create_registry(
        profile=profile,
        workspace=workspace,
        frozen_test_files=["tests/fixtures/test_frozen_cart.py"],
    )

    write_tool = registry.get("write_file")
    with pytest.raises(FrozenTestViolationError):
        write_tool.handler(path="tests/fixtures/test_frozen_cart.py", content="# injected cheat")


def test_adversarial_forging_qa_report_blocked():
    """Adversarial check: QA reports cannot be forged without harness runner."""
    # Attempting to forge an accepted report with failing tests
    report = QAReport.create_from_runner(
        report_id="fake-report",
        command="pytest tests/",
        exit_code=1,  # Non-zero exit code
        output_log="FAILED 1 test",
        total_tests=1,
        passed=0,
        failed=1,
    )
    # The factory enforces status == 'REJECTED' when exit_code != 0 or failed > 0
    assert report.status == "REJECTED"


def test_adversarial_unapproved_spec_cannot_decompose(tmp_path: Path):
    """Adversarial check: manager cannot decompose task if user has not approved spec."""
    workspace = Workspace([tmp_path])
    workflow = SoftwareCompanyWorkflow(workspace=workspace)
    graph = HierarchicalTaskGraph()

    task, spec = workflow.intake_request(
        task_id="unapproved_task",
        title="Unapproved",
        goal="Secret goal",
        requirements=[],
        acceptance_criteria=[],
        interface_contracts={},
        frozen_test_files=[],
    )

    with pytest.raises(SpecNotApprovedError):
        workflow.decompose_task(task, graph)


def test_adversarial_setting_completed_without_evidence_blocked():
    """Adversarial check: transitioning to COMPLETED without evidence is blocked."""
    task = CompanyTask(id="adv_task", title="Adv Task")
    verdict_empty = VerificationVerdict(
        verdict_id="adv_v",
        status="VERIFIED",
        criteria_met=[],  # Empty evidence
        verified_by="verifier",
    )
    with pytest.raises(ValueError) as exc:
        task.complete(verdict_empty, caller_role="verifier")
    assert "No criteria_met provided" in str(exc.value)
