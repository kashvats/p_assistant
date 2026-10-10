"""Unified AI Coding Assistant API router."""
from __future__ import annotations

import ast
import logging
from pathlib import Path
import subprocess
from typing import Any

from fastapi import APIRouter, Header, HTTPException

from living_assistant.api_routes.dependencies import authorize, runtime
from living_assistant.api_routes.schemas import (
    CodingAuditRequest,
    CodingAuditResponse,
    CodingExplainRequest,
    CodingExplainResponse,
    CodingGenerateRequest,
    CodingGenerateResponse,
    CodingPatchRequest,
    CodingPatchResponse,
    CodingRepairRequest,
    CodingRepairResponse,
    CodingSearchRequest,
    CodingSearchResponse,
)
from living_assistant.core.workspace import WorkspaceViolation
from living_assistant.learning.patch_engine import ASTSafePatchEngine
from living_assistant.security.security_utils import redact_secrets
from living_assistant.system.project_auditor import ProjectAuditor

logger = logging.getLogger("living_assistant.api_routes.coding")

router = APIRouter(tags=["coding"])


def _redact_data(data: Any) -> Any:
    """Recursively redact secrets from nested dictionary, list, or string structures."""
    if isinstance(data, str):
        return redact_secrets(data)
    elif isinstance(data, dict):
        return {k: _redact_data(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_redact_data(x) for x in data]
    return data


@router.post("/coding/generate", response_model=CodingGenerateResponse)
def coding_generate(
    request: CodingGenerateRequest,
    authorization: str | None = Header(default=None),
) -> CodingGenerateResponse:
    """Generate code or scaffolds via HermesContractor or configured LLM."""
    authorize(authorization)
    rt = runtime()

    target_resolved: Path | None = None
    if request.target_path:
        try:
            target_resolved = rt.workspace.resolve(request.target_path)
        except WorkspaceViolation as exc:
            raise HTTPException(
                status_code=403,
                detail=f"Target path is outside allowed workspace roots: {exc}",
            )

    output = ""
    contractor_name = "hermes_agent"
    error = None
    ok = False

    try:
        from living_assistant.integrations.hermes_contractor import HermesContractor

        base_url = "http://127.0.0.1:8080/v1"
        if hasattr(rt, "config") and isinstance(rt.config, dict):
            base_url = (
                rt.config.get("models", {})
                .get("providers", {})
                .get("collibri", {})
                .get("base_url", base_url)
            )

        contractor = HermesContractor(
            model_manager=getattr(rt, "model_manager", None),
            session_id="coding_api",
            tool_registry=getattr(rt, "skills", None).tool_registry
            if hasattr(getattr(rt, "skills", None), "tool_registry")
            else None,
            base_url=base_url,
            model_name=request.model or "openai/collibri",
            provider=request.provider,
        )
        res = contractor.execute_task(
            task=request.task,
            context=request.context,
            timeout=request.timeout,
        )
        ok = bool(res.get("ok"))
        output = str(res.get("output") or "")
        error = res.get("error")
        contractor_name = str(res.get("contractor") or "hermes_agent")
    except Exception as exc:
        logger.warning("HermesContractor execution fallback: %s", exc)
        gen_fn = getattr(getattr(rt, "model_manager", None), "generate", None)
        if callable(gen_fn):
            try:
                prompt = f"Task: {request.task}\n\nContext:\n{request.context}"
                output = gen_fn(prompt=prompt, model=request.model)
                ok = True
                contractor_name = "model_manager"
            except Exception as m_exc:
                error = f"Generation failed: {m_exc}"
        else:
            error = f"HermesContractor unavailable and no model generator configured: {exc}"

    return CodingGenerateResponse(
        ok=ok,
        output=output,
        contractor=contractor_name,
        target_path=str(target_resolved) if target_resolved else None,
        error=error,
    )


@router.post("/coding/patch", response_model=CodingPatchResponse)
def coding_patch(
    request: CodingPatchRequest,
    authorization: str | None = Header(default=None),
) -> CodingPatchResponse:
    """AST-guided or semantic file patching with removal guard."""
    authorize(authorization)
    rt = runtime()

    try:
        target = rt.workspace.resolve(request.path)
    except WorkspaceViolation as exc:
        raise HTTPException(
            status_code=403,
            detail=f"Path is outside allowed workspace roots: {exc}",
        )

    original_content = ""
    if target.exists() and target.is_file():
        original_content = target.read_text(encoding="utf-8", errors="replace")

    patch_engine = ASTSafePatchEngine()
    analysis = patch_engine.analyze(original_content, request.content, target)

    # Check strict_ast constraints
    if request.strict_ast and analysis.get("removed_symbols"):
        return CodingPatchResponse(
            ok=False,
            path=str(target),
            applied=False,
            diff=analysis.get("diff", ""),
            added_symbols=analysis.get("added_symbols", []),
            changed_symbols=analysis.get("changed_symbols", []),
            removed_symbols=analysis.get("removed_symbols", []),
            ast_checked=analysis.get("ast_checked", False),
            error=analysis.get("error", "AST safety blocked removal of existing symbols."),
        )

    # Check syntax errors
    if not analysis.get("ok", True) and analysis.get("syntax_error"):
        syn_err_msg = analysis.get("error", "Proposed patch contains Python syntax error.")
        if "syntax" not in syn_err_msg.lower():
            syn_err_msg = f"Syntax error in proposed patch: {syn_err_msg}"
        return CodingPatchResponse(
            ok=False,
            path=str(target),
            applied=False,
            diff=analysis.get("diff", ""),
            ast_checked=True,
            syntax_error=analysis.get("syntax_error"),
            error=syn_err_msg,
        )

    if not analysis.get("ok", True):
        return CodingPatchResponse(
            ok=False,
            path=str(target),
            applied=False,
            diff=analysis.get("diff", ""),
            added_symbols=analysis.get("added_symbols", []),
            changed_symbols=analysis.get("changed_symbols", []),
            removed_symbols=analysis.get("removed_symbols", []),
            ast_checked=analysis.get("ast_checked", False),
            syntax_error=analysis.get("syntax_error"),
            error=analysis.get("error", "AST patch analysis failed."),
        )

    # Dry-run return
    if request.dry_run:
        return CodingPatchResponse(
            ok=analysis.get("ok", True),
            path=str(target),
            applied=False,
            diff=analysis.get("diff", ""),
            added_symbols=analysis.get("added_symbols", []),
            changed_symbols=analysis.get("changed_symbols", []),
            removed_symbols=analysis.get("removed_symbols", []),
            ast_checked=analysis.get("ast_checked", False),
            error=analysis.get("error"),
        )

    # Take workspace snapshot backup if requested
    if request.backup and hasattr(rt, "snapshots") and rt.snapshots:
        try:
            rt.snapshots.create_checkpoint(f"Pre-patch {target.name}")
        except Exception as exc:
            logger.debug("Checkpoint creation skipped: %s", exc)

    # Write file content
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(request.content, encoding="utf-8")

    return CodingPatchResponse(
        ok=True,
        path=str(target),
        applied=True,
        diff=analysis.get("diff", ""),
        added_symbols=analysis.get("added_symbols", []),
        changed_symbols=analysis.get("changed_symbols", []),
        removed_symbols=analysis.get("removed_symbols", []),
        ast_checked=analysis.get("ast_checked", False),
    )


@router.post("/coding/audit", response_model=CodingAuditResponse)
def coding_audit(
    request: CodingAuditRequest,
    authorization: str | None = Header(default=None),
) -> CodingAuditResponse:
    """Static and deep codebase health audit."""
    authorize(authorization)
    rt = runtime()

    try:
        target = rt.workspace.resolve(request.path)
    except WorkspaceViolation as exc:
        raise HTTPException(
            status_code=403,
            detail=f"Path is outside allowed workspace roots: {exc}",
        )

    if not target.exists():
        raise HTTPException(
            status_code=400,
            detail=f"Target path does not exist: {request.path}",
        )

    auditor = ProjectAuditor(workspace=rt.workspace, max_files=request.max_files)

    if target.is_file():
        files = [target]
        code = auditor._python_scan(target.parent, files)
        return CodingAuditResponse(
            ok=True,
            path=str(target),
            health_score=float(code["lint"]["score"]),
            files_scanned=1,
            lint=_redact_data(code["lint"]),
            dead_code=_redact_data(code["dead_code"]),
            security=_redact_data(code["security"]),
        )

    audit_data = auditor.audit(target)
    if not audit_data.get("ok"):
        raise HTTPException(
            status_code=400,
            detail=audit_data.get("error", "Project audit failed."),
        )

    deep_analysis = None
    if request.depth == "deep":
        try:
            from living_assistant.system.codebase_onboarding import CodebaseOnboardingEngine

            engine = CodebaseOnboardingEngine(
                workspace=rt.workspace,
                codebase_index=getattr(rt, "code_index", None),
            )
            onboard_res = engine.onboard_repository(target, update_graph=False)
            deep_dict = (
                onboard_res.model_dump()
                if hasattr(onboard_res, "model_dump")
                else onboard_res.dict()
            )
            deep_analysis = _redact_data(deep_dict)
        except Exception as exc:
            logger.warning("Deep audit onboarding error: %s", exc)
            deep_analysis = {"error": f"Deep onboarding analysis encountered: {exc}"}

    return CodingAuditResponse(
        ok=True,
        path=str(target),
        health_score=float(audit_data.get("health_score", 0.0)),
        files_scanned=int(audit_data.get("scan", {}).get("files_scanned", 0)),
        dependencies=_redact_data(audit_data.get("dependencies", {})),
        lint=_redact_data(audit_data.get("lint", {})),
        dead_code=_redact_data(audit_data.get("dead_code", {})),
        security=_redact_data(audit_data.get("security", {})),
        deep_analysis=deep_analysis,
    )


@router.post("/coding/repair", response_model=CodingRepairResponse)
def coding_repair(
    request: CodingRepairRequest,
    authorization: str | None = Header(default=None),
) -> CodingRepairResponse:
    """Autonomous syntax/test error repair loop."""
    authorize(authorization)
    rt = runtime()

    try:
        target = rt.workspace.resolve(request.path)
    except WorkspaceViolation as exc:
        raise HTTPException(
            status_code=403,
            detail=f"Path is outside allowed workspace roots: {exc}",
        )

    if not target.exists() or not target.is_file():
        raise HTTPException(
            status_code=400,
            detail=f"Target file does not exist: {request.path}",
        )

    max_cycles = max(1, min(request.max_cycles, 5))

    # Evaluation-linked repair route
    if request.evaluation_id and hasattr(rt, "repairs") and rt.repairs:
        rep_res = rt.repairs.run(request.evaluation_id, max_cycles=max_cycles)
        return CodingRepairResponse(
            ok=bool(rep_res.get("ok")),
            path=str(target),
            status="repaired" if rep_res.get("ok") else "failed",
            cycles_run=len(rep_res.get("attempts", [])),
            diff=rep_res.get("diff"),
            repaired_content=rep_res.get("repaired_content"),
            verification_passed=bool(rep_res.get("ok")),
            attempts=rep_res.get("attempts", []),
            error=rep_res.get("error"),
        )

    original_code = target.read_text(encoding="utf-8", errors="replace")
    patch_engine = ASTSafePatchEngine()

    attempts: list[dict[str, Any]] = []
    status = "failed"
    repaired_content: str | None = None
    diff: str | None = None
    verification_passed = False

    for cycle in range(1, max_cycles + 1):
        # Diagnose syntax error
        syntax_info = ""
        try:
            ast.parse(original_code, filename=target.name)
        except SyntaxError as syn_exc:
            syntax_info = f"SyntaxError: {syn_exc.msg} at line {syn_exc.lineno}, offset {syn_exc.offset}"

        # Generate candidate fix via model manager
        prompt = (
            f"Fix the error in this code:\nFile: {target.name}\n"
            f"Error details: {request.error_context}\n"
            f"{syntax_info}\n\n"
            f"Original code:\n```python\n{original_code}\n```\n"
            f"Output ONLY the corrected complete python file."
        )

        candidate = ""
        gen_fn = getattr(getattr(rt, "model_manager", None), "generate", None)
        if callable(gen_fn):
            try:
                candidate = gen_fn(prompt=prompt)
                candidate = candidate.strip()
                if candidate.startswith("```python"):
                    candidate = candidate[len("```python"):].strip()
                if candidate.startswith("```"):
                    candidate = candidate[3:].strip()
                if candidate.endswith("```"):
                    candidate = candidate[:-3].strip()
                if not candidate.endswith("\n"):
                    candidate += "\n"
            except Exception as gen_exc:
                attempts.append({"cycle": cycle, "stage": "generation", "error": str(gen_exc)})
                continue
        else:
            attempts.append({"cycle": cycle, "stage": "generation", "error": "No model manager available."})
            break

        # Validate with ASTSafePatchEngine
        analysis = patch_engine.analyze(original_code, candidate, target)
        if not analysis.get("ok"):
            attempts.append({
                "cycle": cycle,
                "stage": "ast_validation",
                "error": analysis.get("error"),
                "syntax_error": analysis.get("syntax_error"),
            })
            continue

        # Test command verification if requested
        tests_passed = True
        if request.test_commands:
            backup_content = target.read_text(encoding="utf-8") if target.exists() else ""
            try:
                target.write_text(candidate, encoding="utf-8")
                # Invalidate any bytecode cache in directory so tests re-evaluate newly written candidate
                pycache_dir = target.parent / "__pycache__"
                if pycache_dir.is_dir():
                    try:
                        import shutil
                        shutil.rmtree(pycache_dir, ignore_errors=True)
                    except Exception:
                        pass
                for cmd in request.test_commands:
                    proc = subprocess.run(
                        cmd,
                        shell=True,
                        cwd=str(target.parent),
                        capture_output=True,
                        timeout=30,
                    )
                    if proc.returncode != 0:
                        tests_passed = False
                        attempts.append({
                            "cycle": cycle,
                            "stage": "test_verification",
                            "command": cmd,
                            "exit_code": proc.returncode,
                            "output": (proc.stdout + proc.stderr).decode("utf-8", errors="replace")[:1000],
                        })
                        break
            finally:
                if not request.auto_apply or not tests_passed:
                    target.write_text(backup_content, encoding="utf-8")
            if not tests_passed:
                continue

        diff = analysis.get("diff")
        repaired_content = candidate
        verification_passed = True
        attempts.append({"cycle": cycle, "stage": "verification", "status": "passed"})
        status = "candidate_generated"

        if request.auto_apply:
            target.write_text(candidate, encoding="utf-8")
            status = "repaired"
        break

    return CodingRepairResponse(
        ok=verification_passed,
        path=str(target),
        status=status,
        cycles_run=len(attempts),
        diff=diff,
        repaired_content=repaired_content,
        verification_passed=verification_passed,
        attempts=attempts,
        error=None if verification_passed else "Repair loop failed to produce passing candidate.",
    )


@router.post("/coding/search", response_model=CodingSearchResponse)
def coding_search(
    request: CodingSearchRequest,
    authorization: str | None = Header(default=None),
) -> CodingSearchResponse:
    """SearXNG and local semantic codebase search."""
    authorize(authorization)
    rt = runtime()

    if not request.query or not request.query.strip():
        raise HTTPException(
            status_code=400,
            detail="Search query must not be empty.",
        )

    try:
        target = rt.workspace.resolve(request.path)
    except WorkspaceViolation as exc:
        raise HTTPException(
            status_code=403,
            detail=f"Path is outside allowed workspace roots: {exc}",
        )

    local_results: list[dict[str, Any]] = []
    web_results: list[dict[str, Any]] = []
    sources: list[str] = []

    # Local codebase index search
    if request.source in {"local", "all"}:
        sources.append("local")
        if hasattr(rt, "code_index") and rt.code_index is not None:
            try:
                res = rt.code_index.search(
                    query=request.query,
                    path=target,
                    limit=request.limit,
                )
                if res.get("ok"):
                    local_results = _redact_data(res.get("results", []))
            except Exception as exc:
                logger.warning("Codebase index search failed: %s", exc)

    # Web search via SearXNG or tool registry
    if request.source in {"web", "all"}:
        sources.append("web")
        try:
            from living_assistant.tools import webtools

            search_fn = getattr(webtools, "_searxng_search", None)
            if callable(search_fn):
                res = search_fn(request.query, limit=request.limit, images=False)
                if res.get("ok"):
                    web_results = _redact_data(res.get("results", []))
            elif hasattr(rt, "skills") and hasattr(rt.skills, "tool_registry"):
                tool = rt.skills.tool_registry.get("web_search")
                if tool and callable(getattr(tool, "handler", None)):
                    res = tool.handler(query=request.query, num=request.limit)
                    if res.get("ok"):
                        web_results = _redact_data(res.get("results", []))
        except Exception as exc:
            logger.warning("Web search failed: %s", exc)

    return CodingSearchResponse(
        ok=True,
        query=request.query,
        local_results=local_results,
        web_results=web_results,
        total_results=len(local_results) + len(web_results),
        sources_searched=sources,
    )


@router.post("/coding/explain", response_model=CodingExplainResponse)
def coding_explain(
    request: CodingExplainRequest,
    authorization: str | None = Header(default=None),
) -> CodingExplainResponse:
    """Safe shell command explainer without echoing arguments."""
    authorize(authorization)

    if not request.command or not request.command.strip():
        raise HTTPException(
            status_code=400,
            detail="Command must not be empty.",
        )

    try:
        from living_assistant.security.safe_commands import explain_command

        exp = explain_command(request.command)
        return CodingExplainResponse(
            ok=True,
            command=request.command,
            risk_level=exp.risk_level,
            allowed=exp.allowed,
            summary=exp.summary,
            requires_approval=exp.requires_approval,
            policy_reason=exp.policy_reason,
            executable=exp.executable,
        )
    except Exception as exc:
        logger.error("Command explanation failed: %s", exc)
        return CodingExplainResponse(
            ok=False,
            command=request.command,
            error=str(exc),
        )
