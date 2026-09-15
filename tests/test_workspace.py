from pathlib import Path
import pytest
from living_assistant.workspace import Workspace, WorkspaceViolation

def test_workspace_rejects_escape(tmp_path):
    ws = Workspace([tmp_path / "safe"])
    with pytest.raises(WorkspaceViolation):
        ws.resolve("../outside.txt")

def test_workspace_write(tmp_path):
    ws = Workspace([tmp_path / "safe"])
    p = ws.write_text("a/b.txt","hello")
    assert Path(p).read_text() == "hello"
