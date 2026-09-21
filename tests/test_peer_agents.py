import os
import sys
from types import SimpleNamespace

import httpx
from fastapi.testclient import TestClient

from living_assistant.system.peer_agents import PeerAgentManager, _SERVICE_TYPE


class FakeResponse:
    status_code=200
    def json(self): return {'ok':True,'model':'qwen','answer':'remote answer'}

class FakeClient:
    def __init__(self): self.calls=[]
    def post(self,url,headers=None,json=None):
        self.calls.append((url,headers,json)); return FakeResponse()


def config(**overrides):
    peers={
        'enabled':True,'advertise':False,'accept_delegation':True,
        'trusted_peer_ids':['peer-2'],'token_env':'ASSISTANT_PEER_TOKEN',
        'verify_tls':True,'allowed_roles':['general','coder','researcher','planner'],
    }
    peers.update(overrides)
    return {'peers':peers}


def test_discovered_peer_is_not_trusted_unless_allowlisted(tmp_path):
    manager=PeerAgentManager(config(trusted_peer_ids=[]),'lite',{},identity_path=tmp_path/'id.json')
    info=SimpleNamespace(
        properties={b'peer_id':b'peer-2',b'name':b'box',b'url':b'https://10.0.0.2:8787',b'profile':b'power',b'ram_gb':b'64',b'vram_gb':b'24',b'cpu_count':b'16'},
        parsed_addresses=lambda:['10.0.0.2'],
    )
    zc=SimpleNamespace(get_service_info=lambda *a,**k:info)
    manager._record_service(zc,_SERVICE_TYPE,'peer-2.'+_SERVICE_TYPE)
    listing=manager.list_peers()
    # list_peers may report optional zeroconf missing, but discovered state remains inspectable.
    assert listing['peers'][0]['peer_id']=='peer-2'
    assert listing['peers'][0]['trusted'] is False


def test_delegate_uses_only_trusted_peer_https_and_redacts_payload(tmp_path, monkeypatch):
    monkeypatch.setenv('ASSISTANT_PEER_TOKEN','shared-secret')
    client=FakeClient()
    manager=PeerAgentManager(config(),'lite',{},identity_path=tmp_path/'id.json',client=client)
    manager.ensure_started=lambda:{'ok':True}
    manager._peers['peer-2']={'peer_id':'peer-2','name':'box','url':'https://10.0.0.2:8787','trusted':True,'vram_gb':24,'ram_gb':64,'cpu_count':16,'last_seen':9999999999}
    result=manager.delegate('review sk-live-ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890','coder','context')
    assert result['ok'] is True and result['peer_id']=='peer-2'
    url,headers,payload=client.calls[0]
    assert url=='https://10.0.0.2:8787/peer/delegate'
    assert headers['Authorization']=='Bearer shared-secret'
    assert 'sk-live-' not in payload['task']
    assert result['untrusted_external'] is True
    assert '[UNTRUSTED_EXTERNAL_OBSERVATION]' in result['answer']


def test_untrusted_peer_never_receives_token(tmp_path, monkeypatch):
    monkeypatch.setenv('ASSISTANT_PEER_TOKEN','shared-secret')
    client=FakeClient()
    manager=PeerAgentManager(config(trusted_peer_ids=[]),'lite',{},identity_path=tmp_path/'id.json',client=client)
    manager.ensure_started=lambda:{'ok':True}
    manager._peers['peer-2']={'peer_id':'peer-2','url':'https://10.0.0.2:8787','trusted':False,'last_seen':9999999999}
    result=manager.delegate('task',peer_id='peer-2')
    assert result['ok'] is False
    assert client.calls==[]


def test_accept_delegation_requires_peer_token_and_is_tool_free(tmp_path, monkeypatch):
    monkeypatch.setenv('ASSISTANT_PEER_TOKEN','shared-secret')
    calls=[]
    manager=PeerAgentManager(config(),'lite',{},lambda role,task,context:calls.append((role,task,context)) or {'ok':True,'model':'q','answer':'done'},identity_path=tmp_path/'id.json')
    denied=manager.accept_delegation('Bearer wrong',role='coder',task='task')
    assert denied['status_code']==401 and not calls
    allowed=manager.accept_delegation('Bearer shared-secret',role='coder',task='task',context='data')
    assert allowed['ok'] is True and calls==[('coder','task','data')]


def test_peer_api_uses_separate_peer_auth(monkeypatch,tmp_path):
    import living_assistant.api as api
    monkeypatch.setenv('ASSISTANT_PEER_TOKEN','shared-secret')
    manager=PeerAgentManager(config(),'lite',{},lambda role,task,context:{'ok':True,'model':'q','answer':'done'},identity_path=tmp_path/'id.json')
    fake=SimpleNamespace(peers=manager)
    monkeypatch.setattr(api,'get_runtime',lambda:fake)
    client=TestClient(api.app)
    assert client.post('/peer/delegate',headers={'Authorization':'Bearer wrong'},json={'task':'x','role':'coder'}).status_code==401
    r=client.post('/peer/delegate',headers={'Authorization':'Bearer shared-secret'},json={'task':'x','role':'coder'})
    assert r.status_code==200 and r.json()['answer']=='done'


def test_runtime_registers_peer_tools_when_feature_disabled_by_default():
    from living_assistant.core.runtime import build_runtime
    rt=build_runtime(interactive=False)
    assert 'peer_list' in rt.orchestrator.tools
    assert 'peer_delegate' in rt.orchestrator.tools
    assert rt.peers.enabled is False
    rt.model_manager.sleep()

def test_mdns_start_uses_zeroconf_browser_without_advertising_secret(tmp_path, monkeypatch):
    calls={}
    class ZC:
        def __init__(self): calls['zc']=self
        def close(self): calls['closed']=True
        def unregister_service(self, info): calls['unregistered']=info
    class Browser:
        def __init__(self, zc, service_type, listener):
            calls['browser']=(zc,service_type,listener)
    class Info: pass
    fake=SimpleNamespace(Zeroconf=ZC, ServiceBrowser=Browser, ServiceInfo=Info)
    monkeypatch.setitem(sys.modules,'zeroconf',fake)
    manager=PeerAgentManager(config(advertise=False),'lite',{},identity_path=tmp_path/'id.json')
    result=manager.ensure_started()
    assert result['ok'] is True
    assert calls['browser'][1]==_SERVICE_TYPE
    manager.stop()
    assert calls['closed'] is True
