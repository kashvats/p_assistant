from __future__ import annotations
import json
from contextlib import nullcontext
from .model_provider import ModelManager
from .prompts import ORCHESTRATOR
from .tools.base import Tool
from .agents import SpecialistRouter
from .skills import SkillRegistry
from .resource_manager import ResourceManager
from .security_utils import redact_secrets

class Orchestrator:
    def __init__(self, model_manager: ModelManager, model: str, tools: list[Tool],
                 specialist_router: SpecialistRouter, keep_alive: int = 45, max_steps: int = 10,
                 context_tokens: int = 4096, skills: SkillRegistry | None = None,
                 resource_manager: ResourceManager | None = None, session_store=None,
                 max_session_messages: int = 12, experiences=None, event_bus=None):
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
        self.experiences = experiences
        self.event_bus = event_bus
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

    def _model_lease(self):
        lease = getattr(self.mm, 'lease', None)
        if callable(lease):
            try:
                return lease(self.model, priority=100)
            except TypeError:
                return lease(self.model)
        # Compatibility with older/custom ModelManager implementations and test
        # doubles that only implement the original activate() contract.
        try:
            self.mm.activate(self.model, priority=100)
        except TypeError:
            self.mm.activate(self.model)
        return nullcontext(self.keep_alive)

    def _publish(self, event_type: str, **data):
        if self.event_bus:
            try:
                return self.event_bus.publish(event_type, **data)
            except Exception:
                return None
        return None

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


    @staticmethod
    def _project_hint(context: str) -> str | None:
        import re
        from pathlib import Path
        for pat in (r'Project(?: path)?:\s*([^\n]+)', r'Preferred working directory:\s*([^\n]+)'):
            m=re.search(pat,context or '',re.I)
            if m:
                value=m.group(1).strip().strip('`"')
                if value not in {'.','./'}:
                    try: return Path(value).expanduser().name or value[:120]
                    except Exception: return value[:120]
        return None

    def _experience_context(self, user_text: str, context: str) -> str:
        if not self.experiences: return ''
        try: return self.experiences.context_for(user_text + (' ' + context if context else ''), project=self._project_hint(context))
        except Exception: return ''

    def _finish(self, answer: str, session_id: str | None) -> str:
        if self.sessions and session_id:
            self.sessions.add_message(session_id,'assistant',answer)
        return answer

    def _prepare(self, user_text: str, context: str, session_id: str | None):
        if self.sessions and session_id:
            self.sessions.ensure(session_id)
            prior = self._session_context(session_id)
            self.sessions.add_message(session_id, 'user', user_text)
        else:
            prior = ''
        skill_ctx = self._skill_context(user_text)
        experience_ctx = self._experience_context(user_text, context)
        system = ORCHESTRATOR + skill_ctx + experience_ctx
        user_payload = user_text
        if prior:
            user_payload += prior
        if context:
            user_payload += f'\n\nWorking context:\n{context}'
        messages = [{'role': 'system', 'content': system}, {'role': 'user', 'content': user_payload}]
        schemas = [t.ollama_schema() for t in self.tools.values()]
        return messages, schemas, self._project_hint(context)

    def _execute_tool(self, name: str | None, args):
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except Exception:
                args = {}
        if not isinstance(args, dict):
            args = {}
        tool = self.tools.get(name)
        if not tool:
            return args, {'ok': False, 'error': f'Unknown tool {name}'}
        try:
            return args, tool.handler(**args)
        except TypeError as e:
            return args, {'ok': False, 'error': redact_secrets(f'Tool arguments invalid: {e}', 2000)}
        except Exception as e:
            return args, {'ok': False, 'error': redact_secrets(e, 2000)}

    def run(self, user_text: str, context: str = '', session_id: str | None = None) -> str:
        self._publish('chat.started', session_id=session_id, model=self.model)
        if self.resources:
            ok, reason = self.resources.can_start_model()
            if not ok:
                self.mm.sleep()
                answer = f'I did not load the local model because the machine is under memory pressure. {reason}'
                self._publish('chat.completed', session_id=session_id, model=self.model)
                return self._finish(answer, session_id)
        messages, schemas, project_hint = self._prepare(user_text, context, session_id)
        trace = []

        try:
            for _ in range(self.max_steps):
                with self._model_lease() as keep_alive:
                    data = self.mm.provider.chat(self.model, messages, tools=schemas, keep_alive=keep_alive,
                                                 options={'num_ctx': self.context_tokens})
                msg = data.get('message', {})
                messages.append(msg)
                tool_calls = msg.get('tool_calls') or []
                if not tool_calls:
                    if self.experiences and trace:
                        try:
                            self.experiences.learn_from_trace(user_text, trace, project=project_hint, session_id=session_id)
                        except Exception:
                            pass
                    answer = msg.get('content', '')
                    self._publish('chat.completed', session_id=session_id, model=self.model)
                    return self._finish(answer, session_id)
                for call in tool_calls:
                    fn = call.get('function', {})
                    name = fn.get('name')
                    args = fn.get('arguments') or {}
                    self._publish('tool.started', session_id=session_id, tool=name)
                    args, result = self._execute_tool(name, args)
                    messages.append({'role': 'tool', 'tool_name': name, 'content': json.dumps(result, default=str)[:60000]})
                    self._publish('tool.completed', session_id=session_id, tool=name, ok=bool(result.get('ok', True)) if isinstance(result, dict) else True)
                    if self.experiences:
                        try:
                            ep = self.experiences.record_episode(user_text, name, args, result, project=project_hint, session_id=session_id)
                            trace.append({'tool_name': name, **ep})
                        except Exception:
                            pass
        except Exception as exc:
            self._publish('chat.error', session_id=session_id, model=self.model, error=redact_secrets(exc, 500))
            raise
        if self.experiences and trace:
            try:
                self.experiences.learn_from_trace(user_text, trace, project=project_hint, session_id=session_id)
            except Exception:
                pass
        answer = 'I reached the configured tool-step limit before completing the task. Review the latest tool results and retry with a narrower goal.'
        self._publish('chat.completed', session_id=session_id, model=self.model, limited=True)
        return self._finish(answer, session_id)

    def run_stream(self, user_text: str, context: str = '', session_id: str | None = None):
        """Yield structured streaming events without bypassing the normal tool loop."""
        self._publish('chat.started', session_id=session_id, model=self.model)
        yield {'type': 'status', 'status': 'starting', 'model': self.model}
        if self.resources:
            ok, reason = self.resources.can_start_model()
            if not ok:
                self.mm.sleep()
                answer = f'I did not load the local model because the machine is under memory pressure. {reason}'
                self._finish(answer, session_id)
                self._publish('chat.completed', session_id=session_id, model=self.model)
                yield {'type': 'final', 'text': answer, 'session_id': session_id}
                return

        messages, schemas, project_hint = self._prepare(user_text, context, session_id)
        trace = []

        try:
            for step in range(self.max_steps):
                self._publish('model.generating', session_id=session_id, model=self.model, step=step + 1)
                yield {'type': 'status', 'status': 'generating', 'model': self.model, 'step': step + 1}
                content_parts: list[str] = []
                tool_calls: list[dict] = []
                seen_calls: set[str] = set()
                with self._model_lease() as keep_alive:
                    for chunk in self.mm.provider.chat_stream(
                        self.model, messages, tools=schemas, keep_alive=keep_alive,
                        options={'num_ctx': self.context_tokens}
                    ):
                        msg_part = chunk.get('message') or {}
                        text = msg_part.get('content') or ''
                        if text:
                            content_parts.append(text)
                            yield {'type': 'token', 'text': text}
                        for call in msg_part.get('tool_calls') or []:
                            try:
                                key = json.dumps(call, sort_keys=True, default=str)
                            except Exception:
                                key = repr(call)
                            if key not in seen_calls:
                                seen_calls.add(key)
                                tool_calls.append(call)
                msg = {'role': 'assistant', 'content': ''.join(content_parts)}
                if tool_calls:
                    msg['tool_calls'] = tool_calls
                messages.append(msg)

                if not tool_calls:
                    if self.experiences and trace:
                        try:
                            self.experiences.learn_from_trace(user_text, trace, project=project_hint, session_id=session_id)
                        except Exception:
                            pass
                    answer = msg.get('content', '')
                    self._finish(answer, session_id)
                    self._publish('chat.completed', session_id=session_id, model=self.model)
                    yield {'type': 'final', 'text': answer, 'session_id': session_id}
                    return

                for call in tool_calls:
                    fn = call.get('function', {})
                    name = fn.get('name')
                    args = fn.get('arguments') or {}
                    self._publish('tool.started', session_id=session_id, tool=name)
                    yield {'type': 'tool', 'tool': name, 'status': 'started'}
                    args, result = self._execute_tool(name, args)
                    messages.append({'role': 'tool', 'tool_name': name, 'content': json.dumps(result, default=str)[:60000]})
                    ok_result = bool(result.get('ok', True)) if isinstance(result, dict) else True
                    self._publish('tool.completed', session_id=session_id, tool=name, ok=ok_result)
                    yield {'type': 'tool', 'tool': name, 'status': 'completed', 'ok': ok_result}
                    if self.experiences:
                        try:
                            ep = self.experiences.record_episode(user_text, name, args, result, project=project_hint, session_id=session_id)
                            trace.append({'tool_name': name, **ep})
                        except Exception:
                            pass
        except Exception as exc:
            self._publish('chat.error', session_id=session_id, model=self.model, error=redact_secrets(exc, 500))
            yield {'type': 'error', 'error': redact_secrets(exc, 1200)}
            return

        if self.experiences and trace:
            try:
                self.experiences.learn_from_trace(user_text, trace, project=project_hint, session_id=session_id)
            except Exception:
                pass
        answer = 'I reached the configured tool-step limit before completing the task. Review the latest tool results and retry with a narrower goal.'
        self._finish(answer, session_id)
        self._publish('chat.completed', session_id=session_id, model=self.model, limited=True)
        yield {'type': 'final', 'text': answer, 'session_id': session_id}
