import sys
import types
from pathlib import Path

import numpy as np

from living_assistant.voice import VoiceEngine
from living_assistant.workspace import Workspace


class AllowApproval:
    def __init__(self): self.calls=[]
    def request(self,*args,**kwargs):
        self.calls.append((args,kwargs))
        return {'allowed':True}


class DenyApproval:
    def request(self,*args,**kwargs): return {'allowed':False,'pending':True,'approval_id':'x'}


def cfg(hands_free=True):
    return {
        'voice': {
            'enabled': True,
            'lite_enabled': False,
            'stt_model': 'tiny',
            'hands_free': {
                'enabled': hands_free,
                'lite_enabled': False,
                'wake_threshold': 0.5,
                'wake_chunk_ms': 80,
                'wake_timeout_seconds': 1,
                'barge_in_enabled': True,
            },
            'vad': {
                'block_ms': 80,
                'calibration_seconds': 0.16,
                'pre_roll_seconds': 0.08,
                'min_seconds': 0.16,
                'silence_seconds': 0.16,
                'max_seconds': 2,
                'min_rms': 200,
                'noise_multiplier': 2,
            },
        }
    }


class FakeStream:
    def __init__(self, blocks):
        self.blocks=list(blocks); self.i=0
    def __enter__(self): return self
    def __exit__(self,*a): return False
    def read(self, frames):
        if self.i < len(self.blocks):
            block=self.blocks[self.i]; self.i += 1
        else:
            block=np.zeros(frames,dtype=np.int16)
        if block.size != frames:
            block=np.resize(block,frames).astype(np.int16)
        return block.tobytes(), False


class FakeSD:
    def __init__(self, blocks): self.blocks=blocks
    def RawInputStream(self, **kwargs): return FakeStream(self.blocks)


def test_hands_free_is_opt_in_and_lite_gated(tmp_path):
    ws=Workspace([tmp_path/'w'])
    assert VoiceEngine(ws,AllowApproval(),cfg(False),'balanced').hands_free_enabled() is False
    assert VoiceEngine(ws,AllowApproval(),cfg(True),'balanced').hands_free_enabled() is True
    assert VoiceEngine(ws,AllowApproval(),cfg(True),'lite').hands_free_enabled() is False


def test_wake_word_detection_is_local_and_approval_gated(tmp_path, monkeypatch):
    ws=Workspace([tmp_path/'w']); approval=AllowApproval(); v=VoiceEngine(ws,approval,cfg(True),'balanced')
    block=np.zeros(1280,dtype=np.int16)
    monkeypatch.setattr(v,'_import_audio',lambda:(FakeSD([block,block]),np))
    class Model:
        def __init__(self): self.n=0
        def predict(self,samples):
            self.n += 1
            return {'hey_jarvis': 0.1 if self.n == 1 else 0.83}
    monkeypatch.setattr(v,'_load_wake_model',lambda:Model())
    out=v.listen_for_wake_word(1)
    assert out['ok'] is True and out['detected'] is True
    assert out['wake_word']=='hey_jarvis' and out['score']==0.83
    assert approval.calls and approval.calls[0][0][2]=='SENSITIVE_READ'


def test_wake_word_denial_never_opens_audio_device(tmp_path, monkeypatch):
    ws=Workspace([tmp_path/'w']); v=VoiceEngine(ws,DenyApproval(),cfg(True),'balanced')
    monkeypatch.setattr(v,'_import_audio',lambda:(_ for _ in ()).throw(AssertionError('audio should not open')))
    out=v.listen_for_wake_word(1)
    assert out['ok'] is False and out['approval_required'] is True


def test_adaptive_vad_records_speech_then_stops_on_silence(tmp_path, monkeypatch):
    ws=Workspace([tmp_path/'w']); v=VoiceEngine(ws,AllowApproval(),cfg(True),'balanced')
    frames=1280
    low=np.full(frames,80,dtype=np.int16)
    high=np.full(frames,1800,dtype=np.int16)
    blocks=[low,low,low,high,high,high,low,low,low]
    monkeypatch.setattr(v,'_import_audio',lambda:(FakeSD(blocks),np))
    out=v.record_until_silence('artifacts/test-vad.wav')
    assert out['ok'] is True
    assert Path(out['path']).exists() and out['seconds'] > 0
    assert out['threshold_rms'] >= 200


def test_no_speech_does_not_write_audio(tmp_path, monkeypatch):
    ws=Workspace([tmp_path/'w']); v=VoiceEngine(ws,AllowApproval(),cfg(True),'balanced')
    frames=1280; low=np.full(frames,50,dtype=np.int16)
    monkeypatch.setattr(v,'_import_audio',lambda:(FakeSD([low]*40),np))
    out=v.record_until_silence('artifacts/no-speech.wav',max_seconds=0.7)
    assert out['ok'] is False and 'No speech detected' in out['error']
    assert not (tmp_path/'w'/'artifacts'/'no-speech.wav').exists()


def test_barge_in_denial_falls_back_to_normal_tts(tmp_path, monkeypatch):
    ws=Workspace([tmp_path/'w']); v=VoiceEngine(ws,DenyApproval(),cfg(True),'balanced')
    events=[]
    class Engine:
        def setProperty(self,*a): pass
        def say(self,text): events.append(('say',text))
        def runAndWait(self): events.append(('run',None))
        def stop(self): events.append(('stop',None))
    fake=types.SimpleNamespace(init=lambda:Engine())
    monkeypatch.setitem(sys.modules,'piper',None)
    monkeypatch.setitem(sys.modules,'pyttsx3',fake)
    out=v.speak('hello',allow_barge_in=True)
    assert out['ok'] is True and out['barge_in_denied'] is True and out['interrupted'] is False
    assert ('say','hello') in events


def test_status_does_not_import_heavy_voice_models(tmp_path, monkeypatch):
    ws=Workspace([tmp_path/'w']); v=VoiceEngine(ws,AllowApproval(),cfg(True),'balanced')
    monkeypatch.setattr(v,'_module_available',lambda name: name in {'numpy','sounddevice'})
    out=v.status()
    assert out['hands_free_enabled'] is True
    assert out['dependencies']['openwakeword'] is False
    assert v._wake_model is None and v._stt_model is None

def test_wake_and_command_capture_keeps_single_stream_audio(tmp_path, monkeypatch):
    ws=Workspace([tmp_path/'w']); v=VoiceEngine(ws,AllowApproval(),cfg(True),'balanced')
    frames=1280
    quiet=np.full(frames,70,dtype=np.int16)
    wake=np.full(frames,1200,dtype=np.int16)
    speech=np.full(frames,1800,dtype=np.int16)
    blocks=[quiet,quiet,wake,speech,speech,speech,quiet,quiet,quiet]
    monkeypatch.setattr(v,'_import_audio',lambda:(FakeSD(blocks),np))
    class Model:
        def __init__(self): self.n=0
        def predict(self,samples):
            self.n += 1
            return {'hey_jarvis': 0.8 if self.n == 3 else 0.05}
    monkeypatch.setattr(v,'_load_wake_model',lambda:Model())
    out=v.listen_for_command('artifacts/command.wav',1)
    assert out['ok'] is True and out['wake_word']=='hey_jarvis'
    assert Path(out['path']).exists() and out['seconds'] > 0


def test_clean_command_text_only_strips_leading_wake_phrase(tmp_path):
    ws=Workspace([tmp_path/'w']); c=cfg(True)
    c['voice']['hands_free']['wake_phrase_text']='hey jarvis'
    v=VoiceEngine(ws,AllowApproval(),c,'balanced')
    assert v.clean_command_text('Hey Jarvis, open my project','hey_jarvis') == 'open my project'
    assert v.clean_command_text('tell me about hey jarvis','hey_jarvis') == 'tell me about hey jarvis'
