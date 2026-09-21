from __future__ import annotations

import json
from pathlib import Path

import pytest

import living_assistant.security_sensors as ss
from living_assistant.security_sensors import SecuritySensorPlatform, RansomwareBehaviorDetector


class AllowApproval:
    def request(self,*a,**k): return {'allowed':True,'id':'ok'}

class DenyApproval:
    def request(self,*a,**k): return {'allowed':False,'id':'pending'}

class GuardianStub:
    def __init__(self): self.recorded=[]; self._findings=[]
    def record_finding(self,kind,severity,title,details):
        item={'id':str(len(self.recorded)+1),'kind':kind,'severity':severity,'title':title,'details':details,'_new':True}
        self.recorded.append(item); return item
    def findings(self,status='open',limit=200): return list(self._findings)


def platform(tmp_path,config=None,approval=None,guardian=None):
    cfg={'security_sensors':{'enabled':True,'network_isolation':{'auto_enabled':False,'auto_armed':False}}}
    if config:
        cfg['security_sensors'].update(config)
    return SecuritySensorPlatform(cfg,approval=approval,guardian=guardian,db_path=tmp_path/'s.sqlite3')


def test_sysmon_dns_normalization():
    e=ss.normalize_sysmon_event({'id':22,'time':'2026-01-01T00:00:00Z','data':{'ProcessId':'12','Image':'C:/a.exe','QueryName':'Example.COM','QueryResults':'1.2.3.4'}})
    assert e['kind']=='dns_query' and e['pid']==12 and e['query_name']=='Example.COM'


def test_windows_security_4688_normalization():
    e=ss.normalize_windows_security_event({'id':4688,'data':{'NewProcessId':'0x2a','NewProcessName':'C:/Windows/System32/powershell.exe','ParentProcessName':'C:/x/WINWORD.EXE','CommandLine':'powershell -enc aaa'}})
    assert e['kind']=='process_create' and e['pid']==42 and 'powershell' in e['image'].lower()


def test_event_correlation_office_powershell_network():
    events=[
        {'kind':'process_create','pid':4,'image':'C:/Windows/System32/powershell.exe','parent_image':'C:/Office/WINWORD.EXE','command_line':'powershell -enc abc'},
        {'kind':'dns_query','pid':4,'query_name':'x.example'},
        {'kind':'network_connect','pid':4,'destination_ip':'203.0.113.3'},
    ]
    out=ss.correlate_security_events(events)
    assert out and out[0]['severity']=='critical'
    assert 'office_to_script_interpreter' in out[0]['signals']


def test_auditd_parser_groups_records():
    text='''type=SYSCALL msg=audit(1700000000.123:99): pid=123 ppid=1 exe="/usr/bin/bash" success=yes\ntype=PATH msg=audit(1700000000.123:99): name="/tmp/a"\n'''
    out=ss.parse_auditd_text(text)
    assert len(out)==1 and out[0]['pid']==123 and out[0]['path']=='/tmp/a'


def test_dns_algorithmic_heuristic():
    events=[{'kind':'dns_query','query_name':'a8x29s17q93z5k20f1.example','source':'sysmon'}]
    out=ss.summarize_dns(events)
    assert out['count']==1 and out['algorithmic_candidates']


def test_ransomware_burst_detector():
    d=RansomwareBehaviorDetector(window_seconds=30,file_threshold=10,directory_threshold=2)
    events=[]
    for i in range(12):
        events.append({'kind':'file_changed','path':f'/data/{i%3}/doc{i}.{["docx","xlsx","jpg","pdf"][i%4]}'})
    out=d.observe(events,now=100)
    assert out['score']>=60 and 'mass_file_change' in out['signals']


def test_tls_context_reads_only_configured_jsonl(tmp_path):
    p=tmp_path/'tls.jsonl'; p.write_text(json.dumps({'server_name':'example.com','remote_ip':'1.2.3.4','tls_version':'TLS1.3'})+'\n')
    sp=platform(tmp_path,{'tls_context_jsonl':str(p)})
    out=sp.tls_context()
    assert out['ok'] and out['events'][0]['server_name']=='example.com'


def test_dns_context_accepts_local_collector(tmp_path,monkeypatch):
    p=tmp_path/'dns.jsonl'; p.write_text(json.dumps({'query':'example.org','source':'test'})+'\n')
    sp=platform(tmp_path,{'dns_context_jsonl':str(p)})
    monkeypatch.setattr(sp,'collect_events',lambda *a,**k:{'events':[]})
    out=sp.dns_context()
    assert out['count']==1 and out['events'][0]['query']=='example.org'


def test_yara_scan_requires_approval(tmp_path):
    f=tmp_path/'a.bin'; f.write_bytes(b'abc')
    r=tmp_path/'r.yar'; r.write_text('rule x { condition: true }')
    sp=platform(tmp_path,{'yara_rules':[str(r)]},approval=DenyApproval())
    out=sp.yara_scan(f)
    assert out['approval_required'] is True


def test_usb_baseline_new_device(tmp_path,monkeypatch):
    sp=platform(tmp_path,approval=AllowApproval())
    monkeypatch.setattr(ss,'usb_inventory',lambda:{'devices':[{'id':'1'}],'count':1,'fingerprint':'a','errors':[],'os':'Linux'})
    assert sp.capture_usb_baseline()['ok']
    monkeypatch.setattr(ss,'usb_inventory',lambda:{'devices':[{'id':'1'},{'id':'2'}],'count':2,'fingerprint':'b','errors':[],'os':'Linux'})
    out=sp.check_usb(); assert [x['id'] for x in out['new']]==['2']


def test_extension_permission_change(tmp_path,monkeypatch):
    sp=platform(tmp_path,approval=AllowApproval())
    a={'browser_root':'chrome','profile':'Default','id':'abc','version':'1','permissions':['tabs'],'manifest_sha256':'1'}
    b={**a,'version':'2','permissions':['tabs','webRequest'],'manifest_sha256':'2'}
    monkeypatch.setattr(ss,'browser_extension_inventory',lambda:{'extensions':[a],'count':1,'fingerprint':'a','note':''})
    assert sp.capture_extension_baseline()['ok']
    monkeypatch.setattr(ss,'browser_extension_inventory',lambda:{'extensions':[b],'count':1,'fingerprint':'b','note':''})
    out=sp.check_extensions(); assert out['changed'] and 'webRequest' in out['changed'][0]['after']['permissions']


def test_backup_integrity_detects_removed_file(tmp_path):
    root=tmp_path/'backup'; root.mkdir(); (root/'a.txt').write_text('one')
    g=GuardianStub(); sp=platform(tmp_path,approval=AllowApproval(),guardian=g)
    assert sp.capture_backup_baseline('b',root)['ok']
    (root/'a.txt').unlink()
    out=sp.check_backup_baseline('b')
    assert out['removed']==['a.txt'] and any(x['kind']=='backup_integrity_change' for x in g.recorded)


def test_binary_trust_detects_hash_change(tmp_path):
    f=tmp_path/'tool.bin'; f.write_bytes(b'one')
    sp=platform(tmp_path,approval=AllowApproval())
    assert sp.trust_binary(f)['ok']
    f.write_bytes(b'two')
    out=sp.assess_binary(f)
    assert out['trusted'] and 'hash_changed' in out['changes']


def test_reputation_missing_key_does_not_upload(tmp_path,monkeypatch):
    monkeypatch.delenv('VIRUSTOTAL_API_KEY',raising=False)
    sp=platform(tmp_path)
    out=sp.reputation_hash('a'*64)
    assert not out['ok'] and out['available'] is False


def test_reputation_records_high_confidence_malicious_hash(tmp_path,monkeypatch):
    g=GuardianStub(); sp=platform(tmp_path,guardian=g)
    monkeypatch.setenv('VIRUSTOTAL_API_KEY','secret')
    class Resp:
        status_code=200
        def json(self): return {'data':{'attributes':{'last_analysis_stats':{'malicious':9,'harmless':20}}}}
    class Client:
        def __init__(self,*a,**k): pass
        def __enter__(self): return self
        def __exit__(self,*a): pass
        def get(self,*a,**k): return Resp()
    monkeypatch.setattr(ss.httpx,'Client',Client)
    out=sp.reputation_hash('b'*64)
    assert out['ok'] and any(x['kind']=='known_malicious_hash' for x in g.recorded)


def test_automatic_isolation_disabled_by_default(tmp_path):
    sp=platform(tmp_path)
    out=sp.isolate_network(True,{'signals':['mass_file_change','known_malicious_hash']})
    assert out['blocked'] is True


def test_automatic_isolation_requires_independent_signals(tmp_path):
    sp=platform(tmp_path,{'network_isolation':{'auto_enabled':True,'auto_armed':True,'auto_required_signals':['mass_file_change','known_malicious_hash']}})
    out=sp.isolate_network(True,{'signals':['mass_file_change']})
    assert out['blocked'] is True


def test_network_isolation_and_restore_are_reversible(tmp_path,monkeypatch):
    sp=platform(tmp_path,approval=AllowApproval())
    monkeypatch.setattr(sp,'_network_isolation_commands',lambda restore=False: ([['fake','off']],{'provider':'fake'}) if not restore else [['fake','on']])
    monkeypatch.setattr(ss,'_run',lambda *a,**k:{'ok':True,'returncode':0,'stdout':'','stderr':''})
    assert sp.isolate_network(False)['ok']
    assert sp.status()['network_isolated'] is True
    assert sp.restore_network()['ok']
    assert sp.status()['network_isolated'] is False


def test_periodic_extension_permission_finding(tmp_path,monkeypatch):
    g=GuardianStub(); sp=platform(tmp_path,approval=AllowApproval(),guardian=g)
    monkeypatch.setattr(sp,'correlations',lambda *a,**k:{'correlations':[]})
    monkeypatch.setattr(sp,'check_usb',lambda:{'new':[]})
    monkeypatch.setattr(sp,'list_backup_baselines',lambda:[])
    monkeypatch.setattr(sp,'check_trusted_binaries',lambda:{'changed':[]})
    monkeypatch.setattr(sp,'check_extensions',lambda:{'new':[],'changed':[{'before':{'permissions':['tabs']},'after':{'browser_root':'c','profile':'d','id':'e','permissions':['tabs','webRequest']}}]})
    out=sp.periodic_scan()
    assert any(x['kind']=='security_extension_permissions' for x in out)


def test_native_macos_helper_source_is_shipped():
    root=Path(__file__).resolve().parents[1]
    assert (root/'native/macos_endpoint_security/main.c').exists()

def test_security_sensor_api_status(monkeypatch):
    from types import SimpleNamespace
    from fastapi.testclient import TestClient
    import living_assistant.api as api
    fake=SimpleNamespace(security_sensors=SimpleNamespace(status=lambda:{'enabled':True,'yara':False}))
    monkeypatch.setattr(api,'runtime',fake)
    monkeypatch.delenv('ASSISTANT_API_TOKEN',raising=False)
    monkeypatch.setenv('ASSISTANT_API_TOKEN','test-token')
    r=TestClient(api.app,headers={'Authorization':'Bearer test-token'}).get('/security/sensors/status')
    assert r.status_code==200 and r.json()['enabled'] is True


def test_dashboard_surfaces_sensor_platform(monkeypatch):
    from fastapi.testclient import TestClient
    import living_assistant.api as api
    monkeypatch.delenv('ASSISTANT_API_TOKEN',raising=False)
    monkeypatch.setenv('ASSISTANT_API_TOKEN','test-token')
    r=TestClient(api.app,headers={'Authorization':'Bearer test-token'}).get('/dashboard')
    assert r.status_code==200
    assert 'Sensor platform' in r.text
    assert '/security/sensors/status' in r.text

def test_partial_network_isolation_keeps_restore_state(tmp_path,monkeypatch):
    sp=platform(tmp_path,approval=AllowApproval())
    monkeypatch.setattr(sp,'_network_isolation_commands',lambda restore=False: ([['fake','a'],['fake','b']],{'services':['a','b']}) if not restore else [['fake','on']])
    calls={'n':0}
    def run(*a,**k):
        calls['n']+=1
        return {'ok':calls['n']==1,'returncode':0 if calls['n']==1 else 1,'stdout':'','stderr':'fail' if calls['n']>1 else ''}
    monkeypatch.setattr(ss,'_run',run)
    out=sp.isolate_network(False)
    assert out['partial'] is True
    assert sp.status()['network_isolated'] is True


def test_security_tools_include_sensor_controls(tmp_path):
    from living_assistant.tools.security import build_security_tools
    class WS:
        def resolve(self,p): return Path(tmp_path,p).resolve()
    sp=platform(tmp_path,approval=AllowApproval())
    names={t.name for t in build_security_tools(WS(),AllowApproval(),GuardianStub(),sp)}
    for name in {'security_sensor_status','security_event_correlations','security_dns_summary','security_yara_scan','security_binary_assess','security_network_isolate'}:
        assert name in names
