from __future__ import annotations

import json
import struct
import wave
from pathlib import Path

import pytest

from gateway.calls.native import voice_turn
from gateway.calls.native.voice_turn import HermesVoiceTurnPipeline, VoiceDebugTracePolicy


def _pcm16_samples() -> bytes:
    return struct.pack("<hhhh", 1200, -1200, 900, -900)


class CapturingTracer:
    def __init__(self) -> None:
        self.rows: list[tuple[str, str, dict]] = []

    def record(self, call_id: str, event: str, **fields):
        self.rows.append((call_id, event, fields))
        return Path("/tmp/fake-trace.jsonl")


@pytest.mark.asyncio
async def test_voice_turn_pipeline_transcribes_agent_response_and_tts(tmp_path):
    calls: dict[str, list] = {
        "transcribe": [],
        "respond": [],
        "synthesize": [],
    }
    output_path = tmp_path / "reply.wav"

    def transcribe(audio_path: str) -> dict:
        calls["transcribe"].append(audio_path)
        with wave.open(audio_path, "rb") as wav:
            assert wav.getframerate() == 48000
            assert wav.getnchannels() == 1
            assert wav.getsampwidth() == 2
            assert wav.readframes(4) == _pcm16_samples()
        return {"success": True, "transcript": "are you there?", "provider": "fake-stt"}

    async def respond(transcript: str) -> str:
        calls["respond"].append(transcript)
        return "Yes. I am on the call."

    def synthesize(text: str, path: str) -> str:
        calls["synthesize"].append((text, path))
        Path(path).write_bytes(b"RIFFfake")
        return json.dumps({"success": True, "file_path": str(output_path)})

    pipeline = HermesVoiceTurnPipeline(
        audio_dir=tmp_path,
        transcriber=transcribe,
        responder=respond,
        synthesizer=synthesize,
    )

    result = await pipeline.process_pcm16(
        call_id="call-1",
        pcm16=_pcm16_samples(),
        sample_rate=48000,
    )

    assert result.ok is True
    assert result.code == "call_voice_turn_completed"
    assert result.transcript == "are you there?"
    assert result.response_text == "Yes. I am on the call."
    assert result.audio_path == output_path
    assert calls["respond"] == ["are you there?"]
    assert calls["synthesize"][0][0] == "Yes. I am on the call."


@pytest.mark.asyncio
async def test_voice_turn_pipeline_omits_debug_previews_by_default(tmp_path):
    tracer = CapturingTracer()
    output_path = tmp_path / "reply.wav"

    pipeline = HermesVoiceTurnPipeline(
        audio_dir=tmp_path,
        transcriber=lambda _path: {
            "success": True,
            "transcript": "can you hear my private sentence?",
            "provider": "fake-stt",
        },
        responder=lambda _transcript: "Yes, I can hear your private sentence.",
        synthesizer=lambda _text, _path: json.dumps(
            {"success": True, "file_path": str(output_path)}
        ),
        tracer=tracer,
        debug_policy=VoiceDebugTracePolicy(),
    )

    result = await pipeline.process_pcm16(
        call_id="call-1",
        pcm16=_pcm16_samples(),
        sample_rate=48000,
    )

    assert result.ok is True
    events = [event for _call_id, event, _fields in tracer.rows]
    assert "voice_turn_transcript_observed" not in events
    assert "voice_turn_agent_response_observed" not in events
    assert "can you hear my private sentence" not in json.dumps(tracer.rows)


@pytest.mark.asyncio
async def test_voice_turn_pipeline_emits_opt_in_debug_previews(tmp_path):
    tracer = CapturingTracer()
    output_path = tmp_path / "reply.wav"
    transcript = "Can you tell me about the weather in Leawood, Kansas?"
    response_text = "The weather lookup needs Leawood, Kansas."

    pipeline = HermesVoiceTurnPipeline(
        audio_dir=tmp_path,
        transcriber=lambda _path: {
            "success": True,
            "transcript": transcript,
            "provider": "fake-stt",
        },
        responder=lambda _transcript: response_text,
        synthesizer=lambda _text, _path: json.dumps(
            {"success": True, "file_path": str(output_path)}
        ),
        tracer=tracer,
        debug_policy=VoiceDebugTracePolicy(
            transcript_previews=True,
            max_preview_chars=32,
        ),
    )

    result = await pipeline.process_pcm16(
        call_id="call-1",
        pcm16=_pcm16_samples(),
        sample_rate=48000,
    )

    rows_by_event = {event: fields for _call_id, event, fields in tracer.rows}

    assert result.ok is True
    assert rows_by_event["voice_turn_transcript_observed"] == {
        "preview": "Can you tell me about the weather...",
        "chars": len(transcript),
        "preview_chars": 32,
        "sensitive": True,
        "stt_provider": "fake-stt",
    }
    assert rows_by_event["voice_turn_agent_response_observed"] == {
        "preview": "The weather lookup needs Leawood...",
        "chars": len(response_text),
        "preview_chars": 32,
        "sensitive": True,
    }
    assert rows_by_event["tool_intent_observed"] == {
        "intent": "weather",
        "source": "speech_transcript",
        "needs_tool": True,
    }


@pytest.mark.asyncio
async def test_voice_turn_pipeline_short_circuits_when_stt_fails(tmp_path):
    called = {"respond": False, "synthesize": False}

    async def respond(_transcript: str) -> str:
        called["respond"] = True
        return "should not happen"

    def synthesize(_text: str, _path: str) -> str:
        called["synthesize"] = True
        return "{}"

    pipeline = HermesVoiceTurnPipeline(
        audio_dir=tmp_path,
        transcriber=lambda _path: {
            "success": False,
            "error": "no stt backend",
        },
        responder=respond,
        synthesizer=synthesize,
    )

    result = await pipeline.process_pcm16(
        call_id="call-1",
        pcm16=_pcm16_samples(),
        sample_rate=48000,
    )

    assert result.ok is False
    assert result.code == "call_voice_stt_failed"
    assert "no stt backend" in result.message
    assert called == {"respond": False, "synthesize": False}


@pytest.mark.asyncio
async def test_voice_turn_pipeline_skips_empty_transcript(tmp_path):
    pipeline = HermesVoiceTurnPipeline(
        audio_dir=tmp_path,
        transcriber=lambda _path: {"success": True, "transcript": "  "},
        responder=lambda _transcript: "should not happen",
        synthesizer=lambda _text, _path: "{}",
    )

    result = await pipeline.process_pcm16(
        call_id="call-1",
        pcm16=_pcm16_samples(),
        sample_rate=48000,
    )

    assert result.ok is False
    assert result.code == "call_voice_transcript_empty"


def test_default_agent_response_uses_native_call_agent_config(monkeypatch):
    captured: dict[str, object] = {}
    resolved: dict[str, object] = {}

    monkeypatch.setattr(
        "hermes_cli.config.load_config",
        lambda: {
            "calls": {
                "native": {
                    "agent": {
                        "provider": "copilot",
                        "model": "gpt-4o-mini",
                        "base_url": "https://api.githubcopilot.com",
                        "api_mode": "chat_completions",
                        "max_iterations": 2,
                        "max_tokens": 128,
                        "enabled_toolsets": ["gmail"],
                        "disabled_toolsets": ["terminal"],
                        "skip_memory": True,
                        "skip_context_files": True,
                        "system_prompt": "Keep it brief.",
                    }
                }
            }
        },
    )

    def fake_resolve_runtime_provider(**kwargs):
        resolved.update(kwargs)
        return {
            "provider": kwargs["requested"],
            "api_mode": "chat_completions",
            "base_url": kwargs["explicit_base_url"],
            "api_key": "secret",
        }

    monkeypatch.setattr(
        "hermes_cli.runtime_provider.resolve_runtime_provider",
        fake_resolve_runtime_provider,
    )

    class FakeAgent:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def chat(self, transcript: str) -> str:
            captured["transcript"] = transcript
            return "voice response"

    monkeypatch.setattr("run_agent.AIAgent", FakeAgent)

    response = voice_turn._default_agent_response("call/one", "hello")

    assert response == "voice response"
    assert resolved == {
        "requested": "copilot",
        "explicit_base_url": "https://api.githubcopilot.com",
        "target_model": "gpt-4o-mini",
    }
    assert captured["provider"] == "copilot"
    assert captured["model"] == "gpt-4o-mini"
    assert captured["base_url"] == "https://api.githubcopilot.com"
    assert captured["api_mode"] == "chat_completions"
    assert captured["max_iterations"] == 2
    assert captured["max_tokens"] == 128
    assert captured["enabled_toolsets"] == ["gmail"]
    assert captured["disabled_toolsets"] == ["terminal"]
    assert captured["skip_memory"] is True
    assert captured["skip_context_files"] is True
    assert captured["ephemeral_system_prompt"] == "Keep it brief."
    assert captured["platform"] == "simplex_call"
    assert captured["session_id"] == "simplex-native-call:call_one"
    assert captured["transcript"] == "hello"
