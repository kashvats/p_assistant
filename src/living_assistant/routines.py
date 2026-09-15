from __future__ import annotations
from pathlib import Path
import datetime as dt
import json, time
from .config import data_dir
from .storage_utils import atomic_write_json

WEEKDAYS={'mon':0,'tue':1,'wed':2,'thu':3,'fri':4,'sat':5,'sun':6}

def _parse_hhmm(value: str) -> tuple[int,int]:
    try:
        h,m=[int(x) for x in value.split(':',1)]
        if not (0<=h<=23 and 0<=m<=59): raise ValueError
        return h,m
    except Exception as exc:
        raise ValueError('Routine time must use HH:MM in 24-hour format.') from exc

class RoutineRegistry:
    """Deterministic event/interval/daily/weekly routines with optional model wake."""
    def __init__(self,path: Path | None=None):
        self.path=path or (data_dir()/'routines.json')
        if not self.path.exists(): atomic_write_json(self.path, {})
    def _load(self):
        try: return json.loads(self.path.read_text(encoding='utf-8'))
        except Exception: return {}
    def _save(self,data): atomic_write_json(self.path, data)

    def add(self,name: str,trigger: dict,action: dict,enabled: bool=True) -> dict:
        ttype=trigger.get('type')
        if ttype not in {'event','interval','daily','weekly'}: raise ValueError('Trigger type must be event, interval, daily or weekly.')
        if action.get('type') not in {'notify','todo','assistant_prompt'}: raise ValueError('Action type must be notify, todo, or assistant_prompt.')
        if ttype=='event' and not trigger.get('kind'): raise ValueError('Event trigger requires kind.')
        if ttype=='interval': trigger={**trigger,'seconds':max(30,int(trigger.get('seconds',60)))}
        if ttype in {'daily','weekly'}:
            _parse_hhmm(str(trigger.get('time','')))
        if ttype=='weekly':
            days=[str(x).lower()[:3] for x in trigger.get('days',[])]
            if not days or any(x not in WEEKDAYS for x in days): raise ValueError('Weekly trigger days must use mon,tue,wed,thu,fri,sat,sun.')
            trigger={**trigger,'days':sorted(set(days),key=lambda x:WEEKDAYS[x])}
        data=self._load(); data[name]={'trigger':trigger,'action':action,'enabled':bool(enabled),'last_run':None,'updated_at':time.time()}
        self._save(data); return {'name':name,**data[name]}
    def list(self): return self._load()
    def get(self,name):
        item=self._load().get(name); return {'name':name,**item} if item else None
    def remove(self,name):
        data=self._load(); ok=name in data; data.pop(name,None); self._save(data); return ok
    def set_enabled(self,name,enabled):
        data=self._load()
        if name not in data: return False
        data[name]['enabled']=bool(enabled); data[name]['updated_at']=time.time(); self._save(data); return True
    def _mark_run(self,name,when):
        data=self._load()
        if name in data: data[name]['last_run']=when; self._save(data)

    @staticmethod
    def _clock_due(trigger: dict, now: float, last_run: float | None) -> bool:
        current=dt.datetime.fromtimestamp(now)
        h,m=_parse_hhmm(str(trigger.get('time')))
        if (current.hour,current.minute)<(h,m): return False
        if trigger.get('type')=='weekly':
            allowed={WEEKDAYS[x] for x in trigger.get('days',[])}
            if current.weekday() not in allowed: return False
        if last_run is None: return True
        previous=dt.datetime.fromtimestamp(float(last_run))
        return previous.date()!=current.date()

    def process(self,events: list[dict],memory,notifier,orchestrator=None,allow_model_wake: bool=False,model_manager=None,now: float | None=None) -> list[dict]:
        now=float(now if now is not None else time.time()); emitted=[]
        for name,item in list(self._load().items()):
            if not item.get('enabled',True): continue
            trig=item.get('trigger',{}); ttype=trig.get('type'); last=item.get('last_run')
            if ttype=='event': due=any(e.get('kind')==trig.get('kind') for e in events)
            elif ttype=='interval': due=last is None or now-float(last)>=max(30,int(trig.get('seconds',60)))
            else: due=self._clock_due(trig,now,last)
            if not due: continue
            action=item.get('action',{}); atype=action.get('type'); result={'kind':'routine_ran','routine':name,'action':atype}
            if atype=='notify':
                message=str(action.get('message') or f'Routine {name} ran.'); notifier.send('Living Assistant',message); result['message']=message
            elif atype=='todo':
                title=str(action.get('title') or f'Routine: {name}'); result['todo_id']=memory.add_todo(title,action.get('due_at'))
            elif atype=='assistant_prompt':
                if not allow_model_wake or orchestrator is None: result.update({'ok':False,'skipped':True,'reason':'assistant_prompt model wake is disabled'})
                else:
                    prompt=str(action.get('prompt','')).strip()
                    if not prompt: result.update({'ok':False,'skipped':True,'reason':'empty prompt'})
                    else:
                        try: result['answer']=orchestrator.run(prompt,context=f'Routine {name} fired from deterministic daemon.')
                        except Exception as exc: result.update({'ok':False,'error':str(exc)})
                        finally:
                            if model_manager: model_manager.sleep()
            self._mark_run(name,now); emitted.append(result)
        return emitted
