from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import datetime as dt
import hashlib
import ipaddress
import json
import os
import platform
import re
import shutil
import socket
import sqlite3
import subprocess
import uuid
from typing import Iterable

import psutil

from living_assistant.core.config import data_dir
from living_assistant.core.sqlite_utils import ThreadLocalSQLite
from living_assistant.system.platform_hardening import iter_tree_without_link_traversal, is_link_like, link_target_description
from living_assistant.core.sessions import SessionStore

SCHEMA = """
CREATE TABLE IF NOT EXISTS security_state(
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS security_findings(
  id TEXT PRIMARY KEY,
  fingerprint TEXT UNIQUE NOT NULL,
  kind TEXT NOT NULL,
  severity TEXT NOT NULL,
  title TEXT NOT NULL,
  details TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'open',
  first_seen TEXT NOT NULL,
  last_seen TEXT NOT NULL,
  count INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS security_findings_status ON security_findings(status,last_seen);
CREATE TABLE IF NOT EXISTS integrity_baselines(
  id TEXT PRIMARY KEY,
  name TEXT UNIQUE NOT NULL,
  path TEXT NOT NULL,
  recursive INTEGER NOT NULL,
  extensions TEXT NOT NULL,
  max_files INTEGER NOT NULL,
  max_file_mb INTEGER NOT NULL,
  snapshot TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
"""

CRITICAL_PROCESS_NAMES = {
    'system','system idle process','registry','smss.exe','csrss.exe','wininit.exe','services.exe',
    'lsass.exe','winlogon.exe','svchost.exe','explorer.exe','kernel_task','launchd','windowserver',
    'systemd','init','kthreadd','dbus-daemon','loginwindow','securityd'
}

SUSPICIOUS_PATH_PARTS = (
    '/tmp/','/var/tmp/','\\temp\\','\\tmp\\','/downloads/','\\downloads\\',
    '/appdata/local/temp/','\\appdata\\local\\temp\\'
)


def _now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec='seconds')


def _json_hash(value) -> str:
    raw=json.dumps(value,sort_keys=True,separators=(',',':'),default=str).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def _run(args: list[str], timeout: float=8.0) -> dict:
    try:
        p=subprocess.run(args,capture_output=True,text=True,timeout=timeout,errors='replace')
        return {'ok':p.returncode==0,'returncode':p.returncode,'stdout':p.stdout[-30000:],'stderr':p.stderr[-8000:]}
    except FileNotFoundError:
        return {'ok':False,'unavailable':True,'error':f'{args[0]} not found'}
    except subprocess.TimeoutExpired:
        return {'ok':False,'timeout':True,'error':f'Command timed out after {timeout}s'}
    except Exception as e:
        return {'ok':False,'error':str(e)}


def _redact_cmdline(parts: Iterable[str]) -> list[str]:
    joined=' '.join(str(x) for x in parts)
    redacted=SessionStore._redact(joined)
    redacted=re.sub(r'(?i)(--(?:password|passwd|token|api-key|apikey|secret)(?:=|\s+))[^\s]+',r'\1[REDACTED]',redacted)
    return redacted.split(' ')

def _redact_text(text: str) -> str:
    redacted=SessionStore._redact(str(text))
    redacted=re.sub(r'(?i)(--(?:password|passwd|token|api-key|apikey|secret)(?:=|\s+))[^\s]+',r'\1[REDACTED]',redacted)
    redacted=re.sub(r'(?i)([?&](?:token|access_token|api_key|apikey|signature|sig|x-amz-signature)=)[^&\s]+',r'\1[REDACTED]',redacted)
    return redacted

def _redact_obj(value):
    if isinstance(value,str): return _redact_text(value)
    if isinstance(value,list): return [_redact_obj(x) for x in value]
    if isinstance(value,dict): return {k:_redact_obj(v) for k,v in value.items()}
    return value


def sha256_file(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):
            h.update(chunk)
    return h.hexdigest()

def _small_file_hash(path: Path,max_bytes: int=1024*1024) -> str|None:
    try:
        if path.is_file() and path.stat().st_size<=max_bytes: return sha256_file(path)
    except Exception: pass
    return None


def startup_inventory() -> dict:
    osname=platform.system()
    items=[]; notes=[]
    if osname=='Windows':
        script=r'''$ErrorActionPreference='SilentlyContinue';
$items=@();
Get-CimInstance Win32_StartupCommand | ForEach-Object {$items += [PSCustomObject]@{type='startup';name=$_.Name;command=$_.Command;location=$_.Location;user=$_.User}};
Get-ScheduledTask | Where-Object { $_.Triggers | Where-Object { $_.CimClass.CimClassName -match 'BootTrigger|LogonTrigger' } } | ForEach-Object {$items += [PSCustomObject]@{type='scheduled_task';name=$_.TaskName;path=$_.TaskPath;state=[string]$_.State}};
$items | ConvertTo-Json -Depth 5'''
        result=_run(['powershell','-NoProfile','-Command',script],12)
        if result.get('ok') and result.get('stdout','').strip():
            try:
                parsed=json.loads(result['stdout']); items=parsed if isinstance(parsed,list) else [parsed]
            except Exception: notes.append('Could not parse Windows startup inventory.')
        else: notes.append(result.get('error') or result.get('stderr') or 'Windows startup query failed.')
    elif osname=='Darwin':
        for base,kind in [
            (Path.home()/'Library/LaunchAgents','launch_agent'),
            (Path('/Library/LaunchAgents'),'launch_agent'),
            (Path('/Library/LaunchDaemons'),'launch_daemon'),
        ]:
            if base.exists():
                for p in sorted(base.glob('*.plist'))[:500]: items.append({'type':kind,'path':str(p),'name':p.name,'sha256':_small_file_hash(p)})
        res=_run(['launchctl','list'],5)
        if res.get('ok'):
            for line in res.get('stdout','').splitlines()[1:501]:
                cols=line.split('\t')
                if cols: items.append({'type':'launchctl','label':cols[-1]})
    else:
        # Linux/Unix read-only persistence inventory.
        for base,kind in [
            (Path.home()/'.config/autostart','xdg_autostart'),
            (Path('/etc/xdg/autostart'),'xdg_autostart'),
            (Path('/etc/cron.d'),'cron'),
            (Path('/etc/cron.daily'),'cron'),
            (Path('/etc/cron.hourly'),'cron'),
            (Path('/etc/cron.weekly'),'cron'),
        ]:
            if base.exists():
                try:
                    for p in sorted(base.iterdir())[:500]:
                        if p.is_file(): items.append({'type':kind,'path':str(p),'name':p.name,'sha256':_small_file_hash(p)})
                except PermissionError: notes.append(f'Permission denied reading {base}')
        for args,kind in [
            (['systemctl','--user','list-unit-files','--state=enabled','--type=service','--no-legend'],'systemd_user'),
            (['systemctl','list-unit-files','--state=enabled','--type=service','--no-legend'],'systemd_system'),
            (['crontab','-l'],'user_crontab'),
        ]:
            res=_run(args,5)
            if res.get('ok'):
                for line in res.get('stdout','').splitlines()[:500]:
                    line=line.strip()
                    if line and not line.startswith('#'): items.append({'type':kind,'entry':line})
    normalized=sorted((_redact_obj(x) for x in items),key=lambda x:json.dumps(x,sort_keys=True,default=str))
    return {'os':osname,'items':normalized,'fingerprint':_json_hash(normalized),'notes':notes}


def firewall_status() -> dict:
    osname=platform.system()
    if osname=='Windows':
        r=_run(['powershell','-NoProfile','-Command','Get-NetFirewallProfile | Select Name,Enabled,DefaultInboundAction,DefaultOutboundAction | ConvertTo-Json'],8)
        return {'provider':'Windows Defender Firewall',**r}
    if osname=='Darwin':
        tool='/usr/libexec/ApplicationFirewall/socketfilterfw'
        r=_run([tool,'--getglobalstate'],5) if Path(tool).exists() else {'ok':False,'unavailable':True}
        return {'provider':'macOS Application Firewall',**r}
    if shutil.which('ufw'):
        return {'provider':'ufw',**_run(['ufw','status'],5)}
    if shutil.which('firewall-cmd'):
        return {'provider':'firewalld',**_run(['firewall-cmd','--state'],5)}
    if shutil.which('nft'):
        r=_run(['nft','list','ruleset'],5); r['stdout']=r.get('stdout','')[:12000]
        return {'provider':'nftables',**r}
    return {'provider':None,'ok':False,'unavailable':True,'message':'No supported firewall CLI detected.'}


def encryption_status() -> dict:
    osname=platform.system()
    if osname=='Windows':
        r=_run(['powershell','-NoProfile','-Command','Get-BitLockerVolume | Select MountPoint,VolumeStatus,ProtectionStatus,EncryptionPercentage | ConvertTo-Json'],8)
        return {'provider':'BitLocker',**r}
    if osname=='Darwin':
        return {'provider':'FileVault',**_run(['fdesetup','status'],5)}
    if shutil.which('lsblk'):
        r=_run(['lsblk','-J','-o','NAME,TYPE,FSTYPE,MOUNTPOINTS'],5)
        if r.get('ok'):
            try:
                parsed=json.loads(r['stdout'])
                encrypted=[]
                def walk(nodes):
                    for x in nodes or []:
                        if str(x.get('type','')).lower()=='crypt' or str(x.get('fstype','')).lower() in {'crypto_luks','crypto_luks2'}:
                            encrypted.append(x.get('name'))
                        walk(x.get('children'))
                walk(parsed.get('blockdevices'))
                return {'provider':'dm-crypt/LUKS','ok':True,'encrypted_devices':encrypted,'detected':bool(encrypted)}
            except Exception: pass
        return {'provider':'dm-crypt/LUKS','ok':False,'error':r.get('stderr') or 'Could not parse lsblk.'}
    return {'provider':None,'ok':False,'unavailable':True}


def update_posture() -> dict:
    osname=platform.system()
    if osname=='Windows':
        return {'provider':'Windows Update','service':_run(['powershell','-NoProfile','-Command','Get-Service wuauserv | Select Status,StartType | ConvertTo-Json'],5),
                'note':'Pending-update enumeration is intentionally not performed automatically.'}
    if osname=='Darwin':
        return {'provider':'softwareupdate','schedule':_run(['softwareupdate','--schedule'],5),
                'note':'Network update enumeration is intentionally not performed automatically.'}
    if shutil.which('apt'):
        r=_run(['apt','list','--upgradable'],8)
        lines=[x for x in r.get('stdout','').splitlines() if x and not x.startswith('Listing')][:200]
        return {'provider':'apt','ok':r.get('ok',False),'upgradable_count':len(lines),'sample':lines[:25],'stderr':r.get('stderr','')[-1000:]}
    if shutil.which('dnf'):
        r=_run(['dnf','check-update','--cacheonly','-q'],8)
        lines=[x for x in r.get('stdout','').splitlines() if x.strip()][:200]
        return {'provider':'dnf','ok':r.get('returncode') in {0,100},'sample':lines[:25],'note':'Uses local metadata cache only.'}
    return {'provider':None,'ok':False,'unavailable':True}


def antivirus_posture() -> dict:
    osname=platform.system()
    if osname=='Windows':
        return {'provider':'Microsoft Defender',**_run(['powershell','-NoProfile','-Command','Get-MpComputerStatus | Select AntivirusEnabled,RealTimeProtectionEnabled,BehaviorMonitorEnabled,IoavProtectionEnabled,AntivirusSignatureLastUpdated | ConvertTo-Json'],8)}
    if shutil.which('clamscan'):
        return {'provider':'ClamAV',**_run(['clamscan','--version'],5)}
    if osname=='Darwin':
        return {'provider':'macOS built-in protections','ok':True,'note':'Gatekeeper/XProtect are OS-managed; no full AV state is exposed by this MVP.'}
    return {'provider':None,'ok':False,'unavailable':True}


def inspect_process(pid: int) -> dict:
    try:
        p=psutil.Process(int(pid))
        info={'pid':p.pid,'name':p.name(),'username':p.username() if hasattr(p,'username') else None}
        try: info['exe']=p.exe()
        except Exception: info['exe']=None
        try: info['cmdline']=_redact_cmdline(p.cmdline())
        except Exception: info['cmdline']=[]
        try: info['create_time']=dt.datetime.fromtimestamp(p.create_time()).astimezone().isoformat(timespec='seconds')
        except Exception: info['create_time']=None
        ancestry=[]; cur=p
        for _ in range(8):
            try: cur=cur.parent()
            except Exception: cur=None
            if cur is None: break
            try: ancestry.append({'pid':cur.pid,'name':cur.name(),'exe':cur.exe()})
            except Exception: ancestry.append({'pid':cur.pid,'name':getattr(cur,'name',lambda:'?')()})
        info['ancestry']=ancestry
        flags=[]; score=0
        exe=(info.get('exe') or '').lower().replace('\\','/')
        if exe and any(x.replace('\\','/') in exe for x in SUSPICIOUS_PATH_PARTS): flags.append('executable_from_temporary_or_download_location'); score+=30
        if not info.get('exe'): flags.append('executable_path_unavailable'); score+=5
        try:
            conns=p.net_connections(kind='inet')
            listeners=[str(c.laddr) for c in conns if c.status==psutil.CONN_LISTEN]
            remotes=[str(c.raddr) for c in conns if c.raddr and c.status==psutil.CONN_ESTABLISHED]
        except Exception: listeners=[]; remotes=[]
        info['listeners']=listeners[:50]; info['remote_connections']=remotes[:50]
        if listeners and exe and any(x.replace('\\','/') in exe for x in SUSPICIOUS_PATH_PARTS): flags.append('temporary_executable_is_listening'); score+=35
        info['signals']=flags; info['signal_score']=min(score,100)
        info['note']='Heuristic signals are not proof of malware.'
        return {'ok':True,**info}
    except psutil.NoSuchProcess:
        return {'ok':False,'error':'Process no longer exists.'}
    except Exception as e:
        return {'ok':False,'error':str(e)}



def score_process_record(record: dict,listening: bool=False) -> dict:
    name=str(record.get('name') or '').lower(); exe=str(record.get('exe') or '').lower().replace('\\','/')
    cmd=' '.join(record.get('cmdline') or []).lower(); parent=str(record.get('parent_name') or '').lower()
    flags=[]; score=0
    if exe and any(x.replace('\\','/') in exe for x in SUSPICIOUS_PATH_PARTS):
        flags.append('executable_from_temporary_or_download_location'); score+=30
    if listening and 'executable_from_temporary_or_download_location' in flags:
        flags.append('temporary_executable_is_listening'); score+=35
    if name in {'powershell.exe','pwsh.exe','powershell','pwsh'} and re.search(r'(^|\s)-(enc|encodedcommand)(\s|$)',cmd):
        flags.append('powershell_encoded_command'); score+=45
    if parent in {'winword.exe','excel.exe','powerpnt.exe','outlook.exe'} and name in {'powershell.exe','pwsh.exe','cmd.exe','wscript.exe','cscript.exe','mshta.exe','rundll32.exe','regsvr32.exe'}:
        flags.append('office_spawned_script_or_lolbin'); score+=55
    return {'score':min(score,100),'signals':flags}


def process_triage(min_score: int=30,limit: int=50) -> list[dict]:
    listening_pids=set()
    try:
        for c in psutil.net_connections(kind='inet'):
            if c.status==psutil.CONN_LISTEN and c.pid: listening_pids.add(c.pid)
    except Exception: pass
    raw=[]; by_pid={}
    for p in psutil.process_iter(['pid','ppid','name','exe','cmdline','username']):
        try:
            x=dict(p.info); x['cmdline']=_redact_cmdline(x.get('cmdline') or []); by_pid[x['pid']]=x; raw.append(x)
        except Exception: pass
    out=[]
    for x in raw:
        parent=by_pid.get(x.get('ppid')) or {}; x['parent_name']=parent.get('name')
        scored=score_process_record(x,x.get('pid') in listening_pids)
        if scored['score']>=min_score:
            out.append({**x,**scored,'listening':x.get('pid') in listening_pids})
    return sorted(out,key=lambda x:x['score'],reverse=True)[:max(1,min(limit,200))]


def network_activity_summary(limit: int=100) -> dict:
    rows=[]; public=0; private=0
    try: conns=psutil.net_connections(kind='inet')
    except Exception: conns=[]
    for c in conns:
        if c.status!=psutil.CONN_ESTABLISHED or not c.raddr: continue
        try: rip=c.raddr.ip; rport=c.raddr.port; lip=c.laddr.ip; lport=c.laddr.port
        except Exception: continue
        try:
            addr=ipaddress.ip_address(rip); scope='private' if (addr.is_private or addr.is_loopback or addr.is_link_local) else 'public'
        except Exception: scope='unknown'
        if scope=='public': public+=1
        elif scope=='private': private+=1
        proc=None
        if c.pid:
            try: proc=psutil.Process(c.pid).name()
            except Exception: pass
        rows.append({'pid':c.pid,'process':proc,'local':f'{lip}:{lport}','remote':f'{rip}:{rport}','scope':scope})
    rows=rows[:max(1,min(limit,500))]
    return {'established_count':len(rows),'public_count':public,'private_count':private,'connections':rows,
            'note':'Remote connections are observations only; public connectivity is normal for many applications.'}

def file_signature(path: str | Path) -> dict:
    p=Path(path).expanduser().resolve()
    if not p.exists() or not p.is_file(): return {'ok':False,'error':'File not found.'}
    result={'ok':True,'path':str(p),'sha256':sha256_file(p),'bytes':p.stat().st_size,'platform':platform.system()}
    if platform.system()=='Windows':
        ps=str(p).replace("'","''")
        result['signature']=_run(['powershell','-NoProfile','-Command',f"Get-AuthenticodeSignature -LiteralPath '{ps}' | Select Status,StatusMessage,SignerCertificate | ConvertTo-Json -Depth 4"],8)
    elif platform.system()=='Darwin' and shutil.which('codesign'):
        result['signature']=_run(['codesign','-dv','--verbose=2',str(p)],8)
    elif shutil.which('dpkg'):
        result['package_owner']=_run(['dpkg','-S',str(p)],5)
    elif shutil.which('rpm'):
        result['package_owner']=_run(['rpm','-qf',str(p)],5)
    return result


def _parse_json_stdout(section: dict):
    raw=str(section.get('stdout') or '').strip()
    if not raw: return None
    try: return json.loads(raw)
    except Exception: return None


def evaluate_security_posture(posture: dict) -> list[dict]:
    """Convert clear protection-state observations into conservative findings.

    Absence of a supported CLI is not treated as compromise. We only flag states we can
    positively identify as disabled/off.
    """
    signals=[]
    fw=posture.get('firewall') or {}; provider=str(fw.get('provider') or '')
    fw_json=_parse_json_stdout(fw)
    if provider=='Windows Defender Firewall' and fw_json is not None:
        rows=fw_json if isinstance(fw_json,list) else [fw_json]
        disabled=[x.get('Name') for x in rows if x.get('Enabled') is False]
        if disabled: signals.append({'kind':'firewall_disabled','severity':'high','title':'Firewall profile disabled','details':{'profiles':disabled,'key':'windows-firewall-disabled'}})
    elif provider=='macOS Application Firewall' and 'disabled' in str(fw.get('stdout','')).lower():
        signals.append({'kind':'firewall_disabled','severity':'medium','title':'macOS application firewall appears disabled','details':{'key':'macos-firewall-disabled'}})
    elif provider=='ufw' and 'status: inactive' in str(fw.get('stdout','')).lower():
        signals.append({'kind':'firewall_disabled','severity':'high','title':'UFW firewall is inactive','details':{'key':'ufw-inactive'}})
    elif provider=='firewalld' and 'not running' in (str(fw.get('stdout',''))+str(fw.get('stderr',''))).lower():
        signals.append({'kind':'firewall_disabled','severity':'high','title':'firewalld is not running','details':{'key':'firewalld-inactive'}})

    av=posture.get('antivirus') or {}; av_json=_parse_json_stdout(av)
    if av.get('provider')=='Microsoft Defender' and isinstance(av_json,dict):
        if av_json.get('AntivirusEnabled') is False:
            signals.append({'kind':'antivirus_disabled','severity':'critical','title':'Microsoft Defender antivirus is disabled','details':{'key':'defender-av-disabled'}})
        if av_json.get('RealTimeProtectionEnabled') is False:
            signals.append({'kind':'realtime_protection_disabled','severity':'high','title':'Microsoft Defender real-time protection is disabled','details':{'key':'defender-realtime-disabled'}})

    enc=posture.get('disk_encryption') or {}
    if enc.get('provider')=='FileVault' and 'filevault is off' in str(enc.get('stdout','')).lower():
        signals.append({'kind':'disk_encryption_off','severity':'medium','title':'FileVault is off','details':{'key':'filevault-off'}})
    if enc.get('provider')=='dm-crypt/LUKS' and enc.get('ok') and enc.get('detected') is False:
        signals.append({'kind':'disk_encryption_not_detected','severity':'low','title':'No dm-crypt/LUKS device detected','details':{'key':'linux-encryption-not-detected'}})
    return signals


@dataclass
class SecurityGuardian:
    config: dict
    approval: object | None = None
    db_path: Path | None = None

    def __post_init__(self):
        self.db_path=self.db_path or (data_dir()/'assistant.sqlite3')
        self.conn=ThreadLocalSQLite(self.db_path)
        self.conn.row_factory=sqlite3.Row
        self.conn.executescript(SCHEMA); self.conn.commit()
        self.cfg=self.config.get('security_guardian',{})

    def _state_get(self,key: str,default=None):
        row=self.conn.execute('SELECT value FROM security_state WHERE key=?',(key,)).fetchone()
        if not row: return default
        try: return json.loads(row['value'])
        except Exception: return default

    def _state_set(self,key: str,value):
        now=_now()
        self.conn.execute('INSERT INTO security_state(key,value,updated_at) VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at',(key,json.dumps(value,default=str),now)); self.conn.commit()

    def record_finding(self,kind: str,severity: str,title: str,details: dict) -> dict:
        severity=severity.lower()
        fp=_json_hash({'kind':kind,'title':title,'key':details.get('key') or details.get('path') or details.get('signature') or details})
        now=_now(); row=self.conn.execute('SELECT * FROM security_findings WHERE fingerprint=?',(fp,)).fetchone()
        if row:
            reopened=str(row['status'])=='resolved'
            self.conn.execute('UPDATE security_findings SET last_seen=?,count=count+1,details=?,status=CASE WHEN status="resolved" THEN "open" ELSE status END WHERE fingerprint=?',(now,json.dumps(details,default=str),fp)); self.conn.commit()
            item=dict(self.conn.execute('SELECT * FROM security_findings WHERE fingerprint=?',(fp,)).fetchone()); item['_new']=reopened; return item
        item_id=uuid.uuid4().hex[:12]
        self.conn.execute('INSERT INTO security_findings(id,fingerprint,kind,severity,title,details,status,first_seen,last_seen,count) VALUES(?,?,?,?,?,?,"open",?,?,1)',(item_id,fp,kind,severity,title,json.dumps(details,default=str),now,now)); self.conn.commit()
        item=dict(self.conn.execute('SELECT * FROM security_findings WHERE id=?',(item_id,)).fetchone()); item['_new']=True; return item

    def findings(self,status: str | None='open',limit: int=200) -> list[dict]:
        if status:
            rows=self.conn.execute('SELECT * FROM security_findings WHERE status=? ORDER BY CASE severity WHEN "critical" THEN 4 WHEN "high" THEN 3 WHEN "medium" THEN 2 ELSE 1 END DESC,last_seen DESC LIMIT ?',(status,max(1,min(limit,1000)))).fetchall()
        else:
            rows=self.conn.execute('SELECT * FROM security_findings ORDER BY last_seen DESC LIMIT ?',(max(1,min(limit,1000)),)).fetchall()
        out=[]
        for r in rows:
            x=dict(r)
            try: x['details']=json.loads(x['details'])
            except Exception: pass
            out.append(x)
        return out

    def resolve_finding(self,finding_id: str) -> bool:
        cur=self.conn.execute('UPDATE security_findings SET status="resolved",last_seen=? WHERE id=?',(_now(),finding_id)); self.conn.commit(); return cur.rowcount>0

    def _resolve_findings_with_key(self,key: str):
        rows=self.conn.execute('SELECT id,details FROM security_findings WHERE status="open"').fetchall()
        ids=[]
        for row in rows:
            try: details=json.loads(row['details'])
            except Exception: continue
            if details.get('key')==key: ids.append(row['id'])
        if ids:
            self.conn.executemany('UPDATE security_findings SET status="resolved",last_seen=? WHERE id=?',[(_now(),x) for x in ids]); self.conn.commit()
        return len(ids)

    def posture(self,include_updates: bool=False) -> dict:
        result={
            'hostname':socket.gethostname(),'os':platform.system(),
            'firewall':firewall_status(),'antivirus':antivirus_posture(),'disk_encryption':encryption_status(),
        }
        if include_updates: result['updates']=update_posture()
        return result

    def posture_scan(self,record: bool=True) -> dict:
        posture=self.posture(include_updates=False); signals=evaluate_security_posture(posture); findings=[]
        self._state_set('last_posture',{'at':_now(),'posture':posture,'signals':signals})
        if record:
            for signal in signals:
                findings.append(self.record_finding(signal['kind'],signal['severity'],signal['title'],signal['details']))
        return {'posture':posture,'signals':signals,'findings':findings}

    def cached_posture(self) -> dict:
        return self._state_get('last_posture',{'at':None,'posture':None,'signals':[]})

    def baseline_status(self) -> dict:
        return {
            'startup_initialized':self._state_get('startup_baseline') is not None,
            'listener_initialized':self._state_get('listener_baseline') is not None,
            'integrity_baselines':len(self.list_integrity_baselines()),
        }

    def summary(self) -> dict:
        findings=self.findings('open',50)
        counts={}
        for f in findings: counts[f.get('severity','unknown')]=counts.get(f.get('severity','unknown'),0)+1
        return {'baselines':self.baseline_status(),'cached_posture':self.cached_posture(),'open_finding_counts':counts,'findings':findings}

    def process_triage(self,min_score: int=30,record: bool=False) -> list[dict]:
        items=process_triage(min_score=min_score,limit=100)
        if record:
            for item in items:
                if item.get('score',0)>=60:
                    self.record_finding('suspicious_process','high',f"Suspicious process signals: {item.get('name')}",{'pid':item.get('pid'),'name':item.get('name'),'exe':item.get('exe'),'signals':item.get('signals'),'score':item.get('score'),'key':f"{item.get('pid')}:{item.get('exe')}"})
        return items

    def network_activity(self,limit: int=100) -> dict:
        return network_activity_summary(limit)

    @staticmethod
    def listener_snapshot() -> list[dict]:
        items=[]
        try: conns=psutil.net_connections(kind='inet')
        except Exception: conns=[]
        for c in conns:
            if c.status!=psutil.CONN_LISTEN: continue
            try:
                ip=c.laddr.ip; port=c.laddr.port
            except Exception: continue
            proc_name=None; exe=None
            if c.pid:
                try:
                    p=psutil.Process(c.pid); proc_name=p.name(); exe=p.exe()
                except Exception: pass
            sig=f'{ip}:{port}|{proc_name or "?"}|{exe or "?"}'
            items.append({'signature':sig,'ip':ip,'port':port,'pid':c.pid,'process':proc_name,'exe':exe})
        return sorted(items,key=lambda x:(x['ip'],x['port'],x.get('process') or ''))[:1000]

    def capture_network_baseline(self) -> dict:
        snap=self.listener_snapshot(); self._state_set('listener_baseline',snap); self._resolve_findings_with_key('listener-baseline-missing')
        return {'ok':True,'count':len(snap),'captured_at':_now(),'listeners':snap}

    def check_network_baseline(self,record: bool=True) -> dict:
        baseline=self._state_get('listener_baseline')
        current=self.listener_snapshot()
        if baseline is None:
            if bool(self.cfg.get('auto_initialize_baselines',False)):
                self._state_set('listener_baseline',current)
                return {'ok':True,'initialized':True,'new':[],'missing':[],'current_count':len(current)}
            return {'ok':True,'initialized':False,'baseline_missing':True,'new':[],'missing':[],'current_count':len(current)}
        b={x['signature']:x for x in baseline}; c={x['signature']:x for x in current}
        new=[c[k] for k in sorted(c.keys()-b.keys())]; missing=[b[k] for k in sorted(b.keys()-c.keys())]
        findings=[]
        if record:
            for item in new:
                sev='medium' if item.get('ip') not in {'127.0.0.1','::1'} else 'low'
                findings.append(self.record_finding('new_listener',sev,f"New listening service on {item['ip']}:{item['port']}",{**item,'key':item['signature']}))
        return {'ok':True,'initialized':False,'new':new,'missing':missing,'current_count':len(current),'findings':findings}

    def capture_startup_baseline(self) -> dict:
        inv=startup_inventory(); self._state_set('startup_baseline',inv['items']); self._resolve_findings_with_key('startup-baseline-missing')
        return {'ok':True,'count':len(inv['items']),'fingerprint':inv['fingerprint'],'notes':inv['notes']}

    def check_startup_baseline(self,record: bool=True) -> dict:
        inv=startup_inventory(); baseline=self._state_get('startup_baseline')
        if baseline is None:
            if bool(self.cfg.get('auto_initialize_baselines',False)):
                self._state_set('startup_baseline',inv['items'])
                return {'ok':True,'initialized':True,'added':[],'removed':[],'notes':inv['notes']}
            return {'ok':True,'initialized':False,'baseline_missing':True,'added':[],'removed':[],'notes':inv['notes'],'findings':[]}
        b={_json_hash(x):x for x in baseline}; c={_json_hash(x):x for x in inv['items']}
        added=[c[k] for k in sorted(c.keys()-b.keys())]; removed=[b[k] for k in sorted(b.keys()-c.keys())]
        findings=[]
        if record:
            for item in added:
                findings.append(self.record_finding('new_persistence','high','New startup/persistence item detected',{'item':item,'key':_json_hash(item)}))
        return {'ok':True,'initialized':False,'added':added,'removed':removed,'notes':inv['notes'],'findings':findings}

    def _snapshot_path(self,path: Path,recursive: bool,extensions: list[str],max_files: int,max_file_mb: int) -> dict:
        if not path.exists(): raise FileNotFoundError(path)
        extset={x.lower() if x.startswith('.') else '.'+x.lower() for x in extensions if x}
        candidates=[path] if path.is_file() else iter_tree_without_link_traversal(path, recursive=recursive)
        items={}; skipped=0
        for p in candidates:
            if len(items)>=max_files: break
            try:
                rel=str(p.relative_to(path.parent if path.is_file() else path))
                if is_link_like(p):
                    target=link_target_description(p)
                    items[rel]={'symlink':target,'sha256':hashlib.sha256(target.encode('utf-8',errors='replace')).hexdigest(),'bytes':0,'mtime_ns':p.lstat().st_mtime_ns}
                    continue
                if not p.is_file(): continue
                if extset and p.suffix.lower() not in extset: continue
                size=p.stat().st_size
                if size>max_file_mb*1024*1024: skipped+=1; continue
                st=p.stat(); items[rel]={'sha256':sha256_file(p),'bytes':size,'mtime_ns':st.st_mtime_ns}
            except (PermissionError,OSError): skipped+=1
        return {'items':items,'skipped':skipped,'truncated':len(items)>=max_files}

    def add_integrity_baseline(self,name: str,path: str|Path,recursive: bool=True,extensions: list[str]|None=None,max_files: int|None=None,max_file_mb: int|None=None) -> dict:
        p=Path(path).expanduser().resolve(); max_files=int(max_files or self.cfg.get('integrity_max_files',1000)); max_file_mb=int(max_file_mb or self.cfg.get('integrity_max_file_mb',20))
        snap=self._snapshot_path(p,recursive,extensions or [],max_files,max_file_mb); now=_now(); item_id=uuid.uuid4().hex[:12]
        self.conn.execute('INSERT INTO integrity_baselines(id,name,path,recursive,extensions,max_files,max_file_mb,snapshot,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(name) DO UPDATE SET path=excluded.path,recursive=excluded.recursive,extensions=excluded.extensions,max_files=excluded.max_files,max_file_mb=excluded.max_file_mb,snapshot=excluded.snapshot,updated_at=excluded.updated_at',(item_id,name,str(p),1 if recursive else 0,json.dumps(extensions or []),max_files,max_file_mb,json.dumps(snap),now,now)); self.conn.commit()
        row=self.conn.execute('SELECT * FROM integrity_baselines WHERE name=?',(name,)).fetchone()
        return {'ok':True,'baseline':self._baseline_row(row),'file_count':len(snap['items']),'skipped':snap['skipped'],'truncated':snap['truncated']}

    @staticmethod
    def _baseline_row(row) -> dict:
        x=dict(row); x['recursive']=bool(x['recursive'])
        try: x['extensions']=json.loads(x['extensions'])
        except Exception: pass
        x.pop('snapshot',None); return x

    def list_integrity_baselines(self) -> list[dict]:
        return [self._baseline_row(r) for r in self.conn.execute('SELECT * FROM integrity_baselines ORDER BY name').fetchall()]

    def remove_integrity_baseline(self,name: str) -> bool:
        cur=self.conn.execute('DELETE FROM integrity_baselines WHERE name=?',(name,)); self.conn.commit(); return cur.rowcount>0

    def check_integrity_baseline(self,name: str,record: bool=True) -> dict:
        row=self.conn.execute('SELECT * FROM integrity_baselines WHERE name=?',(name,)).fetchone()
        if not row: return {'ok':False,'error':'Unknown integrity baseline.'}
        old=json.loads(row['snapshot']); extensions=json.loads(row['extensions']); p=Path(row['path'])
        if not p.exists():
            finding=self.record_finding('integrity_missing','high',f'Protected path missing: {name}',{'path':str(p),'key':name}) if record else None
            return {'ok':True,'missing_path':True,'added':[],'changed':[],'removed':list(old.get('items',{})),'finding':finding}
        cur=self._snapshot_path(p,bool(row['recursive']),extensions,int(row['max_files']),int(row['max_file_mb']))
        a=old.get('items',{}); b=cur.get('items',{})
        added=sorted(b.keys()-a.keys()); removed=sorted(a.keys()-b.keys()); changed=sorted(k for k in a.keys()&b.keys() if a[k].get('sha256')!=b[k].get('sha256'))
        findings=[]
        if record and (added or removed or changed):
            findings.append(self.record_finding('integrity_change','high',f'Protected files changed: {name}',{'path':str(p),'baseline':name,'added':added[:100],'removed':removed[:100],'changed':changed[:100],'key':name}))
        return {'ok':True,'name':name,'path':str(p),'added':added,'removed':removed,'changed':changed,'findings':findings,'truncated':cur['truncated'],'skipped':cur['skipped']}

    def check_all_integrity(self,record: bool=True) -> list[dict]:
        return [self.check_integrity_baseline(x['name'],record=record) for x in self.list_integrity_baselines()]

    def refresh_integrity_baseline(self,name: str) -> dict:
        row=self.conn.execute('SELECT * FROM integrity_baselines WHERE name=?',(name,)).fetchone()
        if not row: return {'ok':False,'error':'Unknown integrity baseline.'}
        return self.add_integrity_baseline(name,row['path'],bool(row['recursive']),json.loads(row['extensions']),int(row['max_files']),int(row['max_file_mb']))

    def periodic_scan(self) -> list[dict]:
        events=[]
        s=self.check_startup_baseline(record=True)
        if s.get('baseline_missing'):
            finding=self.record_finding('baseline_missing','medium','Startup/persistence security baseline is not initialized',{'key':'startup-baseline-missing'})
            if finding.get('_new'): events.append({'kind':'security_baseline_missing','severity':'medium','finding_id':finding.get('id'),'baseline':'startup'})
        for finding in s.get('findings',[]):
            if finding.get('_new'):
                events.append({'kind':'security_new_persistence','severity':finding.get('severity','high'),'finding_id':finding.get('id'),'item':json.loads(finding.get('details','{}')).get('item') if isinstance(finding.get('details'),str) else finding.get('details',{}).get('item')})
        n=self.check_network_baseline(record=True)
        if n.get('baseline_missing'):
            finding=self.record_finding('baseline_missing','medium','Listening-service security baseline is not initialized',{'key':'listener-baseline-missing'})
            if finding.get('_new'): events.append({'kind':'security_baseline_missing','severity':'medium','finding_id':finding.get('id'),'baseline':'network'})
        by_sig={x['signature']:x for x in n.get('new',[])}
        for finding in n.get('findings',[]):
            if finding.get('_new'):
                details=json.loads(finding.get('details','{}')) if isinstance(finding.get('details'),str) else finding.get('details',{})
                events.append({'kind':'security_new_listener','severity':finding.get('severity','medium'),'finding_id':finding.get('id'),'listener':by_sig.get(details.get('key'),details)})
        for check in self.check_all_integrity(record=True):
            fresh=[f for f in check.get('findings',[]) if f.get('_new')]
            if fresh:
                events.append({'kind':'security_integrity_change','severity':fresh[0].get('severity','high'),'finding_id':fresh[0].get('id'),'baseline':check.get('name'),'path':check.get('path'),'added':check.get('added',[])[:20],'removed':check.get('removed',[])[:20],'changed':check.get('changed',[])[:20]})
        process_threshold=max(30,int(self.cfg.get('process_alert_score',60)))
        for item in process_triage(min_score=process_threshold,limit=25):
            severity='high' if item.get('score',0)>=60 else 'medium'
            stable_key=f"{item.get('exe') or item.get('name')}|{','.join(sorted(item.get('signals') or []))}"
            finding=self.record_finding('suspicious_process',severity,f"Suspicious process signals: {item.get('name')}",{'pid':item.get('pid'),'name':item.get('name'),'exe':item.get('exe'),'signals':item.get('signals'),'score':item.get('score'),'key':stable_key})
            if finding.get('_new'):
                events.append({'kind':'security_suspicious_process','severity':'high','finding_id':finding.get('id'),'pid':item.get('pid'),'name':item.get('name'),'signals':item.get('signals'),'score':item.get('score')})
        return events

    def scan_path_antivirus(self,path: str|Path) -> dict:
        p=Path(path).expanduser().resolve()
        if not p.exists(): return {'ok':False,'error':'Path not found.'}
        if self.approval is None: return {'ok':False,'error':'Approval manager is unavailable.'}
        req=self.approval.request(f'Antivirus scan: {p}','Scan a local file/path using the installed endpoint protection tool.','SECURITY_ANTIVIRUS_SCAN')
        if not req.get('allowed'): return {'ok':False,'approval_required':True,**req}
        if platform.system()=='Windows':
            q=str(p).replace("'","''"); result=_run(['powershell','-NoProfile','-Command',f"Start-MpScan -ScanType CustomScan -ScanPath '{q}'"],600)
            return {'provider':'Microsoft Defender',**result}
        if shutil.which('clamscan'):
            args=['clamscan']+(['-r'] if p.is_dir() else [])+[str(p)]; result=_run(args,600)
            # ClamAV 1 means infected files were found, which is a completed scan rather than tool failure.
            result['ok']=result.get('returncode') in {0,1}; return {'provider':'ClamAV',**result}
        return {'ok':False,'error':'No supported antivirus command is available.'}

    def terminate_user_process(self,pid: int) -> dict:
        info=inspect_process(pid)
        if not info.get('ok'): return info
        name=str(info.get('name') or '').lower()
        if name in CRITICAL_PROCESS_NAMES: return {'ok':False,'blocked':True,'error':'Critical OS process is protected.'}
        if int(pid) in {os.getpid(),os.getppid()}: return {'ok':False,'blocked':True,'error':'Living Assistant process is protected.'}
        try:
            proc=psutil.Process(int(pid)); owner=proc.username(); current=psutil.Process().username()
        except Exception as e: return {'ok':False,'error':str(e)}
        if owner and current and owner!=current:
            return {'ok':False,'blocked':True,'error':'Only processes owned by the current user can be contained by this MVP.'}
        if self.approval is None: return {'ok':False,'error':'Approval manager is unavailable.'}
        reason=f"Terminate user-owned process {info.get('name')} PID={pid}; signals={','.join(info.get('signals',[])) or 'none'}"
        req=self.approval.request(f'Terminate process PID {pid}',reason,'SECURITY_CONTAIN_PROCESS')
        if not req.get('allowed'): return {'ok':False,'approval_required':True,**req,'process':info}
        try:
            proc.terminate(); proc.wait(timeout=8)
            return {'ok':True,'pid':pid,'name':info.get('name'),'action':'terminated'}
        except psutil.TimeoutExpired:
            return {'ok':False,'error':'Process did not exit after terminate; force-kill is not automatic.'}
        except Exception as e: return {'ok':False,'error':str(e)}
