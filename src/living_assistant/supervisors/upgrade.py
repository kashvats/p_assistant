from __future__ import annotations
import json
import logging
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from living_assistant.core.model_provider import ModelManager
from living_assistant.core.models import SpecialistResponse

logger = logging.getLogger(__name__)

UPGRADE_PROMPTS = {
    "evaluation": "You are an evaluation specialist. Compare baseline models and run sandboxed tests.",
    "learning": "You are a learning specialist. Extract reusable workflows, experiences, and rules from traces."
}

JSON_INSTRUCTION = """
IMPORTANT: You MUST respond with a raw, valid JSON object matching this schema:
{
  "specialist": "string",
  "summary": "string",
  "findings": ["string"],
  "evidence": ["string"],
  "confidence": 1.0,
  "uncertainties": ["string"],
  "recommended_actions": ["string"],
  "proposed_mutations": [{"action": "string", "target": "string", "payload": "string", "justification": "string"}]
}
Do not include markdown blocks or other text outside the JSON.
"""

class UpgradeSupervisor:
    def __init__(self, model_manager: ModelManager, model: str, context_tokens: int = 4096):
        self.mm = model_manager
        self.model = model
        self.context_tokens = context_tokens

    def _execute_specialist(self, role: str, task: str, context: str) -> SpecialistResponse | dict:
        prompt = UPGRADE_PROMPTS.get(role, UPGRADE_PROMPTS["learning"]) + "\n" + JSON_INSTRUCTION
        messages = [
            {"role": "system", "content": prompt.strip()},
            {"role": "user", "content": f"Task:\n{task}\n\nContext:\n{context[:15000]}"}
        ]

        try:
            format_schema = SpecialistResponse.model_json_schema()
        except Exception:
            format_schema = "json"

        # Model lease is handled externally or within mm.activate logic.
        # But we must ensure thread safety if running concurrently.
        # Ollama supports concurrent queues, but on GTX 1650 we just queue against the single resident model.
        # To prevent resource deadlock, we acquire the mm lease here.
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
                return SpecialistResponse(**parsed)
            except Exception:
                return {"error": "JSON Parse failed", "raw": answer, "role": role}
        except Exception as exc:
            return {"error": str(exc), "role": role}

    def dispatch(self, task: str, context: str, specialists: List[str]) -> Dict[str, SpecialistResponse | dict]:
        """Runs the requested development specialists concurrently."""
        results = {}
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_to_role = {
                executor.submit(self._execute_specialist, role, task, context): role 
                for role in specialists
            }
            for future in as_completed(future_to_role):
                role = future_to_role[future]
                try:
                    results[role] = future.result()
                except Exception as exc:
                    results[role] = {"error": str(exc)}
        return results
