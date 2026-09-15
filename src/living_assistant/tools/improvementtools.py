from __future__ import annotations
from .base import Tool
from ..improvements import ImprovementEngine
from ..evaluation import EvaluationEngine


def build_improvement_tools(engine: ImprovementEngine, evaluations: EvaluationEngine | None = None) -> list[Tool]:
    def propose_improvement(target_path: str, new_content: str, title: str, rationale: str, tests: list[str] | None = None):
        return engine.propose(target_path, new_content, title, rationale, tests)

    tools = [
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
            'Apply an unchanged, approved proposal directly. Prefer evaluated promotion when an evaluation suite is available. Security-critical core files are blocked from auto-apply.',
            {'type':'object','properties':{'proposal_id':{'type':'string'}},'required':['proposal_id']},
            engine.apply,
        ),
        Tool(
            'rollback_improvement',
            'Restore the backup created by a directly applied proposal. Requires approval.',
            {'type':'object','properties':{'proposal_id':{'type':'string'}},'required':['proposal_id']},
            engine.rollback,
        ),
    ]
    if evaluations is not None:
        tools.extend([
            Tool(
                'evaluate_improvement',
                'Run an improvement candidate against approved tests/static checks/benchmarks in isolated Git worktrees or project copies. Does not promote it to the active source tree.',
                {'type':'object','properties':{
                    'proposal_id':{'type':'string'}, 'suite_name':{'type':'string'}, 'project_path':{'type':'string'},
                    'test_commands':{'type':'array','items':{'type':'string'}},
                    'lint_commands':{'type':'array','items':{'type':'string'}},
                    'benchmark_commands':{'type':'array','items':{'type':'string'}},
                    'repetitions':{'type':'integer'},
                },'required':['proposal_id']},
                evaluations.evaluate,
            ),
            Tool(
                'list_improvement_evaluations',
                'List stored evaluated self-improvement runs and verdicts.',
                {'type':'object','properties':{'status':{'type':'string'}}},
                evaluations.store.list,
            ),
            Tool(
                'get_improvement_evaluation',
                'Get the full report for one evaluated improvement.',
                {'type':'object','properties':{'evaluation_id':{'type':'string'}},'required':['evaluation_id']},
                evaluations.store.get,
            ),
            Tool(
                'promote_evaluated_improvement',
                'Promote only a completed passing evaluated candidate. Requires explicit approval and refuses stale/dirty repositories and protected security core.',
                {'type':'object','properties':{'evaluation_id':{'type':'string'}},'required':['evaluation_id']},
                evaluations.promote,
            ),
        ])
    return tools
