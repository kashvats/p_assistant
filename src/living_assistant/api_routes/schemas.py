from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    message: str
    context: str = ""
    session_id: str | None = None  # omitted: continue the shared active conversation
    source: str = "text"  # how the user asked: text | voice
    images: list[str] = Field(default_factory=list, max_length=4)  # attached image ids (POST /attachments)
    files: list[str] = Field(default_factory=list, max_length=8)  # attached file ids (POST /files/upload)


class ApprovalDecision(BaseModel):
    approved: bool


class TodoRequest(BaseModel):
    title: str
    due_at: str | None = None


class BrowserStartRequest(BaseModel):
    name: str
    url: str
    persistent: bool = False
    allowed_hosts: list[str] = Field(default_factory=list)


class BrowserInteractRequest(BaseModel):
    action: str
    selector: str
    value: str | None = None


class BrowserNavigateRequest(BaseModel):
    url: str


class CalendarEventRequest(BaseModel):
    title: str
    start_at: str
    end_at: str | None = None
    location: str | None = None
    notes: str | None = None


class FocusRequest(BaseModel):
    minutes: int = 60
    label: str | None = None


class QuietRequest(BaseModel):
    start: str = "22:00"
    end: str = "07:00"
    enabled: bool = True


class IntegrityBaselineRequest(BaseModel):
    name: str
    path: str
    recursive: bool = True
    extensions: list[str] = Field(default_factory=list)


class EvaluationSuiteRequest(BaseModel):
    name: str
    project_path: str
    test_commands: list[str] = Field(default_factory=list)
    lint_commands: list[str] = Field(default_factory=list)
    benchmark_commands: list[str] = Field(default_factory=list)
    repetitions: int | None = None
    max_latency_regression_pct: float | None = None
    max_memory_regression_pct: float | None = None
    execution_provider: str = "host"
    sandbox_image: str | None = None
    require_canary: bool = False


class SecurityPathRequest(BaseModel):
    path: str
    label: str | None = None
    rules: list[str] = Field(default_factory=list)


class BackupBaselineCreateRequest(BaseModel):
    name: str
    path: str


class ImprovementEvaluateRequest(BaseModel):
    suite_name: str | None = None
    project_path: str | None = None
    test_commands: list[str] | None = None
    lint_commands: list[str] | None = None
    benchmark_commands: list[str] | None = None
    repetitions: int | None = None
    max_latency_regression_pct: float | None = None
    max_memory_regression_pct: float | None = None
    execution_provider: str | None = None
    sandbox_image: str | None = None


class CanaryRequest(BaseModel):
    command: str
    provider: str = "host"
    image: str | None = None
    health_path: str = "/health"
    service_port: int = 8000
    observe_seconds: int | None = None
    startup_timeout_seconds: int | None = None
    max_latency_regression_pct: float | None = None
    max_memory_regression_pct: float | None = None
    min_health_success_pct: float | None = None


class ExperienceRecordRequest(BaseModel):
    kind: str
    situation: str
    lesson: str
    project: str | None = None
    action_taken: str | None = None
    outcome: str | None = None
    root_cause: str | None = None
    better_action: str | None = None
    verified: bool = False
    evidence: str | None = None


class ExperienceVerifyRequest(BaseModel):
    useful: bool
    evidence: str | None = None


class ExperienceConfirmRequest(BaseModel):
    notes: str | None = None


class ConnectorCallRequest(BaseModel):
    action: str
    params: dict = Field(default_factory=dict)


class ModelRequest(BaseModel):
    model: str = Field(min_length=1, max_length=300)


class ModelDeleteRequest(BaseModel):
    model: str = Field(min_length=1, max_length=300)
    confirm: bool = False


class EnabledRequest(BaseModel):
    enabled: bool


class VoiceSpeakRequest(BaseModel):
    text: str = Field(min_length=1, max_length=20000)


class VoiceAskRequest(BaseModel):
    max_seconds: float = Field(default=15.0, ge=1.0, le=60.0)
    language: str | None = Field(default=None, max_length=32)
    speak: bool = False


class DesktopAnalyzeRequest(BaseModel):
    prompt: str = Field(
        default="Describe the visible UI and actionable controls.",
        max_length=4000,
    )
    monitor_id: int = Field(default=0, ge=0, le=64)
    session_id: str | None = Field(default=None, max_length=128)


class PeerDelegateRequest(BaseModel):
    source_peer_id: str = Field(default="", max_length=128)
    role: str = Field(default="general", max_length=32)
    task: str = Field(min_length=1, max_length=30000)
    context: str = Field(default="", max_length=50000)


class ProjectOnboardRequest(BaseModel):
    path: str = Field(default=".", description="Filesystem path to the repository to onboard.", strict=True)
    update_graph: bool = Field(default=True, description="Whether to generate or update system.graph.yaml.", strict=True)


# =============================================================================
# Feature F9: Unified AI Coding Assistant Schemas
# =============================================================================


class CodingGenerateRequest(BaseModel):
    task: str | None = Field(default=None, max_length=20000, description="Task description or coding instructions.")
    prompt: str | None = Field(default=None, max_length=20000, description="Prompt or coding instructions.")
    context: str = Field(default="", max_length=50000, description="Relevant code or context snippet.")
    language: str | None = Field(default=None, max_length=32, description="Target programming language.")
    target_path: str | None = Field(default=None, max_length=500, description="Optional target file path to generate into.")
    provider: str = Field(default="ollama", max_length=32, description="Model provider (e.g. ollama, collibri, openai).")
    model: str | None = Field(default=None, max_length=128, description="Specific model name (e.g. openai/collibri).")
    timeout: float = Field(default=300.0, ge=1.0, le=600.0, description="Execution timeout in seconds.")


class CodingGenerateResponse(BaseModel):
    ok: bool
    output: str = ""
    code: str = ""
    language: str | None = None
    model: str | None = None
    contractor: str = "hermes_agent"
    target_path: str | None = None
    error: str | None = None


class CodingPatchRequest(BaseModel):
    path: str = Field(default="", max_length=500, description="Target file path in workspace to patch.")
    content: str | None = Field(default=None, description="Proposed new file content.")
    proposed: str | None = Field(default=None, description="Proposed new file content.")
    patch_mode: str = Field(default="full_file", description="Patch mode: 'full_file' or 'semantic'.")
    dry_run: bool | None = Field(default=None, description="If True, performs AST analysis without writing to disk.")
    apply: bool | None = Field(default=None, description="If True, applies patch to disk.")
    strict_ast: bool = Field(default=True, description="If True, blocks deletion/removal of existing symbols.")
    backup: bool = Field(default=True, description="Whether to take a workspace snapshot before writing.")


class CodingPatchResponse(BaseModel):
    ok: bool
    path: str
    applied: bool = False
    diff: str = ""
    added_symbols: list[str] = Field(default_factory=list)
    changed_symbols: list[str] = Field(default_factory=list)
    removed_symbols: list[str] = Field(default_factory=list)
    ast_checked: bool = False
    syntax_error: dict[str, Any] | None = None
    error: str | None = None


class CodingAuditRequest(BaseModel):
    path: str = Field(default=".", max_length=500, description="Workspace directory or file path to audit.")
    depth: str = Field(default="standard", description="Audit depth: 'standard' (ProjectAuditor) or 'deep' (ProjectAuditor + OnboardingEngine).")
    max_files: int = Field(default=1500, ge=1, le=10000, description="Max files to scan.")


class CodingAuditResponse(BaseModel):
    ok: bool
    path: str
    health_score: float = 0.0
    files_scanned: int = 0
    bounded: bool = True
    scan: dict[str, Any] = Field(default_factory=dict)
    dependencies: dict[str, Any] = Field(default_factory=dict)
    lint: dict[str, Any] = Field(default_factory=dict)
    dead_code: dict[str, Any] = Field(default_factory=dict)
    security: dict[str, Any] = Field(default_factory=dict)
    deep_analysis: dict[str, Any] | None = None
    error: str | None = None


class CodingRepairRequest(BaseModel):
    path: str | None = Field(default=None, max_length=500, description="Target file path with syntax or test failures.")
    error_context: str | None = Field(default=None, max_length=50000, description="Error message, stack trace, or test failure logs.")
    failed_evaluation_id: str | None = Field(default=None, max_length=128, description="Existing evaluation ID if repairing an existing failed evaluation.")
    test_commands: list[str] = Field(default_factory=list, description="Optional verification commands to run.")
    max_cycles: int = Field(default=3, ge=1, le=5, description="Max repair loop iterations (1-5).")
    evaluation_id: str | None = Field(default=None, max_length=128, description="Existing evaluation ID if repairing an existing failed evaluation.")
    auto_apply: bool = Field(default=False, description="Whether to apply repaired candidate to disk if verified.")


class CodingRepairResponse(BaseModel):
    ok: bool
    path: str = ""
    status: str = "failed"  # "repaired" | "candidate_generated" | "failed" | "pending_approval"
    failed_evaluation_id: str | None = None
    cycles_run: int = 0
    cycles_completed: int = 0
    diff: str | None = None
    repaired_content: str | None = None
    passed: bool = False
    verification_passed: bool = False
    approval_required: bool = False
    plan: dict[str, Any] | None = None
    attempts: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None


class CodingSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000, description="Search terms, code query, or API identifier.")
    source: str = Field(default="all", description="Search domain: 'local', 'web', or 'all'.")
    path: str = Field(default=".", max_length=500, description="Workspace path for local codebase search.")
    limit: int = Field(default=10, ge=1, le=50, description="Max results per search domain.")
    images: bool = Field(default=False, description="Whether to search for image results.")
    web_provider: str = Field(default="auto", description="Web search provider: 'auto', 'searxng', etc.")


class CodingSearchResponse(BaseModel):
    ok: bool
    query: str = ""
    provider: str = "searxng"
    count: int = 0
    local_results: list[dict[str, Any]] = Field(default_factory=list)
    web_results: list[dict[str, Any]] = Field(default_factory=list)
    results: list[dict[str, Any]] = Field(default_factory=list)
    total_results: int = 0
    sources_searched: list[str] = Field(default_factory=list)
    error: str | None = None


class CodingExplainRequest(BaseModel):
    command: str = Field(default="", max_length=4000, description="Shell command to explain.")


class CodingExplainResponse(BaseModel):
    ok: bool
    command: str = ""
    risk_level: str = "medium"
    allowed: bool = True
    summary: str = ""
    requires_approval: bool = False
    policy_reason: str = ""
    executable: str | None = None
    error: str | None = None
