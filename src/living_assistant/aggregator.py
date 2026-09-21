import json
from pydantic import BaseModel, Field
from typing import List, Dict
from contextlib import nullcontext
from .model_provider import ModelManager
from .models import SpecialistResponse

class AggregatedResult(BaseModel):
    root_cause: str = Field(description="Synthesized root cause or conclusion across all specialists.")
    evidence: List[str] = Field(description="Top prioritized evidence supporting the conclusion.")
    confidence: float = Field(description="Overall confidence score (0.0 to 1.0).")
    disagreements: List[str] = Field(default_factory=list, description="Any conflicting findings between specialists.")
    missing_data: List[str] = Field(default_factory=list, description="Crucial missing context needed to finalize.")
    recommended_actions: List[str] = Field(default_factory=list, description="Aggregated and prioritized recommended next steps.")

AGGREGATOR_PROMPT = """
You are the central Aggregator for a multi-agent personal assistant.
Your job is to synthesize findings from multiple specialized agents into a single coherent conclusion.
- Resolve duplicates.
- Highlight contradictions or disagreements.
- Do not fabricate missing results; if research failed, note it.

IMPORTANT: You MUST respond with a raw, valid JSON object matching the AggregatedResult schema.
"""

class Aggregator:
    def __init__(self, model_manager: ModelManager, model: str, context_tokens: int = 4096):
        self.mm = model_manager
        self.model = model
        self.context_tokens = context_tokens

    def aggregate(self, objective: str, specialist_results: Dict[str, SpecialistResponse | dict]) -> AggregatedResult | dict:
        results_str = ""
        for role, result in specialist_results.items():
            if isinstance(result, SpecialistResponse):
                res_json = result.model_dump_json(indent=2)
            else:
                res_json = json.dumps(result, indent=2)
            results_str += f"\n--- Specialist: {role} ---\n{res_json}\n"
        
        messages = [
            {"role": "system", "content": AGGREGATOR_PROMPT.strip()},
            {"role": "user", "content": f"Objective: {objective}\n\nResults to Aggregate:\n{results_str}"}
        ]

        try:
            format_schema = AggregatedResult.model_json_schema()
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
                return AggregatedResult(**parsed)
            except Exception:
                return {"error": "JSON Parse failed", "raw": answer}
        except Exception as exc:
            return {"error": str(exc)}
