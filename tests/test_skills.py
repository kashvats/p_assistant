from living_assistant.skills import SkillRegistry

def test_skill_matching(tmp_path):
    reg = SkillRegistry(tmp_path / "skills.json")
    reg.add("retail-debug", "debug flow", ["retaileye", "camera backend"], "inspect logs first")
    hits = reg.match("Please debug my RetailEye backend")
    assert hits and hits[0]["name"] == "retail-debug"
