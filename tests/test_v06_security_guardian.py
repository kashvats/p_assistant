from pathlib import Path
import os

from living_assistant.security_guardian import SecurityGuardian, inspect_process


def guardian(tmp_path):
    return SecurityGuardian({'security_guardian':{'integrity_max_files':50,'integrity_max_file_mb':2}},db_path=tmp_path/'security.sqlite3')


def test_integrity_baseline_detects_change(tmp_path):
    root=tmp_path/'protected'; root.mkdir(); f=root/'config.txt'; f.write_text('one')
    g=guardian(tmp_path)
    added=g.add_integrity_baseline('cfg',root,True,['txt'])
    assert added['ok'] and added['file_count']==1
    assert g.check_integrity_baseline('cfg')['changed']==[]
    f.write_text('two')
    result=g.check_integrity_baseline('cfg')
    assert result['changed']==['config.txt']
    assert g.findings('open')[0]['kind']=='integrity_change'


def test_network_baseline_initializes_and_deduplicates_findings(tmp_path, monkeypatch):
    g=guardian(tmp_path)
    clean=[{'signature':'127.0.0.1:8000|api|/api','ip':'127.0.0.1','port':8000,'pid':1,'process':'api','exe':'/api'}]
    changed=[
        {'signature':'127.0.0.1:8000|api|/api','ip':'127.0.0.1','port':8000,'pid':1,'process':'api','exe':'/api'},
        {'signature':'0.0.0.0:9999|x|/tmp/x','ip':'0.0.0.0','port':9999,'pid':2,'process':'x','exe':'/tmp/x'},
    ]
    snapshots=[clean,clean,changed]
    monkeypatch.setattr(g,'listener_snapshot',lambda:snapshots.pop(0) if snapshots else [
        {'signature':'127.0.0.1:8000|api|/api','ip':'127.0.0.1','port':8000,'pid':1,'process':'api','exe':'/api'},
        {'signature':'0.0.0.0:9999|x|/tmp/x','ip':'0.0.0.0','port':9999,'pid':2,'process':'x','exe':'/tmp/x'},
    ])
    missing=g.check_network_baseline(); assert missing['baseline_missing'] is True
    g.capture_network_baseline()
    second=g.check_network_baseline(); assert len(second['new'])==1
    assert second['findings'][0]['_new'] is True
    third=g.check_network_baseline(); assert third['findings'][0]['_new'] is False
    assert len(g.findings('open'))==1


def test_resolved_finding_reopens_as_new_signal(tmp_path):
    g=guardian(tmp_path)
    f=g.record_finding('demo','medium','Demo',{'key':'x'})
    assert f['_new'] is True
    assert g.resolve_finding(f['id'])
    again=g.record_finding('demo','medium','Demo',{'key':'x'})
    assert again['_new'] is True and again['status']=='open'


def test_process_inspection_current_process_is_bounded():
    result=inspect_process(os.getpid())
    assert result['ok'] is True
    assert result['pid']==os.getpid()
    assert result['signal_score'] <= 100
    assert len(result['ancestry']) <= 8

from living_assistant.security_guardian import evaluate_security_posture


def test_posture_evaluator_only_flags_explicit_disabled_states():
    posture={
        'firewall':{'provider':'ufw','stdout':'Status: inactive'},
        'antivirus':{'provider':'Microsoft Defender','stdout':'{"AntivirusEnabled":true,"RealTimeProtectionEnabled":false}'},
        'disk_encryption':{'provider':'dm-crypt/LUKS','ok':True,'detected':True},
    }
    signals=evaluate_security_posture(posture)
    kinds={x['kind'] for x in signals}
    assert 'firewall_disabled' in kinds
    assert 'realtime_protection_disabled' in kinds
    assert 'disk_encryption_not_detected' not in kinds


def test_posture_evaluator_does_not_treat_unknown_tool_as_compromise():
    posture={'firewall':{'provider':None,'ok':False,'unavailable':True},'antivirus':{'provider':None,'ok':False},'disk_encryption':{'provider':None,'ok':False}}
    assert evaluate_security_posture(posture)==[]

from living_assistant.security_guardian import score_process_record


def test_process_scoring_flags_temp_listener():
    record={'name':'odd','exe':'/tmp/odd','cmdline':['/tmp/odd'],'parent_name':'bash'}
    result=score_process_record(record,listening=True)
    assert result['score'] >= 60
    assert 'temporary_executable_is_listening' in result['signals']


def test_process_scoring_flags_office_spawned_script_host():
    record={'name':'powershell.exe','exe':'C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe','cmdline':['powershell.exe'],'parent_name':'WINWORD.EXE'}
    result=score_process_record(record,listening=False)
    assert result['score'] >= 50
    assert 'office_spawned_script_or_lolbin' in result['signals']

from living_assistant.security_guardian import _redact_obj


def test_security_persistence_redacts_secrets_before_storage():
    item={'command':'worker --token=supersecret https://x.test/?api_key=abc'}
    redacted=_redact_obj(item)
    assert 'supersecret' not in redacted['command']
    assert 'abc' not in redacted['command']
    assert '[REDACTED]' in redacted['command']


def test_missing_baseline_is_not_silently_trusted(tmp_path, monkeypatch):
    g=guardian(tmp_path)
    monkeypatch.setattr(g,'listener_snapshot',lambda:[{'signature':'0.0.0.0:4444|x|/tmp/x','ip':'0.0.0.0','port':4444,'pid':2,'process':'x','exe':'/tmp/x'}])
    result=g.check_network_baseline()
    assert result['baseline_missing'] is True
    assert g.baseline_status()['listener_initialized'] is False


def test_capturing_baseline_resolves_setup_finding(tmp_path, monkeypatch):
    g=guardian(tmp_path)
    monkeypatch.setattr(g,'listener_snapshot',lambda:[])
    f=g.record_finding('baseline_missing','medium','Listening baseline missing',{'key':'listener-baseline-missing'})
    assert f['status']=='open'
    g.capture_network_baseline()
    assert all(x['id']!=f['id'] for x in g.findings('open'))


def test_integrity_baseline_does_not_hash_symlink_target(tmp_path):
    root=tmp_path/'protected'; root.mkdir()
    outside=tmp_path/'outside-secret.txt'; outside.write_text('secret-one')
    link=root/'link.txt'; link.symlink_to(outside)
    g=guardian(tmp_path)
    g.add_integrity_baseline('links',root,True,[])
    outside.write_text('secret-two')
    # Target content changed, but the symlink itself did not. This proves the baseline
    # did not follow the link outside the selected tree.
    result=g.check_integrity_baseline('links')
    assert result['changed']==[]
    link.unlink(); link.symlink_to(tmp_path/'different.txt')
    result=g.check_integrity_baseline('links')
    assert result['changed']==['link.txt']


def test_security_guardian_core_is_self_improvement_protected(tmp_path):
    from living_assistant.workspace import Workspace
    from living_assistant.approval import ApprovalStore, ApprovalManager
    from living_assistant.improvements import ImprovementStore, ImprovementEngine
    root=tmp_path/'assistant'; (root/'src'/'living_assistant').mkdir(parents=True)
    (root/'pyproject.toml').write_text('[project]\nname="living-assistant"\n')
    target=root/'src'/'living_assistant'/'security_guardian.py'; target.write_text('old')
    ws=Workspace([root]); approvals=ApprovalStore(tmp_path/'a.sqlite3')
    engine=ImprovementEngine(ws,ApprovalManager(interactive=False,store=approvals),ImprovementStore(tmp_path/'i.sqlite3'))
    proposal=engine.propose(str(target),'new','change guardian','reason')
    result=engine.apply(proposal['id'])
    assert result['manual_required'] is True
