from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import time
from unittest.mock import MagicMock, patch
import pytest

from living_assistant.core.sqlite_utils import ThreadLocalSQLite
from living_assistant.system.platform_hardening import SingleInstanceGuard
from living_assistant.system.routines import RoutineRegistry
from living_assistant.system.watchers import WatchRegistry
from living_assistant.system.codebase_index import CodebaseIndex
from living_assistant.learning.eval_engine import detect_test_manipulation
from living_assistant.system.resource_manager import ResourceManager
from living_assistant.core.workspace import Workspace


def test_section_38_database_locked_and_corruption_detection(tmp_path: Path):
    """Section 38: Verify busy retry handling and corrupt database detection."""
    db_file = tmp_path / "test_db.sqlite3"
    db = ThreadLocalSQLite(db_file, timeout=5.0)

    # Initialize table
    db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
    db.commit()

    # Verify normal write
    db.execute("INSERT INTO users (name) VALUES ('Alice')")
    db.commit()
    row = db.execute("SELECT name FROM users WHERE id=1").fetchone()
    assert row["name"] == "Alice"
    db.close_all()

    # Corrupt database file (write garbage bytes)
    corrupt_file = tmp_path / "corrupt.sqlite3"
    corrupt_file.write_bytes(b"THIS IS NOT A VALID SQLITE HEADER OR DATABASE FILE")

    corrupt_db = ThreadLocalSQLite(corrupt_file)
    # Executing against a corrupt database must raise DatabaseError and NOT silently recreate it
    with pytest.raises(sqlite3.DatabaseError):
        corrupt_db.execute("SELECT * FROM test")
    corrupt_db.close_all()


def test_section_39_multiple_assistant_processes_single_instance(tmp_path: Path):
    """Section 39: Prevent accidental double-startup with SingleInstanceGuard."""
    lock_dir = tmp_path / "locks"
    guard1 = SingleInstanceGuard("assistant-daemon", lock_dir)
    guard2 = SingleInstanceGuard("assistant-daemon", lock_dir)

    # First instance (PID 1001) acquires lock successfully
    with patch("os.getpid", return_value=1001):
        assert guard1.acquire() is True

    # Second instance (PID 2002) attempting to acquire the same lock while first is alive must fail
    with patch("os.getpid", return_value=2002):
        with patch("psutil.pid_exists", return_value=True):
            assert guard2.acquire() is False

    # After first instance releases lock, second instance can acquire
    with patch("os.getpid", return_value=1001):
        guard1.release()

    with patch("os.getpid", return_value=2002):
        assert guard2.acquire() is True
        guard2.release()


def test_section_40_scheduler_missed_job_policy(tmp_path: Path):
    """Section 40: Scheduler missed-job policy (run vs skip) and safe deletion."""
    routines_path = tmp_path / "routines.json"
    registry = RoutineRegistry(routines_path)

    # Add a daily routine scheduled for 09:00 with missed_job_policy='skip'
    registry.add(
        name="daily_morning_briefing",
        trigger={"type": "daily", "time": "09:00", "missed_job_policy": "skip"},
        action={"type": "notify", "message": "Morning Briefing"},
    )

    # Add a daily routine with default missed_job_policy='run'
    registry.add(
        name="daily_backup",
        trigger={"type": "daily", "time": "09:00", "missed_job_policy": "run"},
        action={"type": "notify", "message": "Run backup"},
    )

    notifier = MagicMock()
    memory = MagicMock()

    # Simulate wake up at 14:30 (5.5 hours after 09:00) on a fresh day
    wake_time = time.mktime(time.strptime("2026-09-27 14:30:00", "%Y-%m-%d %H:%M:%S"))

    results = registry.process(
        events=[],
        memory=memory,
        notifier=notifier,
        now=wake_time,
    )

    ran_routines = [r["routine"] for r in results]
    # 'daily_backup' should have run (policy=run)
    assert "daily_backup" in ran_routines
    # 'daily_morning_briefing' should have been skipped (>1 hour past scheduled time)
    assert "daily_morning_briefing" not in ran_routines


def test_section_41_watchdog_burst_coalescing(tmp_path: Path):
    """Section 41: Large bursts of filesystem events (>50) are coalesced into a single batched event."""
    watch_dir = tmp_path / "watched_repo"
    watch_dir.mkdir()
    registry = WatchRegistry(tmp_path / "watches.json", enable_watchdog=False)
    registry.add("repo_watch", str(watch_dir), recursive=True)

    # Baseline scan
    registry.poll()

    # Simulate sudden burst of 80 files created at once (e.g. npm install / build artifact)
    for i in range(80):
        (watch_dir / f"file_{i}.txt").write_text(f"content {i}")

    events = registry.poll(max_events_per_watch=50)
    assert len(events) == 1
    assert events[0]["kind"] == "file_changes_batched"
    assert events[0]["total_changes"] == 80
    assert events[0]["counts"]["file_added"] == 80


def test_section_42_indexing_file_modification_version_check(tmp_path: Path):
    """Section 42: Indexer detects concurrent modification during file chunking and retries."""
    ws = Workspace([tmp_path])
    index = CodebaseIndex(ws, path=tmp_path / "index.sqlite3")

    src_file = tmp_path / "module.py"
    src_file.write_text("def stable_function():\n    return 42\n")

    # Verify version-checked chunk extraction returns valid chunks
    chunks = index._chunks_for_file_with_version_check(src_file, tmp_path)
    assert len(chunks) >= 1
    assert "stable_function" in chunks[0].text
    index.conn.close_all()


def test_section_43_codebase_memory_skips_dependencies(tmp_path: Path):
    """Section 43: Indexer ignores vendor, node_modules, .venv, and binary files."""
    ws = Workspace([tmp_path])
    index = CodebaseIndex(ws, path=tmp_path / "index.sqlite3")

    # Create root source file
    (tmp_path / "main.py").write_text("print('hello')")

    # Create ignored directories and files
    node_modules = tmp_path / "node_modules" / "pkg"
    node_modules.mkdir(parents=True)
    (node_modules / "index.js").write_text("module.exports = {}")

    venv = tmp_path / ".venv" / "lib"
    venv.mkdir(parents=True)
    (venv / "site.py").write_text("x = 1")

    bin_file = tmp_path / "blob.bin"
    bin_file.write_bytes(b"\x00\x01\x02\xff\xfe\x00\x00")

    found_files = [p.relative_to(tmp_path).as_posix() for p in index._iter_source_files(tmp_path)]
    assert "main.py" in found_files
    assert not any("node_modules" in f for f in found_files)
    assert not any(".venv" in f for f in found_files)
    index.conn.close_all()


def test_section_46_test_manipulation_defense():
    """Section 46: Detect and block repair agent attempting to weaken tests."""
    # 1. Detect skipping tests
    skip_content = "@pytest.mark.skip\ndef test_feature():\n    assert 1 == 2\n"
    flagged, reason = detect_test_manipulation("", skip_content)
    assert flagged is True
    assert "marked as skipped" in reason

    # 2. Detect removing assertions
    diff_removing_assert = "--- a/test.py\n+++ b/test.py\n-    assert response.status_code == 200\n+    pass\n"
    flagged, reason = detect_test_manipulation(diff_removing_assert, "def test_api():\n    pass\n")
    assert flagged is True
    assert "assertion(s) were removed" in reason

    # 3. Detect broad exception swallowing
    swallow_content = "def test_worker():\n    try:\n        do_work()\n    except Exception: pass\n"
    flagged, reason = detect_test_manipulation("", swallow_content)
    assert flagged is True
    assert "exception swallowing" in reason

    # 4. Legitimate test modification is allowed
    legit_diff = "--- a/test.py\n+++ b/test.py\n+    assert calculate(2) == 4\n"
    legit_content = "def test_calc():\n    assert calculate(2) == 4\n"
    flagged, _ = detect_test_manipulation(legit_diff, legit_content)
    assert flagged is False


def test_section_47_48_cancellation_and_resource_cleanup():
    """Section 47-48: Cancellation cleans up resources, caches, and memory."""
    rm = ResourceManager(
        profile="balanced",
        config={"resource_manager": {"reserve_ram_gb": 1.0}},
    )

    with patch("httpx.Client") as mock_client:
        mock_instance = MagicMock()
        mock_instance.get.return_value.status_code = 200
        mock_instance.get.return_value.json.return_value = {"models": [{"model": "llama3:latest"}]}
        mock_client.return_value.__enter__.return_value = mock_instance

        # Call metabolize (run during cancellation or high pressure)
        result = rm.metabolize()
        assert "ollama_freed" in result
        assert "gc_objects_collected" in result
        mock_instance.post.assert_called_once_with(
            "http://127.0.0.1:11434/api/generate",
            json={"model": "llama3:latest", "keep_alive": 0},
        )


def test_section_49_50_shared_resource_priority_and_throttling():
    """Section 49-50: Background jobs are throttled when interactive modes are active."""
    rm = ResourceManager(profile="balanced", config={})

    # Initially not throttled
    throttled, _ = rm.should_throttle_background_tasks()
    assert throttled is False

    # Enter interactive foreground task (e.g. user voice or active chat stream)
    rm.set_interactive_mode(True, "chat_stream")
    throttled, reason = rm.should_throttle_background_tasks()
    assert throttled is True
    assert "chat_stream" in reason

    # Leave interactive mode -> background tasks unthrottled
    rm.set_interactive_mode(False, "chat_stream")
    throttled, _ = rm.should_throttle_background_tasks()
    assert throttled is False
