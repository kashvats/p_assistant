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


def test_watcher_batches_large_change_bursts(tmp_path):
    watched = tmp_path / 'burst'; watched.mkdir()
    reg = WatchRegistry(tmp_path / 'watches-burst.json')
    reg.add('build', str(watched))
    assert reg.poll(max_events_per_watch=25) == []

    for i in range(100):
        (watched / f'generated-{i}.txt').write_text(str(i))

    events = reg.poll(max_events_per_watch=25)
    assert len(events) == 1
    event = events[0]
    assert event['kind'] == 'file_changes_batched'
    assert event['total_changes'] == 100
    assert event['counts']['file_added'] == 100
    assert len(event['paths']['file_added']) == 100
