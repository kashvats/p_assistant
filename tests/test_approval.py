from living_assistant.approval import ApprovalStore

def test_one_time_approval(tmp_path):
    store = ApprovalStore(tmp_path / "a.sqlite3")
    item = store.create("npm run dev", "Starting a project", "EXECUTE")
    assert item["status"] == "pending"
    assert store.resolve(item["id"], True)["ok"]
    assert store.consume_preapproval("npm run dev", "Starting a project", "EXECUTE") == item["id"]
    assert store.consume_preapproval("npm run dev", "Starting a project", "EXECUTE") is None
