import pytest
from living_assistant.models import ExecutivePlan, SpecialistResponse
from living_assistant.supervisors.executive import ExecutiveSupervisor
from living_assistant.supervisors.development import DevelopmentSupervisor

class DummyModelManager:
    def __init__(self):
        self.provider = DummyProvider()
    def activate(self, model): pass
    def sleep(self): pass
    def lease(self, model): 
        from contextlib import nullcontext
        return nullcontext(45)

class DummyProvider:
    def chat(self, model, messages, tools=None, keep_alive=45, options=None, format=None):
        if "Executive Supervisor" in messages[0]["content"]:
            # Mock ExecutivePlan
            plan = {
                "objective": "Fix the database error",
                "teams": ["development"],
                "parallel": True,
                "risk": "medium",
                "reason": "It involves backend code.",
                "requires_planning": False
            }
            import json
            return {"message": {"content": json.dumps(plan)}}
        else:
            # Mock SpecialistResponse
            resp = {
                "specialist": "coding",
                "summary": "I found the bug.",
                "findings": ["Line 42 has a typo"],
                "evidence": ["stack trace shows KeyError"],
                "confidence": 0.95,
                "uncertainties": [],
                "recommended_actions": ["Fix typo"],
                "proposed_mutations": []
            }
            import json
            return {"message": {"content": json.dumps(resp)}}

def test_executive_routing():
    mm = DummyModelManager()
    executive = ExecutiveSupervisor(mm, "dummy")
    plan = executive.route("The database is crashing")
    assert isinstance(plan, ExecutivePlan)
    assert plan.teams == ["development"]
    assert plan.risk == "medium"

def test_development_supervisor_parallel():
    mm = DummyModelManager()
    dev_sup = DevelopmentSupervisor(mm, "dummy")
    results = dev_sup.dispatch("Fix bug", "context", ["coding", "debugging"])
    assert "coding" in results
    assert "debugging" in results
    
    coding_res = results["coding"]
    assert isinstance(coding_res, SpecialistResponse)
    assert coding_res.confidence == 0.95
    assert coding_res.findings == ["Line 42 has a typo"]

def test_aggregator_and_verifier():
    from living_assistant.aggregator import Aggregator, AggregatedResult
    from living_assistant.verifier import Verifier, VerificationResult
    
    class AdvancedDummyProvider:
        def chat(self, model, messages, tools=None, keep_alive=45, options=None, format=None):
            sys_prompt = messages[0]["content"]
            import json
            if "Aggregator" in sys_prompt:
                res = {
                    "root_cause": "Typo in code",
                    "evidence": ["stack trace"],
                    "confidence": 0.9,
                    "disagreements": [],
                    "missing_data": [],
                    "recommended_actions": ["Fix it"]
                }
                return {"message": {"content": json.dumps(res)}}
            elif "Verifier" in sys_prompt:
                res = {
                    "passed": True,
                    "score": 1.0,
                    "unresolved_issues": [],
                    "failed_expectations": []
                }
                return {"message": {"content": json.dumps(res)}}
                
    mm = DummyModelManager()
    mm.provider = AdvancedDummyProvider()
    
    aggregator = Aggregator(mm, "dummy")
    result = aggregator.aggregate("fix bug", {})
    assert isinstance(result, AggregatedResult)
    assert result.root_cause == "Typo in code"
    
    verifier = Verifier(mm, "dummy")
    v_result = verifier.verify("fix bug", [], result.model_dump())
    assert isinstance(v_result, VerificationResult)
    assert v_result.passed is True
