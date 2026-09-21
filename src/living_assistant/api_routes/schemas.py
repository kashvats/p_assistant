from __future__ import annotations

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    message: str
    context: str = ""
    session_id: str | None = None


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


class DesktopAnalyzeRequest(BaseModel):
    prompt: str = Field(
        default="Describe the visible UI and actionable controls.",
        max_length=4000,
    )
    monitor_id: int = Field(default=0, ge=0, le=64)


class PeerDelegateRequest(BaseModel):
    source_peer_id: str = Field(default="", max_length=128)
    role: str = Field(default="general", max_length=32)
    task: str = Field(min_length=1, max_length=30000)
    context: str = Field(default="", max_length=50000)
