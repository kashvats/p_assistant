import os, time
from living_assistant.watchers import WatchRegistry

def test_watcher_detects_change(tmp_path):
    watched = tmp_path / "watched"; watched.mkdir()
    f = watched / "a.py"; f.write_text("x=1")
    reg = WatchRegistry(tmp_path / "watches.json")
    reg.add("code", str(watched), extensions=["py"])
    assert reg.poll() == []  # baseline
    f.write_text("x=2")
    os.utime(f, None)
    events = reg.poll()
    assert any(e["kind"] == "file_changed" and e["path"].endswith("a.py") for e in events)
