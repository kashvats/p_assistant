from __future__ import annotations
from .base import Tool
from living_assistant.desktop.browser import BrowserController

def build_browser_tools(controller: BrowserController, enabled: bool = True, external=None) -> list[Tool]:
    if not enabled:
        return []
    tools = [
        Tool('browser_snapshot','Open a page in a fresh isolated browser and return rendered body text. Downloads are disabled. Optionally save a screenshot.',
             {'type':'object','properties':{'url':{'type':'string'},'screenshot':{'type':'string'}},'required':['url']},controller.snapshot),
        Tool('browser_interact','Perform one approved click/fill in a fresh isolated browser. Requires explicit approval.',
             {'type':'object','properties':{'url':{'type':'string'},'action':{'type':'string','enum':['click','fill']},'selector':{'type':'string'},'value':{'type':'string'}},'required':['url','action','selector']},controller.interact),
        Tool('browser_session_start','Start a named isolated live browser session. Persistent profiles require approval and never reuse the user normal browser profile.',
             {'type':'object','properties':{'name':{'type':'string'},'url':{'type':'string'},'persistent':{'type':'boolean','default':False},'allowed_hosts':{'type':'array','items':{'type':'string'}}},'required':['name','url']},controller.start_session),
        Tool('browser_session_list','List live isolated browser sessions.',{'type':'object','properties':{}},controller.list_sessions),
        Tool('browser_session_snapshot','Read the current rendered page in a named isolated session.',
             {'type':'object','properties':{'name':{'type':'string'},'screenshot':{'type':'string'}},'required':['name']},controller.snapshot_session),
        Tool('browser_session_navigate','Navigate a named isolated session within its allowed host scope.',
             {'type':'object','properties':{'name':{'type':'string'},'url':{'type':'string'}},'required':['name','url']},controller.navigate_session),
        Tool('browser_session_interact','Perform one approved click/fill in a named isolated session.',
             {'type':'object','properties':{'name':{'type':'string'},'action':{'type':'string','enum':['click','fill']},'selector':{'type':'string'},'value':{'type':'string'}},'required':['name','action','selector']},controller.interact_session),
        Tool('browser_session_close','Close a named isolated browser session.',
             {'type':'object','properties':{'name':{'type':'string'},'delete_profile':{'type':'boolean','default':False}},'required':['name']},controller.close_session),
    ]
    if external is not None and external.available():
        tools.append(
            Tool(
                "browser_use_task",
                "Run a multi-step browser task through the pinned Browser Use engine.",
                {
                    "type": "object",
                    "properties": {
                        "task": {"type": "string"},
                        "timeout_seconds": {"type": "number", "default": 120},
                    },
                    "required": ["task"],
                },
                external.run,
            )
        )
    return tools
