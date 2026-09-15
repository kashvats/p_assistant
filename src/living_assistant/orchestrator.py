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
                 resource_manager: ResourceManager | None = None, session_store=None,
                 max_session_messages: int = 12):
        self.mm = model_manager
        self.model = model
        self.keep_alive = keep_alive
        self.max_steps = max_steps
        self.context_tokens = context_tokens
        self.specialists = specialist_router
        self.skills = skills
        self.resources = resource_manager
        self.sessions = session_store
        self.max_session_messages = max(2, min(int(max_session_messages), 30))
        self.tools = {t.name:t for t in tools}
        self.tools['delegate_agent'] = Tool(
            'delegate_agent',
            'Ask a sleeping specialist SLM/persona for help. Use only when it materially improves the task.',
            {'type':'object','properties':{
                'role':{'type':'string','enum':['general','coder','researcher','security','database','planner']},
                'task':{'type':'string'}, 'context':{'type':'string','default':''}
             },'required':['role','task']}, self._delegate
        )

    def _delegate(self, role: str, task: str, context: str = ''):
        return self.specialists.delegate(role, task, context)

    def _skill_context(self, user_text: str) -> str:
        if not self.skills: return ''
        matched = self.skills.match(user_text)
        if not matched: return ''
        blocks=[f"Skill {item['name']} ({item.get('description','')}):\n{item.get('instructions','')}" for item in matched]
        return '\n\n[USER-CONFIRMED LOCAL SKILLS]\n' + '\n\n'.join(blocks)

    def _session_context(self, session_id: str | None) -> str:
        if not self.sessions or not session_id: return ''
        rows=self.sessions.recent_messages(session_id,self.max_session_messages)
        if not rows: return ''
        rendered='\n'.join(f"{r['role'].upper()}: {r['content'][:4000]}" for r in rows)
        return '\n\n[BOUNDED LOCAL SESSION HISTORY]\n' + rendered

    def _finish(self, answer: str, session_id: str | None) -> str:
        if self.sessions and session_id:
            self.sessions.add_message(session_id,'assistant',answer)
        return answer

    def run(self, user_text: str, context: str = '', session_id: str | None = None) -> str:
        if self.sessions and session_id:
            self.sessions.ensure(session_id)
            prior=self._session_context(session_id)
            self.sessions.add_message(session_id,'user',user_text)
        else:
            prior=''
        if self.resources:
            ok, reason = self.resources.can_start_model()
            if not ok:
                self.mm.sleep()
                return self._finish(f'I did not load the local model because the machine is under memory pressure. {reason}', session_id)
        self.mm.activate(self.model)
        skill_ctx = self._skill_context(user_text)
        system = ORCHESTRATOR + skill_ctx
        user_payload = user_text
        if prior: user_payload += prior
        if context: user_payload += f'\n\nWorking context:\n{context}'
        messages=[{'role':'system','content':system},{'role':'user','content':user_payload}]
        schemas=[t.ollama_schema() for t in self.tools.values()]

        for _ in range(self.max_steps):
            self.mm.activate(self.model)
            data=self.mm.provider.chat(self.model,messages,tools=schemas,keep_alive=self.keep_alive,
                                       options={'num_ctx':self.context_tokens})
            msg=data.get('message',{}); messages.append(msg)
            tool_calls=msg.get('tool_calls') or []
            if not tool_calls:
                return self._finish(msg.get('content',''), session_id)
            for call in tool_calls:
                fn=call.get('function',{}); name=fn.get('name'); args=fn.get('arguments') or {}
                if isinstance(args,str):
                    try: args=json.loads(args)
                    except Exception: args={}
                tool=self.tools.get(name)
                if not tool: result={'ok':False,'error':f'Unknown tool {name}'}
                else:
                    try: result=tool.handler(**args)
                    except TypeError as e: result={'ok':False,'error':f'Tool arguments invalid: {e}'}
                    except Exception as e: result={'ok':False,'error':str(e)}
                messages.append({'role':'tool','tool_name':name,'content':json.dumps(result,default=str)[:60000]})
        return self._finish('I reached the configured tool-step limit before completing the task. Review the latest tool results and retry with a narrower goal.', session_id)
