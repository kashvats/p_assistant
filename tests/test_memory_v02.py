import datetime as dt
from living_assistant.memory import MemoryStore

def test_due_todo_and_events(tmp_path):
    m = MemoryStore(tmp_path / "memory.sqlite3")
    past = (dt.datetime.now() - dt.timedelta(minutes=1)).isoformat(timespec="seconds")
    todo_id = m.add_todo("check service", past)
    due = m.due_todos()
    assert due and due[0]["id"] == todo_id
    m.mark_todo_notified(todo_id)
    assert m.due_todos() == []
    event_id = m.add_event("test", {"x": 1})
    events = m.list_events()
    assert events[0]["id"] == event_id and events[0]["payload"]["x"] == 1
