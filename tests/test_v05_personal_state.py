import datetime as dt
from living_assistant.personal_state import PersonalState


def test_quiet_hours_wrap_midnight(tmp_path):
    s=PersonalState(tmp_path/'state.json')
    s.set_quiet_hours('22:00','07:00',True)
    assert s.is_quiet(dt.datetime(2026,1,1,23,0))
    assert s.is_quiet(dt.datetime(2026,1,2,6,30))
    assert not s.is_quiet(dt.datetime(2026,1,2,12,0))


def test_focus_expires(tmp_path):
    s=PersonalState(tmp_path/'state.json')
    now=dt.datetime(2026,1,1,10,0)
    s.start_focus(30,'deep work',now=now)
    assert s.is_quiet(now+dt.timedelta(minutes=10))
    status=s.status(now+dt.timedelta(minutes=31))
    assert status['focus']['enabled'] is False
