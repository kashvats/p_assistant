from __future__ import annotations
from .base import Tool
from ..browser import BrowserController


def build_browser_tools(controller: BrowserController, enabled: bool = True) -> list[Tool]:
    if not enabled:
        return []
    return [
        Tool('browser_snapshot', 'Open a page in an isolated browser context and return rendered body text. Downloads are disabled. Optionally save a screenshot.',
             {'type':'object','properties':{'url':{'type':'string'},'screenshot':{'type':'string'}},'required':['url']}, controller.snapshot),
        Tool('browser_interact', 'Perform one approved click or fill operation in a fresh isolated browser session. Requires explicit approval.',
             {'type':'object','properties':{'url':{'type':'string'},'action':{'type':'string','enum':['click','fill']},'selector':{'type':'string'},'value':{'type':'string'}},'required':['url','action','selector']}, controller.interact),
    ]
