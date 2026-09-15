from __future__ import annotations
from .base import Tool


def build_personal_state_tools(state) -> list[Tool]:
    def personal_status(): return state.status()
    def focus_start(minutes: int = 60, label: str | None = None): return {'ok': True, 'focus': state.start_focus(minutes, label)}
    def focus_stop(): return {'ok': True, 'focus': state.stop_focus()}
    return [
        Tool('personal_status', 'Read local quiet-hours/focus-mode status.', {'type':'object','properties':{}}, personal_status),
        Tool('focus_start', 'Start local focus mode, suppressing non-urgent notifications for a bounded time.',
             {'type':'object','properties':{'minutes':{'type':'integer','default':60},'label':{'type':'string'}}}, focus_start),
        Tool('focus_stop', 'Stop local focus mode.', {'type':'object','properties':{}}, focus_stop),
    ]
