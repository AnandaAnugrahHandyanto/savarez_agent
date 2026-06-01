from __future__ import annotations

import contextlib
import io
import json
from dataclasses import dataclass, field

import pytest

from gateway.calls.native.simplex_session_codec import (
    decode_webrtc_session,
    encode_webrtc_session,
)
from gateway.calls.native.simplex_sidecar import (
    SimplexNativeSidecarRunner,
    SimplexNativeSidecarError,
    SimplexSidecarAnswer,
    SimplexSidecarOffer,
    run_jsonl_sidecar,
)
from gateway.calls.native.voice_turn import VoiceTurnResult


@dataclass
class FakeEngine:
    start_requests: list[dict] = field(default_factory=list)
    outgoing_answer_requests: list[tuple[dict, dict, list]] = field(default_factory=list)
    answers: list[tuple[str, dict, list]] = field(default_factory=list)
    extras: list[tuple[str, list]] = field(default_factory=list)
    stopped: list[str] = field(default_factory=list)
    start_error: Exception | None = None
    event_sink: object | None = None

    def set_event_sink(self, event_sink) -> None:
        self.event_sink = event_sink

    async def start_incoming(self, request: dict) -> SimplexSidecarOffer:
        self.start_requests.append(request)
        if self.start_error is not None:
            raise self.start_error
        return SimplexSidecarOffer(
            sdp={"type": "offer", "sdp": "v=0\r\nm=audio 9 UDP/TLS/RTP/SAVPF 111\r\n"},
            ice_candidates=[{"candidate": "candidate:1", "sdpMid": "0"}],
            capabilities={"encryption": True},
            call_dh_pub_key="dh-pub-b64",
        )

    async def start_outgoing_answer(
        self,
        request: dict,
        sdp: dict,
        ice_candidates: list,
    ) -> SimplexSidecarAnswer:
        self.outgoing_answer_requests.append((request, sdp, ice_candidates))
        if self.start_error is not None:
            raise self.start_error
        return SimplexSidecarAnswer(
            sdp={"type": "answer", "sdp": "v=0\r\nm=audio 9 UDP/TLS/RTP/SAVPF 111\r\n"},
            ice_candidates=[{"candidate": "candidate:answer", "sdpMid": "0"}],
        )

    async def apply_answer(self, call_id: str, sdp: dict, ice_candidates: list) -> None:
        self.answers.append((call_id, sdp, ice_candidates))

    async def add_extra_ice(self, call_id: str, ice_candidates: list) -> None:
        self.extras.append((call_id, ice_candidates))

    async def stop(self, call_id: str) -> None:
        self.stopped.append(call_id)

    async def process_audio_file(self, call_id: str, audio_path: str) -> VoiceTurnResult:
        return VoiceTurnResult(
            ok=True,
            code="call_voice_turn_completed",
            message="Voice turn completed.",
            transcript="caller said a private sentence",
            response_text="Hermes said a private reply.",
            audio_path=audio_path + ".reply.wav",
            stt_provider="fake-stt",
            tts_provider="fake-tts",
        )


@dataclass
class NoisyFakeEngine(FakeEngine):
    async def process_audio_file(self, call_id: str, audio_path: str) -> VoiceTurnResult:
        print("internal agent log that must not reach JSONL protocol stdout")
        return await super().process_audio_file(call_id, audio_path)


@dataclass
class EventFakeEngine(FakeEngine):
    async def apply_answer(self, call_id: str, sdp: dict, ice_candidates: list) -> None:
        await super().apply_answer(call_id, sdp, ice_candidates)
        await self.event_sink(  # type: ignore[misc]
            {
                "type": "status",
                "callId": call_id,
                "status": "failed",
                "reasonCode": "remote_audio_ended_before_first_frame",
                "details": {"remoteAudioFrames": 0},
            }
        )


@dataclass
class StartEventFakeEngine(FakeEngine):
    async def start_incoming(self, request: dict) -> SimplexSidecarOffer:
        if self.event_sink is not None:
            await self.event_sink(
                {
                    "type": "event",
                    "callId": request["callId"],
                    "event": "local_offer_sdp",
                    "details": {
                        "sdp": {
                            "direction": "sendrecv",
                            "codecs": ["opus"],
                        }
                    },
                }
            )
        return await super().start_incoming(request)


@pytest.mark.asyncio
async def test_sidecar_runner_start_encodes_simplex_offer():
    engine = FakeEngine()
    runner = SimplexNativeSidecarRunner(engine)

    response = await runner.handle_message(
        {
            "type": "start_incoming",
            "callId": "call-1",
            "contactId": "contact-1",
            "media": "audio",
            "encrypted": True,
            "sharedKey": "shared-secret",
        }
    )

    assert response is not None
    assert response["ok"] is True
    offer = response["offer"]
    assert offer["capabilities"] == {"encryption": True}
    assert offer["callDhPubKey"] == "dh-pub-b64"
    assert decode_webrtc_session(offer) == (
        {"type": "offer", "sdp": "v=0\r\nm=audio 9 UDP/TLS/RTP/SAVPF 111\r\n"},
        [{"candidate": "candidate:1", "sdpMid": "0"}],
    )
    assert engine.start_requests == [
        {
            "callId": "call-1",
            "contactId": "contact-1",
            "media": "audio",
            "encrypted": True,
            "sharedKey": "shared-secret",
        }
    ]


@pytest.mark.asyncio
async def test_sidecar_runner_start_outgoing_answer_decodes_offer_and_encodes_answer():
    engine = FakeEngine()
    runner = SimplexNativeSidecarRunner(engine)
    offer_sdp = {"type": "offer", "sdp": "v=0\r\n"}
    offer_ice = [{"candidate": "candidate:offer", "sdpMid": "0"}]

    response = await runner.handle_message(
        {
            "type": "start_outgoing_answer",
            "callId": "call-1",
            "contactId": "contact-1",
            "media": "audio",
            "encrypted": True,
            "sharedKey": "shared-secret",
            "offer": encode_webrtc_session(offer_sdp, offer_ice),
        }
    )

    assert response is not None
    assert response["ok"] is True
    assert decode_webrtc_session(response["answer"]) == (
        {"type": "answer", "sdp": "v=0\r\nm=audio 9 UDP/TLS/RTP/SAVPF 111\r\n"},
        [{"candidate": "candidate:answer", "sdpMid": "0"}],
    )
    assert engine.outgoing_answer_requests == [
        (
            {
                "callId": "call-1",
                "contactId": "contact-1",
                "media": "audio",
                "encrypted": True,
                "sharedKey": "shared-secret",
            },
            offer_sdp,
            offer_ice,
        )
    ]


@pytest.mark.asyncio
async def test_sidecar_runner_applies_compressed_answer():
    engine = FakeEngine()
    runner = SimplexNativeSidecarRunner(engine)
    answer_sdp = {"type": "answer", "sdp": "v=0\r\n"}
    answer_ice = [{"candidate": "candidate:answer", "sdpMid": "0"}]

    response = await runner.handle_message(
        {
            "type": "apply_answer",
            "callId": "call-1",
            "answer": encode_webrtc_session(answer_sdp, answer_ice),
        }
    )

    assert response is None
    assert engine.answers == [("call-1", answer_sdp, answer_ice)]


@pytest.mark.asyncio
async def test_sidecar_runner_accepts_legacy_answer_control_message():
    engine = FakeEngine()
    runner = SimplexNativeSidecarRunner(engine)
    answer_sdp = {"type": "answer", "sdp": "v=0\r\n"}
    answer_ice = [{"candidate": "candidate:answer", "sdpMid": "0"}]
    encoded = encode_webrtc_session(answer_sdp, answer_ice)

    response = await runner.handle_message(
        {
            "type": "answer",
            "callId": "call-1",
            "rtcSession": encoded["rtcSession"],
            "rtcIceCandidates": encoded["rtcIceCandidates"],
            "answer": encoded["rtcSession"],
            "iceCandidates": encoded["rtcIceCandidates"],
        }
    )

    assert response is None
    assert engine.answers == [("call-1", answer_sdp, answer_ice)]


@pytest.mark.asyncio
async def test_sidecar_runner_adds_compressed_extra_ice():
    engine = FakeEngine()
    runner = SimplexNativeSidecarRunner(engine)
    extra_ice = [{"candidate": "candidate:extra", "sdpMid": "0"}]

    response = await runner.handle_message(
        {
            "type": "add_extra_ice",
            "callId": "call-1",
            "extra": {
                "rtcExtraInfo": encode_webrtc_session({"type": "ignored"}, extra_ice)
            },
        }
    )

    assert response is None
    assert engine.extras == [("call-1", extra_ice)]


@pytest.mark.asyncio
async def test_sidecar_runner_accepts_legacy_extra_control_message():
    engine = FakeEngine()
    runner = SimplexNativeSidecarRunner(engine)
    extra_ice = [{"candidate": "candidate:extra", "sdpMid": "0"}]
    encoded = encode_webrtc_session({"type": "ignored"}, extra_ice)

    response = await runner.handle_message(
        {
            "type": "extra",
            "callId": "call-1",
            "rtcIceCandidates": encoded["rtcIceCandidates"],
            "iceCandidates": encoded["rtcIceCandidates"],
        }
    )

    assert response is None
    assert engine.extras == [("call-1", extra_ice)]


@pytest.mark.asyncio
async def test_sidecar_runner_stop_closes_media_engine():
    engine = FakeEngine()
    runner = SimplexNativeSidecarRunner(engine)

    response = await runner.handle_message({"type": "stop", "callId": "call-1"})

    assert response is None
    assert engine.stopped == ["call-1"]


@pytest.mark.asyncio
async def test_sidecar_runner_start_failure_returns_protocol_error():
    engine = FakeEngine(start_error=RuntimeError("missing media backend"))
    runner = SimplexNativeSidecarRunner(engine)

    response = await runner.handle_message({"type": "start_incoming", "callId": "call-1"})

    assert response == {
        "ok": False,
        "code": "call_simplex_native_sidecar_failed",
        "message": "native SimpleX media sidecar failed to start",
    }


@pytest.mark.asyncio
async def test_sidecar_runner_start_failure_can_return_specific_error():
    engine = FakeEngine(
        start_error=SimplexNativeSidecarError(
            "call_simplex_native_dependency_missing",
            "aiortc is not installed",
        )
    )
    runner = SimplexNativeSidecarRunner(engine)

    response = await runner.handle_message({"type": "start_incoming", "callId": "call-1"})

    assert response == {
        "ok": False,
        "code": "call_simplex_native_dependency_missing",
        "message": "aiortc is not installed",
    }


@pytest.mark.asyncio
async def test_sidecar_runner_debug_audio_returns_redacted_voice_turn_metadata():
    engine = FakeEngine()
    runner = SimplexNativeSidecarRunner(engine)

    response = await runner.handle_message(
        {
            "type": "debug_process_audio",
            "callId": "call-1",
            "audioPath": "/tmp/caller.wav",
        }
    )

    assert response == {
        "ok": True,
        "code": "call_voice_turn_completed",
        "message": "Voice turn completed.",
        "transcriptChars": 30,
        "responseChars": 28,
        "audioPath": "/tmp/caller.wav.reply.wav",
        "sttProvider": "fake-stt",
        "ttsProvider": "fake-tts",
    }


@pytest.mark.asyncio
async def test_jsonl_sidecar_keeps_internal_stdout_out_of_protocol_stream():
    stdin = io.StringIO(
        json.dumps(
            {
                "type": "debug_process_audio",
                "callId": "call-1",
                "audioPath": "/tmp/caller.wav",
            }
        )
        + "\n"
    )
    stdout = io.StringIO()

    with contextlib.redirect_stdout(stdout):
        await run_jsonl_sidecar(NoisyFakeEngine(), stdin=stdin)

    lines = stdout.getvalue().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == {
        "ok": True,
        "code": "call_voice_turn_completed",
        "message": "Voice turn completed.",
        "transcriptChars": 30,
        "responseChars": 28,
        "audioPath": "/tmp/caller.wav.reply.wav",
        "sttProvider": "fake-stt",
        "ttsProvider": "fake-tts",
    }


@pytest.mark.asyncio
async def test_jsonl_sidecar_emits_async_media_events():
    answer_sdp = {"type": "answer", "sdp": "v=0\r\n"}
    answer_ice = [{"candidate": "candidate:answer", "sdpMid": "0"}]
    stdin = io.StringIO(
        json.dumps(
            {
                "type": "apply_answer",
                "callId": "call-1",
                "answer": encode_webrtc_session(answer_sdp, answer_ice),
            }
        )
        + "\n"
    )
    stdout = io.StringIO()

    with contextlib.redirect_stdout(stdout):
        await run_jsonl_sidecar(EventFakeEngine(), stdin=stdin)

    lines = stdout.getvalue().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == {
        "type": "status",
        "callId": "call-1",
        "status": "failed",
        "reasonCode": "remote_audio_ended_before_first_frame",
        "details": {"remoteAudioFrames": 0},
    }


@pytest.mark.asyncio
async def test_jsonl_sidecar_buffers_start_events_until_after_offer_response():
    stdin = io.StringIO(
        json.dumps(
            {
                "type": "start_incoming",
                "callId": "call-1",
                "contactId": "contact-1",
                "media": "audio",
                "encrypted": True,
            }
        )
        + "\n"
    )
    stdout = io.StringIO()

    with contextlib.redirect_stdout(stdout):
        await run_jsonl_sidecar(StartEventFakeEngine(), stdin=stdin)

    lines = [json.loads(line) for line in stdout.getvalue().splitlines()]
    assert len(lines) == 2
    assert lines[0]["ok"] is True
    assert lines[0]["offer"]["callDhPubKey"] == "dh-pub-b64"
    assert lines[1] == {
        "type": "event",
        "callId": "call-1",
        "event": "local_offer_sdp",
        "details": {
            "sdp": {
                "direction": "sendrecv",
                "codecs": ["opus"],
            }
        },
    }
