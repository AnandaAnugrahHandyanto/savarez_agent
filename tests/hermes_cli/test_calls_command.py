from __future__ import annotations

import json
import subprocess
import sys
import textwrap
import asyncio
from pathlib import Path
from types import SimpleNamespace

from hermes_cli.calls import (
    _simplex_acceptance_summary,
    _simplex_observation_summary,
    _call_voice_provider_health,
    _redact_simplex_event,
    _simplex_event_watch,
    _simplex_live_debug,
    _simplex_live_debug_verdict,
    _summarize_trace_file,
    _summarize_simplex_chat_response,
    _summarize_simplex_chats_response,
    cmd_calls,
)


def _write_child(tmp_path, source: str) -> list[str]:
    child_path = tmp_path / "fake_sidecar.py"
    child_path.write_text(textwrap.dedent(source), encoding="utf-8")
    return [sys.executable, str(child_path)]


def test_calls_trace_lists_available_call_traces(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    trace_dir = tmp_path / "logs" / "calls"
    trace_dir.mkdir(parents=True)
    (trace_dir / "call-1.jsonl").write_text('{"event":"ok"}\n', encoding="utf-8")

    cmd_calls(SimpleNamespace(calls_command="trace", call_id=None, trace_root=None, lines=20))

    output = capsys.readouterr().out
    assert "call-1.jsonl" in output


def test_calls_trace_prints_existing_trace(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    trace_dir = tmp_path / "logs" / "calls"
    trace_dir.mkdir(parents=True)
    (trace_dir / "call-1.jsonl").write_text(
        '{"event":"native_signal_received","payload":{"rtcSession":"[REDACTED]"}}\n',
        encoding="utf-8",
    )

    cmd_calls(SimpleNamespace(calls_command="trace", call_id="call-1", trace_root=None, lines=20))

    output = capsys.readouterr().out
    assert "native_signal_received" in output
    assert "[REDACTED]" in output


def test_calls_trace_lists_date_partitioned_call_traces(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    trace_dir = tmp_path / "logs" / "calls" / "2026-05-31"
    trace_dir.mkdir(parents=True)
    (trace_dir / "call-live.jsonl").write_text('{"event":"ok"}\n', encoding="utf-8")

    cmd_calls(SimpleNamespace(calls_command="trace", call_id=None, trace_root=None, lines=20))

    output = capsys.readouterr().out
    assert "2026-05-31/call-live.jsonl" in output


def test_calls_trace_prints_date_partitioned_trace_by_call_id(
    monkeypatch, tmp_path, capsys
):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    trace_dir = tmp_path / "logs" / "calls" / "2026-05-31"
    trace_dir.mkdir(parents=True)
    (trace_dir / "call-live.jsonl").write_text(
        '{"event":"webrtc_connected"}\n',
        encoding="utf-8",
    )

    rc = cmd_calls(
        SimpleNamespace(calls_command="trace", call_id="call-live", trace_root=None, lines=20)
    )

    output = capsys.readouterr().out
    assert rc == 0
    assert "webrtc_connected" in output


def test_calls_simulate_simplex_native_outputs_json_result(tmp_path, capsys):
    command = _write_child(
        tmp_path,
        """
        import json
        import sys

        sys.stdin.readline()
        sys.stdout.write(json.dumps({
            "ok": True,
            "offer": {
                "rtcSession": "offer-secret-sdp",
                "rtcIceCandidates": "offer-secret-ice",
            },
        }) + "\\n")
        sys.stdout.flush()
        sys.stdin.readline()
        sys.stdin.readline()
        sys.stdin.readline()
        """,
    )
    trace_root = tmp_path / "traces"

    cmd_calls(
        SimpleNamespace(
            calls_command="simulate-simplex-native",
            sidecar_command=command,
            call_id="cli-sim-call",
            contact_id="contact-1",
            trace_root=str(trace_root),
            timeout=0.5,
            encrypted=False,
            shared_key=None,
            json=True,
        )
    )

    result = json.loads(capsys.readouterr().out)
    trace_text = (trace_root / "cli-sim-call.jsonl").read_text(encoding="utf-8")
    assert result["ok"] is True
    assert result["code"] == "call_simplex_native_simulation_passed"
    assert result["trace_path"].endswith("cli-sim-call.jsonl")
    assert "offer-secret-sdp" not in trace_text


def test_calls_simplex_native_sidecar_dispatches_runner(monkeypatch):
    called = []

    async def fake_run_sidecar():
        called.append(True)

    monkeypatch.setattr(
        "gateway.calls.native.aiortc_engine.run_simplex_aiortc_sidecar",
        fake_run_sidecar,
    )

    rc = cmd_calls(SimpleNamespace(calls_command="simplex-native-sidecar"))

    assert rc == 0
    assert called == [True]


def test_calls_loopback_aiortc_outputs_json_probe_result(monkeypatch, capsys):
    class FakeProbeResult:
        ok = True
        remote_audio_frames = 3
        voice_turns = 1
        voice_pcm_bytes = 9600
        local_sdp = {"direction": "sendrecv"}
        remote_sdp = {"direction": "sendrecv"}
        message = ""
        stats = {"inboundRtp": [{"packetsReceived": 3}]}

    async def fake_probe(*, timeout_seconds, require_voice_turn):
        assert timeout_seconds == 2.5
        assert require_voice_turn is True
        return FakeProbeResult()

    monkeypatch.setattr(
        "gateway.calls.native.aiortc_engine.run_aiortc_loopback_probe",
        fake_probe,
    )

    rc = cmd_calls(
        SimpleNamespace(
            calls_command="loopback-aiortc",
            timeout=2.5,
            voice_turn=True,
            json=True,
        )
    )

    result = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert result["ok"] is True
    assert result["remote_audio_frames"] == 3
    assert result["voice_turns"] == 1
    assert result["voice_pcm_bytes"] == 9600
    assert result["local_sdp"]["direction"] == "sendrecv"


def test_calls_simplex_simulate_voice_turn_outputs_json(monkeypatch, capsys):
    class FakeSimulationResult:
        ok = True
        code = "call_simplex_voice_turn_simulation_passed"
        message = "SimpleX simulated voice turn passed."
        call_id = "voice-sim"
        contact_id = "simulated-contact"
        trace_path = Path("/tmp/voice-sim.jsonl")
        offer_sent = True
        answer_applied = True
        connected = True
        inbound_audio_frames = 12
        transcript_chars = 18
        expected_transcript_present = True
        agent_response_chars = 24
        tts_audio_bytes = 4096
        remote_received_audio_frames = 30
        remote_received_non_silent_frames = 10
        local_sdp = {"direction": "sendrecv"}
        remote_sdp = {"direction": "sendrecv"}
        events = ["simulation_started", "simulation_completed"]

    async def fake_simulation(**kwargs):
        assert kwargs["call_id"] == "voice-sim"
        assert kwargs["audio_path"] == "/tmp/caller.wav"
        assert kwargs["expected_transcript"] == "hello hermes"
        assert kwargs["timeout_seconds"] == 4.5
        return FakeSimulationResult()

    monkeypatch.setattr(
        "gateway.calls.native.aiortc_engine.run_aiortc_voice_turn_simulation",
        fake_simulation,
    )

    rc = cmd_calls(
        SimpleNamespace(
            calls_command="simplex-simulate-voice-turn",
            call_id="voice-sim",
            contact_id="simulated-contact",
            trace_root=None,
            audio_path="/tmp/caller.wav",
            caller_text="hello hermes",
            expect_transcript="hello hermes",
            timeout=4.5,
            json=True,
        )
    )

    result = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert result["code"] == "call_simplex_voice_turn_simulation_passed"
    assert result["offer_sent"] is True
    assert result["answer_applied"] is True
    assert result["connected"] is True
    assert result["inbound_audio_frames"] == 12
    assert result["expected_transcript_present"] is True
    assert result["remote_received_non_silent_frames"] == 10


def test_call_voice_provider_health_flags_nonlocal_tts(monkeypatch):
    monkeypatch.setattr(
        "hermes_cli.config.load_config",
        lambda: {
            "stt": {
                "provider": "local",
                "local": {"model": "base"},
            },
            "tts": {
                "provider": "edge",
            },
        },
    )
    monkeypatch.setattr("hermes_cli.calls._module_available", lambda name: False)
    monkeypatch.setattr("hermes_cli.calls._binary_available", lambda name: name == "whisper")
    # _call_voice_provider_health resolves the STT provider via
    # transcription_tools._get_provider, which probes faster-whisper / the
    # whisper binary through its OWN module-level state (not the helpers
    # mocked above). Pin the resolved provider so the test is deterministic
    # across environments (CI lacks both faster-whisper and the binary).
    monkeypatch.setattr(
        "tools.transcription_tools._get_provider", lambda cfg: "local_command"
    )

    health = _call_voice_provider_health()

    assert health["ok"] is False
    assert health["stt"]["local"] is True
    assert health["stt"]["available"] is True
    assert health["stt"]["provider"] == "local_command"
    assert health["tts"]["local"] is False
    assert health["tts"]["available"] is False
    assert health["tts"]["provider"] == "edge"


def test_calls_voice_health_outputs_json(monkeypatch, capsys):
    monkeypatch.setattr(
        "hermes_cli.calls._call_voice_provider_health",
        lambda: {
            "ok": True,
            "stt": {"provider": "local", "local": True, "available": True},
            "tts": {"provider": "piper", "local": True, "available": True},
        },
    )

    rc = cmd_calls(
        SimpleNamespace(
            calls_command="voice-health",
            json=True,
        )
    )

    result = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert result["ok"] is True
    assert result["tts"]["provider"] == "piper"


def test_calls_simplex_call_enqueues_gateway_request(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    rc = cmd_calls(
        SimpleNamespace(
            calls_command="simplex-call",
            contact_id="4",
            reason="manual-live-test",
            wait_timeout=0.0,
            json=True,
        )
    )

    output = capsys.readouterr().out
    result = json.loads(output)
    request_files = list(
        (tmp_path / "run" / "simplex-native-outbound" / "requests").glob("*.json")
    )

    assert rc == 0
    assert result["ok"] is True
    assert result["queued"] is True
    assert result["contact_id"] == "4"
    assert result["request_id"]
    assert len(request_files) == 1
    request = json.loads(request_files[0].read_text(encoding="utf-8"))
    assert request["type"] == "simplex_native_outbound_call"
    assert request["contact_id"] == "4"
    assert request["reason"] == "manual-live-test"


def test_calls_simplex_health_outputs_redacted_contact_status(monkeypatch, capsys):
    async def fake_health(*, ws_url, contact_id, count, timeout_seconds):
        assert ws_url == "ws://127.0.0.1:5225"
        assert contact_id == "4"
        assert count == 5
        assert timeout_seconds == 3.0
        return {
            "ok": True,
            "contact_id": "4",
            "contact_active": True,
            "connection_ready": True,
            "calls_enabled": True,
            "voice_enabled": True,
            "latest_item": {
                "item_id": 145,
                "direction": "directSnd",
                "content_type": "sndMsgContent",
                "msg_type": "text",
                "text_chars": 65,
            },
            "recent_call_items": 0,
        }

    monkeypatch.setattr("hermes_cli.calls._simplex_health_check", fake_health)

    rc = cmd_calls(
        SimpleNamespace(
            calls_command="simplex-health",
            ws_url="ws://127.0.0.1:5225",
            contact_id="4",
            count=5,
            timeout=3.0,
            json=True,
        )
    )

    result = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert result["ok"] is True
    assert result["calls_enabled"] is True
    assert result["latest_item"]["item_id"] == 145
    assert "Gateway shutting down" not in json.dumps(result)


def test_simplex_health_summary_uses_highest_item_id_as_latest():
    summary = _summarize_simplex_chat_response(
        {
            "resp": {
                "type": "apiChat",
                "chat": {
                    "chatInfo": {
                        "contact": {
                            "contactStatus": "active",
                            "activeConn": {"connStatus": {"type": "ready"}},
                            "mergedPreferences": {
                                "calls": {
                                    "enabled": {"forContact": True, "forUser": True}
                                },
                                "voice": {
                                    "enabled": {"forContact": True, "forUser": True}
                                },
                            },
                        }
                    },
                    "chatItems": [
                        {
                            "chatDir": {"type": "directRcv"},
                            "content": {"type": "rcvcall", "callType": {"media": "audio"}},
                            "meta": {"itemId": 10, "createdAt": "old"},
                        },
                        {
                            "chatDir": {"type": "directSnd"},
                            "content": {
                                "type": "sndMsgContent",
                                "msgContent": {"type": "text", "text": "private text"},
                            },
                            "meta": {"itemId": 12, "createdAt": "new"},
                        },
                    ],
                    "chatStats": {"unreadCount": 0},
                },
            }
        },
        contact_id="4",
    )

    assert summary["latest_item"]["item_id"] == 12
    assert summary["latest_call_item"]["item_id"] == 10
    assert "private text" not in json.dumps(summary)


def test_simplex_health_summary_does_not_treat_text_mentions_as_call_items():
    summary = _summarize_simplex_chat_response(
        {
            "resp": {
                "type": "apiChat",
                "chat": {
                    "chatInfo": {
                        "contact": {
                            "contactStatus": "active",
                            "activeConn": {"connStatus": {"type": "ready"}},
                            "mergedPreferences": {},
                        }
                    },
                    "chatItems": [
                        {
                            "chatDir": {"type": "directSnd"},
                            "content": {
                                "type": "sndMsgContent",
                                "msgContent": {
                                    "type": "text",
                                    "text": "Please place the SimpleX call from here.",
                                },
                            },
                            "meta": {"itemId": 20, "createdAt": "new"},
                        },
                        {
                            "chatDir": {"type": "directRcv"},
                            "content": {"type": "rcvCall", "callType": {"media": "audio"}},
                            "meta": {"itemId": 19, "createdAt": "old"},
                        },
                    ],
                    "chatStats": {"unreadCount": 0},
                },
            }
        },
        contact_id="4",
    )

    assert summary["latest_item"]["item_id"] == 20
    assert summary["latest_call_item"]["item_id"] == 19
    assert summary["recent_call_items"] == 1


def test_simplex_chats_summary_reports_all_contacts_without_text():
    summary = _summarize_simplex_chats_response(
        {
            "resp": {
                "type": "apiChats",
                "chats": [
                    {
                        "chatInfo": {
                            "type": "direct",
                            "contact": {
                                "contactId": 4,
                                "localDisplayName": "Private Name",
                                "contactStatus": "active",
                                "activeConn": {"connStatus": {"type": "ready"}},
                                "mergedPreferences": {
                                    "calls": {
                                        "enabled": {"forContact": True, "forUser": True}
                                    },
                                    "voice": {
                                        "enabled": {"forContact": True, "forUser": True}
                                    },
                                },
                            },
                        },
                        "chatItems": [
                            {
                                "chatDir": {"type": "directRcv"},
                                "content": {
                                    "type": "rcvCall",
                                    "callType": {"media": "audio"},
                                },
                                "meta": {"itemId": 10, "createdAt": "old"},
                            },
                            {
                                "chatDir": {"type": "directSnd"},
                                "content": {
                                    "type": "sndMsgContent",
                                    "msgContent": {
                                        "type": "text",
                                        "text": "private marker",
                                    },
                                },
                                "meta": {"itemId": 11, "createdAt": "new"},
                            },
                        ],
                        "chatStats": {"unreadCount": 0},
                    }
                ],
            }
        }
    )

    assert summary["ok"] is True
    assert summary["contacts"][0]["contact_id"] == "4"
    assert summary["contacts"][0]["latest_item"]["item_id"] == 11
    assert summary["contacts"][0]["latest_call_item"]["item_id"] == 10
    assert "Private Name" not in json.dumps(summary)
    assert "private marker" not in json.dumps(summary)


def test_calls_simplex_watch_reports_new_call_item(monkeypatch, capsys):
    responses = iter(
        [
            {
                "ok": True,
                "contact_id": "4",
                "latest_call_item": {"item_id": 144, "created_at": "old"},
            },
            {
                "ok": True,
                "contact_id": "4",
                "latest_call_item": {"item_id": 146, "created_at": "new"},
            },
        ]
    )

    async def fake_health(*, ws_url, contact_id, count, timeout_seconds):
        assert ws_url == "ws://127.0.0.1:5225"
        assert contact_id == "4"
        assert count == 50
        assert timeout_seconds == 2.0
        return next(responses)

    async def fake_sleep(_seconds):
        return None

    monkeypatch.setattr("hermes_cli.calls._simplex_health_check", fake_health)
    monkeypatch.setattr("hermes_cli.calls.asyncio.sleep", fake_sleep)

    rc = cmd_calls(
        SimpleNamespace(
            calls_command="simplex-watch",
            ws_url="ws://127.0.0.1:5225",
            contact_id="4",
            count=50,
            request_timeout=2.0,
            timeout=10.0,
            interval=0.1,
            json=True,
        )
    )

    result = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert result["ok"] is True
    assert result["baseline_call_item"]["item_id"] == 144
    assert result["latest_call_item"]["item_id"] == 146
    assert result["changed"] is True


def test_calls_simplex_watch_all_reports_any_new_call_item(monkeypatch, capsys):
    responses = iter(
        [
            {
                "ok": True,
                "contacts": [
                    {"contact_id": "4", "latest_call_item": {"item_id": 144}},
                    {"contact_id": "8", "latest_call_item": {"item_id": 2}},
                ],
            },
            {
                "ok": True,
                "contacts": [
                    {"contact_id": "4", "latest_call_item": {"item_id": 144}},
                    {"contact_id": "8", "latest_call_item": {"item_id": 3}},
                ],
            },
        ]
    )

    async def fake_health(*, ws_url, count, timeout_seconds):
        assert ws_url == "ws://127.0.0.1:5225"
        assert count == 50
        assert timeout_seconds == 2.0
        return next(responses)

    async def fake_sleep(_seconds):
        return None

    monkeypatch.setattr("hermes_cli.calls._simplex_all_chats_health_check", fake_health)
    monkeypatch.setattr("hermes_cli.calls.asyncio.sleep", fake_sleep)

    rc = cmd_calls(
        SimpleNamespace(
            calls_command="simplex-watch",
            ws_url="ws://127.0.0.1:5225",
            contact_id="all",
            count=50,
            request_timeout=2.0,
            timeout=10.0,
            interval=0.1,
            json=True,
        )
    )

    result = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert result["ok"] is True
    assert result["changed"] is True
    assert result["changed_contact_id"] == "8"
    assert result["latest_call_item"]["item_id"] == 3


def test_simplex_event_redaction_preserves_call_shape_without_secrets():
    event = {
        "resp": {
            "type": "callInvitation",
            "contact": {
                "contactId": 4,
                "localDisplayName": "Private Name",
            },
            "callInvitation": {
                "callDhPubKey": "secret-dh-key",
                "rtcSession": "secret-session",
                "rtcIceCandidates": "secret-ice",
                "sharedKey": "secret-shared-key",
                "callType": {"media": "audio"},
            },
        }
    }

    redacted = _redact_simplex_event(event)

    dumped = json.dumps(redacted, sort_keys=True)
    assert redacted["resp"]["type"] == "callInvitation"
    assert redacted["resp"]["contact"]["contactId"] == 4
    assert redacted["resp"]["contact"]["localDisplayName"] == "[REDACTED]"
    assert redacted["resp"]["callInvitation"]["callDhPubKey"] == "[REDACTED]"
    assert redacted["resp"]["callInvitation"]["rtcSession"] == "[REDACTED]"
    assert redacted["resp"]["callInvitation"]["rtcIceCandidates"] == "[REDACTED]"
    assert "Private Name" not in dumped
    assert "secret" not in dumped


def test_calls_simplex_events_reports_redacted_raw_call_event(monkeypatch, capsys):
    async def fake_events(*, ws_url, timeout_seconds):
        assert ws_url == "ws://127.0.0.1:5225"
        assert timeout_seconds == 4.0
        return {
            "ok": True,
            "changed": True,
            "checks": 1,
            "event": {
                "resp": {
                    "type": "callInvitation",
                    "contact": {"contactId": 4, "localDisplayName": "Private Name"},
                    "callInvitation": {"rtcSession": "secret-session"},
                }
            },
        }

    monkeypatch.setattr("hermes_cli.calls._simplex_event_watch", fake_events)

    rc = cmd_calls(
        SimpleNamespace(
            calls_command="simplex-events",
            ws_url="ws://127.0.0.1:5225",
            timeout=4.0,
            json=True,
        )
    )

    result = json.loads(capsys.readouterr().out)
    dumped = json.dumps(result, sort_keys=True)
    assert rc == 0
    assert result["ok"] is True
    assert result["event"]["resp"]["type"] == "callInvitation"
    assert result["event"]["resp"]["contact"]["localDisplayName"] == "[REDACTED]"
    assert "secret-session" not in dumped
    assert "Private Name" not in dumped


def test_simplex_event_watch_reports_clean_timeout(monkeypatch):
    class QuietWebSocket:
        async def recv(self):
            await asyncio.sleep(10)

    class Connect:
        def __init__(self, *_args, **_kwargs):
            pass

        async def __aenter__(self):
            return QuietWebSocket()

        async def __aexit__(self, *_exc):
            return None

    monkeypatch.setitem(sys.modules, "websockets", SimpleNamespace(connect=Connect))

    result = asyncio.run(
        _simplex_event_watch(
            ws_url="ws://127.0.0.1:5225",
            timeout_seconds=0.01,
        )
    )

    assert result["ok"] is False
    assert result["changed"] is False
    assert "No SimpleX call websocket event" in result["message"]
    assert "error" not in result


def test_simplex_live_debug_verdict_identifies_inbound_audio_trace(tmp_path):
    trace_path = tmp_path / "call-live.jsonl"
    trace_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "call_id": "call-live",
                        "event": "native_media_event",
                        "data": {"media_event": "remote_track"},
                    }
                ),
                json.dumps(
                    {
                        "call_id": "call-live",
                        "event": "native_media_event",
                        "data": {"media_event": "first_remote_audio_frame"},
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    summary = _summarize_trace_file(trace_path)
    verdict = _simplex_live_debug_verdict(
        simplex_event={"ok": True},
        call_item={"ok": True},
        traces=[summary],
    )

    assert verdict == "inbound_audio_seen"
    assert summary["call_id"] == "call-live"
    assert summary["media_events"] == ["remote_track", "first_remote_audio_frame"]


def test_simplex_live_debug_verdict_identifies_webrtc_connected_trace(tmp_path):
    trace_path = tmp_path / "call-live.jsonl"
    trace_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "call_id": "call-live",
                        "event": "native_media_event",
                        "media_event": "remote_answer_sdp",
                    }
                ),
                json.dumps(
                    {
                        "call_id": "call-live",
                        "event": "native_media_event",
                        "media_event": "connection_state",
                        "details": {"status": "connected"},
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    summary = _summarize_trace_file(trace_path)
    verdict = _simplex_live_debug_verdict(
        simplex_event={"ok": True},
        call_item={"ok": True},
        traces=[summary],
    )

    assert verdict == "webrtc_connected"
    assert "connected" in summary["statuses"]


def test_simplex_acceptance_summary_separates_technical_and_manual_audio(tmp_path):
    trace_path = tmp_path / "call-live.jsonl"
    trace_path.write_text(
        "\n".join(
            [
                json.dumps({"call_id": "call-live", "event": "native_call_registered"}),
                json.dumps(
                    {
                        "call_id": "call-live",
                        "event": "native_signal_received",
                        "signal_type": "answer",
                    }
                ),
                json.dumps(
                    {
                        "call_id": "call-live",
                        "event": "native_media_event",
                        "media_event": "remote_answer_sdp",
                    }
                ),
                json.dumps(
                    {
                        "call_id": "call-live",
                        "event": "native_media_event",
                        "media_event": "connection_state",
                        "details": {"status": "connected"},
                    }
                ),
                json.dumps(
                    {
                        "call_id": "call-live",
                        "event": "native_media_event",
                        "media_event": "first_remote_audio_frame",
                    }
                ),
                json.dumps({"call_id": "call-live", "event": "voice_turn_transcribed"}),
                json.dumps({"call_id": "call-live", "event": "voice_turn_agent_responded"}),
                json.dumps({"call_id": "call-live", "event": "voice_turn_tts_ready"}),
                json.dumps(
                    {
                        "call_id": "call-live",
                        "event": "native_media_event",
                        "media_event": "outbound_tts_playback_started",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    summary = _simplex_acceptance_summary(trace_path, manual_heard=False)

    assert summary["technical_ok"] is True
    assert summary["manual_ok"] is False
    assert summary["ok"] is False
    assert summary["manual_required"] is True
    assert summary["checks"]["outbound_tts_playback_started"] is True


def test_simplex_acceptance_summary_accepts_outbound_offer_answer_trace(tmp_path):
    trace_path = tmp_path / "call-outbound.jsonl"
    trace_path.write_text(
        "\n".join(
            [
                json.dumps({"call_id": "call-outbound", "event": "native_call_registered"}),
                json.dumps(
                    {
                        "call_id": "call-outbound",
                        "event": "native_signal_received",
                        "signal_type": "offer",
                    }
                ),
                json.dumps(
                    {
                        "call_id": "call-outbound",
                        "event": "native_media_event",
                        "media_event": "remote_offer_sdp",
                    }
                ),
                json.dumps(
                    {
                        "call_id": "call-outbound",
                        "event": "native_media_event",
                        "media_event": "local_answer_sdp",
                    }
                ),
                json.dumps(
                    {
                        "call_id": "call-outbound",
                        "event": "native_media_event",
                        "media_event": "connection_state",
                        "details": {"status": "connected"},
                    }
                ),
                json.dumps(
                    {
                        "call_id": "call-outbound",
                        "event": "native_media_event",
                        "media_event": "first_remote_audio_frame",
                    }
                ),
                json.dumps({"call_id": "call-outbound", "event": "voice_turn_transcribed"}),
                json.dumps(
                    {"call_id": "call-outbound", "event": "voice_turn_agent_responded"}
                ),
                json.dumps({"call_id": "call-outbound", "event": "voice_turn_tts_ready"}),
                json.dumps(
                    {
                        "call_id": "call-outbound",
                        "event": "native_media_event",
                        "media_event": "outbound_tts_playback_completed",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    summary = _simplex_acceptance_summary(trace_path, manual_heard=True)

    assert summary["technical_ok"] is True
    assert summary["ok"] is True
    assert summary["checks"]["answer_negotiated"] is True
    assert summary["missing"] == []


def test_calls_simplex_acceptance_outputs_json(monkeypatch, tmp_path, capsys):
    trace_root = tmp_path / "traces"
    trace_root.mkdir()
    trace_path = trace_root / "call-live.jsonl"
    trace_path.write_text(
        "\n".join(
            [
                json.dumps({"call_id": "call-live", "event": "native_call_registered"}),
                json.dumps(
                    {
                        "call_id": "call-live",
                        "event": "native_signal_received",
                        "signal_type": "answer",
                    }
                ),
                json.dumps(
                    {
                        "call_id": "call-live",
                        "event": "native_media_event",
                        "media_event": "remote_answer_sdp",
                    }
                ),
                json.dumps(
                    {
                        "call_id": "call-live",
                        "event": "native_media_event",
                        "media_event": "connection_state",
                        "details": {"status": "connected"},
                    }
                ),
                json.dumps(
                    {
                        "call_id": "call-live",
                        "event": "native_media_event",
                        "media_event": "first_remote_audio_frame",
                    }
                ),
                json.dumps({"call_id": "call-live", "event": "voice_turn_transcribed"}),
                json.dumps({"call_id": "call-live", "event": "voice_turn_agent_responded"}),
                json.dumps({"call_id": "call-live", "event": "voice_turn_tts_ready"}),
                json.dumps(
                    {
                        "call_id": "call-live",
                        "event": "native_media_event",
                        "media_event": "outbound_tts_playback_started",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    rc = cmd_calls(
        SimpleNamespace(
            calls_command="simplex-acceptance",
            call_id="call-live",
            trace_root=str(trace_root),
            manual_heard=True,
            json=True,
        )
    )

    result = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert result["ok"] is True
    assert result["technical_ok"] is True
    assert result["manual_ok"] is True


def test_simplex_observation_summary_reports_observed_voice_turns(tmp_path):
    trace_path = tmp_path / "call-observed.jsonl"
    trace_path.write_text(
        "\n".join(
            [
                json.dumps({"call_id": "call-observed", "event": "native_call_registered"}),
                json.dumps(
                    {
                        "call_id": "call-observed",
                        "event": "voice_turn_transcript_observed",
                        "preview": "Can you tell me about the weather in Lee Wood, Kansas?",
                        "chars": 56,
                        "stt_provider": "local_command",
                        "sensitive": True,
                    }
                ),
                json.dumps(
                    {
                        "call_id": "call-observed",
                        "event": "tool_intent_observed",
                        "intent": "weather",
                        "needs_tool": True,
                    }
                ),
                json.dumps(
                    {
                        "call_id": "call-observed",
                        "event": "voice_turn_agent_response_observed",
                        "preview": "I heard you ask about weather.",
                        "chars": 31,
                        "sensitive": True,
                    }
                ),
                json.dumps(
                    {
                        "call_id": "call-observed",
                        "event": "native_media_event",
                        "media_event": "outbound_tts_playback_completed",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    summary = _simplex_observation_summary(trace_path)

    assert summary["ok"] is True
    assert summary["call_id"] == "call-observed"
    assert summary["turns"] == [
        {
            "transcript_preview": "Can you tell me about the weather in Lee Wood, Kansas?",
            "transcript_chars": 56,
            "stt_provider": "local_command",
            "agent_response_preview": "I heard you ask about weather.",
            "agent_response_chars": 31,
            "tts_playback_started": True,
            "tts_playback_completed": True,
            "outbound_audio_received": False,
            "tool_intents": ["weather"],
        }
    ]
    assert summary["weather_intent_observed"] is True


def test_calls_simplex_observe_outputs_json(monkeypatch, tmp_path, capsys):
    trace_root = tmp_path / "traces"
    trace_root.mkdir()
    trace_path = trace_root / "call-observed.jsonl"
    trace_path.write_text(
        "\n".join(
            [
                json.dumps({"call_id": "call-observed", "event": "native_call_registered"}),
                json.dumps(
                    {
                        "call_id": "call-observed",
                        "event": "voice_turn_transcript_observed",
                        "preview": "hello hermes",
                        "chars": 12,
                    }
                ),
                json.dumps(
                    {
                        "call_id": "call-observed",
                        "event": "voice_turn_agent_response_observed",
                        "preview": "hello back",
                        "chars": 10,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    rc = cmd_calls(
        SimpleNamespace(
            calls_command="simplex-observe",
            call_id="call-observed",
            trace_root=str(trace_root),
            json=True,
        )
    )

    result = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert result["ok"] is True
    assert result["turns"][0]["transcript_preview"] == "hello hermes"
    assert result["turns"][0]["agent_response_preview"] == "hello back"


def test_simplex_live_debug_waits_for_decisive_trace_after_call_seen(
    monkeypatch,
    tmp_path,
):
    trace_path = tmp_path / "call-live.jsonl"

    async def fake_call_item_watch(**_kwargs):
        async def write_later():
            await asyncio.sleep(0.05)
            trace_path.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "call_id": "call-live",
                                "event": "native_media_event",
                                "media_event": "local_offer_sdp",
                            }
                        ),
                        json.dumps(
                            {
                                "call_id": "call-live",
                                "event": "native_media_event",
                                "data": {"media_event": "first_remote_audio_frame"},
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

        asyncio.create_task(write_later())
        return {"ok": True, "changed": True, "latest_call_item": {"item_id": 1}}

    monkeypatch.setattr(
        "hermes_cli.calls._simplex_watch_all_for_call",
        fake_call_item_watch,
    )

    result = asyncio.run(
        _simplex_live_debug(
            ws_url="ws://127.0.0.1:5225",
            timeout_seconds=1.0,
            settle_seconds=0.0,
            count=50,
            request_timeout_seconds=0.2,
            interval_seconds=0.01,
            trace_root=tmp_path,
            raw_events=False,
        )
    )

    assert result["ok"] is True
    assert result["decisive"] is True
    assert result["raw_events"] is False
    assert "disabled" in result["simplex_event"]["message"]
    assert result["timed_out"] is False
    assert result["verdict"] == "inbound_audio_seen"
    assert result["new_traces"][0]["call_id"] == "call-live"


def test_simplex_live_debug_includes_acceptance_summary(monkeypatch, tmp_path):
    trace_path = tmp_path / "call-live.jsonl"

    async def fake_call_item_watch(**_kwargs):
        async def write_later():
            await asyncio.sleep(0.05)
            trace_path.write_text(
                "\n".join(
                    [
                        json.dumps({"call_id": "call-live", "event": "native_call_registered"}),
                        json.dumps(
                            {
                                "call_id": "call-live",
                                "event": "native_signal_received",
                                "signal_type": "answer",
                            }
                        ),
                        json.dumps(
                            {
                                "call_id": "call-live",
                                "event": "native_media_event",
                                "media_event": "remote_answer_sdp",
                            }
                        ),
                        json.dumps(
                            {
                                "call_id": "call-live",
                                "event": "native_media_event",
                                "media_event": "connection_state",
                                "details": {"status": "connected"},
                            }
                        ),
                        json.dumps(
                            {
                                "call_id": "call-live",
                                "event": "native_media_event",
                                "media_event": "first_remote_audio_frame",
                            }
                        ),
                        json.dumps({"call_id": "call-live", "event": "voice_turn_transcribed"}),
                        json.dumps({"call_id": "call-live", "event": "voice_turn_agent_responded"}),
                        json.dumps({"call_id": "call-live", "event": "voice_turn_tts_ready"}),
                        json.dumps(
                            {
                                "call_id": "call-live",
                                "event": "native_media_event",
                                "media_event": "outbound_tts_playback_started",
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

        asyncio.create_task(write_later())
        return {"ok": True, "changed": True, "latest_call_item": {"item_id": 1}}

    monkeypatch.setattr(
        "hermes_cli.calls._simplex_watch_all_for_call",
        fake_call_item_watch,
    )

    result = asyncio.run(
        _simplex_live_debug(
            ws_url="ws://127.0.0.1:5225",
            timeout_seconds=1.0,
            settle_seconds=0.0,
            count=50,
            request_timeout_seconds=0.2,
            interval_seconds=0.01,
            trace_root=tmp_path,
            raw_events=False,
        )
    )

    assert result["acceptance"]["technical_ok"] is True
    assert result["acceptance"]["manual_required"] is True
    assert result["acceptance"]["ok"] is False
    assert result["acceptance"]["call_id"] == "call-live"


def test_calls_simplex_live_debug_outputs_combined_result(monkeypatch, capsys):
    async def fake_debug(**kwargs):
        assert kwargs["ws_url"] == "ws://127.0.0.1:5225"
        assert kwargs["timeout_seconds"] == 5.0
        assert kwargs["settle_seconds"] == 0.5
        assert kwargs["raw_events"] is False
        return {
            "ok": True,
            "verdict": "inbound_audio_seen",
            "simplex_event": {"ok": True},
            "call_item": {"ok": False},
            "new_traces": [
                {
                    "call_id": "call-live",
                    "events": ["native_media_event"],
                    "media_events": ["first_remote_audio_frame"],
                }
            ],
        }

    monkeypatch.setattr("hermes_cli.calls._simplex_live_debug", fake_debug)

    rc = cmd_calls(
        SimpleNamespace(
            calls_command="simplex-live-debug",
            ws_url="ws://127.0.0.1:5225",
            timeout=5.0,
            settle=0.5,
            count=50,
            request_timeout=2.0,
            interval=0.1,
            trace_root=None,
            raw_events=False,
            json=True,
        )
    )

    result = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert result["verdict"] == "inbound_audio_seen"
    assert result["new_traces"][0]["call_id"] == "call-live"


def test_simplex_native_sidecar_script_exits_cleanly_on_empty_stdin():
    script = Path(__file__).resolve().parents[2] / "scripts" / "simplex_native_sidecar.py"

    result = subprocess.run(
        [sys.executable, str(script)],
        input="",
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout == ""
