import json
from pydantic import BaseModel, Field
from typing import List, Dict, Any
from contextlib import nullcontext
from .model_provider import ModelManager

class VerificationResult(BaseModel):
    passed: bool = Field(description="True if the objective was fully achieved and verified.")
    score: float = Field(description="Verification confidence score (0.0 to 1.0).")
    unresolved_issues: List[str] = Field(default_factory=list, description="List of issues or goals that were not resolved.")
    failed_expectations: List[str] = Field(default_factory=list, description="State changes that were expected but did not occur.")

VERIFIER_PROMPT = """
You are the Verifier agent.
Your job is to evaluate if a multi-agent orchestration run successfully achieved its original objective.
Examine the objective, the executed mutations/tools, and the final state or aggregated result.
- Did the answer address the objective?
- Are conclusions supported by evidence?
- Did proposed mutations execute successfully?
- Did the expected state change occur?

IMPORTANT: You MUST respond with a raw, valid JSON object matching the VerificationResult schema.
"""

class Verifier:
    def __init__(self, model_manager: ModelManager, model: str, context_tokens: int = 4096):
        self.mm = model_manager
        self.model = model
        self.context_tokens = context_tokens

    def verify(self, objective: str, execution_trace: List[Dict[str, Any]], final_state: Any) -> VerificationResult | dict:
        trace_json = json.dumps(execution_trace, indent=2, default=str)
        final_json = json.dumps(final_state, indent=2, default=str) if isinstance(final_state, dict) else str(final_state)
        
        messages = [
            {"role": "system", "content": VERIFIER_PROMPT.strip()},
            {"role": "user", "content": f"Objective: {objective}\n\nExecution Trace:\n{trace_json[:20000]}\n\nFinal State/Result:\n{final_json[:10000]}"}
        ]

        try:
            format_schema = VerificationResult.model_json_schema()
        except Exception:
            format_schema = "json"

        lease = getattr(self.mm, 'lease', None)
        try:
            with (lease(self.model) if callable(lease) else self.mm.activate(self.model) or True):
                data = self.mm.provider.chat(
                    self.model,
                    messages,
                    options={"num_ctx": self.context_tokens},
                    format=format_schema
                )
            answer = data.get("message", {}).get("content", "")
            try:
                parsed = json.loads(answer)
                return VerificationResult(**parsed)
            except Exception:
                return {"error": "JSON Parse failed", "raw": answer}
        except Exception as exc:
            return {"error": str(exc)}
