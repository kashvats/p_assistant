import pytest
from living_assistant.tools.careertools import build_career_tools
from living_assistant.career.profile import CareerProfileStore
from living_assistant.career.tracker import ApplicationTracker

def test_career_tools_manifest(tmp_path):
    store = CareerProfileStore(storage_dir=tmp_path)
    tracker = ApplicationTracker(db_path=tmp_path / "apps.db")
    tools = build_career_tools(profile_store=store, tracker=tracker)
    
    names = [t.name for t in tools]
    assert "career_profile_get" in names
    assert "career_profile_update" in names
    assert "career_job_analyze" in names
    assert "career_apply" in names
    assert "career_applications_list" in names
    assert "career_outreach_generate" in names

def test_career_tools_execution(tmp_path):
    store = CareerProfileStore(storage_dir=tmp_path)
    tracker = ApplicationTracker(db_path=tmp_path / "apps.db")
    tools = {t.name: t for t in build_career_tools(profile_store=store, tracker=tracker)}
    
    # 1. Update profile tool
    res = tools["career_profile_update"].handler({"full_name": "Dev Person", "skills": ["Python", "Docker"]})
    assert res["ok"] is True
    assert res["profile"]["full_name"] == "Dev Person"
    
    # 2. Get profile tool
    get_res = tools["career_profile_get"].handler()
    assert get_res["ok"] is True
    assert get_res["profile"]["full_name"] == "Dev Person"
    assert "Python" in get_res["profile"]["skills"]
    
    # 3. List applications tool
    list_res = tools["career_applications_list"].handler()
    assert list_res["ok"] is True
    assert list_res["applications"] == []
