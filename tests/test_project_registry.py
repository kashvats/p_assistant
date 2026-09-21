import json
from living_assistant.tools.projects import ProjectRegistry

def test_v01_project_registry_migrates(tmp_path):
    p = tmp_path / "projects.json"
    p.write_text(json.dumps({"old": str(tmp_path)}))
    reg = ProjectRegistry(p)
    item = reg.get("old")
    assert item["path"] == str(tmp_path.resolve())
    assert item["auto_restart"] is False
    assert item["max_restarts"] == 3

def test_project_add_detects_start(tmp_path):
    project = tmp_path / "app"; project.mkdir()
    (project / "package.json").write_text('{"scripts":{"dev":"vite","test":"vitest"}}')
    reg = ProjectRegistry(tmp_path / "projects.json")
    item = reg.add("app", str(project), auto_restart=True)
    assert item["start_command"] == "npm run dev"
    assert item["test_command"] == "npm test"
    assert item["auto_restart"] is True

def test_project_environment_is_stored_and_updateable(tmp_path):
    project=tmp_path/'app'; project.mkdir()
    reg=ProjectRegistry(tmp_path/'projects.json')
    item=reg.add('app',str(project),start_command='python app.py',env={'PORT':'3000','APP_MODE':'dev'})
    assert item['env']=={'PORT':'3000','APP_MODE':'dev'}
    updated=reg.update('app',env={'PORT':'4000'})
    assert updated['env']=={'PORT':'4000'}


def test_project_environment_rejects_secret_like_values(tmp_path):
    import pytest
    project=tmp_path/'app'; project.mkdir()
    reg=ProjectRegistry(tmp_path/'projects.json')
    with pytest.raises(ValueError):
        reg.add('app',str(project),env={'API_KEY':'not-safe-to-store'})
    with pytest.raises(ValueError):
        reg.add('app',str(project),env={'NORMAL':'ghp_abcdefghijklmnopqrstuvwxyz123456'})
