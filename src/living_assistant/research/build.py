"""The build gate: research never turns into implementation on its own.

A project enters BUILDING only when (1) it is a software project, (2) its research
reached READY_TO_BUILD (a core hypothesis VERIFIED or PROVEN by the rules in
``epistemics``), and (3) the user explicitly approves the build on an approval
card - a model calling the tool is not enough. Everything else is refused with
the reason. Non-software projects keep their knowledge and are never built.

The build is handed to the durable GoalRunner with a brief assembled from the
project's verified findings, experiments/baselines, failed approaches and open
risks; the outcome is written back as an Implementation object.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from .store import KnowledgeStore

BUILDABLE = ("READY_TO_BUILD",)


def readiness(store: KnowledgeStore, project_id: str) -> dict:
    project = store.get_project(project_id)
    if project is None:
        return {"ready": False, "reasons": [f"Unknown project {project_id}."]}
    hyps = store.find(project["id"], "hypothesis", limit=10_000)
    verified = [h for h in hyps if h["status"] in ("VERIFIED", "PROVEN")]
    reasons = []
    if project["kind"] != "software":
        reasons.append(f"'{project['name']}' is a {project['kind']} research project; its knowledge is preserved, nothing is built.")
    if project["status"] in ("BUILDING", "IMPLEMENTED"):
        reasons.append(f"The project is already {project['status']}.")
    elif project["status"] not in BUILDABLE:
        reasons.append(f"Research status is {project['status']}; building needs READY_TO_BUILD "
                       "(a core hypothesis VERIFIED or PROVEN by experiments, held-out prediction, sources or proof).")
    return {"ready": not reasons, "reasons": reasons, "status": project["status"], "kind": project["kind"],
            "verified": [f"{h['id']}: {h['title']}" for h in verified]}


def brief(store: KnowledgeStore, project_id: str, instructions: str = "") -> str:
    project = store.get_project(project_id)
    pid = project["id"]
    hyps = store.find(pid, "hypothesis", limit=10_000)
    lines = [f"# Build brief: {project['name']}", "", project.get("description") or "", ""]
    if instructions:
        lines += ["## User instructions", instructions, ""]
    lines += ["## Verified / proven findings (build on these)"]
    for h in hyps:
        if h["status"] in ("VERIFIED", "PROVEN"):
            lines.append(f"- {h['id']} [{h['level']}] {h['title']} - {h['data'].get('assessment', '')}")
            for l in store.links_from(h["id"], "tested_by"):
                v = store.get(l["dst"])
                if v and v["data"].get("passed"):
                    lines.append(f"  - {v['id']} {v['data'].get('method')}: {v['data'].get('stats')}")
    lines += ["", "## Experiments and baselines (the implementation must match or beat these)"]
    for x in store.find(pid, "experiment", limit=200):
        d = x["data"]
        lines.append(f"- {x['id']} {x['title']} variant={d.get('variant')} dataset={d.get('dataset_label')} "
                     f"reproducible={d.get('reproducible')} metrics={ {k: round(v['mean'], 4) for k, v in (d.get('metrics') or {}).items()} }")
        lines.append(f"  command: {d.get('command')}  code: {d.get('code_version')}")
    lines += ["", "## Failed approaches (do not repeat)"]
    lines += [f"- {h['id']} {h['title']} - {h['data'].get('assessment', '')}" for h in hyps if h["status"] == "CONTRADICTED"] or ["- none recorded"]
    lines += ["", "## Unverified ideas (treat as risks, not facts)"]
    lines += [f"- {h['id']} [{h['status']}] {h['title']}" for h in hyps if h["status"] not in ("VERIFIED", "PROVEN", "CONTRADICTED")][:20] or ["- none"]
    lines += ["", "## Open questions"]
    lines += [f"- {q['title']}" for q in store.find(pid, "question", status="OPEN", limit=20)] or ["- none"]
    lines += ["", "## Definition of done",
              "- Implement the verified approach; add tests; benchmark against the recorded baselines on the same datasets.",
              "- Report benchmark results as JSON on the last output line so they can be stored as experiments."]
    return "\n".join(lines)


class BuildGate:
    def __init__(self, store: KnowledgeStore, approval, start_goal: Callable[..., dict], goal_status: Callable[[str], dict | None],
                 project_folder: Callable[[dict], Path]):
        self.store = store
        self.approval = approval
        self.start_goal = start_goal
        self.goal_status = goal_status
        self.project_folder = project_folder

    def request(self, project_ref: str, instructions: str = "", check_command: str = "", cwd: str = "") -> dict:
        project = self.store.get_project(project_ref)
        if project is None:
            return {"ok": False, "error": f"Unknown project {project_ref}."}
        state = readiness(self.store, project["id"])
        if not state["ready"]:
            return {"ok": False, "built": False, **state}
        if self.approval is None:
            return {"ok": False, "error": "Building needs an approval manager to confirm the user's request."}
        req = self.approval.request(
            f"Build software for research project '{project['name']}'",
            "Starts implementing code from the project's verified research. Approve only if you asked for this build.",
            "BUILD_PROJECT")
        if not req.get("allowed"):
            return {"ok": False, "approval_required": True, **req,
                    "message": "Building starts only after you approve it. Approve the request, then ask again."}
        folder = self.project_folder(project)
        folder.mkdir(parents=True, exist_ok=True)
        text = brief(self.store, project["id"], instructions)
        brief_path = folder / "BUILD_BRIEF.md"
        brief_path.write_text(text, encoding="utf-8")
        goal = (f"Implement the software for research project '{project['name']}'. Read the build brief at {brief_path} "
                "first: build only on its VERIFIED findings, avoid its failed approaches, and benchmark against its baselines.")
        started = self.start_goal(goal=goal, check_command=check_command, cwd=cwd or str(folder))
        if not started.get("ok"):
            return {"ok": False, "error": started.get("error") or "Could not start the build goal.", "brief": str(brief_path)}
        impl = self.store.add(project["id"], "implementation", f"Build of {project['name']}", kind=started["id"], status="BUILDING",
                              data={"goal_id": started["id"], "brief": str(brief_path), "instructions": instructions,
                                    "check_command": check_command, "based_on": state["verified"]})
        self.store.update_project(project["id"], "build approved by user", status="BUILDING", build_requested=True)
        return {"ok": True, "status": "BUILDING", "implementation": impl["id"], "goal_id": started["id"], "brief": str(brief_path)}

    def sync(self, project_ref: str) -> dict:
        """Mirror the build goal's outcome into the project (BUILDING -> IMPLEMENTED, or back to READY_TO_BUILD)."""
        project = self.store.get_project(project_ref)
        if project is None:
            return {"ok": False, "error": f"Unknown project {project_ref}."}
        out = []
        for impl in self.store.find(project["id"], "implementation", status="BUILDING"):
            goal = self.goal_status(impl["data"]["goal_id"]) or {}
            status = goal.get("status")
            if status == "completed":
                self.store.update(impl["id"], "build goal completed", status="IMPLEMENTED",
                                  data={**impl["data"], "result": goal.get("last_check"), "rounds": goal.get("rounds")})
                self.store.update_project(project["id"], "build goal completed", status="IMPLEMENTED")
            elif status in ("blocked", "cancelled", "failed"):
                self.store.update(impl["id"], f"build goal {status}", status=status.upper(),
                                  data={**impl["data"], "error": goal.get("last_error"), "rounds": goal.get("rounds")})
                self.store.update_project(project["id"], f"build goal {status}", status="READY_TO_BUILD")
            out.append({"implementation": impl["id"], "goal": impl["data"]["goal_id"], "goal_status": status})
        return {"ok": True, "project_status": self.store.get_project(project["id"])["status"], "builds": out}
