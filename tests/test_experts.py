from __future__ import annotations

from types import SimpleNamespace

import pytest

from living_assistant.experts.store import DEFAULT_AGENT_ID, ExpertStore, mbti_catalog
from living_assistant.experts.tools import build_expert_tools, run_member
from living_assistant.skills.library import SkillLibrary


def _store(tmp_path):
    lib = SkillLibrary(tmp_path / "skills", builtin=tmp_path / "builtin")
    return ExpertStore(tmp_path / "experts.json", skill_library=lib), lib


def test_templates_come_from_the_octop_expert_library_and_hiring_installs_their_skills(tmp_path):
    store, lib = _store(tmp_path)
    templates = {t["id"]: t for t in store.templates()}
    office = templates["office-automation"]
    assert office["name"] and "xlsx" in office["skills"] and office["quick_prompts"][0]["prompt"]
    agent = store.hire("office-automation")
    assert agent["id"].startswith("auto") or agent["name"] == office["name"]
    assert set(office["skills"]) <= {s["name"] for s in lib.list()}  # its skills are now installed
    assert agent["instructions"] and agent["skills"] == office["skills"]
    again = store.hire("office-automation", name="Office 2")
    assert again["id"] != agent["id"] and again["skills_kept"]  # skills already there: kept, not replaced
    with pytest.raises(KeyError):
        store.hire("nope")


def test_agents_and_teams_are_created_validated_and_cleaned_up(tmp_path):
    store, _ = _store(tmp_path)
    assert store.agents()[0]["id"] == DEFAULT_AGENT_ID and len(mbti_catalog()) == 16
    writer = store.save_agent({"name": "Writer", "description": "Writes drafts", "mbti": "enfp", "skills": ["docx"]})
    checker = store.save_agent({"name": "Checker", "description": "Checks facts"})
    assert writer["mbti"] == "ENFP"
    with pytest.raises(ValueError):
        store.save_agent({"name": "X", "mbti": "ABCD"})
    with pytest.raises(ValueError):
        store.save_agent({"name": "Y"}, DEFAULT_AGENT_ID)
    with pytest.raises(ValueError, match="at least two"):
        store.save_team({"name": "Solo", "members": [writer["id"]]})
    with pytest.raises(ValueError, match="Unknown"):
        store.save_team({"name": "Ghosts", "members": [writer["id"], "ghost"]})
    team = store.save_team({"name": "Content company", "members": [writer["id"], checker["id"]]})
    ctx, found = store.context_for(f"team:{team['id']}")
    assert found and "team_ask" in ctx and "Writer" in ctx and "Checker" in ctx
    ctx, found = store.context_for(writer["id"])
    assert not found and "ENFP" in ctx and "docx" in ctx and "language the user writes in" in ctx
    assert store.context_for(DEFAULT_AGENT_ID)[0] == ""  # the plain assistant adds nothing
    store.bind("s1", f"team:{team['id']}")
    assert store.bound("s1") == f"team:{team['id']}" and store.bound("other") == DEFAULT_AGENT_ID
    store.delete_agent(checker["id"])
    assert store.team(team["id"])["members"] == [writer["id"]]
    store.delete_team(team["id"])
    assert store.bound("s1") == DEFAULT_AGENT_ID  # deleted team: back to the assistant


def test_a_team_member_works_with_its_own_profile_and_reports_each_step(tmp_path):
    store, _ = _store(tmp_path)
    member = store.save_agent({"name": "Analyst", "description": "Crunches numbers", "instructions": "Show your sums."})
    seen = {}

    def run_stream(task, context, session_id=None, excluded_tools=()):
        seen.update(task=task, context=context, session=session_id, excluded=excluded_tools)
        yield {"type": "tool", "tool": "calculator", "status": "started", "args": "{}"}
        yield {"type": "tool", "tool": "calculator", "status": "completed", "ok": True}
        yield {"type": "final", "text": "The total is 42."}

    events = []
    out = run_member(store, SimpleNamespace(run_stream=run_stream), member["id"], "Add the numbers",
                     publish=lambda e, **d: events.append((e, d)), parent_session="s9")
    assert out == {"ok": True, "member": member["id"], "name": "Analyst", "steps": 1, "answer": "The total is 42."}
    assert "Show your sums." in seen["context"] and seen["session"] is None and "team_ask" in seen["excluded"]
    assert [e for e, _ in events] == ["team.member_started", "team.member_step", "team.member_step", "team.member_finished"]
    assert all(d["session_id"] == "s9" for _, d in events)  # shown in the lead's conversation
    tools = {t.name: t.handler for t in build_expert_tools(store, lambda: None, publish=lambda *a, **k: None)}
    assert tools["team_ask"](member="ghost", task="x")["ok"] is False
    made = tools["team_create"](name="Duo", members=[DEFAULT_AGENT_ID, member["id"]])
    assert made["ok"] and made["chat_with"].startswith("team:")


def test_chat_turns_use_the_conversations_agent(tmp_path, monkeypatch):
    from living_assistant.api_routes.conversations import agent_turn

    store, _ = _store(tmp_path)
    writer = store.save_agent({"name": "Writer", "instructions": "Write warmly."})
    team = store.save_team({"name": "Pair", "members": [DEFAULT_AGENT_ID, writer["id"]]})
    rt = SimpleNamespace(experts=store)
    ctx, pinned, excluded = agent_turn(rt, "s1", writer["id"])
    assert "Write warmly." in ctx and pinned == () and excluded == ("team_ask",)
    ctx, pinned, excluded = agent_turn(rt, "s1")  # remembered
    assert "Write warmly." in ctx
    ctx, pinned, excluded = agent_turn(rt, "s1", f"team:{team['id']}")
    assert "ACTIVE TEAM" in ctx and pinned == ("team_ask",) and excluded == ()
    with pytest.raises(KeyError):
        agent_turn(rt, "s1", "missing-agent")


def test_dashboard_routes(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    import living_assistant.api as api

    store, _ = _store(tmp_path)
    monkeypatch.setattr(api, "runtime", SimpleNamespace(experts=store))
    monkeypatch.setenv("ASSISTANT_API_TOKEN", "t")
    c = TestClient(api.app, headers={"Authorization": "Bearer t"})
    overview = c.get("/experts").json()
    assert overview["agents"][0]["id"] == DEFAULT_AGENT_ID and overview["templates"] and len(overview["personalities"]) == 16
    a = c.post("/experts/agents", json={"name": "Planner", "mbti": "INTJ"}).json()
    assert c.put(f"/experts/agents/{a['id']}", json={"name": "Planner 2"}).json()["name"] == "Planner 2"
    hired = c.post("/experts/hire", json={"template": "general-assistant"}).json()
    t = c.post("/experts/teams", json={"name": "Crew", "members": [a["id"], hired["id"]]}).json()
    assert c.put("/experts/conversations/s1", json={"target": f"team:{t['id']}"}).json()["target"] == f"team:{t['id']}"
    assert c.get("/experts/conversations/s1").json()["target"] == f"team:{t['id']}"
    assert c.put("/experts/conversations/s1", json={"target": "nobody"}).status_code == 404
    assert c.post("/experts/teams", json={"name": "Bad", "members": ["x"]}).status_code == 400
    assert c.delete(f"/experts/teams/{t['id']}").json()["ok"] and c.delete(f"/experts/agents/{a['id']}").json()["ok"]


def test_starter_agents_and_teams_are_made_once(tmp_path):
    store, _ = _store(tmp_path)
    made = store.ensure_starters()
    names = {a["name"] for a in store.agents()}
    assert {"Writer", "Researcher", "Coder", "Reviewer", "Planner", "Organizer"} <= names
    assert {t["name"] for t in store.teams()} == {"Software company", "Content studio", "Office team"}
    assert all(len(t["members"]) == 3 for t in store.teams())
    store.delete_team(store.teams()[0]["id"])
    assert store.ensure_starters() == [] and len(store.teams()) == 2 and made  # deleting is respected


def test_tools_that_act_on_the_conversation_receive_it_from_the_orchestrator(tmp_path):
    from living_assistant.agents.orchestrator import Orchestrator
    from living_assistant.skills.library_tools import build_skill_library_tools

    store, lib = _store(tmp_path)
    expert_tools = {t.name: t for t in build_expert_tools(store, lambda: None, publish=lambda *a, **k: None)}
    skill_tools = {t.name: t for t in build_skill_library_tools(lib)}
    assert Orchestrator._wants_session(expert_tools["team_ask"])
    assert Orchestrator._wants_session(skill_tools["skill_learn"])
    assert not Orchestrator._wants_session(skill_tools["skill_list"])
