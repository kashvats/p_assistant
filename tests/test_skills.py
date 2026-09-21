from living_assistant.skills import SkillRegistry

def test_skill_matching(tmp_path):
    reg = SkillRegistry(tmp_path / "skills.json")
    reg.add("retail-debug", "debug flow", ["retaileye", "camera backend"], "inspect logs first")
    hits = reg.match("Please debug my RetailEye backend")
    assert hits and hits[0]["name"] == "retail-debug"


def test_fresh_skill_registry_is_seeded_with_builtin_defaults(tmp_path):
    reg = SkillRegistry(tmp_path / 'skills.json')
    skills = reg.list()
    assert {'debug-systematically','code-change-discipline','research-with-evidence'} <= set(skills)
    hit = reg.match('Please debug this failing test and traceback')
    assert hit and hit[0]['name'] == 'debug-systematically'
    assert hit[0]['source'] == 'builtin'


def test_existing_empty_skill_registry_is_respected(tmp_path):
    path=tmp_path/'skills.json'
    path.write_text('{}', encoding='utf-8')
    reg=SkillRegistry(path)
    assert reg.list() == {}


def test_default_skills_resource_is_packaged_source_data():
    from importlib import resources
    import json
    data=json.loads(resources.files('living_assistant').joinpath('default_skills.json').read_text(encoding='utf-8'))
    assert 'debug-systematically' in data
