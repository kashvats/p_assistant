from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from living_assistant.api_routes.dependencies import authorize, runtime
from living_assistant.api_routes.schemas import (
    ApprovalDecision,
    BackupBaselineCreateRequest,
    IntegrityBaselineRequest,
    SecurityPathRequest,
)
from living_assistant.security.security_guardian import (
    file_signature,
    inspect_process,
    process_triage,
)

router = APIRouter(tags=["security"])


@router.get("/approvals")
def approvals(
    status: str = "pending",
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return runtime().approvals.list(status=None if status == "all" else status)


@router.post("/approvals/{approval_id}")
def approval_decide(
    approval_id: str,
    decision: ApprovalDecision,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return runtime().approvals.resolve(approval_id, decision.approved)


@router.get("/quarantine")
def quarantine(authorization: str | None = Header(default=None)):
    authorize(authorization)
    return runtime().quarantine.list()


@router.get("/quarantine/{item_id}")
def quarantine_item(
    item_id: str,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    rt = runtime()
    item = rt.quarantine.get(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Unknown quarantine item")
    return {"item": item, "file": file_signature(item["path"])}


@router.post("/quarantine/{item_id}/scan")
def quarantine_scan(
    item_id: str,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    rt = runtime()
    item = rt.quarantine.get(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Unknown quarantine item")
    result = rt.guardian.scan_path_antivirus(item["path"])
    if result.get("ok") or result.get("returncode") is not None:
        rt.quarantine.record_scan(
            item_id,
            result.get("provider", "unknown"),
            result,
        )
    return result


@router.get("/security/summary")
def security_summary(authorization: str | None = Header(default=None)):
    authorize(authorization)
    return runtime().guardian.summary()


@router.get("/security/posture")
def security_posture(
    updates: bool = False,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return runtime().guardian.posture(include_updates=updates)


@router.get("/security/findings")
def security_findings(
    status: str = "open",
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return runtime().guardian.findings(
        None if status == "all" else status,
        200,
    )


@router.post("/security/findings/{finding_id}/resolve")
def security_finding_resolve(
    finding_id: str,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    rt = runtime()
    req = rt.approval_manager.request(
        f"Resolve security finding {finding_id}",
        "Mark a security finding as resolved.",
        "SECURITY_FINDING_RESOLVE",
    )
    if not req.get("allowed"):
        return {"ok": False, "approval_required": True, **req}
    return {"ok": rt.guardian.resolve_finding(finding_id)}


@router.get("/security/startup")
def security_startup(authorization: str | None = Header(default=None)):
    authorize(authorization)
    return runtime().guardian.check_startup_baseline(record=True)


@router.post("/security/startup/capture")
def security_startup_capture(authorization: str | None = Header(default=None)):
    authorize(authorization)
    rt = runtime()
    req = rt.approval_manager.request(
        "Replace startup persistence baseline",
        "Capture current startup/persistence state as trusted reference.",
        "SECURITY_BASELINE_CHANGE",
    )
    if not req.get("allowed"):
        return {"ok": False, "approval_required": True, **req}
    return rt.guardian.capture_startup_baseline()


@router.get("/security/network")
def security_network(authorization: str | None = Header(default=None)):
    authorize(authorization)
    return runtime().guardian.check_network_baseline(record=True)


@router.post("/security/network/capture")
def security_network_capture(authorization: str | None = Header(default=None)):
    authorize(authorization)
    rt = runtime()
    req = rt.approval_manager.request(
        "Replace listening-service baseline",
        "Capture current listening services as trusted reference.",
        "SECURITY_BASELINE_CHANGE",
    )
    if not req.get("allowed"):
        return {"ok": False, "approval_required": True, **req}
    return rt.guardian.capture_network_baseline()


@router.get("/security/integrity")
def security_integrity(authorization: str | None = Header(default=None)):
    authorize(authorization)
    return runtime().guardian.list_integrity_baselines()


@router.post("/security/integrity")
def security_integrity_add(
    req: IntegrityBaselineRequest,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    rt = runtime()
    target = rt.workspace.resolve(req.path)
    approval = rt.approval_manager.request(
        f"Security baseline change: {req.name}",
        f"Create or replace integrity baseline for {target}.",
        "SECURITY_BASELINE_CHANGE",
    )
    if not approval.get("allowed"):
        return {"ok": False, "approval_required": True, **approval}
    return rt.guardian.add_integrity_baseline(
        req.name,
        target,
        req.recursive,
        req.extensions,
    )


@router.get("/security/integrity/{name}/check")
def security_integrity_check(
    name: str,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return runtime().guardian.check_integrity_baseline(name, record=True)


@router.post("/security/integrity/{name}/refresh")
def security_integrity_refresh(
    name: str,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    rt = runtime()
    approval = rt.approval_manager.request(
        f"Refresh security baseline: {name}",
        "Replace stored protected-file hashes with current file hashes.",
        "SECURITY_BASELINE_CHANGE",
    )
    if not approval.get("allowed"):
        return {"ok": False, "approval_required": True, **approval}
    return rt.guardian.refresh_integrity_baseline(name)


@router.delete("/security/integrity/{name}")
def security_integrity_remove(
    name: str,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    rt = runtime()
    approval = rt.approval_manager.request(
        f"Remove security baseline: {name}",
        "Stop monitoring this protected-file baseline.",
        "SECURITY_BASELINE_CHANGE",
    )
    if not approval.get("allowed"):
        return {"ok": False, "approval_required": True, **approval}
    return {"ok": rt.guardian.remove_integrity_baseline(name)}


@router.get("/security/processes/triage")
def security_processes_triage(
    min_score: int = 30,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return process_triage(min_score=min_score, limit=100)


@router.get("/security/network/activity")
def security_network_activity(
    limit: int = 100,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return runtime().guardian.network_activity(limit)


@router.get("/security/process/{pid}")
def security_process(
    pid: int,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return inspect_process(pid)


@router.post("/security/process/{pid}/contain")
def security_process_contain(
    pid: int,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return runtime().guardian.terminate_user_process(pid)


@router.get("/security/sensors/status")
def security_sensors_status(authorization: str | None = Header(default=None)):
    authorize(authorization)
    return runtime().security_sensors.status()


@router.get("/security/sensors/events")
def security_sensors_events(
    minutes: int = 10,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return runtime().security_sensors.collect_events(minutes)


@router.get("/security/sensors/correlations")
def security_sensors_correlations(
    minutes: int = 10,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return runtime().security_sensors.correlations(minutes)


@router.get("/security/sensors/dns")
def security_sensors_dns(
    minutes: int = 10,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return runtime().security_sensors.dns_context(minutes)


@router.get("/security/sensors/tls")
def security_sensors_tls(
    limit: int = 100,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return runtime().security_sensors.tls_context(limit)


@router.post("/security/sensors/yara")
def security_sensors_yara(
    req: SecurityPathRequest,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    rt = runtime()
    return rt.security_sensors.yara_scan(
        rt.workspace.resolve(req.path),
        req.rules,
    )


@router.post("/security/sensors/reputation")
def security_sensors_reputation(
    req: SecurityPathRequest,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    rt = runtime()
    return rt.security_sensors.reputation_file(rt.workspace.resolve(req.path))


@router.get("/security/sensors/reputation/process/{pid}")
def security_sensors_reputation_process(
    pid: int,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return runtime().security_sensors.reputation_process(pid)


@router.post("/security/sensors/binary/assess")
def security_sensors_binary_assess(
    req: SecurityPathRequest,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    rt = runtime()
    return rt.security_sensors.assess_binary(rt.workspace.resolve(req.path))


@router.post("/security/sensors/binary/trust")
def security_sensors_binary_trust(
    req: SecurityPathRequest,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    rt = runtime()
    return rt.security_sensors.trust_binary(
        rt.workspace.resolve(req.path),
        req.label or "trusted",
    )


@router.get("/security/sensors/binary/check")
def security_sensors_binary_check(
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return runtime().security_sensors.check_trusted_binaries()


@router.get("/security/sensors/usb")
def security_sensors_usb(authorization: str | None = Header(default=None)):
    authorize(authorization)
    return runtime().security_sensors.check_usb()


@router.post("/security/sensors/usb/baseline")
def security_sensors_usb_baseline(
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return runtime().security_sensors.capture_usb_baseline()


@router.get("/security/sensors/extensions")
def security_sensors_extensions(
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return runtime().security_sensors.check_extensions()


@router.post("/security/sensors/extensions/baseline")
def security_sensors_extensions_baseline(
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return runtime().security_sensors.capture_extension_baseline()


@router.get("/security/sensors/backups")
def security_sensors_backups(authorization: str | None = Header(default=None)):
    authorize(authorization)
    return runtime().security_sensors.list_backup_baselines()


@router.post("/security/sensors/backups")
def security_sensors_backup_create(
    req: BackupBaselineCreateRequest,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    rt = runtime()
    return rt.security_sensors.capture_backup_baseline(
        req.name,
        rt.workspace.resolve(req.path),
    )


@router.get("/security/sensors/backups/{name}/check")
def security_sensors_backup_check(
    name: str,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return runtime().security_sensors.check_backup_baseline(name)


@router.post("/security/sensors/network/isolate")
def security_sensors_network_isolate(
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return runtime().security_sensors.isolate_network(False)


@router.post("/security/sensors/network/restore")
def security_sensors_network_restore(
    authorization: str | None = Header(default=None),
):
    authorize(authorization)
    return runtime().security_sensors.restore_network()
