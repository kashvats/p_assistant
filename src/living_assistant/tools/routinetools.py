from __future__ import annotations
from .base import Tool

def build_routine_tools(routines) -> list[Tool]:
    def add_event_notify(name: str, event_kind: str, message: str):
        return routines.add(name, {'type':'event','kind':event_kind}, {'type':'notify','message':message})
    def add_interval_notify(name: str, seconds: int, message: str):
        return routines.add(name, {'type':'interval','seconds':seconds}, {'type':'notify','message':message})
    return [
        Tool(
            'routine_add_event_notification',
            'Create a deterministic notification routine triggered by a local assistant event.',
            {'type':'object','properties':{'name':{'type':'string'},'event_kind':{'type':'string'},'message':{'type':'string'}},'required':['name','event_kind','message']},
            add_event_notify,
        ),
        Tool(
            'routine_add_interval_notification',
            'Create a deterministic periodic notification routine. Minimum interval is 30 seconds.',
            {'type':'object','properties':{'name':{'type':'string'},'seconds':{'type':'integer'},'message':{'type':'string'}},'required':['name','seconds','message']},
            add_interval_notify,
        ),
        Tool('routine_list', 'List configured deterministic routines.', {'type':'object','properties':{}}, routines.list),
    ]
