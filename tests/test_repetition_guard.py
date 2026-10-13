from living_assistant.agents.orchestrator import Orchestrator


def test_a_line_repeated_over_and_over_is_detected_and_collapsed():
    parts = ["Done.\n"] + ["I will now create a backup of the workspace.\n"] * 6 + ["I will"]
    assert Orchestrator._is_looping(parts)
    assert Orchestrator._drop_repeats("".join(parts)).count("create a backup") == 1


def test_normal_replies_and_short_repeated_lines_are_left_alone():
    assert not Orchestrator._is_looping([f"Step {i}: do thing {i}\n" for i in range(10)])
    assert not Orchestrator._is_looping(["---\n"] * 8)  # short separators repeat legitimately
