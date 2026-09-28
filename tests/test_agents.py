from living_assistant.agents import HANDOFF_RE

def test_handoff_protocol():
    m = HANDOFF_RE.search("answer\nHANDOFF::security::check the port exposure")
    assert m and m.group(1) == "security"

    roles = ["general", "coder", "researcher", "security", "database", "planner", "contractor"]
    for role in roles:
        match = HANDOFF_RE.search(f"prefix\nHANDOFF::{role}::do something useful")
        assert match is not None
        assert match.group(1) == role
        assert match.group(2) == "do something useful"
