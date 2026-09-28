import pytest
import os
from pathlib import Path

from living_assistant.core.workspace import Workspace, WorkspaceViolation


# ==========================================
# SECTION 17: FILESYSTEM DEEP EDGE CASES
# ==========================================

def test_section_17_unicode_and_emoji_filenames(tmp_path):
    """Verify writing, reading, and listing files with complex Unicode and emojis."""
    ws = Workspace([tmp_path])
    filename = "report_📊_файл_日本語.txt"
    content = "Unicode content: 🚀 日本語 testing こんにちは"

    # Write
    written_path = ws.write_text(filename, content)
    assert Path(written_path).exists()

    # Read
    read_back = ws.read_text(filename)
    assert read_back == content

    # List
    items = ws.list(".")
    matching = [x for x in items if x["name"] == filename]
    assert len(matching) == 1
    assert matching[0]["is_file"] is True


def test_section_17_zero_byte_file(tmp_path):
    """Verify zero-byte files are created, listed with size 0, and read back cleanly without error."""
    ws = Workspace([tmp_path])
    filename = "empty.txt"

    ws.write_text(filename, "")
    assert ws.read_text(filename) == ""

    items = ws.list(".")
    matching = [x for x in items if x["name"] == filename]
    assert len(matching) == 1
    assert matching[0]["size"] == 0


def test_section_17_non_existent_file_raises_not_found(tmp_path):
    """Verify attempting to read a non-existent file cleanly raises FileNotFoundError."""
    ws = Workspace([tmp_path])
    with pytest.raises(FileNotFoundError):
        ws.read_text("does_not_exist_at_all.txt")


# ==========================================
# SECTION 18: PATH TRAVERSAL & ESCAPE ATTEMPTS
# ==========================================

def test_section_18_dot_dot_traversal_blocked(tmp_path):
    """Verify relative traversal sequences (../, ../../) escaping the root are blocked."""
    ws = Workspace([tmp_path / "sandbox"])
    
    with pytest.raises(WorkspaceViolation):
        ws.resolve("../outside.txt")

    with pytest.raises(WorkspaceViolation):
        ws.resolve("../../Windows/System32")


def test_section_18_absolute_path_escape_blocked(tmp_path):
    """Verify absolute paths outside authorized roots are strictly blocked."""
    ws = Workspace([tmp_path / "sandbox"])
    outside = tmp_path / "secret"
    outside.mkdir()

    with pytest.raises(WorkspaceViolation):
        ws.resolve(str(outside / "passwords.txt"))


def test_section_18_symlink_pointing_outside_workspace_blocked(tmp_path):
    """Verify that a symlink inside the workspace pointing to an external directory is rejected upon resolution."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    outside_file = outside / "secret.txt"
    outside_file.write_text("classified", encoding="utf-8")

    symlink_file = sandbox / "link_to_outside.txt"
    try:
        symlink_file.symlink_to(outside_file)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation not supported or requires elevation on this platform")

    ws = Workspace([sandbox])
    with pytest.raises(WorkspaceViolation):
        ws.resolve("link_to_outside.txt")


# ==========================================
# SECTION 19: TOCTOU SYMLINK RACE CONDITIONS
# ==========================================

def test_section_19_atomic_replace_replaces_symlink_itself(tmp_path):
    """Verify that writing to a symlink replaces the link itself rather than corrupting the underlying target."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    target = sandbox / "original_target.txt"
    target.write_text("target_initial_content", encoding="utf-8")

    link = sandbox / "link.txt"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation not supported on this platform")

    ws = Workspace([sandbox])
    # Write to link.txt using atomic replace
    ws.write_text("link.txt", "new_link_content")

    # The link should have been atomically replaced with a regular file
    assert not link.is_symlink()
    assert link.read_text(encoding="utf-8") == "new_link_content"
    # The original target file remains pristine and untouched
    assert target.read_text(encoding="utf-8") == "target_initial_content"


# ==========================================
# SECTION 20: FILE WRITE ATOMICITY
# ==========================================

def test_section_20_atomic_write_preserves_original_on_failure(tmp_path, monkeypatch):
    """Verify that if an exception occurs mid-write, the original file is preserved untouched without corruption."""
    ws = Workspace([tmp_path])
    filename = "important_data.json"
    original_content = '{"state": "stable"}'
    ws.write_text(filename, original_content)

    # Simulate an error occurring during file writing before replace
    def failing_write(*args, **kwargs):
        raise IOError("Disk write simulation failure")

    monkeypatch.setattr(os, "replace", failing_write)

    with pytest.raises(IOError):
        ws.write_text(filename, '{"state": "corrupted"}')

    # Original file is intact
    assert ws.read_text(filename) == original_content
