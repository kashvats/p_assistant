from living_assistant.voice import VoiceEngine
from living_assistant.workspace import Workspace

class Approval:
    def request(self,*a,**k): return {'allowed':False}


def test_voice_profile_gate(tmp_path):
    ws=Workspace([tmp_path/'w'])
    cfg={'voice':{'enabled':True,'lite_enabled':False}}
    assert VoiceEngine(ws,Approval(),cfg,'lite').enabled() is False
    assert VoiceEngine(ws,Approval(),cfg,'balanced').enabled() is True


def test_disabled_record_does_not_need_audio_dependencies(tmp_path):
    ws=Workspace([tmp_path/'w'])
    v=VoiceEngine(ws,Approval(),{'voice':{'enabled':False}},'balanced')
    assert v.record()['ok'] is False
