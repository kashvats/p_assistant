from __future__ import annotations

from pathlib import Path
import pytest

from living_assistant.core.memory import MemoryStore


def test_section_34_memory_metadata_and_confidence(tmp_path: Path):
    """Section 34: Memories must store confidence, source, timestamp, and kind."""
    db_file = tmp_path / "test_memory.sqlite3"
    store = MemoryStore(db_file)

    mem_id = store.remember(
        "User prefers Python 3.12 over Python 3.11",
        kind="preference",
        metadata={"confidence": 0.95, "source": "user_explicit"},
    )

    mem = store.get_memory(mem_id)
    assert mem is not None
    assert mem["kind"] == "preference"
    assert "User prefers Python 3.12" in mem["content"]
    assert "created_at" in mem

    meta = mem["metadata"]
    assert meta["confidence"] == 0.95
    assert meta["source"] == "user_explicit"


def test_section_35_memory_contradiction_resolution(tmp_path: Path):
    """Section 35: Latest preference overrides older contradictory preference."""
    db_file = tmp_path / "test_memory.sqlite3"
    store = MemoryStore(db_file)

    # 1. Old preference: dark mode
    id1 = store.remember(
        "UI theme is set to dark mode",
        kind="preference",
        key="preference:theme",
    )

    results1 = store.search("theme")
    assert len(results1) == 1
    assert "dark mode" in results1[0]["content"]

    # 2. User explicitly updates to light mode
    id2 = store.remember(
        "UI theme is set to light mode",
        kind="preference",
        key="preference:theme",
    )

    # Must update existing key record (or same ID), resolving contradiction
    assert id2 == id1

    results2 = store.search("theme")
    assert len(results2) == 1
    assert "light mode" in results2[0]["content"]
    assert "dark mode" not in results2[0]["content"]


def test_section_36_memory_deletion_and_fts_cleanup(tmp_path: Path):
    """Section 36: Deleting a memory cleans it permanently from table and FTS index."""
    db_file = tmp_path / "test_memory.sqlite3"
    store = MemoryStore(db_file)

    mem_id = store.remember("Secret project code name is Project Chimera", kind="secret")

    # Search finds it before deletion
    found_before = store.search("Chimera")
    assert len(found_before) == 1
    assert found_before[0]["id"] == mem_id

    # Delete memory
    deleted = store.delete_memory(mem_id)
    assert deleted is True

    # Record no longer exists in primary table
    assert store.get_memory(mem_id) is None

    # FTS search must NOT return the deleted memory
    found_after = store.search("Chimera")
    assert len(found_after) == 0

    # Test clear_memories by kind
    store.remember("Note A", kind="scratch")
    store.remember("Note B", kind="scratch")
    store.remember("Permanent Fact", kind="fact")

    cleared = store.clear_memories(kind="scratch")
    assert cleared == 2
    assert len(store.search("Note")) == 0
    assert len(store.search("Permanent Fact")) == 1


def test_section_37_memory_deduplication(tmp_path: Path):
    """Section 37: Repeated identical statements are deduplicated instead of duplicating."""
    db_file = tmp_path / "test_memory.sqlite3"
    store = MemoryStore(db_file)

    statement = "The user prefers dark mode for all code editors."

    # Insert identical memory 10 times in conversation turns
    first_id = None
    for _ in range(10):
        current_id = store.remember(statement, kind="preference")
        if first_id is None:
            first_id = current_id
        else:
            # Deduplication should return the same existing record id
            assert current_id == first_id

    # Primary table should have exactly 1 record, not 10
    total_rows = store.conn.execute("SELECT count(*) as count FROM memories").fetchone()["count"]
    assert total_rows == 1

    # FTS search should return exactly 1 hit
    results = store.search("dark mode")
    assert len(results) == 1
