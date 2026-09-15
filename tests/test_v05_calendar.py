from living_assistant.calendar_store import CalendarStore


def test_calendar_add_range_cancel_and_export(tmp_path):
    c=CalendarStore(tmp_path/'cal.sqlite3')
    e=c.add('Meeting','2026-09-15T10:00:00','2026-09-15T11:00:00','Office','Discuss release')
    rows=c.list('2026-09-15T00:00:00','2026-09-16T00:00:00')
    assert rows and rows[0]['title']=='Meeting'
    path=c.export_ics(tmp_path/'out.ics')
    text=(tmp_path/'out.ics').read_text()
    assert 'BEGIN:VEVENT' in text and 'SUMMARY:Meeting' in text and path.endswith('out.ics')
    assert c.cancel(e['id']) is True
    assert c.list('2026-09-15T00:00:00','2026-09-16T00:00:00') == []
