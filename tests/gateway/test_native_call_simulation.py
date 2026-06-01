from __future__ import annotations

import json
import sys
import textwrap

import pytest

from gateway.calls.native.simulation import run_native_call_simulation


def _write_child(tmp_path, source: str) -> list[str]:
    child_path = tmp_path / "fake_sidecar.py"
    child_path.write_text(textwrap.dedent(source), encoding="utf-8")
    return [sys.executable, str(child_path)]


@pytest.mark.asyncio
async def test_native_call_simulation_drives_sidecar_and_writes_redacted_trace(tmp_path):
    transcript_path = tmp_path / "sidecar.jsonl"
    trace_root = tmp_path / "traces"
    audio_path = tmp_path / "caller.wav"
    audio_path.write_bytes(b"RIFFfake")
    command = _write_child(
        tmp_path,
        f"""
        import json
        import pathlib
        import sys

        transcript = pathlib.Path({str(transcript_path)!r})
        start = sys.stdin.readline()
        transcript.write_text(start)
        sys.stdout.write(json.dumps({{
            "ok": True,
            "offer": {{
                "rtcSession": "offer-secret-sdp",
                "rtcIceCandidates": "offer-secret-ice",
                "capabilities": {{"encryption": True}},
            }},
        }}, separators=(",", ":")) + "\\n")
        sys.stdout.flush()
        for _ in range(2):
            line = sys.stdin.readline()
            if not line:
                break
            with transcript.open("a", encoding="utf-8") as handle:
                handle.write(line)
        debug_line = sys.stdin.readline()
        if debug_line:
            with transcript.open("a", encoding="utf-8") as handle:
                handle.write(debug_line)
            sys.stdout.write(json.dumps({{
                "ok": True,
                "code": "call_voice_turn_completed",
                "message": "Voice turn completed.",
                "transcriptChars": 24,
                "responseChars": 31,
                "audioPath": "/tmp/private-reply.wav",
            }}, separators=(",", ":")) + "\\n")
            sys.stdout.flush()
        stop_line = sys.stdin.readline()
        if stop_line:
            with transcript.open("a", encoding="utf-8") as handle:
                handle.write(stop_line)
        """,
    )

    result = await run_native_call_simulation(
        command=command,
        call_id="sim-call-1",
        contact_id="contact-1",
        trace_root=trace_root,
        encrypted=True,
        shared_key="shared-secret-key",
        answer={
            "rtcSession": "answer-secret-sdp",
            "rtcIceCandidates": "answer-secret-ice",
        },
        extra={"rtcIceCandidates": "extra-secret-ice"},
        audio_path=audio_path,
        timeout_seconds=0.5,
    )

    sidecar_rows = [
        json.loads(line) for line in transcript_path.read_text(encoding="utf-8").splitlines()
    ]
    trace_text = result.trace_path.read_text(encoding="utf-8")
    trace_rows = [json.loads(line) for line in trace_text.splitlines()]

    assert result.ok is True
    assert [row["type"] for row in sidecar_rows] == [
        "start_incoming",
        "apply_answer",
        "add_extra_ice",
        "debug_process_audio",
        "stop",
    ]
    assert result.events == [
        "simulation_started",
        "simulation_offer_ready",
        "simulation_answer_applied",
        "simulation_extra_applied",
        "simulation_voice_turn_completed",
        "simulation_stopped",
        "simulation_completed",
    ]
    assert result.trace_path == trace_root / "sim-call-1.jsonl"
    assert "shared-secret-key" not in trace_text
    assert "offer-secret-sdp" not in trace_text
    assert "answer-secret-sdp" not in trace_text
    assert "extra-secret-ice" not in trace_text
    assert "/tmp/private-reply.wav" not in trace_text
    assert any(
        row["event"] == "simulation_answer_applied"
        and row["payload"]["rtcSession"] == "[REDACTED]"
        for row in trace_rows
    )
    assert any(
        row["event"] == "simulation_voice_turn_completed"
        and row["voiceTurn"]["transcriptChars"] == 24
        for row in trace_rows
    )


@pytest.mark.asyncio
async def test_native_call_simulation_fails_loudly_without_sidecar_command(tmp_path):
    result = await run_native_call_simulation(
        command=[],
        call_id="sim-call-2",
        contact_id="contact-1",
        trace_root=tmp_path / "traces",
    )

    assert result.ok is False
    assert result.code == "call_sidecar_start_failed"
    assert "sidecar command" in result.message
    assert result.trace_path.exists()
