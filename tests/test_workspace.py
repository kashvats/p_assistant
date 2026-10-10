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

def test_workspace_resolves_root_name_prefixes(tmp_path):
    ws_dir = tmp_path / "workspace"
    ws_dir.mkdir()
    books = ws_dir / "books"
    books.mkdir()
    sample_pdf = books / "guide.pdf"
    sample_pdf.write_bytes(b"%PDF-1.4 sample")
    root_pdf = ws_dir / "root.pdf"
    root_pdf.write_bytes(b"%PDF-1.4 root")

    ws = Workspace([ws_dir])

    # Root name prefixes
    assert ws.resolve("workspace") == ws_dir
    assert ws.resolve("/workspace") == ws_dir
    assert ws.resolve("./workspace") == ws_dir
    assert ws.resolve("workspace/books") == books
    assert ws.resolve("/workspace/books") == books
    assert ws.resolve("./workspace/books") == books
    assert ws.resolve("workspace/books/guide.pdf") == sample_pdf
    assert ws.resolve("/workspace/books/guide.pdf") == sample_pdf
    assert ws.resolve("workspace/root.pdf") == root_pdf

    # Relative paths without root name prefix
    assert ws.resolve(".") == ws_dir
    assert ws.resolve("books") == books
    assert ws.resolve("books/guide.pdf") == sample_pdf
    assert ws.resolve("root.pdf") == root_pdf

    # Path traversal with root name still blocked
    with pytest.raises(WorkspaceViolation):
        ws.resolve("workspace/../outside.txt")
    with pytest.raises(WorkspaceViolation):
        ws.resolve("/outside.txt")


def test_workspace_edit_and_delete(tmp_path):
    ws_dir = tmp_path / "workspace"
    ws_dir.mkdir()
    ws = Workspace([ws_dir])

    # Add/write
    f = ws.write_text("notes.txt", "line 1\nold line\nline 3")
    assert Path(f).read_text(encoding="utf-8") == "line 1\nold line\nline 3"

    # Edit
    ws.edit_text("notes.txt", "old line", "new line")
    assert Path(f).read_text(encoding="utf-8") == "line 1\nnew line\nline 3"

    # Edit missing target raises ValueError
    with pytest.raises(ValueError):
        ws.edit_text("notes.txt", "nonexistent line", "replacement")

    # Delete file
    assert ws.delete("notes.txt") is True
    assert not Path(f).exists()

    # Create subfolder and delete recursively
    sub = ws.write_text("sub/nested.txt", "nested content")
    assert Path(sub).exists()
    assert ws.delete("sub", recursive=True) is True
    assert not (ws_dir / "sub").exists()

    # Deleting root is rejected
    with pytest.raises(WorkspaceViolation):
        ws.delete(".")
