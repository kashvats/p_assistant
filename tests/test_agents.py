from living_assistant.agents import HANDOFF_RE

def test_handoff_protocol():
    m = HANDOFF_RE.search("answer\nHANDOFF::security::check the port exposure")
    assert m and m.group(1) == "security"
