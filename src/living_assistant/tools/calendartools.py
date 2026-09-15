from __future__ import annotations
from .base import Tool


def build_calendar_tools(calendar) -> list[Tool]:
    def calendar_add(title: str, start_at: str, end_at: str | None = None,
                     location: str | None = None, notes: str | None = None):
        return {'ok': True, 'event': calendar.add(title, start_at, end_at, location, notes)}

    def calendar_list(start: str | None = None, end: str | None = None, limit: int = 50):
        return {'ok': True, 'events': calendar.list(start, end, limit=limit)}

    def calendar_upcoming(hours: int = 24, limit: int = 50):
        return {'ok': True, 'events': calendar.upcoming(hours=hours, limit=limit)}

    def calendar_cancel(event_id: str):
        return {'ok': calendar.cancel(event_id)}

    return [
        Tool('calendar_add', 'Add an event to the local personal calendar.',
             {'type':'object','properties':{
                 'title':{'type':'string'},'start_at':{'type':'string'},'end_at':{'type':'string'},
                 'location':{'type':'string'},'notes':{'type':'string'}},'required':['title','start_at']}, calendar_add),
        Tool('calendar_list', 'List local calendar events in an optional ISO date/time range.',
             {'type':'object','properties':{'start':{'type':'string'},'end':{'type':'string'},'limit':{'type':'integer','default':50}}}, calendar_list),
        Tool('calendar_upcoming', 'List upcoming local calendar events.',
             {'type':'object','properties':{'hours':{'type':'integer','default':24},'limit':{'type':'integer','default':50}}}, calendar_upcoming),
        Tool('calendar_cancel', 'Cancel a local calendar event.',
             {'type':'object','properties':{'event_id':{'type':'string'}},'required':['event_id']}, calendar_cancel),
    ]
