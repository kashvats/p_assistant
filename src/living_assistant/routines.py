from __future__ import annotations
from pathlib import Path
import json, time
from .config import data_dir

class RoutineRegistry:
    """Deterministic event/interval routines with optional model wake."""
    def __init__(self, path: Path | None = None):
        self.path = path or (data_dir() / 'routines.json')
        if not self.path.exists():
            self.path.write_text('{}', encoding='utf-8')

    def _load(self) -> dict:
        try:
            return json.loads(self.path.read_text(encoding='utf-8'))
        except Exception:
            return {}

    def _save(self, data: dict):
        self.path.write_text(json.dumps(data, indent=2), encoding='utf-8')

    def add(self, name: str, trigger: dict, action: dict, enabled: bool = True) -> dict:
        if trigger.get('type') not in {'event', 'interval'}:
            raise ValueError('Trigger type must be event or interval.')
        if action.get('type') not in {'notify', 'todo', 'assistant_prompt'}:
            raise ValueError('Action type must be notify, todo, or assistant_prompt.')
        if trigger.get('type') == 'event' and not trigger.get('kind'):
            raise ValueError('Event trigger requires kind.')
        if trigger.get('type') == 'interval':
            trigger = {**trigger, 'seconds': max(30, int(trigger.get('seconds', 60)))}
        data = self._load()
        data[name] = {
            'trigger': trigger, 'action': action, 'enabled': bool(enabled),
            'last_run': None, 'updated_at': time.time(),
        }
        self._save(data)
        return {'name': name, **data[name]}

    def list(self) -> dict:
        return self._load()

    def get(self, name: str) -> dict | None:
        item = self._load().get(name)
        return {'name': name, **item} if item else None

    def remove(self, name: str) -> bool:
        data = self._load(); ok = name in data; data.pop(name, None); self._save(data); return ok

    def set_enabled(self, name: str, enabled: bool) -> bool:
        data = self._load()
        if name not in data:
            return False
        data[name]['enabled'] = bool(enabled)
        data[name]['updated_at'] = time.time()
        self._save(data)
        return True

    def _mark_run(self, name: str, when: float):
        data = self._load()
        if name in data:
            data[name]['last_run'] = when
            self._save(data)

    def process(self, events: list[dict], memory, notifier, orchestrator=None,
                allow_model_wake: bool = False, model_manager=None, now: float | None = None) -> list[dict]:
        now = float(now if now is not None else time.time())
        emitted = []
        for name, item in list(self._load().items()):
            if not item.get('enabled', True):
                continue
            trig = item.get('trigger', {})
            if trig.get('type') == 'event':
                due = any(e.get('kind') == trig.get('kind') for e in events)
            else:
                last = item.get('last_run')
                due = last is None or now - float(last) >= max(30, int(trig.get('seconds', 60)))
            if not due:
                continue
            action = item.get('action', {})
            atype = action.get('type')
            result = {'kind': 'routine_ran', 'routine': name, 'action': atype}
            if atype == 'notify':
                message = str(action.get('message') or f'Routine {name} ran.')
                notifier.send('Living Assistant', message)
                result['message'] = message
            elif atype == 'todo':
                title = str(action.get('title') or f'Routine: {name}')
                result['todo_id'] = memory.add_todo(title, action.get('due_at'))
            elif atype == 'assistant_prompt':
                if not allow_model_wake or orchestrator is None:
                    result.update({'ok': False, 'skipped': True, 'reason': 'assistant_prompt model wake is disabled'})
                else:
                    prompt = str(action.get('prompt', '')).strip()
                    if not prompt:
                        result.update({'ok': False, 'skipped': True, 'reason': 'empty prompt'})
                    else:
                        try:
                            result['answer'] = orchestrator.run(prompt, context=f'Routine {name} fired from deterministic daemon.')
                        except Exception as exc:
                            result.update({'ok': False, 'error': str(exc)})
                        finally:
                            if model_manager:
                                model_manager.sleep()
            self._mark_run(name, now)
            emitted.append(result)
        return emitted
