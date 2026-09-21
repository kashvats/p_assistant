from __future__ import annotations
from .base import Tool
from living_assistant.desktop.voice import VoiceEngine

def build_voice_tools(voice: VoiceEngine) -> list[Tool]:
    # Explicit one-shot recording/transcription remain available even when the
    # always-on voice feature is disabled. Both operations retain their own
    # approval/dependency gates inside VoiceEngine.
    tools = [
        Tool(
            'voice_record',
            'Record a short microphone clip to the approved workspace. Always requires explicit approval.',
            {'type':'object','properties':{'destination':{'type':'string','default':'artifacts/voice-input.wav'},'seconds':{'type':'number','default':6.0}}},
            voice.record,
        ),
        Tool(
            'voice_transcribe',
            'Transcribe a local audio file using an optional local faster-whisper model.',
            {'type':'object','properties':{'path':{'type':'string'},'language':{'type':'string'}},'required':['path']},
            voice.transcribe,
        ),
    ]
    if voice.enabled():
        tools.append(
            Tool(
                'voice_speak',
                'Speak text using the optional local offline TTS engine.',
                {'type':'object','properties':{'text':{'type':'string'}},'required':['text']},
                voice.speak,
            )
        )
    return tools
