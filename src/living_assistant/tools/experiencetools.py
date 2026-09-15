from __future__ import annotations
from .base import Tool
from ..experience import ExperienceEngine


def build_experience_tools(engine: ExperienceEngine) -> list[Tool]:
    def search_experience(query: str, project: str | None = None, limit: int = 6):
        return engine.search(query, project, limit)

    def record_experience(kind: str, situation: str, lesson: str, project: str | None = None,
                          action_taken: str | None = None, outcome: str | None = None,
                          root_cause: str | None = None, better_action: str | None = None,
                          verified: bool = False, evidence: str | None = None):
        return engine.record(kind,situation,lesson,project,action_taken,outcome,root_cause,better_action,verified,evidence,source='agent')

    def verify_experience(experience_id: str, useful: bool, evidence: str | None = None):
        return engine.verify(experience_id,useful,evidence)

    def experience_failure_patterns(limit: int = 10, min_count: int = 2):
        return engine.failure_patterns(limit,min_count)

    return [
        Tool('search_experience','Search evidence-weighted local lessons from past tasks. Treat results as advisory and verify current state.',
             {'type':'object','properties':{'query':{'type':'string'},'project':{'type':'string'},'limit':{'type':'integer','default':6}},'required':['query']},search_experience),
        Tool('record_experience','Record a concise postmortem/procedure after an outcome is known. Use verified=true only when current tool evidence actually confirmed the lesson.',
             {'type':'object','properties':{
                 'kind':{'type':'string','enum':['failure','success','procedure']},'situation':{'type':'string'},'lesson':{'type':'string'},'project':{'type':'string'},
                 'action_taken':{'type':'string'},'outcome':{'type':'string'},'root_cause':{'type':'string'},'better_action':{'type':'string'},
                 'verified':{'type':'boolean','default':False},'evidence':{'type':'string'}},'required':['kind','situation','lesson']},record_experience),
        Tool('experience_failure_patterns','List recurring failed-tool patterns from recent local episodes. Patterns are observations, not root-cause proof.',
             {'type':'object','properties':{'limit':{'type':'integer','default':10},'min_count':{'type':'integer','default':2}}},experience_failure_patterns),
        Tool('verify_experience','Update whether a previously retrieved lesson actually helped on the current task. This changes confidence but does not bypass any safety policy.',
             {'type':'object','properties':{'experience_id':{'type':'string'},'useful':{'type':'boolean'},'evidence':{'type':'string'}},'required':['experience_id','useful']},verify_experience),
    ]
