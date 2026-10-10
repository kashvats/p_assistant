"""
Interface Contract 4 Data Models for Software Company Multi-Agent Hierarchy & Dynamic Roles.
Incorporates Phase B Directives (B1, B2, B3, B5, B7) and full Software Company execution lifecycle.
"""

from __future__ import annotations

import hashlib
import time
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr


class RoleDepartment(str, Enum):
    EXECUTIVE = "executive"
    DESIGN = "design"
    ENGINEERING = "engineering"
    QUALITY = "quality"
    SECURITY = "security"
    GOVERNANCE = "governance"
    SPECIALIST = "specialist"


class SpecStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


class WorkflowStatus(str, Enum):
    INITIALIZED = "INITIALIZED"
    PLANNING = "PLANNING"
    DEVELOPING = "DEVELOPING"
    QA_VERIFYING = "QA_VERIFYING"
    REMEDIATING = "REMEDIATING"
    FINAL_VERIFYING = "FINAL_VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ESCALATED_TO_HUMAN = "ESCALATED_TO_HUMAN"


class LicenseVerdict(str, Enum):
    REUSE = "REUSE"        # Permissive, direct dependency / consumption
    ADAPT = "ADAPT"        # Code adaptation with license attribution
    DEPEND = "DEPEND"      # Upstream package dependency
    INSPIRE = "INSPIRE"    # Architectural / algorithmic reference only
    REJECT = "REJECT"      # Incompatible license, unmaintained, security risk


# =============================================================================
# 1. Execution Budget & Loop Control (Directive B3)
# =============================================================================

class ExecutionBudget(BaseModel):
    """
    Execution budget tracking steps, retries, tokens, and wall-clock limits.
    Directives B1 & B3: Loop control, max 3 QA retries, max depth <= 3, token cap.
    """
    model_config = ConfigDict(extra="ignore")

    max_depth: int = Field(default=3, le=3, description="Maximum recursive DAG depth allowed (<=3)")
    max_retries: int = Field(default=3, description="Max QA rejection returns to Manager (at most 3)")
    max_remediation_cycles: int = Field(default=3, description="Alias for max_retries")
    max_steps: int = Field(default=25, description="Max steps in task execution")
    max_total_specs: int = Field(default=20, description="Max specs in task DAG")
    token_cap: int = Field(default=100_000, description="Total token budget limit")
    max_tokens: int = Field(default=100_000, description="Alias for token_cap")
    wall_clock_timeout: float = Field(default=300.0, description="Total wall-clock timeout in seconds")
    max_wall_clock_seconds: float = Field(default=600.0, description="Total task timeout in seconds")
    current_retries: int = Field(default=0, description="Current count of remediation retries")
    current_steps: int = Field(default=0, description="Current execution step count")
    tokens_used: int = Field(default=0, description="Total tokens consumed")
    elapsed_time: float = Field(default=0.0, description="Elapsed time in seconds")
    kill_switch_triggered: bool = Field(default=False, description="Manual or automated kill switch state")

    def can_proceed(self) -> bool:
        """Check if execution can proceed within budget limits."""
        if self.kill_switch_triggered:
            return False
        if self.current_steps > self.max_steps:
            return False
        if self.current_retries > self.max_retries:
            return False
        if self.tokens_used > self.token_cap:
            return False
        if self.elapsed_time > self.wall_clock_timeout:
            return False
        return True

    def record_step(self, tokens: int = 0, delta_time: float = 0.0) -> None:
        """Record an execution step."""
        self.current_steps += 1
        self.tokens_used += tokens
        self.elapsed_time += delta_time

    def record_retry(self) -> None:
        """Record a remediation retry."""
        self.current_retries += 1


TaskBudget = ExecutionBudget


# =============================================================================
# 2. Spec, Node & Plan Models (Directive B1 Recursive DAG)
# =============================================================================

class TaskSpec(BaseModel):
    """
    Modular unit of work and formal requirements specification.
    Supports recursive decomposition within TaskGraphManager DAG (Directive B1).
    """
    model_config = ConfigDict(extra="ignore")

    spec_id: str = Field(description="Unique spec identifier (e.g. 'spec-task-001')")
    title: str = Field(default="", description="Short human-readable title of the task")
    description: str = Field(default="", description="Detailed technical requirements and execution instructions")
    goal: str = Field(default="", description="High-level goal (synonym for description)")
    assigned_role: str = Field(default="", description="Role identifier to execute this spec (e.g. 'backend_dev')")
    requirements: List[str] = Field(default_factory=list, description="Detailed requirements breakdown")
    acceptance_criteria: List[str] = Field(default_factory=list, description="Checkable criteria for this spec")
    interface_contracts: Dict[str, Any] = Field(default_factory=dict, description="Pre-declared interface contracts")
    interface_contract: Optional[Dict[str, Any]] = Field(default=None, description="Interface contract alias")
    frozen_test_files: List[str] = Field(default_factory=list, description="QA test files frozen before dev work")
    frozen_test_paths: List[str] = Field(default_factory=list, description="Alias for frozen_test_files")
    target_files: List[str] = Field(default_factory=list, description="Target files to create, inspect, or modify")
    dependencies: List[str] = Field(default_factory=list, description="List of prerequisite spec_ids")
    status: SpecStatus = Field(default=SpecStatus.PENDING, description="Current execution state")
    context: Dict[str, Any] = Field(default_factory=dict, description="Targeted context")
    parent_spec_id: Optional[str] = Field(default=None, description="Parent spec ID if decomposed recursively")
    depth: int = Field(default=0, description="Nesting depth in task tree (<= 3)")
    approved_by_user: bool = Field(default=False, description="User approval gate flag (Directive B4)")
    approved_at: Optional[float] = Field(default=None, description="Timestamp of user approval")
    created_at: float = Field(default_factory=time.time, description="Creation timestamp")


class TaskNode(BaseModel):
    """
    Persistent graph node representation for the HierarchicalTaskGraph DAG.
    Conforms to Interface Contract 4.
    """
    model_config = ConfigDict(extra="ignore")

    id: str = Field(description="Task node identifier")
    title: str = Field(default="", description="Node task title")
    description: str = Field(default="", description="Node task description")
    role: str = Field(default="manager", description="Role identifier assigned to execute this node")
    parent_id: Optional[str] = Field(default=None, description="Parent node ID in recursive hierarchy")
    depth: int = Field(default=0, description="Recursive depth in hierarchy (<= 3)")
    dependencies: List[str] = Field(default_factory=list, description="Prerequisite sibling node IDs")
    status: str = Field(default="pending", description="Execution status: pending, running, completed, failed, cancelled, rejected")
    contract: Optional[Dict[str, Any]] = Field(default=None, description="Interface contract passed from parent")
    assigned_worker: Optional[str] = Field(default=None, description="Worker identifier")
    input_context: Dict[str, Any] = Field(default_factory=dict, description="Task-scoped context")
    output_result: Optional[Dict[str, Any]] = Field(default=None, description="Structured execution result")
    result: Optional[str] = Field(default=None, description="Serialized result alias")
    artifact_ids: List[str] = Field(default_factory=list, description="Artifact IDs registered during execution")
    step_count: int = Field(default=0, description="Steps executed on this node")
    tokens_used: int = Field(default=0, description="Tokens consumed on this node")
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class CompanyPlan(BaseModel):
    """
    Manager / Tech Lead output decomposing a high-level goal into an execution plan.
    Part of Interface Contract 4.
    """
    model_config = ConfigDict(extra="ignore")

    plan_id: str = Field(default="", description="Unique plan identifier")
    task_id: str = Field(default="", description="Associated task ID")
    goal: str = Field(default="", description="The primary objective or user goal")
    roles_required: List[str] = Field(default_factory=list, description="List of dynamically activated role identifiers")
    nodes: List[TaskNode] = Field(default_factory=list, description="DAG task nodes")
    specs: List[TaskSpec] = Field(default_factory=list, description="Modular task specifications")
    interface_contracts: Dict[str, Any] = Field(default_factory=dict, description="Global interface contracts")
    qa_criteria: List[str] = Field(default_factory=list, description="Independent verification criteria for QA validation")
    architecture_notes: Optional[str] = Field(default=None, description="System boundaries, conventions, and constraints")
    risk_level: str = Field(default="low", description="Assessed risk level: 'low', 'medium', 'high', 'critical'")
    max_depth: int = Field(default=3, description="Maximum recursive DAG depth allowed")
    created_at: float = Field(default_factory=time.time, description="Creation timestamp")


# =============================================================================
# 3. Developer & Specialist Execution Outputs
# =============================================================================

class DeveloperOutput(BaseModel):
    """
    Output produced by a developer or specialist role upon executing a TaskSpec.
    Part of Interface Contract 4.
    """
    model_config = ConfigDict(extra="ignore")

    spec_id: str = Field(description="Identifier of the completed spec")
    role: str = Field(description="Role identifier of the executing specialist")
    files_modified: List[str] = Field(default_factory=list, description="List of files created, modified, or touched")
    api_contracts: List[Dict[str, Any]] = Field(default_factory=list, description="API endpoints, routes, schemas, or interfaces added/modified")
    notes: str = Field(default="", description="Implementation rationale, technical notes, and decisions")
    diff_preview: Optional[str] = Field(default=None, description="Unified diff preview or change summary")
    tests_written: List[str] = Field(default_factory=list, description="List of unit/integration test files written")
    status: str = Field(default="SUCCESS", description="Execution status: 'SUCCESS', 'FAILED', 'BLOCKED'")
    error: Optional[str] = Field(default=None, description="Error message if execution failed")
    evidence: Dict[str, Any] = Field(default_factory=dict, description="Execution evidence, command results, or diagnostics")


# =============================================================================
# 4. QA Gate Output: QAFailureDetail & QAReport (Directive B2 Evidence-Based)
# =============================================================================

class QAFailureDetail(BaseModel):
    """Detailed diagnostic information for a failed test case."""
    model_config = ConfigDict(extra="ignore")

    test_name: str = Field(default="", description="Name of the failing test or check")
    file_path: Optional[str] = Field(default=None, description="Path of test or source file")
    error_message: str = Field(default="", description="Verbatim error message or assertion failure text")
    stack_trace: Optional[str] = Field(default=None, description="Traceback snippet for diagnosis")
    failing_assertion: Optional[str] = Field(default=None, description="The specific failed condition or assertion")


class QAReport(BaseModel):
    """
    Independent QA verification report with authoritative rejection gate.
    Directive B2: Generated by test harness from real runner output (exit code, log hash, commit SHA),
    NEVER hallucinated or fabricated by an agent LLM.
    Part of Interface Contract 4.
    """
    model_config = ConfigDict(extra="ignore")

    report_id: str = Field(default="", description="Unique QA report identifier")
    task_id: str = Field(default="", description="Associated company task ID")
    status: Literal["ACCEPTED", "REJECTED"] = Field(description="Authoritative gate status: 'ACCEPTED' or 'REJECTED'")
    total_tests: int = Field(default=0, description="Total number of test cases executed")
    passed: int = Field(default=0, description="Count of passed tests")
    failed: int = Field(default=0, description="Count of failed tests")
    failures: List[Any] = Field(default_factory=list, description="Diagnostic details for failing tests")
    feedback: str = Field(default="", description="Remediation guidance and root cause summary for the Manager")

    # Directive B2: Deterministic test harness evidence fields
    command: str = Field(default="pytest", description="Test execution command")
    test_command: str = Field(default="pytest", description="Alias for command")
    exit_code: int = Field(default=0, description="Process exit code from test runner (0 = pass, non-zero = fail)")
    log_hash: str = Field(default="", description="SHA-256 hash of verbatim test runner output log")
    commit_sha: Optional[str] = Field(default=None, description="Git commit SHA under test")
    generated_by_harness: bool = Field(default=True, description="Strictly true when generated by machine harness")
    harness_certified: bool = Field(default=True, description="Harness certification flag")
    test_output: Optional[str] = Field(default=None, description="Captured stdout/stderr from test suite")
    regression_passed: bool = Field(default=True, description="Whether all pre-existing regression tests passed")
    edge_cases_tested: List[str] = Field(default_factory=list, description="List of edge cases explicitly validated")
    created_at: float = Field(default_factory=time.time, description="Creation timestamp")
    timestamp: float = Field(default_factory=time.time, description="Unix timestamp of QA evaluation")

    @classmethod
    def create_from_runner(
        cls,
        report_id: str,
        command: str,
        exit_code: int,
        output_log: str,
        total_tests: int,
        passed: int,
        failed: int,
        failures: List[Any] | None = None,
        feedback: str = "",
        commit_sha: str | None = None,
        task_id: str = "",
    ) -> QAReport:
        """Factory method used strictly by the test harness to produce authentic QAReports."""
        log_hash = hashlib.sha256(output_log.encode("utf-8")).hexdigest()
        status: Literal["ACCEPTED", "REJECTED"] = (
            "ACCEPTED" if (exit_code == 0 and failed == 0 and total_tests > 0) else "REJECTED"
        )
        return cls(
            report_id=report_id,
            task_id=task_id or report_id,
            status=status,
            total_tests=total_tests,
            passed=passed,
            failed=failed,
            failures=failures or [],
            feedback=feedback or ("All tests passed successfully." if status == "ACCEPTED" else f"Failed {failed} tests."),
            command=command,
            test_command=command,
            exit_code=exit_code,
            log_hash=log_hash,
            commit_sha=commit_sha or "baseline",
            generated_by_harness=True,
            harness_certified=True,
            test_output=output_log,
        )


# =============================================================================
# 5. Final Verifier Gate: VerificationVerdict (Directive B2 Verified Evidence)
# =============================================================================

class CriteriaEvidence(BaseModel):
    """Directive B2: Evidence linking an acceptance criterion to a concrete artifact."""
    model_config = ConfigDict(extra="ignore")

    criterion: str = Field(description="Acceptance criterion text")
    artifact_id: str = Field(description="Concrete artifact ID: log hash, commit SHA, file path, or test run ID")
    evidence_type: str = Field(default="test_run", description="Type of evidence: 'test_run', 'git_commit', 'file_diff', 'security_audit'")
    verified: bool = Field(default=True, description="Whether the evidence successfully validates the criterion")


class VerificationVerdict(BaseModel):
    """
    Final Verifier completion gate verdict. Sole authority to transition task to COMPLETED.
    Directive B2: Every criteria_met entry must reference an artifact ID.
    Part of Interface Contract 4.
    """
    model_config = ConfigDict(extra="ignore")

    verdict_id: str = Field(default="", description="Unique verdict identifier")
    task_id: str = Field(default="", description="Associated company task ID")
    status: Literal["VERIFIED", "INCOMPLETE", "REJECTED"] = Field(description="Gate status: 'VERIFIED' or 'INCOMPLETE' or 'REJECTED'")
    criteria_met: List[Any] = Field(default_factory=list, description="Criteria verified with concrete artifact IDs")
    remaining_issues: List[str] = Field(default_factory=list, description="Unmet criteria, blockers, or defects")
    security_approved: bool = Field(default=True, description="Whether security checks and boundary audits passed")
    qa_report_ref: Optional[str] = Field(default=None, description="Reference log hash or commit SHA of accepted QA report")
    git_checkpoint_ref: Optional[str] = Field(default=None, description="Git commit SHA or checkpoint reference")
    summary: str = Field(default="", description="Comprehensive verification narrative and justification")
    verified_by: str = Field(default="verifier", description="Verifier role identifier")
    verified_at: float = Field(default_factory=time.time, description="Timestamp of verification")
    completed_at: Optional[float] = Field(default=None, description="Timestamp of completion (set only if VERIFIED)")
    evidence_valid: bool = Field(default=True, description="Whether all evidence references are authentic and valid")


# =============================================================================
# 6. Dynamic Role Profiles & Root Company Task
# =============================================================================

class RoleProfile(BaseModel):
    """YAML-configured role profile specifying metadata, capabilities, and constraints."""
    model_config = ConfigDict(extra="ignore")

    role_id: str
    name: str
    description: str
    tier: str  # "executive", "product", "engineering", "quality", "governance", "specialist"
    model_tier: str = "primary"  # "small", "primary", "strong", "collibri"
    allowed_tools: List[str] = Field(default_factory=list)
    prompt_template: str = ""
    constraints: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def department(self) -> str:
        return self.tier

    @property
    def system_prompt(self) -> str:
        return self.prompt_template

    @property
    def display_name(self) -> str:
        return self.name

    @property
    def default_model_tier(self) -> str:
        return self.model_tier


class CompanyTask(BaseModel):
    """
    Top-level company task representing the full lifecycle.
    Enforces that ONLY the FinalVerifier role can transition the task to COMPLETED,
    and only when all criteria map to valid artifacts.
    """
    model_config = ConfigDict(extra="ignore")

    _completing: bool = PrivateAttr(default=False)

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "status" and value == "COMPLETED" and not getattr(self, "_completing", False):
            raise PermissionError(
                "Direct assignment of status='COMPLETED' is prohibited. Use task.complete(verdict, caller_role='verifier')."
            )
        super().__setattr__(name, value)

    id: str
    title: str
    description: str = ""
    status: str = "PENDING"  # "PENDING", "PLANNING", "IN_PROGRESS", "QA_REVIEW", "VERIFYING", "COMPLETED", "REJECTED", "FAILED", "CANCELLED"
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    budget: ExecutionBudget = Field(default_factory=ExecutionBudget)
    spec: Optional[TaskSpec] = None
    plan: Optional[CompanyPlan] = None
    qa_reports: List[QAReport] = Field(default_factory=list)
    verdict: Optional[VerificationVerdict] = None
    context: Dict[str, Any] = Field(default_factory=dict)
    artifacts: Dict[str, Any] = Field(default_factory=dict)  # artifact_id -> artifact details
    audit_log: List[Dict[str, Any]] = Field(default_factory=list)

    def register_artifact(self, artifact_id: str, artifact_data: Any) -> None:
        """Register an artifact produced by a worker."""
        if not artifact_id:
            raise ValueError("Artifact ID cannot be empty.")
        self.artifacts[artifact_id] = artifact_data
        self.updated_at = time.time()

    def record_audit(self, role: str, action: str, details: Dict[str, Any] | None = None) -> None:
        """Record an entry in the per-task audit log (Directive B7)."""
        self.audit_log.append({
            "timestamp": time.time(),
            "role": role,
            "action": action,
            "details": details or {},
        })

    def complete(self, verdict: VerificationVerdict, caller_role: str = "verifier") -> None:
        """
        Transition task to COMPLETED.
        Enforces:
        1. Caller must be the 'verifier' role.
        2. Verdict status must be 'VERIFIED'.
        3. Every item in criteria_met must reference an existing artifact ID in self.artifacts.
        """
        if caller_role != "verifier":
            raise PermissionError(f"Role '{caller_role}' is not authorized to complete task. Only 'verifier' is permitted.")

        if verdict.status != "VERIFIED":
            raise ValueError(f"Cannot complete task with non-verified status: '{verdict.status}'")

        if not verdict.evidence_valid:
            raise ValueError("Cannot complete task: VerificationVerdict evidence is marked invalid.")

        if not verdict.criteria_met:
            raise ValueError("Cannot complete task: No criteria_met provided in VerificationVerdict.")

        for item in verdict.criteria_met:
            if isinstance(item, dict):
                art_id = item.get("artifact_id")
                crit = item.get("criterion")
            elif hasattr(item, "artifact_id"):
                art_id = getattr(item, "artifact_id")
                crit = getattr(item, "criterion", "")
            else:
                art_id = str(item)
                crit = ""

            if not art_id or art_id not in self.artifacts:
                raise ValueError(
                    f"Criterion '{crit}' references missing or invalid artifact ID '{art_id}'."
                )

        self.verdict = verdict
        object.__setattr__(self, "_completing", True)
        try:
            self.status = "COMPLETED"
        finally:
            object.__setattr__(self, "_completing", False)
        self.updated_at = time.time()
        self.record_audit("verifier", "task_completed", {"verdict_id": verdict.verdict_id})

    def set_status(self, new_status: str, caller_role: str = "") -> None:
        """Safe status update that prevents unauthorized transitions to COMPLETED."""
        if new_status == "COMPLETED":
            raise PermissionError("Direct transition to COMPLETED is prohibited. Use task.complete(verdict, caller_role='verifier').")
        self.status = new_status
        self.updated_at = time.time()


# =============================================================================
# 7. Specialist Research Outputs (GitHub Researcher, Tool Operator)
# =============================================================================

class GitHubCandidate(BaseModel):
    """Candidate open-source repository or library evaluation."""
    model_config = ConfigDict(extra="ignore")

    repo_url: str = Field(description="URL or GitHub slug (owner/repo)")
    name: str = Field(description="Package or repository name")
    license_spdx: str = Field(description="Detected license SPDX ID (e.g. MIT, Apache-2.0, AGPL-3.0)")
    health_score: float = Field(default=0.0, description="Health score (0.0 to 1.0) based on stars, commits, issues")
    maintenance_status: str = Field(default="ACTIVE", description="ACTIVE, DORMANT, DEPRECATED, UNMAINTAINED")
    recommendation: LicenseVerdict = Field(description="REUSE, ADAPT, DEPEND, INSPIRE, or REJECT")
    justification: str = Field(description="Detailed rationale for the recommendation")


class GitHubResearchReport(BaseModel):
    """Structured report produced by GitHub / Open-Source Researcher."""
    model_config = ConfigDict(extra="ignore")

    task_id: str = Field(description="Associated company task ID")
    query: str = Field(description="Search query or problem description investigated")
    candidates: List[GitHubCandidate] = Field(default_factory=list, description="Evaluated candidate repositories")
    chosen_recommendation: Optional[GitHubCandidate] = Field(default=None, description="Top recommended candidate")
    license_audit_passed: bool = Field(default=True, description="Whether all recommended candidates comply with licensing")
    summary: str = Field(description="Executive summary of open-source research")


class ToolExecutionStep(BaseModel):
    """Step in a multi-step complex tool execution pipeline."""
    model_config = ConfigDict(extra="ignore")

    step_number: int
    tool_name: str
    arguments: Dict[str, Any]
    output: Any = None
    success: bool = True
    error: Optional[str] = None
    duration_ms: float = 0.0


class ToolOperatorReport(BaseModel):
    """Report from Tool / Browser Operator executing multi-step complex sequences."""
    model_config = ConfigDict(extra="ignore")

    task_id: str
    action_sequence: str
    total_steps: int
    successful_steps: int
    steps: List[ToolExecutionStep] = Field(default_factory=list)
    artifacts_collected: List[str] = Field(default_factory=list)
    final_output: Any = None
    status: str = "SUCCESS"
    error: Optional[str] = None


# =============================================================================
# 8. Audit & Workflow Result Models (Directives B5, B7)
# =============================================================================

class AuditLogEntry(BaseModel):
    """Directive B7: Per-task audit log for tool calls, models, tokens, and durations."""
    model_config = ConfigDict(extra="ignore")

    task_id: str = Field(description="Task ID")
    step_id: str = Field(description="Execution step or spec ID")
    role: str = Field(description="Role identifier executing the step")
    model: str = Field(default="hermes-agent", description="Model used")
    tool_name: Optional[str] = Field(default=None, description="Tool called, if any")
    tool_arguments: Optional[Dict[str, Any]] = Field(default=None, description="Sanitized arguments")
    tokens_used: int = Field(default=0, description="Tokens consumed")
    duration_seconds: float = Field(default=0.0, description="Execution duration in seconds")
    outcome: str = Field(default="SUCCESS", description="'SUCCESS', 'FAILURE', 'BLOCKED'")
    error: Optional[str] = Field(default=None, description="Error detail if failed")
    timestamp: float = Field(default_factory=time.time, description="Unix timestamp")
    context_tokens: int = Field(default=0, description="Usable context tokens allocated")
    discarded_context_count: int = Field(default=0, description="Count of candidate context items discarded")


AuditRecord = AuditLogEntry


class CompanyWorkflowResult(BaseModel):
    """Consolidated result returned by CompanyWorkflow."""
    model_config = ConfigDict(extra="ignore")

    task_id: str
    status: WorkflowStatus
    plan: Optional[CompanyPlan] = None
    developer_outputs: List[DeveloperOutput] = Field(default_factory=list)
    qa_reports: List[QAReport] = Field(default_factory=list)
    final_qa_report: Optional[QAReport] = None
    verdict: Optional[VerificationVerdict] = None
    remediation_cycles: int = 0
    baseline_commit: Optional[str] = None
    branch_or_worktree: Optional[str] = None
    audit_log: List[AuditLogEntry] = Field(default_factory=list)
    escalated_to_human: bool = False
    error: Optional[str] = None
    duration_seconds: float = 0.0
