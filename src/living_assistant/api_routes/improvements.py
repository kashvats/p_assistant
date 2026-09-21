from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from living_assistant.api_routes.dependencies import authorize, runtime
from living_assistant.api_routes.schemas import (
    CanaryRequest,
    EvaluationSuiteRequest,
    ExperienceConfirmRequest,
    ExperienceRecordRequest,
    ExperienceVerifyRequest,
    ImprovementEvaluateRequest,
)

router = APIRouter(tags=["improvements"])


@router.get("/improvements")
def improvements(
    status: str = "pending",
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return runtime().improvements.store.list(
        None if status == "all" else status,
    )


@router.post("/improvements/{proposal_id}/apply")
def improvement_apply(
    proposal_id: str,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return runtime().improvements.apply(proposal_id)


@router.post("/improvements/{proposal_id}/rollback")
def improvement_rollback(
    proposal_id: str,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return runtime().improvements.rollback(proposal_id)


@router.get("/improvement-suites")
def improvement_suites(authorization: str | None = Header(default=None)):
    authorize(authorization)
    return runtime().evaluations.store.list_suites()


@router.post("/improvement-suites")
def improvement_suite_add(
    req: EvaluationSuiteRequest,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return runtime().evaluations.create_suite(
        req.name,
        req.project_path,
        req.test_commands,
        req.lint_commands,
        req.benchmark_commands,
        req.repetitions,
        req.max_latency_regression_pct,
        req.max_memory_regression_pct,
        req.execution_provider,
        req.sandbox_image,
        "none",
        None,
        None,
        None,
        req.require_canary,
    )


@router.delete("/improvement-suites/{name}")
def improvement_suite_delete(
    name: str,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return {"ok": runtime().evaluations.store.delete_suite(name)}


@router.get("/improvement-evaluations")
def improvement_evaluations(
    status: str = "all",
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return runtime().evaluations.store.list(
        None if status == "all" else status,
    )


@router.get("/improvement-evaluations/{evaluation_id}")
def improvement_evaluation_get(
    evaluation_id: str,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    item = runtime().evaluations.store.get(evaluation_id)
    if not item:
        raise HTTPException(status_code=404, detail="Unknown evaluation id")
    return item


@router.post("/improvements/{proposal_id}/evaluate")
def improvement_evaluate(
    proposal_id: str,
    req: ImprovementEvaluateRequest,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return runtime().evaluations.evaluate(
        proposal_id,
        req.suite_name,
        req.project_path,
        req.test_commands,
        req.lint_commands,
        req.benchmark_commands,
        req.repetitions,
        req.max_latency_regression_pct,
        req.max_memory_regression_pct,
        req.execution_provider,
        req.sandbox_image,
        None,
    )


@router.get("/sandbox/status")
def sandbox_status(authorization: str | None = Header(default=None)):
    authorize(authorization)
    rt = runtime()
    return {
        "evaluation": rt.evaluations.sandbox_status(),
        "canary": rt.canaries.status(),
    }


@router.get("/canaries")
def canaries(
    evaluation_id: str | None = None,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return runtime().canaries.store.list(evaluation_id)


@router.get("/canaries/{canary_id}")
def canary_get(
    canary_id: str,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    item = runtime().canaries.store.get(canary_id)
    if not item:
        raise HTTPException(status_code=404, detail="Unknown canary id")
    return item


@router.post("/improvement-evaluations/{evaluation_id}/canary")
def canary_run(
    evaluation_id: str,
    req: CanaryRequest,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return runtime().canaries.run(
        evaluation_id,
        req.command,
        req.health_path,
        req.service_port,
        req.provider,
        req.image,
        req.observe_seconds,
        req.startup_timeout_seconds,
        req.max_latency_regression_pct,
        req.max_memory_regression_pct,
        req.min_health_success_pct,
    )


@router.post("/improvement-evaluations/{evaluation_id}/promote")
def improvement_promote(
    evaluation_id: str,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return runtime().evaluations.promote(evaluation_id)


@router.post("/improvement-evaluations/{evaluation_id}/revert")
def improvement_revert(
    evaluation_id: str,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return runtime().evaluations.revert_promotion(evaluation_id)


@router.get("/experiences")
def experiences(
    status: str = "active",
    project: str | None = None,
    limit: int = 100,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return runtime().experiences.list(
        None if status == "all" else status,
        project,
        limit,
    )


@router.get("/experiences/search")
def experience_search(
    q: str,
    project: str | None = None,
    include_candidates: bool = False,
    limit: int = 10,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return runtime().experiences.search(
        q,
        project,
        limit,
        include_candidates,
    )


@router.get("/experiences/patterns")
def experience_patterns(
    limit: int = 20,
    min_count: int = 2,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return runtime().experiences.failure_patterns(limit, min_count)


@router.get("/experiences/stats")
def experience_stats(authorization: str | None = Header(default=None)):
    authorize(authorization)
    return runtime().experiences.stats()


@router.get("/experiences/{experience_id}")
def experience_get(
    experience_id: str,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    item = runtime().experiences.get(experience_id)
    if not item:
        raise HTTPException(status_code=404, detail="Unknown experience id")
    return item


@router.post("/experiences")
def experience_record(
    req: ExperienceRecordRequest,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return runtime().experiences.record(
        req.kind,
        req.situation,
        req.lesson,
        req.project,
        req.action_taken,
        req.outcome,
        req.root_cause,
        req.better_action,
        req.verified,
        req.evidence,
        source="api",
    )


@router.post("/experiences/{experience_id}/verify")
def experience_verify(
    experience_id: str,
    req: ExperienceVerifyRequest,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return runtime().experiences.verify(
        experience_id,
        req.useful,
        req.evidence,
    )


@router.post("/experiences/{experience_id}/confirm")
def experience_confirm(
    experience_id: str,
    req: ExperienceConfirmRequest,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return runtime().experiences.confirm(experience_id, req.notes)


@router.delete("/experiences/{experience_id}")
def experience_reject(
    experience_id: str,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return runtime().experiences.reject(
        experience_id,
        "Rejected through local API",
    )
