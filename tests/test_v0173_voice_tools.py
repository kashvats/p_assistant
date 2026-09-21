from living_assistant.approval import ApprovalManager, ApprovalStore
from living_assistant.tools.voicetools import build_voice_tools
from living_assistant.voice import VoiceEngine
from living_assistant.workspace import Workspace


def test_one_shot_voice_tools_remain_available_when_voice_mode_disabled(tmp_path):
    root = tmp_path / 'ws'; root.mkdir()
    approvals = ApprovalManager(interactive=False, store=ApprovalStore(tmp_path / 'a.sqlite3'))
    voice = VoiceEngine(Workspace([root]), approvals, {'voice': {'enabled': False}}, profile='balanced')

    tools = {tool.name: tool.handler for tool in build_voice_tools(voice)}
    assert {'voice_record', 'voice_transcribe'} <= set(tools)
    assert 'voice_speak' not in tools

    record = tools['voice_record']('artifacts/one-shot.wav', 1.0)
    assert record.get('approval_required') is True
    assert 'disabled' not in str(record).lower()

    audio = root / 'sample.wav'; audio.write_bytes(b'placeholder')
    transcribe = tools['voice_transcribe']('sample.wav')
    assert transcribe.get('approval_required') is True
    assert 'disabled' not in str(transcribe).lower()
