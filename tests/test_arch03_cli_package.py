from __future__ import annotations

from living_assistant.cli import app


def _command_tree(typer_app):
    return {
        "commands": sorted(
            (getattr(cmd, "name", None) or cmd.callback.__name__)
            for cmd in typer_app.registered_commands
        ),
        "groups": {
            group.name: _command_tree(group.typer_instance)
            for group in typer_app.registered_groups
        },
    }


def test_cli_package_exposes_expected_root_contract():
    tree = _command_tree(app)
    assert tree["commands"] == ["ask", "chat", "daemon", "doctor", "onboard", "serve", "tick", "tray"]
    assert {
        "agent",
        "approval",
        "briefing",
        "browser",
        "calendar",
        "desktop",
        "experience",
        "git",
        "group",
        "improve",
        "integration",
        "model",
        "personal",
        "platform",
        "project",
        "quarantine",
        "release",
        "routine",
        "security",
        "session",
        "skill",
        "todo",
        "voice",
        "watch",
    } == set(tree["groups"])
    assert "rollback" in tree["groups"]["release"]["commands"]
    assert "status" in tree["groups"]["model"]["commands"]
    assert "run" in tree["groups"]["project"]["commands"]
