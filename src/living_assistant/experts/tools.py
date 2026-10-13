"""Chat tools for agents and teams: hand work to a team member, and create agents/teams by asking."""
from __future__ import annotations

import functools

import time
from typing import Callable

from living_assistant.experts.store import ExpertStore
from living_assistant.security.security_utils import redact_secrets
from living_assistant.tools.base import Tool

MEMBER_EXCLUDED = ("team_ask", "agent_new", "agent_hire", "team_create")


def run_member(store: ExpertStore, orchestrator, member_id: str, task: str, *,
               publish: Callable[..., None], parent_session: str | None, team_id: str = "") -> dict:
    """Run one turn as a team member (its persona, instructions and skills), reporting each step live."""
    agent = store.agent(member_id)
    started = time.time()
    publish("team.member_started", session_id=parent_session, team=team_id, member=agent["id"], name=agent["name"],
            task=task[:300])
    answer, steps, error = "", 0, None
    try:
        for event in orchestrator.run_stream(task, store.agent_context(agent), session_id=None,
                                             excluded_tools=MEMBER_EXCLUDED):
            kind = event.get("type")
            if kind == "tool":
                if event.get("status") == "started":
                    steps += 1
                publish("team.member_step", session_id=parent_session, member=agent["id"], name=agent["name"],
                        tool=event.get("tool"), status=event.get("status"), ok=event.get("ok"),
                        args=str(event.get("args") or "")[:200], error=str(event.get("error") or "")[:200])
            elif kind == "final":
                answer = str(event.get("text") or "")
            elif kind == "error":
                error = str(event.get("error") or "the member's turn failed")
    except Exception as exc:
        error = redact_secrets(exc, 400)
    publish("team.member_finished", session_id=parent_session, member=agent["id"], name=agent["name"], ok=error is None,
            seconds=round(time.time() - started, 1))
    if error:
        return {"ok": False, "member": agent["id"], "error": error}
    return {"ok": True, "member": agent["id"], "name": agent["name"], "steps": steps, "answer": answer[:12_000]}


def build_expert_tools(store: ExpertStore, get_orchestrator: Callable, *, publish: Callable[..., None]) -> list[Tool]:
    def safe(fn):
        @functools.wraps(fn)  # keeps the signature: the orchestrator passes _session_id to tools that take it
        def wrapper(**kwargs):
            try:
                return fn(**kwargs)
            except (KeyError, ValueError) as exc:
                return {"ok": False, "error": str(exc).strip("'\"")}
            except Exception as exc:
                return {"ok": False, "error": redact_secrets(exc, 600)}
        return wrapper

    @safe
    def team_ask(member: str, task: str, _session_id: str | None = None):
        if not str(task or "").strip():
            return {"ok": False, "error": "Give the member a task with everything it needs."}
        return run_member(store, get_orchestrator(), member, task, publish=publish, parent_session=_session_id)

    @safe
    def agent_list():
        return {"ok": True, "agents": [{"id": a["id"], "name": a["name"], "description": a.get("description")} for a in store.agents()],
                "teams": [{"id": f"team:{t['id']}", "name": t["name"], "members": t["members"]} for t in store.teams()],
                "templates": [{"id": t["id"], "name": t["name"], "description": t["description"][:160]} for t in store.templates()]}

    @safe
    def agent_create(name: str, description: str = "", instructions: str = "", skills: list | None = None, mbti: str = ""):
        return {"ok": True, "agent": store.save_agent({"name": name, "description": description, "instructions": instructions,
                                                       "skills": skills or [], "mbti": mbti})}

    @safe
    def agent_hire(template: str, name: str = ""):
        return {"ok": True, "agent": store.hire(template, name)}

    @safe
    def team_create(name: str, members: list, description: str = "", lead_instructions: str = ""):
        team = store.save_team({"name": name, "members": members, "description": description,
                                "lead_instructions": lead_instructions})
        return {"ok": True, "team": team, "chat_with": f"team:{team['id']}"}

    obj, s = {"type": "object"}, {"type": "string"}
    return [
        Tool("team_ask", "Team lead only: give one team member a self-contained task and get its result back. The member "
                         "works with its own persona and skills and does not see this chat.",
             {**obj, "properties": {"member": s, "task": s}, "required": ["member", "task"]}, team_ask),
        Tool("agents_and_teams", "List the user's agents, teams (agent companies) and the agent templates that can be hired.",
             {**obj, "properties": {}}, agent_list),
        Tool("agent_new", "Create an agent: a name, what it is for, instructions, the skills it uses (skill names) and "
                             "an optional MBTI personality (e.g. INTJ).",
             {**obj, "properties": {"name": s, "description": s, "instructions": s, "skills": {"type": "array", "items": s},
                                    "mbti": s}, "required": ["name"]}, agent_create),
        Tool("agent_hire", "Create an agent from a ready-made template (ids from agents_and_teams templates); installs its skills.",
             {**obj, "properties": {"template": s, "name": s}, "required": ["template"]}, agent_hire),
        Tool("team_create", "Create a team (agent company) of at least two member agents (agent ids) with a lead that "
                            "splits work between them.",
             {**obj, "properties": {"name": s, "members": {"type": "array", "items": s}, "description": s,
                                    "lead_instructions": s}, "required": ["name", "members"]}, team_create),
    ]
