from __future__ import annotations
from .base import Tool
from ..groups import ProjectGroupController


def build_group_tools(controller: ProjectGroupController) -> list[Tool]:
    return [
        Tool('project_group_plan', 'Show the registered projects and exact commands that would start for a project group.',
             {'type':'object','properties':{'group_name':{'type':'string'}},'required':['group_name']}, controller.plan),
        Tool('project_group_start', 'Start all projects in a registered group in dependency order, using parallel stages when configured. Requires a single approval for the exact group plan.',
             {'type':'object','properties':{'group_name':{'type':'string'}},'required':['group_name']}, controller.start),
        Tool('project_group_stop', 'Stop managed processes belonging to a registered project group, normally in reverse order.',
             {'type':'object','properties':{'group_name':{'type':'string'}},'required':['group_name']}, controller.stop),
    ]
