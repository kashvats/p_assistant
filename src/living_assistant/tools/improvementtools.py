from __future__ import annotations
from .base import Tool
from ..improvements import ImprovementEngine

def build_improvement_tools(engine: ImprovementEngine) -> list[Tool]:
    def propose_improvement(target_path: str, new_content: str, title: str, rationale: str, tests: list[str] | None = None):
        return engine.propose(target_path, new_content, title, rationale, tests)
    return [
        Tool(
            'propose_improvement',
            'Create a reviewable exact-file improvement proposal. This does not modify the target file.',
            {'type':'object','properties':{'target_path':{'type':'string'},'new_content':{'type':'string'},'title':{'type':'string'},'rationale':{'type':'string'},'tests':{'type':'array','items':{'type':'string'}}},'required':['target_path','new_content','title','rationale']},
            propose_improvement,
        ),
        Tool(
            'list_improvements',
            'List pending/recent improvement proposals.',
            {'type':'object','properties':{'status':{'type':'string'}}},
            engine.store.list,
        ),
        Tool(
            'apply_improvement',
            'Apply an unchanged, approved proposal. Security-critical core files are blocked from auto-apply.',
            {'type':'object','properties':{'proposal_id':{'type':'string'}},'required':['proposal_id']},
            engine.apply,
        ),
        Tool(
            'rollback_improvement',
            'Restore the backup created by an applied proposal. Requires approval.',
            {'type':'object','properties':{'proposal_id':{'type':'string'}},'required':['proposal_id']},
            engine.rollback,
        ),
    ]
