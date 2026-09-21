import logging
# from typing import Dict, List
from .models import ExecutivePlan, SpecialistResponse
from .aggregator import Aggregator

logger = logging.getLogger(__name__)

def dispatch_to_teams(orchestrator, exec_plan: ExecutivePlan, user_text: str, context: str) -> list[dict]:
    """
    Dispatches the task to the requested team supervisors, aggregates the result,
    and returns a list of proposed tool calls to inject into the orchestrator loop.
    """
    if not exec_plan.teams:
        return []
    
    results = {}
    
    for team in exec_plan.teams:
        team_name = team.lower()
        if team_name == "development":
            from .supervisors.development import DevelopmentSupervisor
            sup = DevelopmentSupervisor(orchestrator.mm, orchestrator.model, orchestrator.context_tokens)
            # Dispatch to appropriate specialists based on risk/objective
            res = sup.dispatch(user_text, context, ["coding", "debugging"])
            results.update(res)
        elif team_name == "security":
            from .supervisors.security import SecuritySupervisor
            sup = SecuritySupervisor(orchestrator.mm, orchestrator.model, orchestrator.context_tokens)
            res = sup.dispatch(user_text, context, ["detection"]) if hasattr(sup, "dispatch") else {}
            results.update(res)
        elif team_name == "operations":
            from .supervisors.operations import OperationsSupervisor
            sup = OperationsSupervisor(orchestrator.mm, orchestrator.model, orchestrator.context_tokens)
            res = sup.dispatch(user_text, context, ["monitoring"]) if hasattr(sup, "dispatch") else {}
            results.update(res)
        elif team_name == "knowledge":
            from .supervisors.knowledge import KnowledgeSupervisor
            sup = KnowledgeSupervisor(orchestrator.mm, orchestrator.model, orchestrator.context_tokens)
            res = sup.dispatch(user_text, context, ["research"]) if hasattr(sup, "dispatch") else {}
            results.update(res)
        elif team_name == "personal":
            from .supervisors.personal import PersonalSupervisor
            sup = PersonalSupervisor(orchestrator.mm, orchestrator.model, orchestrator.context_tokens)
            res = sup.dispatch(user_text, context, ["memory"]) if hasattr(sup, "dispatch") else {}
            results.update(res)
        elif team_name == "upgrade":
            from .supervisors.upgrade import UpgradeSupervisor
            sup = UpgradeSupervisor(orchestrator.mm, orchestrator.model, orchestrator.context_tokens)
            res = sup.dispatch(user_text, context, ["learning"]) if hasattr(sup, "dispatch") else {}
            results.update(res)

    if not results:
        return []

    # Run Aggregator (Phase 5)
    aggregator = Aggregator(orchestrator.mm, orchestrator.model, orchestrator.context_tokens)
    _ = aggregator.aggregate(user_text, results)
    
    tool_calls = []
    
    # Extract Proposed Mutations from all team results
    for role, result in results.items():
        if isinstance(result, SpecialistResponse) and result.proposed_mutations:
            for mut in result.proposed_mutations:
                # Provide a generic payload if none provided
                payload = mut.payload if mut.payload else mut.justification
                
                # We need to map it to the actual flat tool names (e.g. read_file, run_command, etc.)
                # But since the prompt might output arbitrary actions, we should sanitize it.
                # Actually, the simplest is to just inject them!
                tool_calls.append({
                    "function": {
                        "name": mut.action,
                        "arguments": {
                            "target": mut.target,
                            "payload": payload,
                            "justification": mut.justification
                        }
                    }
                })
                
    return tool_calls
