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


def test_aggregator_supports_legacy_model_manager_without_lease():
    from living_assistant.aggregator import Aggregator, AggregatedResult
    import json

    class Provider:
        def chat(self, model, messages, tools=None, keep_alive=45, options=None, format=None):
            return {'message': {'content': json.dumps({
                'root_cause':'Combined conclusion','evidence':['e1'], 'confidence':.8,
                'disagreements':[], 'missing_data':[], 'recommended_actions':['a1']
            })}}
    class LegacyMM:
        def __init__(self): self.provider=Provider(); self.activated=[]
        def activate(self, model): self.activated.append(model)

    mm=LegacyMM()
    result=Aggregator(mm,'legacy').aggregate('objective', {'coding': {
        'summary':'s','findings':['f'],'evidence':['e'],'confidence':.7,
        'uncertainties':[],'recommended_actions':['a'],'proposed_mutations':[]
    }})
    assert isinstance(result, AggregatedResult)
    assert result.root_cause == 'Combined conclusion'
    assert mm.activated == ['legacy']


def test_aggregator_invalid_json_falls_back_to_structured_specialist_synthesis():
    from living_assistant.aggregator import Aggregator, AggregatedResult

    class Provider:
        def chat(self, *a, **k): return {'message': {'content': 'not-json'}}
    class MM:
        def __init__(self): self.provider=Provider()
        def lease(self, model):
            from contextlib import nullcontext
            return nullcontext()

    specialist=SpecialistResponse(
        specialist='coding', summary='Null check is missing', findings=['line 42 dereferences None'],
        evidence=['trace shows AttributeError'], confidence=.9, uncertainties=['input contract unknown'],
        recommended_actions=['add validated guard'], proposed_mutations=[]
    )
    result=Aggregator(MM(),'dummy').aggregate('fix bug', {'coding':specialist})
    assert isinstance(result, AggregatedResult)
    assert 'Null check is missing' in result.root_cause
    assert 'trace shows AttributeError' in result.evidence
    assert 'add validated guard' in result.recommended_actions
    assert result.confidence == pytest.approx(.9)
