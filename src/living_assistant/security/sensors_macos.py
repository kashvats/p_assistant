from __future__ import annotations

import platform
import shutil

from living_assistant.security.security_guardian import _run, _now, _redact_text
from .sensor_shared import _safe_json

def collect_macos_unified_log(minutes: int=10,max_events: int=250) -> dict:
    if platform.system()!='Darwin': return {'ok':False,'available':False,'reason':'macOS only','events':[]}
    if not shutil.which('log'): return {'ok':False,'available':False,'events':[],'reason':'macOS log utility unavailable.'}
    predicate='process == "syspolicyd" OR process == "XProtectService" OR process == "tccd" OR subsystem CONTAINS[c] "security"'
    res=_run(['log','show','--last',f'{max(1,int(minutes))}m','--style','ndjson','--predicate',predicate],15)
    events=[]
    for line in res.get('stdout','').splitlines()[-max_events:]:
        item=_safe_json(line)
        if not isinstance(item,dict): continue
        events.append({'source':'macos_unified_log','kind':'macos_security_log','time':item.get('timestamp') or _now(),
                       'process':item.get('process'),'subsystem':item.get('subsystem'),'category':item.get('category'),
                       'message':_redact_text(item.get('eventMessage') or '')})
    return {'ok':res.get('ok',False),'available':True,'provider':'unified-log','events':events,'error':_redact_text(res.get('stderr') or '')}

