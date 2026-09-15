from __future__ import annotations
import json
from .model_provider import ModelManager
from .prompts import ORCHESTRATOR
from .tools.base import Tool
from .agents import SpecialistRouter
from .skills import SkillRegistry
from .resource_manager import ResourceManager

class Orchestrator:
    def __init__(self, model_manager: ModelManager, model: str, tools: list[Tool],
                 specialist_router: SpecialistRouter, keep_alive: int = 45, max_steps: int = 10,
                 context_tokens: int = 4096, skills: SkillRegistry | None = None,
                 resource_manager: ResourceManager | None = None):
        self.mm = model_manager
        self.model = model
        self.keep_alive = keep_alive
        self.max_steps = max_steps
        self.context_tokens = context_tokens
        self.specialists = specialist_router
        self.skills = skills
        self.resources = resource_manager
        self.tools = {t.name:t for t in tools}
        self.tools["delegate_agent"] = Tool(
            "delegate_agent",
            "Ask a sleeping specialist SLM/persona for help. Use only when it materially improves the task.",
            {"type":"object","properties":{
                "role":{"type":"string","enum":["general","coder","researcher","security","database","planner"]},
                "task":{"type":"string"}, "context":{"type":"string","default":""}
             },"required":["role","task"]}, self._delegate
        )

    def _delegate(self, role: str, task: str, context: str = ""):
        return self.specialists.delegate(role, task, context)

    def _skill_context(self, user_text: str) -> str:
        if not self.skills:
            return ""
        matched = self.skills.match(user_text)
        if not matched:
            return ""
        blocks = []
        for item in matched:
            blocks.append(f"Skill {item['name']} ({item.get('description','')}):\n{item.get('instructions','')}")
        return "\n\n[USER-CONFIRMED LOCAL SKILLS]\n" + "\n\n".join(blocks)

    def run(self, user_text: str, context: str = "") -> str:
        if self.resources:
            ok, reason = self.resources.can_start_model()
            if not ok:
                self.mm.sleep()
                return f"I did not load the local model because the machine is under memory pressure. {reason}"
        self.mm.activate(self.model)
        skill_ctx = self._skill_context(user_text)
        messages = [
            {"role":"system","content":ORCHESTRATOR + skill_ctx},
            {"role":"user","content":user_text + (f"\n\nWorking context:\n{context}" if context else "")},
        ]
        schemas = [t.ollama_schema() for t in self.tools.values()]

        for _ in range(self.max_steps):
            self.mm.activate(self.model)
            data = self.mm.provider.chat(self.model, messages, tools=schemas, keep_alive=self.keep_alive,
                                         options={"num_ctx": self.context_tokens})
            msg = data.get("message", {})
            messages.append(msg)
            tool_calls = msg.get("tool_calls") or []
            if not tool_calls:
                return msg.get("content","")

            for call in tool_calls:
                fn = call.get("function",{})
                name = fn.get("name")
                args = fn.get("arguments") or {}
                if isinstance(args, str):
                    try: args = json.loads(args)
                    except Exception: args = {}
                tool = self.tools.get(name)
                if not tool:
                    result = {"ok":False,"error":f"Unknown tool {name}"}
                else:
                    try: result = tool.handler(**args)
                    except TypeError as e: result = {"ok":False,"error":f"Tool arguments invalid: {e}"}
                    except Exception as e: result = {"ok":False,"error":str(e)}
                messages.append({"role":"tool","tool_name":name,"content":json.dumps(result, default=str)[:60000]})

        return "I reached the configured tool-step limit before completing the task. Review the latest tool results and retry with a narrower goal."
