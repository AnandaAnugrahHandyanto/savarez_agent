from __future__ import annotations

import asyncio
import struct
import wave
from dataclasses import dataclass, field
from types import SimpleNamespace
from pathlib import Path

import pytest

# aiortc/av live in the optional `simplex-native-calls` extra, which is not
# part of `[all]` (per the pyproject `[all]` policy), so they are absent in
# the default CI install. Skip the whole module instead of erroring at
# collection when they are unavailable.
pytest.importorskip("av")
pytest.importorskip("aiortc")
from av import AudioFrame

from gateway.calls.native.aiortc_engine import (
    AiortcAudioPeer,
    SimplexAiortcMediaEngine,
    SimplexAiortcConfig,
    _audio_frame_to_pcm16,
    decrypt_simplex_audio_payload,
    decode_simplex_media_key,
    encrypt_simplex_audio_payload,
    allow_trickle_ice_after_remote_description,
    collect_webrtc_stats_summary,
    describe_peer_connection_state,
    describe_sdp,
    prepare_local_offer_transport,
    patch_aiortc_connection_kwargs_for_relay,
    retain_only_relay_candidates_in_sdp,
    run_aiortc_loopback_probe,
    run_aiortc_voice_turn_simulation,
)
from gateway.calls.native.voice_turn import VoiceTurnResult
from gateway.calls.native.webrtc_media import pcm16_rms


@dataclass
class FakePeer:
    offers: list[str] = field(default_factory=list)
    answers: list[tuple[dict, list]] = field(default_factory=list)
    created_answers: list[tuple[dict, list]] = field(default_factory=list)
    extras: list[list] = field(default_factory=list)
    closed: bool = False
    terminal_callback: object | None = None
    event_callback: object | None = None

    async def start(self, call_id: str, pipeline) -> None:
        self.offers.append(call_id)

    async def create_offer(self) -> tuple[dict, list]:
        return (
            {"type": "offer", "sdp": "v=0\r\nm=audio 9 UDP/TLS/RTP/SAVPF 111\r\n"},
            [{"candidate": "candidate:1", "sdpMid": "0"}],
        )

    async def apply_answer(self, sdp: dict, ice_candidates: list) -> None:
        self.answers.append((sdp, ice_candidates))

    async def create_answer(self, sdp: dict, ice_candidates: list) -> tuple[dict, list]:
        self.created_answers.append((sdp, ice_candidates))
        return (
            {"type": "answer", "sdp": "v=0\r\nm=audio 9 UDP/TLS/RTP/SAVPF 111\r\n"},
            [{"candidate": "candidate:answer", "sdpMid": "0"}],
        )

    async def add_extra_ice(self, ice_candidates: list) -> None:
        self.extras.append(ice_candidates)

    async def close(self) -> None:
        self.closed = True

    def set_terminal_callback(self, callback) -> None:
        self.terminal_callback = callback

    def set_event_callback(self, callback) -> None:
        self.event_callback = callback


@dataclass
class FakeVoiceTurnPipeline:
    calls: list[tuple[str, bytes, int]] = field(default_factory=list)

    async def process_pcm16(
        self,
        *,
        call_id: str,
        pcm16: bytes,
        sample_rate: int,
    ) -> VoiceTurnResult:
        self.calls.append((call_id, pcm16, sample_rate))
        return VoiceTurnResult(
            ok=True,
            code="call_voice_turn_completed",
            message="Voice turn completed.",
            transcript="private words",
            response_text="private response",
            audio_path=Path("/tmp/reply.wav"),
        )


def _write_wav(path: Path, pcm16: bytes, sample_rate: int = 16000) -> None:
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm16)


def test_simplex_audio_payload_encryption_round_trips_preserving_opus_toc():
    key = b"0123456789abcdef0123456789abcdef"
    payload = b"\x78encoded-opus-frame"

    encrypted = encrypt_simplex_audio_payload(payload, key, iv=b"123456789012")
    decrypted = decrypt_simplex_audio_payload(encrypted, key)

    assert encrypted[0:1] == payload[0:1]
    assert encrypted != payload
    assert encrypted.endswith(b"123456789012")
    assert decrypted == payload


def test_simplex_audio_payload_encryption_appends_iv_for_prefix_only_frame():
    key = b"0123456789abcdef0123456789abcdef"
    payload = b"\x78"

    encrypted = encrypt_simplex_audio_payload(payload, key, iv=b"123456789012")
    decrypted = decrypt_simplex_audio_payload(encrypted, key)

    assert encrypted == payload + b"123456789012"
    assert decrypted == payload


def test_decode_simplex_media_key_accepts_base64url_without_padding():
    key_text = "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY"

    assert decode_simplex_media_key(key_text) == b"0123456789abcdef0123456789abcdef"


@pytest.mark.asyncio
async def test_aiortc_audio_peer_applies_simplex_media_e2ee_to_sender_and_receiver():
    key_text = "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY"
    key = decode_simplex_media_key(key_text)
    outbound_payload = b"\x78outbound-opus-frame"
    inbound_payload = b"\x78inbound-opus-frame"
    received_payloads = []

    async def next_encoded_frame(codec):
        return SimpleNamespace(payloads=[outbound_payload], timestamp=0, audio_level=None)

    async def handle_rtp_packet(packet, arrival_time_ms):
        received_payloads.append(packet.payload)

    sender = SimpleNamespace(_next_encoded_frame=next_encoded_frame)
    receiver = SimpleNamespace(_handle_rtp_packet=handle_rtp_packet)
    peer = AiortcAudioPeer(
        SimplexAiortcConfig(enable_simplex_media_e2ee=True)
    )
    peer._shared_media_key = key
    peer._pc = SimpleNamespace(
        getTransceivers=lambda: [
            SimpleNamespace(sender=sender, receiver=receiver)
        ]
    )

    await peer._apply_simplex_media_e2ee()

    assert getattr(sender, "_hermes_simplex_media_e2ee", False) is True
    assert getattr(receiver, "_hermes_simplex_media_e2ee", False) is True
    encrypted_frame = await sender._next_encoded_frame(None)
    assert encrypted_frame.payloads[0] != outbound_payload
    assert decrypt_simplex_audio_payload(encrypted_frame.payloads[0], key) == outbound_payload

    inbound_packet = SimpleNamespace(
        payload=encrypt_simplex_audio_payload(inbound_payload, key, iv=b"abcdefghijkl")
    )
    await receiver._handle_rtp_packet(inbound_packet, 0)
    assert received_payloads == [inbound_payload]


def test_audio_frame_to_pcm16_scales_float_planar_audio():
    frame = AudioFrame(format="fltp", layout="mono", samples=4)
    frame.sample_rate = 48000
    frame.planes[0].update(struct.pack("<ffff", 0.0, 0.5, -0.5, 0.25))

    pcm16 = _audio_frame_to_pcm16(frame)

    assert len(pcm16) == 8
    assert pcm16_rms(pcm16) > 1000


def test_patch_aiortc_connection_kwargs_forces_relay_policy_idempotently():
    def original_connection_kwargs(servers):
        return {"servers": servers}

    rtcice_module = SimpleNamespace(connection_kwargs=original_connection_kwargs)

    patch_aiortc_connection_kwargs_for_relay(rtcice_module, "relay")
    first_patch = rtcice_module.connection_kwargs
    patch_aiortc_connection_kwargs_for_relay(rtcice_module, "relay")

    assert rtcice_module.connection_kwargs is first_patch
    assert rtcice_module.connection_kwargs(["turns:turn.simplex.im"]) == {
        "servers": ["turns:turn.simplex.im"],
        "transport_policy": "relay",
    }


def test_allow_trickle_ice_after_remote_description_resets_internal_end_marker():
    connection = SimpleNamespace(_remote_candidates_end=True)
    pc = SimpleNamespace(
        getTransceivers=lambda: [
            SimpleNamespace(
                receiver=SimpleNamespace(
                    transport=SimpleNamespace(
                        transport=SimpleNamespace(_connection=connection)
                    )
                )
            )
        ]
    )

    allow_trickle_ice_after_remote_description(pc)

    assert connection._remote_candidates_end is False


def test_describe_sdp_returns_redacted_media_facts():
    summary = describe_sdp(
        "\r\n".join(
            [
                "v=0",
                "m=audio 9 UDP/TLS/RTP/SAVPF 111 0",
                "a=mid:0",
                "a=sendrecv",
                "a=rtpmap:111 opus/48000/2",
                "a=rtpmap:0 PCMU/8000",
                "a=setup:actpass",
                "a=ice-ufrag:private",
                "a=extmap:1 urn:ietf:params:rtp-hdrext:ssrc-audio-level",
                "a=candidate:1 1 udp 1 192.0.2.1 10000 typ host",
                "a=candidate:2 1 udp 1 198.51.100.1 10001 typ relay",
                "a=end-of-candidates",
                "",
            ]
        )
    )

    assert summary == {
        "audioMLinePayloads": ["111", "0"],
        "candidateTypes": {"host": 1, "relay": 1},
        "codecs": ["opus", "pcmu"],
        "direction": "sendrecv",
        "endOfCandidates": True,
        "extmapCount": 1,
        "iceUfragPresent": True,
        "mediaSections": 1,
        "midCount": 1,
        "setup": "actpass",
    }


def test_retain_only_relay_candidates_in_sdp_removes_host_and_srflx_candidates():
    sdp = "\r\n".join(
        [
            "v=0",
            "m=audio 9 UDP/TLS/RTP/SAVPF 96",
            "a=sendrecv",
            "a=candidate:host 1 udp 1 192.0.2.1 10000 typ host",
            "a=candidate:srflx 1 udp 1 198.51.100.1 10001 typ srflx raddr 10.0.0.1 rport 10001",
            "a=candidate:relay 1 tcp 1 203.0.113.1 443 typ relay raddr 0.0.0.0 rport 0",
            "a=end-of-candidates",
            "",
        ]
    )

    pruned = retain_only_relay_candidates_in_sdp(sdp)

    assert " typ host" not in pruned
    assert " typ srflx" not in pruned
    assert " typ relay" in pruned
    assert describe_sdp(pruned)["candidateTypes"] == {"relay": 1}


def test_default_offer_transport_keeps_gathered_candidates_for_tailnet_paths():
    sdp = "\r\n".join(
        [
            "v=0",
            "m=audio 9 UDP/TLS/RTP/SAVPF 96",
            "a=sendrecv",
            "a=candidate:host 1 udp 1 100.117.103.71 50000 typ host",
            "a=candidate:relay 1 tcp 1 203.0.113.1 443 typ relay raddr 0.0.0.0 rport 0",
            "",
        ]
    )
    candidates = [
        {"candidate": "candidate:host 1 udp 1 100.117.103.71 50000 typ host"},
        {"candidate": "candidate:relay 1 tcp 1 203.0.113.1 443 typ relay"},
    ]

    prepared_sdp, prepared_candidates = prepare_local_offer_transport(
        sdp,
        candidates,
        SimplexAiortcConfig(ice_transport_policy="relay"),
    )

    assert " typ host" in prepared_sdp
    assert " typ relay" in prepared_sdp
    assert prepared_candidates == candidates


def test_offer_transport_can_prune_to_relay_when_explicitly_enabled():
    sdp = "\r\n".join(
        [
            "v=0",
            "m=audio 9 UDP/TLS/RTP/SAVPF 96",
            "a=sendrecv",
            "a=candidate:host 1 udp 1 100.117.103.71 50000 typ host",
            "a=candidate:relay 1 tcp 1 203.0.113.1 443 typ relay raddr 0.0.0.0 rport 0",
            "",
        ]
    )
    candidates = [
        {"candidate": "candidate:host 1 udp 1 100.117.103.71 50000 typ host"},
        {"candidate": "candidate:relay 1 tcp 1 203.0.113.1 443 typ relay"},
    ]

    prepared_sdp, prepared_candidates = prepare_local_offer_transport(
        sdp,
        candidates,
        SimplexAiortcConfig(
            ice_transport_policy="relay",
            prune_non_relay_candidates=True,
        ),
    )

    assert " typ host" not in prepared_sdp
    assert " typ relay" in prepared_sdp
    assert prepared_candidates == [
        {"candidate": "candidate:relay 1 tcp 1 203.0.113.1 443 typ relay"}
    ]


@pytest.mark.asyncio
async def test_collect_webrtc_stats_summary_includes_redacted_selected_ice_pair():
    local_candidate = SimpleNamespace(type="relay", transport="tcp", component=1)
    remote_candidate = SimpleNamespace(type="srflx", transport="udp", component=1)
    pair = SimpleNamespace(
        state=SimpleNamespace(name="SUCCEEDED"),
        nominated=True,
        local_candidate=local_candidate,
        remote_candidate=remote_candidate,
    )
    connection = SimpleNamespace(_nominated={1: pair})

    async def get_stats():
        return {}

    pc = SimpleNamespace(
        getStats=get_stats,
        getTransceivers=lambda: [
            SimpleNamespace(
                receiver=SimpleNamespace(
                    transport=SimpleNamespace(
                        transport=SimpleNamespace(_connection=connection)
                    )
                )
            )
        ],
    )

    summary = await collect_webrtc_stats_summary(pc)

    assert summary["selectedIcePairs"] == [
        {
            "component": 1,
            "state": "SUCCEEDED",
            "nominated": True,
            "local": {"type": "relay", "protocol": "tcp", "component": 1},
            "remote": {"type": "srflx", "protocol": "udp", "component": 1},
        }
    ]


def test_describe_peer_connection_state_returns_redacted_transceiver_facts():
    ice_connection = SimpleNamespace(_remote_candidates_end=True)
    dtls_transport = SimpleNamespace(
        state="connected",
        transport=SimpleNamespace(
            role="controlled",
            state="completed",
            _connection=ice_connection,
        ),
    )
    pc = SimpleNamespace(
        connectionState="connected",
        iceConnectionState="completed",
        iceGatheringState="complete",
        signalingState="stable",
        getTransceivers=lambda: [
            SimpleNamespace(
                mid="0",
                direction="sendrecv",
                currentDirection="sendrecv",
                stopped=False,
                receiver=SimpleNamespace(
                    track=SimpleNamespace(kind="audio", readyState="live"),
                    transport=dtls_transport,
                ),
                sender=SimpleNamespace(
                    track=SimpleNamespace(kind="audio", readyState="live"),
                    transport=dtls_transport,
                ),
            )
        ],
    )

    summary = describe_peer_connection_state(pc)

    assert summary == {
        "connectionState": "connected",
        "iceConnectionState": "completed",
        "iceGatheringState": "complete",
        "signalingState": "stable",
        "transceivers": [
            {
                "mid": "0",
                "direction": "sendrecv",
                "currentDirection": "sendrecv",
                "stopped": False,
                "receiver": {
                    "trackKind": "audio",
                    "trackReadyState": "live",
                    "dtlsState": "connected",
                    "iceRole": "controlled",
                    "iceState": "completed",
                    "remoteCandidatesEnd": True,
                },
                "sender": {
                    "trackKind": "audio",
                    "trackReadyState": "live",
                    "dtlsState": "connected",
                    "iceRole": "controlled",
                    "iceState": "completed",
                    "remoteCandidatesEnd": True,
                },
            }
        ],
    }


@pytest.mark.asyncio
async def test_no_inbound_watchdog_emits_redacted_peer_state():
    events: list[tuple[str, dict]] = []
    peer = AiortcAudioPeer(
        SimplexAiortcConfig(
            ice_servers=[],
            no_inbound_audio_timeout=0.0,
        )
    )

    async def get_stats():
        return {}

    peer._call_id = "call-1"
    peer._pc = SimpleNamespace(
        getStats=get_stats,
        connectionState="connected",
        iceConnectionState="completed",
        iceGatheringState="complete",
        signalingState="stable",
        getTransceivers=lambda: [],
    )
    peer.set_event_callback(lambda event, details: events.append((event, details)))

    await peer._no_inbound_watchdog()

    assert events == [
        (
            "no_inbound_audio_frames",
            {
                "remoteAudioFrames": 0,
                "stats": {
                    "inboundRtp": [],
                    "outboundRtp": [],
                    "candidatePairs": [],
                    "selectedIcePairs": [],
                    "localCandidateTypes": {},
                    "remoteCandidateTypes": {},
                },
                "peerState": {
                    "connectionState": "connected",
                    "iceConnectionState": "completed",
                    "iceGatheringState": "complete",
                    "signalingState": "stable",
                    "transceivers": [],
                },
            },
        )
    ]


@pytest.mark.asyncio
async def test_no_inbound_watchdog_still_emits_when_stats_collection_hangs():
    events: list[tuple[str, dict]] = []
    peer = AiortcAudioPeer(
        SimplexAiortcConfig(
            ice_servers=[],
            no_inbound_audio_timeout=0.0,
            no_inbound_stats_timeout=0.01,
        )
    )

    async def get_stats():
        await asyncio.Event().wait()

    peer._call_id = "call-1"
    peer._pc = SimpleNamespace(
        getStats=get_stats,
        connectionState="connected",
        iceConnectionState="completed",
        iceGatheringState="complete",
        signalingState="stable",
        getTransceivers=lambda: [],
    )
    peer.set_event_callback(lambda event, details: events.append((event, details)))

    await peer._no_inbound_watchdog()

    assert events[0][0] == "no_inbound_audio_frames"
    assert events[0][1]["stats"]["collectionError"] == "timeout"
    assert events[0][1]["peerState"]["connectionState"] == "connected"


@pytest.mark.asyncio
async def test_simplex_aiortc_engine_starts_offer_and_applies_signals():
    peer = FakePeer()
    pipeline = FakeVoiceTurnPipeline()
    engine = SimplexAiortcMediaEngine(
        config=SimplexAiortcConfig(enable_simplex_media_e2ee=True),
        peer_factory=lambda: peer,
        pipeline_factory=lambda: pipeline,
        dh_public_key_factory=lambda: "dh-public-key",
    )

    offer = await engine.start_incoming(
        {
            "callId": "call-1",
            "contactId": "contact-1",
            "media": "audio",
            "encrypted": True,
            "sharedKey": "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY",
        }
    )
    await engine.apply_answer(
        "call-1",
        {"type": "answer", "sdp": "v=0\r\n"},
        [{"candidate": "candidate:answer"}],
    )
    await engine.add_extra_ice("call-1", [{"candidate": "candidate:extra"}])

    assert offer.sdp["type"] == "offer"
    assert offer.ice_candidates == [{"candidate": "candidate:1", "sdpMid": "0"}]
    assert offer.capabilities == {"encryption": True}
    assert offer.call_dh_pub_key == "dh-public-key"
    assert peer.offers == ["call-1"]
    assert peer.answers == [
        ({"type": "answer", "sdp": "v=0\r\n"}, [{"candidate": "candidate:answer"}])
    ]
    assert peer.extras == [[{"candidate": "candidate:extra"}]]


@pytest.mark.asyncio
async def test_simplex_aiortc_engine_answers_outbound_remote_offer():
    peer = FakePeer()
    pipeline = FakeVoiceTurnPipeline()
    engine = SimplexAiortcMediaEngine(
        config=SimplexAiortcConfig(enable_simplex_media_e2ee=True),
        peer_factory=lambda: peer,
        pipeline_factory=lambda: pipeline,
    )

    answer = await engine.start_outgoing_answer(
        {
            "callId": "call-1",
            "contactId": "contact-1",
            "media": "audio",
            "encrypted": True,
            "sharedKey": "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY",
        },
        {"type": "offer", "sdp": "v=0\r\n"},
        [{"candidate": "candidate:offer"}],
    )

    assert answer.sdp["type"] == "answer"
    assert answer.ice_candidates == [{"candidate": "candidate:answer", "sdpMid": "0"}]
    assert peer.offers == ["call-1"]
    assert peer.created_answers == [
        ({"type": "offer", "sdp": "v=0\r\n"}, [{"candidate": "candidate:offer"}])
    ]


@pytest.mark.asyncio
async def test_simplex_aiortc_engine_declines_insertable_stream_e2ee_by_default():
    peer = FakePeer()
    events: list[dict] = []
    engine = SimplexAiortcMediaEngine(
        peer_factory=lambda: peer,
        pipeline_factory=FakeVoiceTurnPipeline,
        dh_public_key_factory=lambda: "dh-public-key",
    )
    engine.set_event_sink(events.append)

    offer = await engine.start_incoming(
        {
            "callId": "call-1",
            "contactId": "contact-1",
            "media": "audio",
            "encrypted": True,
        }
    )

    assert offer.capabilities == {"encryption": False}
    assert offer.call_dh_pub_key is None
    assert events == [
        {
            "type": "event",
            "callId": "call-1",
            "event": "simplex_media_e2ee_disabled",
            "details": {
                "requested": True,
                "reason": "simplex_media_e2ee_not_enabled",
            },
        }
    ]


@pytest.mark.asyncio
async def test_simplex_aiortc_engine_declines_e2ee_when_shared_key_is_invalid():
    peer = FakePeer()
    events: list[dict] = []
    engine = SimplexAiortcMediaEngine(
        config=SimplexAiortcConfig(enable_simplex_media_e2ee=True),
        peer_factory=lambda: peer,
        pipeline_factory=FakeVoiceTurnPipeline,
        dh_public_key_factory=lambda: "dh-public-key",
    )
    engine.set_event_sink(events.append)

    offer = await engine.start_incoming(
        {
            "callId": "call-1",
            "contactId": "contact-1",
            "media": "audio",
            "encrypted": True,
            "sharedKey": "not-a-simplex-media-key",
        }
    )

    assert offer.capabilities == {"encryption": False}
    assert offer.call_dh_pub_key is None
    assert events == [
        {
            "type": "event",
            "callId": "call-1",
            "event": "simplex_media_e2ee_unavailable",
            "details": {"reason": "invalid_shared_key"},
        },
        {
            "type": "event",
            "callId": "call-1",
            "event": "simplex_media_e2ee_disabled",
            "details": {
                "requested": True,
                "reason": "invalid_shared_key",
            },
        },
    ]


@pytest.mark.asyncio
async def test_simplex_aiortc_engine_processes_debug_wav_and_closes_peer(tmp_path):
    peer = FakePeer()
    pipeline = FakeVoiceTurnPipeline()
    engine = SimplexAiortcMediaEngine(
        peer_factory=lambda: peer,
        pipeline_factory=lambda: pipeline,
        dh_public_key_factory=lambda: "dh-public-key",
    )
    pcm16 = struct.pack("<hhhh", 100, -100, 200, -200)
    wav_path = tmp_path / "caller.wav"
    _write_wav(wav_path, pcm16, sample_rate=16000)

    await engine.start_incoming({"callId": "call-1", "contactId": "contact-1"})
    result = await engine.process_audio_file("call-1", str(wav_path))
    await engine.stop("call-1")

    assert result.ok is True
    assert pipeline.calls == [("call-1", pcm16, 16000)]
    assert peer.closed is True


@pytest.mark.asyncio
async def test_simplex_aiortc_engine_emits_terminal_event_and_removes_session():
    peer = FakePeer()
    events: list[dict] = []
    engine = SimplexAiortcMediaEngine(
        peer_factory=lambda: peer,
        pipeline_factory=FakeVoiceTurnPipeline,
    )
    engine.set_event_sink(events.append)

    await engine.start_incoming({"callId": "call-1", "contactId": "contact-1"})
    await peer.terminal_callback(  # type: ignore[misc]
        "failed",
        "remote_audio_ended_before_first_frame",
        {"remoteAudioFrames": 0},
    )

    assert peer.closed is True
    assert events == [
        {
            "type": "status",
            "callId": "call-1",
            "status": "failed",
            "reasonCode": "remote_audio_ended_before_first_frame",
            "details": {"remoteAudioFrames": 0},
        }
    ]
    with pytest.raises(RuntimeError, match="No active native call session"):
        await engine.apply_answer("call-1", {"type": "answer", "sdp": "v=0\r\n"}, [])


@pytest.mark.asyncio
async def test_simplex_aiortc_engine_forwards_redacted_media_events():
    peer = FakePeer()
    events: list[dict] = []
    engine = SimplexAiortcMediaEngine(
        peer_factory=lambda: peer,
        pipeline_factory=FakeVoiceTurnPipeline,
    )
    engine.set_event_sink(events.append)

    await engine.start_incoming({"callId": "call-1", "contactId": "contact-1"})
    await peer.event_callback(  # type: ignore[misc]
        "remote_answer_sdp",
        {
            "sdp": {
                "direction": "sendrecv",
                "codecs": ["opus"],
            },
        },
    )

    assert events == [
        {
            "type": "event",
            "callId": "call-1",
            "event": "remote_answer_sdp",
            "details": {
                "sdp": {
                    "direction": "sendrecv",
                    "codecs": ["opus"],
                },
            },
        }
    ]


@pytest.mark.asyncio
async def test_aiortc_loopback_probe_receives_remote_rtp_frames():
    result = await run_aiortc_loopback_probe(timeout_seconds=8.0)

    assert result.ok is True
    assert result.remote_audio_frames > 0
    assert result.local_sdp["direction"] == "sendrecv"
    assert result.remote_sdp["direction"] == "sendrecv"


@pytest.mark.asyncio
async def test_aiortc_loopback_probe_can_require_voice_turn_input():
    result = await run_aiortc_loopback_probe(
        timeout_seconds=8.0,
        require_voice_turn=True,
    )

    assert result.ok is True
    assert result.remote_audio_frames > 0
    assert result.voice_turns == 1
    assert result.voice_pcm_bytes > 0


@pytest.mark.asyncio
async def test_aiortc_voice_turn_simulation_receives_response_audio(tmp_path):
    caller_audio = tmp_path / "caller.wav"
    reply_audio = tmp_path / "reply.wav"
    frame_samples = 48000 // 50
    caller_pcm = struct.pack(
        "<" + "h" * (frame_samples * 12),
        *([2200] * (frame_samples * 12)),
    )
    reply_pcm = struct.pack(
        "<" + "h" * (frame_samples * 8),
        *([2600] * (frame_samples * 8)),
    )
    _write_wav(caller_audio, caller_pcm, sample_rate=48000)
    _write_wav(reply_audio, reply_pcm, sample_rate=48000)

    class SimulatedPipeline:
        async def process_pcm16(self, *, call_id: str, pcm16: bytes, sample_rate: int):
            assert call_id == "voice-sim"
            assert len(pcm16) > 0
            assert sample_rate == 48000
            return VoiceTurnResult(
                ok=True,
                code="call_voice_turn_completed",
                message="Voice turn completed.",
                transcript="hello hermes",
                response_text="hello from hermes",
                audio_path=reply_audio,
                stt_provider="simulated-stt",
                tts_provider="simulated-tts",
            )

    result = await run_aiortc_voice_turn_simulation(
        call_id="voice-sim",
        contact_id="simulated-contact",
        audio_path=caller_audio,
        expected_transcript="hello hermes",
        trace_root=tmp_path / "traces",
        timeout_seconds=8.0,
        pipeline_factory=SimulatedPipeline,
    )

    assert result.ok is True
    assert result.offer_sent is True
    assert result.answer_applied is True
    assert result.connected is True
    assert result.inbound_audio_frames > 0
    assert result.transcript_chars == len("hello hermes")
    assert result.expected_transcript_present is True
    assert result.agent_response_chars == len("hello from hermes")
    assert result.tts_audio_bytes == reply_audio.stat().st_size
    assert result.remote_received_audio_frames > 0
    assert result.remote_received_non_silent_frames > 0
    trace_text = result.trace_path.read_text(encoding="utf-8")
    assert "simulation_started" in trace_text
    assert "outbound_tts_audio_queued" in trace_text
    assert "outbound_tts_playback_started" in trace_text
    assert "simulation_completed" in trace_text
    assert "hello hermes" not in trace_text
