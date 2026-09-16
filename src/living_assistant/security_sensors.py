from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from collections import deque, Counter, defaultdict
import datetime as dt
import hashlib
import json
import math
import os
import platform
import re
import shutil
import subprocess
import time
from typing import Iterable

import httpx

from .config import data_dir
from .security_guardian import _run, _now, _redact_obj, _redact_text, file_signature, sha256_file
from .sqlite_utils import ThreadLocalSQLite

SENSOR_SCHEMA = """
CREATE TABLE IF NOT EXISTS sensor_state(
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS binary_trust(
  path TEXT PRIMARY KEY,
  sha256 TEXT NOT NULL,
  signer TEXT,
  signature_status TEXT,
  label TEXT,
  first_seen TEXT NOT NULL,
  last_seen TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS backup_baselines(
  name TEXT PRIMARY KEY,
  path TEXT NOT NULL,
  manifest TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
"""

SYSMON_CHANNEL = 'Microsoft-Windows-Sysmon/Operational'
WINDOWS_SECURITY_CHANNEL = 'Security'

HIGH_SIGNAL_SYSMON_IDS = {1,3,6,8,10,11,12,13,14,19,20,21,22,23,25,26,27,28,29}


def _safe_json(raw: str):
    try:
        return json.loads(raw)
    except Exception:
        return None


def _event_time(value) -> str:
    if isinstance(value, str) and value:
        return value
    return _now()


def normalize_sysmon_event(item: dict) -> dict:
    data=item.get('data') or item.get('Data') or {}
    if not isinstance(data,dict): data={}
    eid=int(item.get('id') or item.get('Id') or item.get('event_id') or 0)
    pid=data.get('ProcessId') or data.get('SourceProcessId') or data.get('TargetProcessId')
    try: pid=int(pid) if pid not in {None,''} else None
    except Exception: pid=None
    kind={
        1:'process_create',3:'network_connect',5:'process_terminate',6:'driver_load',8:'remote_thread',
        10:'process_access',11:'file_create',12:'registry_create_delete',13:'registry_value_set',14:'registry_rename',
        19:'wmi_filter',20:'wmi_consumer',21:'wmi_binding',22:'dns_query',23:'file_delete',25:'process_tampering',
        26:'file_delete',27:'file_block_executable',28:'file_block_shredding',29:'file_executable_detected'
    }.get(eid,'sysmon_event')
    out={
        'source':'sysmon','event_id':eid,'kind':kind,'time':_event_time(item.get('time') or item.get('TimeCreated')),
        'pid':pid,'process_guid':data.get('ProcessGuid') or data.get('SourceProcessGuid'),
        'image':data.get('Image') or data.get('SourceImage'),'parent_image':data.get('ParentImage'),
        'command_line':_redact_text(data.get('CommandLine') or ''),
    }
    if kind=='network_connect':
        out.update({'destination_ip':data.get('DestinationIp'),'destination_host':data.get('DestinationHostname'),
                    'destination_port':data.get('DestinationPort'),'protocol':data.get('Protocol')})
    elif kind=='dns_query':
        out.update({'query_name':data.get('QueryName'),'query_status':data.get('QueryStatus'),'query_results':data.get('QueryResults')})
    elif kind in {'file_create','file_delete','file_block_executable','file_block_shredding','file_executable_detected'}:
        out['path']=data.get('TargetFilename') or data.get('Image')
    elif kind.startswith('registry_'):
        out.update({'target_object':data.get('TargetObject'),'details':data.get('Details')})
    out['raw']=_redact_obj({k:v for k,v in data.items() if k not in {'CommandLine'}})
    return out


def _powershell_event_script(channel: str, minutes: int, max_events: int) -> str:
    ch=channel.replace("'","''")
    id_filter="; Id=4688,4697,4698,4702,4720,4732,1102" if channel==WINDOWS_SECURITY_CHANNEL else ""
    return rf"""
$ErrorActionPreference='Stop';
$start=(Get-Date).AddMinutes(-{max(1,int(minutes))});
$rows=@();
Get-WinEvent -FilterHashtable @{{LogName='{ch}'; StartTime=$start{id_filter}}} -MaxEvents {max(1,min(int(max_events),1000))} | ForEach-Object {{
  [xml]$x=$_.ToXml(); $d=@{{}};
  foreach($n in $x.Event.EventData.Data) {{ if($n.Name) {{$d[$n.Name]=[string]$n.'#text'}} }};
  $rows += [PSCustomObject]@{{id=$_.Id; time=$_.TimeCreated.ToUniversalTime().ToString('o'); provider=$_.ProviderName; data=$d; message=$_.Message}}
}};
$rows | ConvertTo-Json -Depth 7 -Compress
"""


def normalize_windows_security_event(item: dict) -> dict:
    data=item.get('data') or item.get('Data') or {}
    if not isinstance(data,dict): data={}
    eid=int(item.get('id') or item.get('Id') or 0)
    if eid==4688:
        raw_pid=data.get('NewProcessId') or data.get('ProcessId'); pid=None
        try: pid=int(str(raw_pid),0) if raw_pid else None
        except Exception: pass
        return {'source':'windows_eventlog','channel':'Security','event_id':eid,'kind':'process_create','time':_event_time(item.get('time')),
                'pid':pid,'image':data.get('NewProcessName'),'parent_image':data.get('ParentProcessName'),
                'command_line':_redact_text(data.get('CommandLine') or data.get('ProcessCommandLine') or ''),'raw':_redact_obj(data)}
    kind={4697:'service_install',4698:'scheduled_task_create',4702:'scheduled_task_update',4720:'user_account_create',4732:'local_group_member_add',1102:'audit_log_cleared'}.get(eid,'windows_security_event')
    return {'source':'windows_eventlog','channel':'Security','event_id':eid,'kind':kind,'time':_event_time(item.get('time')),
            'message':_redact_text(item.get('message') or ''),'raw':_redact_obj(data)}


def collect_windows_eventlog(minutes: int=10,max_events: int=250,include_security: bool=True) -> dict:
    if platform.system()!='Windows': return {'ok':False,'available':False,'reason':'Windows only','events':[]}
    events=[]; errors=[]
    for channel in [SYSMON_CHANNEL]+([WINDOWS_SECURITY_CHANNEL] if include_security else []):
        res=_run(['powershell','-NoProfile','-Command',_powershell_event_script(channel,minutes,max_events)],20)
        if not res.get('ok'):
            errors.append({'channel':channel,'error':res.get('error') or res.get('stderr') or 'unavailable'}); continue
        parsed=_safe_json(res.get('stdout','')) or []
        if isinstance(parsed,dict): parsed=[parsed]
        for item in parsed:
            if channel==SYSMON_CHANNEL:
                events.append(normalize_sysmon_event(item))
            else:
                events.append(normalize_windows_security_event(item))
    events.sort(key=lambda x:str(x.get('time') or ''))
    return {'ok':bool(events) or not errors,'available':True,'events':events[-max_events:],'errors':errors,
            'note':'Windows Security log access may require elevation; Sysmon must be installed/configured separately.'}


_AUDIT_EVENT_RE=re.compile(r'msg=audit\((?P<ts>[0-9.]+):(?P<serial>\d+)\)')
_AUDIT_FIELD_RE=re.compile(r'([A-Za-z_][A-Za-z0-9_]*)=("(?:[^"\\]|\\.)*"|\S+)')


def parse_auditd_text(text: str,limit: int=500) -> list[dict]:
    groups=defaultdict(list)
    for line in text.splitlines():
        m=_AUDIT_EVENT_RE.search(line)
        if not m: continue
        groups[m.group('serial')].append(line.strip())
    out=[]
    for serial,lines in list(groups.items())[-limit:]:
        fields={}; types=[]; ts=None
        for line in lines:
            mm=_AUDIT_EVENT_RE.search(line)
            if mm and ts is None:
                try: ts=dt.datetime.fromtimestamp(float(mm.group('ts')),tz=dt.timezone.utc).isoformat()
                except Exception: ts=None
            tm=re.search(r'\btype=([A-Z0-9_]+)',line)
            if tm: types.append(tm.group(1))
            for k,v in _AUDIT_FIELD_RE.findall(line):
                if v.startswith('"') and v.endswith('"'):
                    try: v=bytes(v[1:-1],'utf-8').decode('unicode_escape')
                    except Exception: v=v[1:-1]
                fields.setdefault(k,v)
        exe=fields.get('exe') or fields.get('comm'); pid=fields.get('pid'); ppid=fields.get('ppid')
        try: pid=int(pid) if pid else None
        except Exception: pid=None
        try: ppid=int(ppid) if ppid else None
        except Exception: ppid=None
        out.append({'source':'auditd','kind':'linux_audit','event_id':serial,'time':ts or _now(),'types':sorted(set(types)),
                    'pid':pid,'ppid':ppid,'image':exe,'command_line':_redact_text(fields.get('cmd') or fields.get('proctitle') or ''),
                    'path':fields.get('name'),'syscall':fields.get('syscall'),'success':fields.get('success'),
                    'raw':_redact_obj({k:v for k,v in fields.items() if k not in {'cmd','proctitle'}})})
    return out


def collect_linux_audit(minutes: int=10,max_events: int=250) -> dict:
    if platform.system()!='Linux': return {'ok':False,'available':False,'reason':'Linux only','events':[]}
    if shutil.which('ausearch'):
        # `recent` is intentionally bounded by the audit utility and avoids reading the entire log.
        res=_run(['ausearch','-ts','recent','-i'],15)
        if res.get('ok') or res.get('returncode')==1:
            return {'ok':True,'available':True,'provider':'ausearch','events':parse_auditd_text(res.get('stdout',''),max_events),
                    'stderr':_redact_text(res.get('stderr','')[-2000:])}
        return {'ok':False,'available':True,'provider':'ausearch','events':[],'error':_redact_text(res.get('stderr') or res.get('error') or '')}
    if shutil.which('journalctl'):
        res=_run(['journalctl','--since',f'-{max(1,int(minutes))} min','_TRANSPORT=audit','--no-pager','-o','cat'],12)
        return {'ok':res.get('ok',False),'available':True,'provider':'journald-audit','events':parse_auditd_text(res.get('stdout',''),max_events),
                'error':_redact_text(res.get('stderr') or '')}
    return {'ok':False,'available':False,'events':[],'reason':'auditd/ausearch telemetry is unavailable.'}


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


def _read_jsonl(path: Path,max_lines: int=500) -> list[dict]:
    if not path.exists() or not path.is_file(): return []
    try:
        lines=path.read_text(encoding='utf-8',errors='replace').splitlines()[-max_lines:]
    except Exception:
        return []
    out=[]
    for line in lines:
        x=_safe_json(line)
        if isinstance(x,dict): out.append(_redact_obj(x))
    return out


def dns_events_from(events: Iterable[dict]) -> list[dict]:
    out=[]
    for e in events:
        if e.get('kind')=='dns_query' and e.get('query_name'):
            out.append({'time':e.get('time'),'pid':e.get('pid'),'process':e.get('image'),'query':str(e.get('query_name')).rstrip('.').lower(),
                        'results':e.get('query_results'),'source':e.get('source')})
        elif e.get('kind') in {'dns','dns_query'} and e.get('query'):
            out.append({'time':e.get('time'),'pid':e.get('pid'),'process':e.get('process'),'query':str(e.get('query')).rstrip('.').lower(),
                        'results':e.get('results'),'source':e.get('source')})
    return out


def _looks_algorithmic_domain(name: str) -> bool:
    label=(name.split('.',1)[0] if name else '').lower()
    if len(label)<16: return False
    if not re.fullmatch(r'[a-z0-9-]+',label): return False
    counts=Counter(label.replace('-',''))
    n=sum(counts.values()) or 1
    entropy=-sum((c/n)*math.log2(c/n) for c in counts.values())
    digit_ratio=sum(ch.isdigit() for ch in label)/max(1,len(label))
    return entropy>=3.4 and (digit_ratio>=0.15 or len(label)>=24)


def summarize_dns(events: Iterable[dict]) -> dict:
    rows=dns_events_from(events); domains=Counter(x['query'] for x in rows)
    suspicious=[d for d in domains if _looks_algorithmic_domain(d)]
    return {'count':len(rows),'unique_domains':len(domains),'top_domains':domains.most_common(25),'algorithmic_candidates':suspicious[:50],
            'events':rows[-200:],'note':'Algorithmic-looking names are heuristic signals, not proof of malicious DNS.'}


def correlate_security_events(events: Iterable[dict]) -> list[dict]:
    rows=sorted(list(events),key=lambda e:str(e.get('time') or ''))
    by_guid=defaultdict(list); by_pid=defaultdict(list)
    for e in rows:
        if e.get('process_guid'): by_guid[str(e['process_guid'])].append(e)
        if e.get('pid') is not None: by_pid[str(e['pid'])].append(e)
    groups=list(by_guid.values()) + [v for k,v in by_pid.items() if not any(str(x.get('pid'))==k for g in by_guid.values() for x in g)]
    findings=[]
    office={'winword.exe','excel.exe','powerpnt.exe','outlook.exe'}
    script={'powershell.exe','pwsh.exe','cmd.exe','wscript.exe','cscript.exe','mshta.exe','rundll32.exe','regsvr32.exe'}
    for g in groups:
        kinds={x.get('kind') for x in g}; creates=[x for x in g if x.get('kind')=='process_create']
        for c in creates:
            name=Path(str(c.get('image') or '')).name.lower(); parent=Path(str(c.get('parent_image') or '')).name.lower()
            signals=[]; score=0
            if parent in office and name in script: signals.append('office_to_script_interpreter'); score+=55
            if name in {'powershell.exe','pwsh.exe','powershell','pwsh'} and re.search(r'(?i)(?:^|\s)-(?:enc|encodedcommand)(?:\s|$)',str(c.get('command_line') or '')):
                signals.append('encoded_powershell'); score+=45
            if 'dns_query' in kinds: signals.append('dns_activity'); score+=10
            if 'network_connect' in kinds: signals.append('network_activity'); score+=10
            if kinds & {'registry_create_delete','registry_value_set','wmi_filter','wmi_consumer','wmi_binding'}: signals.append('persistence_related_activity'); score+=15
            if kinds & {'remote_thread','process_tampering'}: signals.append('process_injection_or_tampering'); score+=50
            if score>=60:
                findings.append({'kind':'correlated_execution_chain','severity':'critical' if score>=90 else 'high','score':min(score,100),
                                 'title':f'Suspicious execution chain involving {name or "process"}','signals':signals,
                                 'pid':c.get('pid'),'process_guid':c.get('process_guid'),'image':c.get('image'),'parent_image':c.get('parent_image'),
                                 'event_kinds':sorted(x for x in kinds if x)})
    return findings


def usb_inventory() -> dict:
    osname=platform.system(); devices=[]; errors=[]
    if osname=='Windows':
        script="Get-PnpDevice -PresentOnly | Where-Object {$_.InstanceId -like 'USB*'} | Select Class,FriendlyName,InstanceId,Status | ConvertTo-Json -Depth 4"
        r=_run(['powershell','-NoProfile','-Command',script],12)
        parsed=_safe_json(r.get('stdout','')) if r.get('ok') else None
        if isinstance(parsed,dict): parsed=[parsed]
        if isinstance(parsed,list): devices=parsed
        elif not r.get('ok'): errors.append(r.get('error') or r.get('stderr'))
    elif osname=='Darwin':
        r=_run(['system_profiler','SPUSBDataType','-json'],15)
        parsed=_safe_json(r.get('stdout','')) if r.get('ok') else None
        def walk(x):
            if isinstance(x,dict):
                if any(k in x for k in ('vendor_id','product_id','serial_num')):
                    devices.append({k:x.get(k) for k in ('_name','vendor_id','product_id','serial_num','manufacturer') if x.get(k) is not None})
                for v in x.values(): walk(v)
            elif isinstance(x,list):
                for v in x: walk(v)
        if parsed: walk(parsed)
        elif not r.get('ok'): errors.append(r.get('error') or r.get('stderr'))
    else:
        if shutil.which('lsusb'):
            r=_run(['lsusb'],8)
            for line in r.get('stdout','').splitlines():
                m=re.match(r'Bus\s+(\d+) Device\s+(\d+): ID\s+([0-9a-fA-F:]+)\s*(.*)',line)
                if m: devices.append({'bus':m.group(1),'device':m.group(2),'id':m.group(3).lower(),'name':m.group(4).strip()})
            if not r.get('ok'): errors.append(r.get('error') or r.get('stderr'))
        else:
            base=Path('/sys/bus/usb/devices')
            if base.exists():
                for p in sorted(base.iterdir()):
                    try:
                        vid=(p/'idVendor').read_text().strip(); pid=(p/'idProduct').read_text().strip()
                    except Exception: continue
                    def rd(n):
                        try: return (p/n).read_text(errors='replace').strip()
                        except Exception: return None
                    devices.append({'id':f'{vid}:{pid}','name':rd('product'),'manufacturer':rd('manufacturer'),'serial':rd('serial')})
    norm=sorted((_redact_obj(x) for x in devices),key=lambda x:json.dumps(x,sort_keys=True,default=str))
    return {'os':osname,'devices':norm,'count':len(norm),'fingerprint':hashlib.sha256(json.dumps(norm,sort_keys=True,default=str).encode()).hexdigest(),'errors':[x for x in errors if x]}


def _chromium_extension_roots() -> list[Path]:
    home=Path.home(); osname=platform.system(); roots=[]
    if osname=='Windows':
        local=Path(os.environ.get('LOCALAPPDATA',home/'AppData/Local'))
        for vendor in ['Google/Chrome/User Data','Microsoft/Edge/User Data','BraveSoftware/Brave-Browser/User Data']:
            roots.append(local/vendor)
    elif osname=='Darwin':
        for vendor in ['Google/Chrome','Microsoft Edge','BraveSoftware/Brave-Browser']:
            roots.append(home/'Library/Application Support'/vendor)
    else:
        for vendor in ['google-chrome','chromium','microsoft-edge','BraveSoftware/Brave-Browser']:
            roots.append(home/'.config'/vendor)
    return roots


def browser_extension_inventory(max_profiles: int=20,max_extensions: int=1000) -> dict:
    rows=[]; home=Path.home()
    for root in _chromium_extension_roots():
        if not root.exists(): continue
        profiles=[p for p in root.iterdir() if p.is_dir() and (p.name=='Default' or p.name.startswith('Profile'))][:max_profiles]
        for profile in profiles:
            extroot=profile/'Extensions'
            if not extroot.exists(): continue
            for extid in extroot.iterdir():
                if len(rows)>=max_extensions or not extid.is_dir(): break
                versions=sorted([p for p in extid.iterdir() if p.is_dir()],reverse=True)
                if not versions: continue
                manifest=versions[0]/'manifest.json'
                try: data=json.loads(manifest.read_text(encoding='utf-8',errors='replace'))
                except Exception: data={}
                perms=(data.get('permissions') or [])+(data.get('host_permissions') or [])
                rows.append({'browser_root':str(root),'profile':profile.name,'id':extid.name,'name':data.get('name'),
                             'version':data.get('version'),'permissions':sorted(str(x) for x in perms)[:100],
                             'manifest_sha256':sha256_file(manifest) if manifest.exists() else None})
    # Firefox exposes extension metadata in extensions.json; do not read browsing history/cookies.
    ffbase=(Path(os.environ.get('APPDATA',home/'AppData/Roaming'))/'Mozilla/Firefox/Profiles' if platform.system()=='Windows'
            else home/'Library/Application Support/Firefox/Profiles' if platform.system()=='Darwin'
            else home/'.mozilla/firefox')
    if ffbase.exists():
        for profile in list(ffbase.iterdir())[:max_profiles]:
            p=profile/'extensions.json'
            if not p.exists(): continue
            try: data=json.loads(p.read_text(encoding='utf-8',errors='replace'))
            except Exception: continue
            for addon in data.get('addons',[])[:max_extensions-len(rows)]:
                if addon.get('type')!='extension': continue
                rows.append({'browser_root':'firefox','profile':profile.name,'id':addon.get('id'),'name':addon.get('defaultLocale',{}).get('name'),
                             'version':addon.get('version'),'active':addon.get('active'),'signedState':addon.get('signedState')})
    rows=sorted(rows,key=lambda x:(str(x.get('browser_root')),str(x.get('profile')),str(x.get('id'))))[:max_extensions]
    return {'extensions':rows,'count':len(rows),'fingerprint':hashlib.sha256(json.dumps(rows,sort_keys=True,default=str).encode()).hexdigest(),
            'note':'Only extension manifests/metadata are inspected; browsing history, cookies and page content are not read.'}


def _manifest_for_path(root: Path,max_files: int=5000,max_file_mb: int=128) -> dict:
    files={}; total=0; skipped=0
    if not root.exists(): return {'missing':True,'files':{},'file_count':0,'total_bytes':0}
    iterator=[root] if root.is_file() else root.rglob('*')
    for p in iterator:
        if len(files)>=max_files: break
        try:
            if p.is_symlink():
                rel=str(p.relative_to(root.parent if root.is_file() else root)); target=os.readlink(p)
                files[rel]={'symlink':target}; continue
            if not p.is_file(): continue
            size=p.stat().st_size
            if size>max_file_mb*1024*1024: skipped+=1; continue
            rel=str(p.relative_to(root.parent if root.is_file() else root)); files[rel]={'sha256':sha256_file(p),'bytes':size}; total+=size
        except (OSError,PermissionError): skipped+=1
    root_hash=hashlib.sha256(json.dumps(files,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return {'missing':False,'files':files,'file_count':len(files),'total_bytes':total,'root_hash':root_hash,'skipped':skipped,'truncated':len(files)>=max_files}


@dataclass
class RansomwareBehaviorDetector:
    window_seconds: int = 20
    file_threshold: int = 80
    directory_threshold: int = 5

    def __post_init__(self):
        self.events=deque()

    def observe(self,file_events: Iterable[dict],now: float|None=None) -> dict:
        now=float(now or time.time())
        for e in file_events:
            if e.get('kind') not in {'file_added','file_changed','file_removed'}: continue
            self.events.append((now,e.get('kind'),str(e.get('path') or '')))
        while self.events and now-self.events[0][0]>self.window_seconds: self.events.popleft()
        rows=list(self.events); paths={x[2] for x in rows if x[2]}; dirs={str(Path(p).parent) for p in paths}; kinds=Counter(x[1] for x in rows)
        suffixes=Counter(Path(p).suffix.lower() for p in paths if Path(p).suffix)
        signals=[]; score=0
        if len(paths)>=self.file_threshold: signals.append('mass_file_change'); score+=45
        if len(dirs)>=self.directory_threshold and len(paths)>=self.file_threshold: signals.append('multi_directory_spread'); score+=25
        if kinds.get('file_removed',0)>=max(20,self.file_threshold//3): signals.append('mass_file_removal'); score+=25
        if len(suffixes)>=8 and len(paths)>=self.file_threshold: signals.append('many_file_types_affected'); score+=10
        severity='critical' if score>=80 else 'high' if score>=60 else 'medium' if score>=40 else 'none'
        return {'score':min(score,100),'severity':severity,'signals':signals,'events_in_window':len(rows),'unique_files':len(paths),'directories':len(dirs),
                'kinds':dict(kinds),'top_extensions':suffixes.most_common(15),'note':'Burst detection is heuristic and does not by itself prove ransomware.'}


class SecuritySensorPlatform:
    def __init__(self, config: dict, approval=None, guardian=None, db_path: Path|None=None):
        self.config=config; self.cfg=config.get('security_sensors',{}); self.approval=approval; self.guardian=guardian
        self.db_path=db_path or (data_dir()/'assistant.sqlite3'); self.conn=ThreadLocalSQLite(self.db_path); self.conn.executescript(SENSOR_SCHEMA); self.conn.commit()
        r=self.cfg.get('ransomware',{})
        self.ransomware=RansomwareBehaviorDetector(int(r.get('window_seconds',20)),int(r.get('file_threshold',80)),int(r.get('directory_threshold',5)))

    def _state_get(self,key,default=None):
        row=self.conn.execute('SELECT value FROM sensor_state WHERE key=?',(key,)).fetchone()
        if not row: return default
        try: return json.loads(row[0])
        except Exception: return default

    def _state_set(self,key,value):
        self.conn.execute('INSERT INTO sensor_state(key,value,updated_at) VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at',
                          (key,json.dumps(value,default=str),_now())); self.conn.commit()

    def status(self) -> dict:
        osname=platform.system(); tls_path=self.cfg.get('tls_context_jsonl') or os.environ.get('LIVING_ASSISTANT_TLS_SENSOR_JSONL','')
        return {'enabled':bool(self.cfg.get('enabled',True)),'os':osname,
                'windows_eventlog':osname=='Windows','sysmon_channel':SYSMON_CHANNEL if osname=='Windows' else None,
                'linux_auditd':osname=='Linux' and bool(shutil.which('ausearch') or shutil.which('journalctl')),
                'macos_endpoint_security_helper':osname=='Darwin' and bool(self.cfg.get('macos_endpoint_security_jsonl')),
                'yara':bool(self._yara_backend()),'dns_context_source':str(self.cfg.get('dns_context_jsonl') or os.environ.get('LIVING_ASSISTANT_DNS_SENSOR_JSONL','')) or None,'tls_context_source':str(tls_path) if tls_path else None,
                'reputation_provider':'virustotal' if os.environ.get('VIRUSTOTAL_API_KEY') else None,
                'network_isolated':bool(self._state_get('network_isolation')),
                'auto_isolation_enabled':bool((self.cfg.get('network_isolation') or {}).get('auto_enabled',False)),
                'auto_isolation_armed':bool((self.cfg.get('network_isolation') or {}).get('auto_armed',False))}

    def collect_events(self,minutes: int|None=None,max_events: int|None=None) -> dict:
        minutes=int(minutes or self.cfg.get('event_lookback_minutes',10)); max_events=int(max_events or self.cfg.get('max_events_per_scan',250)); osname=platform.system()
        if osname=='Windows': base=collect_windows_eventlog(minutes,max_events,True)
        elif osname=='Linux': base=collect_linux_audit(minutes,max_events)
        elif osname=='Darwin': base=collect_macos_unified_log(minutes,max_events)
        else: base={'ok':False,'available':False,'events':[],'reason':'Unsupported platform'}
        # An entitled/native macOS ES helper may append normalized JSONL events. Python never pretends to provide the entitlement itself.
        helper=self.cfg.get('macos_endpoint_security_jsonl')
        if osname=='Darwin' and helper:
            rows=_read_jsonl(Path(helper).expanduser(),max_events)
            for x in rows:
                x.setdefault('source','macos_endpoint_security'); x.setdefault('kind','endpoint_security_event'); x.setdefault('time',_now())
            base.setdefault('events',[]).extend(rows)
        return base

    def dns_context(self,minutes: int|None=None,limit: int=250) -> dict:
        result=self.collect_events(minutes,max_events=limit); events=list(result.get('events',[]))
        raw=self.cfg.get('dns_context_jsonl') or os.environ.get('LIVING_ASSISTANT_DNS_SENSOR_JSONL','')
        if raw:
            for x in _read_jsonl(Path(raw).expanduser(),limit):
                q=x.get('query') or x.get('query_name')
                if q: events.append({'source':x.get('source') or 'local_dns_collector','kind':'dns_query','time':x.get('time') or _now(),
                                     'pid':x.get('pid'),'image':x.get('process'),'query_name':q,'query_results':x.get('results')})
        summary=summarize_dns(events)
        summary.update({'ok':True,'collector_available':bool(summary.get('count')) or bool(raw) or platform.system()=='Windows',
                        'external_collector':str(raw) if raw else None})
        return summary

    def correlations(self,minutes: int|None=None) -> dict:
        result=self.collect_events(minutes); events=list(result.get('events',[]))
        raw_dns=self.cfg.get('dns_context_jsonl') or os.environ.get('LIVING_ASSISTANT_DNS_SENSOR_JSONL','')
        if raw_dns:
            for x in _read_jsonl(Path(raw_dns).expanduser(),int(self.cfg.get('max_events_per_scan',250))):
                q=x.get('query') or x.get('query_name')
                if q: events.append({'source':x.get('source') or 'local_dns_collector','kind':'dns_query','time':x.get('time') or _now(),'pid':x.get('pid'),'image':x.get('process'),'query_name':q,'query_results':x.get('results')})
        findings=correlate_security_events(events); dns=summarize_dns(events)
        ransomware_events=[]
        for e in events:
            if e.get('kind')=='file_create': ransomware_events.append({'kind':'file_changed','path':e.get('path')})
            elif e.get('kind')=='file_delete': ransomware_events.append({'kind':'file_removed','path':e.get('path')})
        burst=self.observe_file_events(ransomware_events) if ransomware_events else {'score':0,'signals':[]}
        if self.guardian:
            for x in findings:
                self.guardian.record_finding(x['kind'],x['severity'],x['title'],{**x,'key':f"{x.get('process_guid') or x.get('pid')}:{','.join(x.get('signals',[]))}"})
            for d in dns.get('algorithmic_candidates',[]):
                self.guardian.record_finding('algorithmic_dns','medium','Algorithmic-looking DNS query observed',{'domain':d,'key':d})
        auto_isolation=None
        if burst.get('score',0)>=60 and self.guardian:
            malicious=any(f.get('kind')=='known_malicious_hash' for f in self.guardian.findings('open',200))
            if malicious:
                auto_isolation=self.isolate_network(True,{'signals':list(set(burst.get('signals',[]))|{'known_malicious_hash'})})
        return {'collector':{k:v for k,v in result.items() if k!='events'},'event_count':len(events),'correlations':findings,'dns':dns,'ransomware':burst,'auto_isolation':auto_isolation}

    def tls_context(self,limit: int=250) -> dict:
        raw=self.cfg.get('tls_context_jsonl') or os.environ.get('LIVING_ASSISTANT_TLS_SENSOR_JSONL','')
        if not raw: return {'ok':False,'available':False,'events':[],'reason':'No local TLS metadata collector configured.'}
        rows=[]
        for x in _read_jsonl(Path(raw).expanduser(),limit):
            rows.append({k:x.get(k) for k in ('time','pid','process','remote_ip','remote_port','server_name','tls_version','ja3','source') if x.get(k) is not None})
        return {'ok':True,'available':True,'events':rows,'count':len(rows),
                'note':'SNI is reported only when the configured local collector can observe it; ECH may intentionally hide server names.'}

    def _yara_backend(self):
        try:
            import yara  # type: ignore
            return ('python',yara)
        except Exception:
            if shutil.which('yara'): return ('cli',None)
        return None

    def yara_scan(self,path: str|Path,rules: list[str]|None=None) -> dict:
        p=Path(path).expanduser().resolve()
        if not p.exists(): return {'ok':False,'error':'Path not found.'}
        if self.approval is not None:
            req=self.approval.request(f'YARA scan: {p}','Read local file content and match configured defensive YARA rules.','SECURITY_YARA_SCAN')
            if not req.get('allowed'): return {'ok':False,'approval_required':True,**req}
        configured=[str(x) for x in (rules or self.cfg.get('yara_rules',[]) or [])]
        rule_paths=[Path(x).expanduser().resolve() for x in configured if Path(x).expanduser().exists()]
        if not rule_paths: return {'ok':False,'error':'No local YARA rule files are configured.'}
        backend=self._yara_backend()
        if not backend: return {'ok':False,'error':'Install yara-python or the yara CLI to enable scanning.'}
        matches=[]
        if backend[0]=='python':
            yara=backend[1]; filepaths={f'r{i}':str(rp) for i,rp in enumerate(rule_paths)}
            compiled=yara.compile(filepaths=filepaths)
            targets=[p] if p.is_file() else [x for x in p.rglob('*') if x.is_file()][:int(self.cfg.get('yara_max_files',500))]
            for target in targets:
                try:
                    ms=compiled.match(str(target),timeout=int(self.cfg.get('yara_timeout_seconds',10)))
                    if ms: matches.append({'path':str(target),'matches':[str(m) for m in ms]})
                except Exception as exc: matches.append({'path':str(target),'error':_redact_text(str(exc))})
        else:
            if len(rule_paths)!=1: return {'ok':False,'error':'The yara CLI backend currently supports one rule file per scan.'}
            args=['yara','-r',str(rule_paths[0]),str(p)] if p.is_dir() else ['yara',str(rule_paths[0]),str(p)]
            res=_run(args,float(self.cfg.get('yara_timeout_seconds',30))); 
            for line in res.get('stdout','').splitlines():
                parts=line.split(' ',1)
                if len(parts)==2: matches.append({'rule':parts[0],'path':parts[1]})
            if not res.get('ok') and res.get('returncode') not in {0,1}: return {'ok':False,'error':_redact_text(res.get('stderr') or res.get('error') or '')}
        return {'ok':True,'backend':backend[0],'matches':matches,'match_count':len(matches)}

    def reputation_hash(self,sha256: str) -> dict:
        digest=str(sha256).strip().lower()
        if not re.fullmatch(r'[0-9a-f]{64}',digest): return {'ok':False,'error':'A SHA-256 hash is required.'}
        key=os.environ.get('VIRUSTOTAL_API_KEY')
        if not key: return {'ok':False,'available':False,'error':'VIRUSTOTAL_API_KEY is not configured.'}
        try:
            with httpx.Client(timeout=12,trust_env=False,follow_redirects=False,headers={'x-apikey':key}) as c:
                r=c.get(f'https://www.virustotal.com/api/v3/files/{digest}')
            if r.status_code==404: return {'ok':True,'found':False,'sha256':digest}
            if r.status_code!=200: return {'ok':False,'error':f'Reputation provider HTTP {r.status_code}'}
            attrs=(r.json().get('data') or {}).get('attributes') or {}; stats=attrs.get('last_analysis_stats') or {}
            result={'ok':True,'found':True,'sha256':digest,'stats':stats,'reputation':attrs.get('reputation'),'type_description':attrs.get('type_description'),
                    'last_analysis_date':attrs.get('last_analysis_date'),'note':'Only the file hash is sent; the file itself is never uploaded.'}
            if self.guardian and int(stats.get('malicious') or 0)>=int(self.cfg.get('reputation_malicious_threshold',5)):
                self.guardian.record_finding('known_malicious_hash','critical','Reputation provider reports file hash as malicious',{'sha256':digest,'stats':stats,'key':digest})
            return result
        except Exception as exc:
            return {'ok':False,'error':_redact_text(str(exc))}

    def reputation_file(self,path: str|Path) -> dict:
        p=Path(path).expanduser().resolve()
        if not p.is_file(): return {'ok':False,'error':'File not found.'}
        return self.reputation_hash(sha256_file(p))

    def reputation_process(self,pid: int) -> dict:
        try:
            import psutil
            p=psutil.Process(int(pid)); exe=p.exe()
        except Exception as exc:
            return {'ok':False,'error':_redact_text(str(exc))}
        result=self.reputation_file(exe); result['pid']=int(pid); result['process_path']=exe
        return result

    @staticmethod
    def _signature_fields(sig: dict) -> tuple[str|None,str|None]:
        raw=(sig.get('signature') or {}) if isinstance(sig,dict) else {}
        parsed=_safe_json(raw.get('stdout','')) if isinstance(raw,dict) else None
        if isinstance(parsed,dict):
            signer=((parsed.get('SignerCertificate') or {}).get('Subject') if isinstance(parsed.get('SignerCertificate'),dict) else None)
            return str(parsed.get('Status') or '') or None, signer
        if platform.system()=='Darwin' and isinstance(raw,dict):
            text=(raw.get('stderr') or '')+'\n'+(raw.get('stdout') or '')
            auth=re.search(r'Authority=([^\n]+)',text)
            return ('valid' if raw.get('ok') else 'unknown'), (auth.group(1).strip() if auth else None)
        owner=sig.get('package_owner') if isinstance(sig,dict) else None
        if isinstance(owner,dict) and owner.get('ok'): return 'package_owned',str(owner.get('stdout','')).strip()[:500]
        return None,None

    def assess_binary(self,path: str|Path) -> dict:
        p=Path(path).expanduser().resolve(); sig=file_signature(p)
        if not sig.get('ok'): return sig
        status,signer=self._signature_fields(sig); row=self.conn.execute('SELECT * FROM binary_trust WHERE path=?',(str(p),)).fetchone(); changes=[]
        if row:
            old=dict(row)
            if old.get('sha256')!=sig.get('sha256'): changes.append('hash_changed')
            if old.get('signer') and signer and old.get('signer')!=signer: changes.append('signer_changed')
            if old.get('signature_status') and status and old.get('signature_status')!=status: changes.append('signature_status_changed')
        return {'ok':True,'path':str(p),'sha256':sig.get('sha256'),'signature_status':status,'signer':signer,'trusted':bool(row),'changes':changes,
                'trust_record':dict(row) if row else None,'signature':sig}

    def trust_binary(self,path: str|Path,label: str='trusted') -> dict:
        p=Path(path).expanduser().resolve(); assessment=self.assess_binary(p)
        if not assessment.get('ok'): return assessment
        if self.approval is not None:
            req=self.approval.request(f'Trust binary: {p}',f"Record hash/signature of {p} as a local trust reference ({label}).",'SECURITY_BASELINE_CHANGE')
            if not req.get('allowed'): return {'ok':False,'approval_required':True,**req}
        now=_now(); self.conn.execute('INSERT INTO binary_trust(path,sha256,signer,signature_status,label,first_seen,last_seen) VALUES(?,?,?,?,?,?,?) ON CONFLICT(path) DO UPDATE SET sha256=excluded.sha256,signer=excluded.signer,signature_status=excluded.signature_status,label=excluded.label,last_seen=excluded.last_seen',
                    (str(p),assessment['sha256'],assessment.get('signer'),assessment.get('signature_status'),label,now,now)); self.conn.commit()
        return {'ok':True,'path':str(p),'sha256':assessment['sha256'],'label':label}

    def check_trusted_binaries(self) -> dict:
        rows=self.conn.execute('SELECT * FROM binary_trust ORDER BY path').fetchall(); changed=[]; missing=[]
        for row in rows:
            old=dict(row); p=Path(old['path'])
            if not p.exists(): missing.append({'path':str(p),'label':old.get('label')}); continue
            cur=self.assess_binary(p)
            if cur.get('changes'): changed.append(cur)
        return {'ok':True,'count':len(rows),'changed':changed,'missing':missing}

    def capture_usb_baseline(self) -> dict:
        inv=usb_inventory()
        if self.approval is not None:
            req=self.approval.request('Capture USB-device baseline','Treat currently attached USB devices as the local trusted reference.','SECURITY_BASELINE_CHANGE')
            if not req.get('allowed'): return {'ok':False,'approval_required':True,**req}
        self._state_set('usb_baseline',inv.get('devices',[])); return {'ok':True,**inv}

    def check_usb(self) -> dict:
        inv=usb_inventory(); baseline=self._state_get('usb_baseline')
        if baseline is None: return {'ok':True,'baseline_missing':True,**inv,'new':[],'removed':[]}
        key=lambda x:hashlib.sha256(json.dumps(x,sort_keys=True,default=str).encode()).hexdigest()
        b={key(x):x for x in baseline}; c={key(x):x for x in inv.get('devices',[])}
        return {'ok':True,**inv,'baseline_missing':False,'new':[c[k] for k in c.keys()-b.keys()],'removed':[b[k] for k in b.keys()-c.keys()]}

    def capture_extension_baseline(self) -> dict:
        inv=browser_extension_inventory()
        if self.approval is not None:
            req=self.approval.request('Capture browser-extension baseline','Treat current extension metadata as the trusted local reference.','SECURITY_BASELINE_CHANGE')
            if not req.get('allowed'): return {'ok':False,'approval_required':True,**req}
        self._state_set('browser_extension_baseline',inv.get('extensions',[])); return {'ok':True,**inv}

    def check_extensions(self) -> dict:
        inv=browser_extension_inventory(); baseline=self._state_get('browser_extension_baseline')
        if baseline is None: return {'ok':True,'baseline_missing':True,**inv,'new':[],'changed':[],'removed':[]}
        def ident(x): return f"{x.get('browser_root')}|{x.get('profile')}|{x.get('id')}"
        b={ident(x):x for x in baseline}; c={ident(x):x for x in inv.get('extensions',[])}
        new=[c[k] for k in c.keys()-b.keys()]; removed=[b[k] for k in b.keys()-c.keys()]; changed=[]
        for k in b.keys()&c.keys():
            if b[k].get('version')!=c[k].get('version') or b[k].get('manifest_sha256')!=c[k].get('manifest_sha256') or b[k].get('permissions')!=c[k].get('permissions'):
                changed.append({'before':b[k],'after':c[k]})
        return {'ok':True,**inv,'baseline_missing':False,'new':new,'changed':changed,'removed':removed}

    def capture_backup_baseline(self,name: str,path: str|Path) -> dict:
        p=Path(path).expanduser().resolve(); manifest=_manifest_for_path(p,int(self.cfg.get('backup_max_files',5000)),int(self.cfg.get('backup_max_file_mb',128)))
        if self.approval is not None:
            req=self.approval.request(f'Capture backup baseline: {name}',f'Treat the current backup contents at {p} as the integrity reference.','SECURITY_BASELINE_CHANGE')
            if not req.get('allowed'): return {'ok':False,'approval_required':True,**req}
        now=_now(); self.conn.execute('INSERT INTO backup_baselines(name,path,manifest,created_at,updated_at) VALUES(?,?,?,?,?) ON CONFLICT(name) DO UPDATE SET path=excluded.path,manifest=excluded.manifest,updated_at=excluded.updated_at',
                    (name,str(p),json.dumps(manifest),now,now)); self.conn.commit(); return {'ok':True,'name':name,'path':str(p),**{k:v for k,v in manifest.items() if k!='files'}}

    def list_backup_baselines(self) -> list[dict]:
        out=[]
        for r in self.conn.execute('SELECT name,path,manifest,created_at,updated_at FROM backup_baselines ORDER BY name').fetchall():
            x=dict(r); m=_safe_json(x.pop('manifest')) or {}; x.update({k:v for k,v in m.items() if k!='files'}); out.append(x)
        return out

    def check_backup_baseline(self,name: str) -> dict:
        row=self.conn.execute('SELECT * FROM backup_baselines WHERE name=?',(name,)).fetchone()
        if not row: return {'ok':False,'error':'Unknown backup baseline.'}
        old=_safe_json(row['manifest']) or {}; p=Path(row['path']); cur=_manifest_for_path(p,int(self.cfg.get('backup_max_files',5000)),int(self.cfg.get('backup_max_file_mb',128)))
        a=old.get('files',{}); b=cur.get('files',{}); added=sorted(b.keys()-a.keys()); removed=sorted(a.keys()-b.keys()); changed=sorted(k for k in a.keys()&b.keys() if a[k]!=b[k])
        severity='high' if cur.get('missing') or removed else 'medium' if changed else 'low'
        result={'ok':True,'name':name,'path':str(p),'missing':cur.get('missing',False),'root_hash_changed':old.get('root_hash')!=cur.get('root_hash'),
                'added':added[:200],'removed':removed[:200],'changed':changed[:200],'current_file_count':cur.get('file_count'),'severity':severity}
        if self.guardian and (result['missing'] or removed or changed):
            self.guardian.record_finding('backup_integrity_change',severity,'Backup integrity changed',{'baseline':name,'path':str(p),'removed':removed[:50],'changed':changed[:50],'key':name})
        return result

    def observe_file_events(self,events: Iterable[dict]) -> dict:
        result=self.ransomware.observe(events)
        if self.guardian and result.get('score',0)>=60:
            self.guardian.record_finding('ransomware_like_file_burst',result['severity'],'Ransomware-like file-change burst detected',{**result,'key':f"burst:{int(time.time()/self.ransomware.window_seconds)}"})
        return result

    def _network_isolation_commands(self,restore: bool=False):
        osname=platform.system(); state=self._state_get('network_isolation') or {}
        if osname=='Windows':
            if restore:
                names=state.get('adapters') or []
                if not names: return []
                arr=','.join("'"+str(n).replace("'","''")+"'" for n in names)
                return [['powershell','-NoProfile','-Command',f"@({arr}) | ForEach-Object {{ Enable-NetAdapter -Name $_ -Confirm:$false }}"]]
            script="Get-NetAdapter | Where-Object {$_.Status -eq 'Up' -and $_.HardwareInterface} | Select -ExpandProperty Name | ConvertTo-Json"
            probe=_run(['powershell','-NoProfile','-Command',script],8); parsed=_safe_json(probe.get('stdout','')) if probe.get('ok') else []
            names=[parsed] if isinstance(parsed,str) else (parsed or [])
            safe=[str(n) for n in names if n]
            if not safe: return ([],{})
            arr=','.join("'"+n.replace("'","''")+"'" for n in safe)
            return ([['powershell','-NoProfile','-Command',f"@({arr}) | ForEach-Object {{ Disable-NetAdapter -Name $_ -Confirm:$false }}"]],{'adapters':safe})
        if osname=='Linux' and shutil.which('nmcli'):
            return ([['nmcli','networking','off']],{'provider':'nmcli'}) if not restore else [['nmcli','networking','on']]
        if osname=='Darwin' and shutil.which('networksetup'):
            if restore:
                return [['networksetup','-setnetworkserviceenabled',x,'on'] for x in state.get('services',[])]
            r=_run(['networksetup','-listallnetworkservices'],8); services=[x.strip() for x in r.get('stdout','').splitlines() if x.strip() and not x.startswith('An asterisk') and not x.startswith('*')]
            return ([['networksetup','-setnetworkserviceenabled',x,'off'] for x in services],{'services':services})
        return [] if restore else ([],{})

    def isolate_network(self,automatic: bool=False,evidence: dict|None=None) -> dict:
        if self._state_get('network_isolation'): return {'ok':True,'already_isolated':True,'state':self._state_get('network_isolation')}
        ni=self.cfg.get('network_isolation') or {}
        if automatic:
            if not (bool(ni.get('auto_enabled',False)) and bool(ni.get('auto_armed',False))): return {'ok':False,'blocked':True,'error':'Automatic isolation is not armed.'}
            signals=set((evidence or {}).get('signals') or [])
            required=set(ni.get('auto_required_signals',['mass_file_change','known_malicious_hash']))
            if not required.issubset(signals): return {'ok':False,'blocked':True,'error':'Automatic isolation requires independent high-confidence signals.'}
        elif self.approval is not None:
            req=self.approval.request('Isolate this computer from the network','Disable active non-loopback network connectivity. This can interrupt remote sessions and requires administrator privileges.','SECURITY_NETWORK_ISOLATION')
            if not req.get('allowed'): return {'ok':False,'approval_required':True,**req}
        pair=self._network_isolation_commands(False)
        commands,state=pair if isinstance(pair,tuple) else (pair,{})
        if not commands: return {'ok':False,'error':'No supported reversible network-isolation backend is available.'}
        results=[]
        for cmd in commands:
            r=_run(cmd,20); results.append({'command':cmd[0],'ok':r.get('ok',False),'error':_redact_text(r.get('stderr') or r.get('error') or '')})
            if not r.get('ok'):
                partial=any(x['ok'] for x in results)
                if partial:
                    saved={'at':_now(),'os':platform.system(),'partial':True,**state}; self._state_set('network_isolation',saved)
                return {'ok':False,'partial':partial,'state':self._state_get('network_isolation'),'results':results,'error':'Network isolation command failed; verify privileges and connectivity. Restore networking if any interface/service was disabled.'}
        saved={'at':_now(),'os':platform.system(),**state}; self._state_set('network_isolation',saved)
        return {'ok':True,'isolated':True,'automatic':automatic,'state':saved,'results':results}

    def restore_network(self) -> dict:
        state=self._state_get('network_isolation')
        if not state: return {'ok':True,'already_restored':True}
        if self.approval is not None:
            req=self.approval.request('Restore network connectivity','Re-enable interfaces/services disabled by Living Assistant network isolation.','SECURITY_NETWORK_RESTORE')
            if not req.get('allowed'): return {'ok':False,'approval_required':True,**req}
        commands=self._network_isolation_commands(True)
        if not commands: return {'ok':False,'error':'No stored/supported network restore operation is available.'}
        results=[]; ok=True
        for cmd in commands:
            r=_run(cmd,20); ok=ok and bool(r.get('ok')); results.append({'command':cmd[0],'ok':r.get('ok',False),'error':_redact_text(r.get('stderr') or r.get('error') or '')})
        if ok: self.conn.execute('DELETE FROM sensor_state WHERE key=?',('network_isolation',)); self.conn.commit()
        return {'ok':ok,'restored':ok,'results':results}

    def periodic_scan(self,file_events: Iterable[dict]|None=None) -> list[dict]:
        emitted=[]
        corr=self.correlations()
        for x in corr.get('correlations',[]): emitted.append({'kind':'security_correlated_chain','severity':x.get('severity','high'),'title':x.get('title'),'signals':x.get('signals')})
        usb=self.check_usb()
        for x in usb.get('new',[]):
            if self.guardian:
                f=self.guardian.record_finding('new_usb_device','medium','New USB device detected',{'device':x,'key':hashlib.sha256(json.dumps(x,sort_keys=True,default=str).encode()).hexdigest()})
                if f.get('_new'): emitted.append({'kind':'security_new_usb','severity':'medium','finding_id':f.get('id'),'device':x})
        ext=self.check_extensions()
        for x in ext.get('new',[]):
            if self.guardian:
                f=self.guardian.record_finding('new_browser_extension','medium','New browser extension detected',{'extension':x,'key':f"{x.get('browser_root')}|{x.get('profile')}|{x.get('id')}"})
                if f.get('_new'): emitted.append({'kind':'security_new_browser_extension','severity':'medium','finding_id':f.get('id'),'extension':x})
        for x in ext.get('changed',[]):
            after=x.get('after') or {}; before=x.get('before') or {}; old=set(before.get('permissions') or []); new=set(after.get('permissions') or []); added=sorted(new-old)
            if added and self.guardian:
                f=self.guardian.record_finding('browser_extension_permissions_changed','high','Browser extension gained permissions',{'extension':after,'added_permissions':added,'key':f"{after.get('browser_root')}|{after.get('profile')}|{after.get('id')}"})
                if f.get('_new'): emitted.append({'kind':'security_extension_permissions','severity':'high','finding_id':f.get('id'),'added_permissions':added})
        for b in self.list_backup_baselines():
            check=self.check_backup_baseline(b['name'])
            if check.get('missing') or check.get('removed') or check.get('changed'):
                emitted.append({'kind':'security_backup_integrity','severity':check.get('severity','high'),'baseline':b['name'],'removed':check.get('removed',[])[:20],'changed':check.get('changed',[])[:20]})
        if file_events:
            burst=self.observe_file_events(file_events)
            if burst.get('score',0)>=60: emitted.append({'kind':'security_ransomware_like_burst','severity':burst.get('severity','high'),'signals':burst.get('signals'),'score':burst.get('score')})
        trusted=self.check_trusted_binaries()
        for x in trusted.get('changed',[]):
            if self.guardian:
                f=self.guardian.record_finding('trusted_binary_changed','high','Trusted binary changed',{'path':x.get('path'),'changes':x.get('changes'),'key':x.get('path')})
                if f.get('_new'): emitted.append({'kind':'security_trusted_binary_changed','severity':'high','finding_id':f.get('id'),'path':x.get('path'),'changes':x.get('changes')})
        return emitted
