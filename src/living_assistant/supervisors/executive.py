from __future__ import annotations
import json
from contextlib import nullcontext
from living_assistant.core.model_provider import ModelManager
from living_assistant.core.models import ExecutivePlan
# from ..security_utils import redact_secrets

EXECUTIVE_PROMPT = """
You are the Executive Supervisor of the local Personal AI Assistant.
Your sole job is to understand the user's intent, inspect context, and identify which specialized teams are needed.
You DO NOT solve the problem yourself.
You DO NOT generate final answers for the user.
You MUST output a valid JSON object matching the ExecutivePlan schema.

Available teams:
- development (for code, debugging, architecture, database)
- operations (for monitoring, network, services)
- security (for threat detection, vulnerability mapping, forensics)
- knowledge (for web research, document parsing)
- personal (for calendar, tasks, notes)
- upgrade (for assistant self-improvement, github research)

Determine if the selected teams can operate concurrently (parallel=true) or if they must run sequentially.
Determine the risk level (low, medium, high, critical).
"""

class ExecutiveSupervisor:
    def __init__(self, model_manager: ModelManager, model: str, context_tokens: int = 4096):
        self.mm = model_manager
        self.model = model
        self.context_tokens = context_tokens

    def _model_lease(self):
        lease = getattr(self.mm, 'lease', None)
        if callable(lease):
            return lease(self.model)
        self.mm.activate(self.model)
        return nullcontext(45)

    def route(self, user_text: str, context: str = "") -> ExecutivePlan | dict:
        messages = [
            {"role": "system", "content": EXECUTIVE_PROMPT.strip()},
            {"role": "user", "content": f"User Request:\n{user_text}\n\nContext:\n{context[:10000]}"}
        ]

        try:
            format_schema = ExecutivePlan.model_json_schema()
        except Exception:
            format_schema = "json"

        try:
            with self._model_lease() as keep_alive:
                data = self.mm.provider.chat(
                    self.model,
                    messages,
                    keep_alive=keep_alive,
                    options={"num_ctx": self.context_tokens},
                    format=format_schema
                )
            answer = data.get("message", {}).get("content", "")
            try:
                parsed = json.loads(answer)
                return ExecutivePlan(**parsed)
            except Exception:
                return {"error": "Failed to parse JSON", "raw": answer}
        except Exception as exc:
            return {"error": str(exc)}
