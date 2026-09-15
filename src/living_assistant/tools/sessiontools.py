from __future__ import annotations
from .base import Tool


def build_session_tools(sessions) -> list[Tool]:
    def session_search(query: str, limit: int = 20):
        return {'ok': True, 'matches': sessions.search(query, limit)}
    def session_list(limit: int = 20):
        return {'ok': True, 'sessions': sessions.list(limit)}
    return [
        Tool('session_search', 'Search local conversation/session history when the user asks to recall prior work.',
             {'type':'object','properties':{'query':{'type':'string'},'limit':{'type':'integer','default':20}},'required':['query']}, session_search),
        Tool('session_list', 'List recent local assistant sessions.',
             {'type':'object','properties':{'limit':{'type':'integer','default':20}}}, session_list),
    ]
