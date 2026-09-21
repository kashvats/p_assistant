from __future__ import annotations

import platform

from living_assistant.security.security_guardian import _run, _redact_obj, _redact_text
from .sensor_shared import _safe_json, _event_time

SYSMON_CHANNEL = 'Microsoft-Windows-Sysmon/Operational'
WINDOWS_SECURITY_CHANNEL = 'Security'
HIGH_SIGNAL_SYSMON_IDS = {1,3,6,8,10,11,12,13,14,19,20,21,22,23,25,26,27,28,29}

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

