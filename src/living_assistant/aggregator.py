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
            if callable(lease):
                model_context = lease(self.model)
            else:
                self.mm.activate(self.model)
                model_context = nullcontext()
            with model_context:
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
                # Fail closed to a structured synthesis of the specialist evidence
                # rather than returning raw model output or discarding all findings.
                evidence=[]
                actions=[]
                missing=[]
                summaries=[]
                confidences=[]
                for result in specialist_results.values():
                    item=result.model_dump() if isinstance(result, SpecialistResponse) else (result if isinstance(result, dict) else {})
                    summary=str(item.get('summary') or '').strip()
                    if summary and summary not in summaries: summaries.append(summary)
                    for value in list(item.get('evidence') or []) + list(item.get('findings') or []):
                        value=str(value).strip()
                        if value and value not in evidence: evidence.append(value)
                    for value in item.get('recommended_actions') or []:
                        value=str(value).strip()
                        if value and value not in actions: actions.append(value)
                    for value in item.get('uncertainties') or []:
                        value=str(value).strip()
                        if value and value not in missing: missing.append(value)
                    try: confidences.append(float(item.get('confidence')))
                    except (TypeError, ValueError): pass
                return AggregatedResult(
                    root_cause='; '.join(summaries[:4]) or 'No reliable synthesized conclusion was returned by the aggregator model.',
                    evidence=evidence[:20],
                    confidence=max(0.0,min(1.0,sum(confidences)/len(confidences))) if confidences else 0.0,
                    disagreements=[],
                    missing_data=missing[:20] or ['Aggregator model returned invalid structured output; verify specialist findings before acting.'],
                    recommended_actions=actions[:20],
                )
        except Exception as exc:
            evidence=[]
            actions=[]
            missing=[f'Aggregator model unavailable: {type(exc).__name__}']
            summaries=[]
            confidences=[]
            for result in specialist_results.values():
                item=result.model_dump() if isinstance(result, SpecialistResponse) else (result if isinstance(result, dict) else {})
                summary=str(item.get('summary') or '').strip()
                if summary and summary not in summaries: summaries.append(summary)
                for value in list(item.get('evidence') or []) + list(item.get('findings') or []):
                    value=str(value).strip()
                    if value and value not in evidence: evidence.append(value)
                for value in item.get('recommended_actions') or []:
                    value=str(value).strip()
                    if value and value not in actions: actions.append(value)
                for value in item.get('uncertainties') or []:
                    value=str(value).strip()
                    if value and value not in missing: missing.append(value)
                try: confidences.append(float(item.get('confidence')))
                except (TypeError, ValueError): pass
            return AggregatedResult(
                root_cause='; '.join(summaries[:4]) or 'Aggregator model unavailable; no synthesized conclusion could be established.',
                evidence=evidence[:20],
                confidence=max(0.0,min(1.0,sum(confidences)/len(confidences))) if confidences else 0.0,
                disagreements=[],
                missing_data=missing[:20],
                recommended_actions=actions[:20],
            )
