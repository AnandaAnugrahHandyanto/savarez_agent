"""Agent tools: voice bridge via harness HTTP (optional local whisper)."""

from __future__ import annotations

import json

from tools.openclaw.voice_bridge import list_audio_devices, voice_stack_status, voice_test_say, voice_turn
from tools.registry import registry


def _json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


registry.register(
    name="voice_bridge_status",
    toolset="harness",
    schema={
        "name": "voice_bridge_status",
        "description": (
            "Report whether voice features are available (harness HTTP, local whisper, VOICEVOX). "
            "Does not record audio."
        ),
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    handler=lambda args, **kw: _json(voice_stack_status()),
    emoji="🎙️",
)

registry.register(
    name="voice_bridge_devices",
    toolset="harness",
    schema={
        "name": "voice_bridge_devices",
        "description": "List audio input/output devices (via harness or local sounddevice).",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    handler=lambda args, **kw: _json(list_audio_devices()),
    emoji="🔊",
)

registry.register(
    name="voice_bridge_turn",
    toolset="harness",
    schema={
        "name": "voice_bridge_turn",
        "description": (
            "Record microphone audio, transcribe with whisper, get agent reply, speak via VOICEVOX. "
            "Requires `hermes harness start` (recommended) or local openclaw-voice extra."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "record_seconds": {
                    "type": "number",
                    "description": "Seconds to record from microphone (default 5).",
                },
                "emotion": {
                    "type": "string",
                    "description": "VOICEVOX emotion for spoken reply (default neutral).",
                },
                "speaker": {
                    "type": "integer",
                    "description": "VOICEVOX speaker id (default 8).",
                },
            },
            "required": [],
        },
    },
    handler=lambda args, **kw: _json(
        voice_turn(
            record_seconds=float(args.get("record_seconds", 5.0)),
            emotion=args.get("emotion", "neutral"),
            speaker=int(args.get("speaker", 8)),
        ),
    ),
    emoji="🗣️",
)

registry.register(
    name="voice_bridge_speak",
    toolset="harness",
    schema={
        "name": "voice_bridge_speak",
        "description": "Speak text through harness VOICEVOX playback (no microphone).",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to synthesize and play."},
                "emotion": {"type": "string", "description": "VOICEVOX emotion (default neutral)."},
                "speaker": {"type": "integer", "description": "VOICEVOX speaker id (default 8)."},
            },
            "required": ["text"],
        },
    },
    handler=lambda args, **kw: _json(
        voice_test_say(
            args["text"],
            emotion=args.get("emotion", "neutral"),
            speaker=int(args.get("speaker", 8)),
        ),
    ),
    emoji="💬",
)
