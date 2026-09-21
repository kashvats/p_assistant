from living_assistant.approval import ApprovalStore

def test_one_time_approval(tmp_path):
    store = ApprovalStore(tmp_path / "a.sqlite3")
    item = store.create("npm run dev", "Starting a project", "EXECUTE")
    assert item["status"] == "pending"
    assert store.resolve(item["id"], True)["ok"]
    assert store.consume_preapproval("npm run dev", "Starting a project", "EXECUTE") == item["id"]
    assert store.consume_preapproval("npm run dev", "Starting a project", "EXECUTE") is None


def test_stale_pending_approval_expires_and_does_not_block_requeue(tmp_path):
    import datetime as dt

    store = ApprovalStore(tmp_path / "a.sqlite3", pending_ttl_hours=24)
    stale = store.create("deploy", "production deploy", "EXECUTE")
    old = (dt.datetime.now() - dt.timedelta(days=3)).isoformat(timespec="seconds")
    store.conn.execute("UPDATE approvals SET created_at=? WHERE id=?", (old, stale["id"]))
    store.conn.commit()

    fresh = store.create("deploy", "production deploy", "EXECUTE")
    assert fresh["id"] != stale["id"]
    assert fresh["status"] == "pending"
    expired = store.conn.execute("SELECT status FROM approvals WHERE id=?", (stale["id"],)).fetchone()
    assert expired[0] == "expired"
    assert [item["id"] for item in store.list("pending")] == [fresh["id"]]


def test_preapproval_hash_ignores_boundary_whitespace_only(tmp_path):
    store = ApprovalStore(tmp_path / "a.sqlite3")
    item = store.create("deploy /srv/app   ", " production deploy\n", " EXECUTE ")
    assert store.resolve(item["id"], True)["ok"]

    assert store.consume_preapproval("deploy /srv/app", "production deploy", "EXECUTE") == item["id"]


def test_preapproval_hash_preserves_internal_whitespace(tmp_path):
    store = ApprovalStore(tmp_path / "a.sqlite3")
    item = store.create("echo  secret", "run exact command", "EXECUTE")
    assert store.resolve(item["id"], True)["ok"]

    # Collapsing internal spaces could authorize a different command.
    assert store.consume_preapproval("echo secret", "run exact command", "EXECUTE") is None
    assert store.consume_preapproval("echo  secret", "run exact command", "EXECUTE") == item["id"]
