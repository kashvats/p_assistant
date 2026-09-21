

def test_memory_search_rebuilds_fts_for_existing_database(tmp_path):
    import sqlite3
    from living_assistant.memory import MemoryStore

    path = tmp_path / 'legacy-memory.sqlite3'
    conn = sqlite3.connect(path)
    conn.executescript('''
      CREATE TABLE memories(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kind TEXT NOT NULL,
        content TEXT NOT NULL,
        metadata TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL
      );
      CREATE TABLE todos(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        due_at TEXT,
        done INTEGER NOT NULL DEFAULT 0,
        notified INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
      );
      CREATE TABLE events(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kind TEXT NOT NULL,
        payload TEXT NOT NULL,
        created_at TEXT NOT NULL
      );
      INSERT INTO memories(kind,content,metadata,created_at)
      VALUES('fact','legacy searchable memory','{}','2026-01-01T00:00:00');
    ''')
    conn.commit(); conn.close()

    store = MemoryStore(path)
    rows = store.search('legacy searchable memory')
    assert rows and rows[0]['content'] == 'legacy searchable memory'
    assert store.conn.execute("SELECT 1 FROM living_assistant_migrations WHERE name='memories_fts_v1'").fetchone()
