from __future__ import annotations
from .base import Tool


def build_briefing_tools(briefings) -> list[Tool]:
    def daily_briefing(kind: str = 'morning'):
        if kind not in {'morning','evening'}: return {'ok': False, 'error': 'kind must be morning or evening'}
        return {'ok': True, **briefings.build(kind)}
    return [Tool('daily_briefing', 'Build a deterministic local morning or evening briefing from calendar, todos, projects and approvals.',
                 {'type':'object','properties':{'kind':{'type':'string','enum':['morning','evening'],'default':'morning'}}}, daily_briefing)]
