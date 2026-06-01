from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import textwrap
import time

import pytest

from gateway.calls.native.ports import NativeMediaAnswerRequest, NativeMediaStartRequest
from gateway.calls.native.sidecar import SidecarMediaPort


def _request() -> NativeMediaStartRequest:
    return NativeMediaStartRequest(
        call_id="call_123",
        contact_id="contact_456",
        media="audio",
        encrypted=True,
        shared_key="shared-secret",
    )


def _answer_request() -> NativeMediaAnswerRequest:
    return NativeMediaAnswerRequest(
        call_id="call_123",
        contact_id="contact_456",
        media="audio",
        offer={"rtcSession": "offer-b64", "rtcIceCandidates": "offer-ice-b64"},
        encrypted=True,
        shared_key="shared-secret",
    )


def _write_child(tmp_path, source: str) -> list[str]:
    child_path = tmp_path / "fake_sidecar.py"
    child_path.write_text(textwrap.dedent(source), encoding="utf-8")
    return [sys.executable, str(child_path)]


def _process_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


@pytest.mark.asyncio
async def test_start_incoming_fails_when_sidecar_command_missing():
    port = SidecarMediaPort(command=[])

    result = await port.start_incoming(_request())

    assert result.ok is False
    assert result.code == "call_sidecar_start_failed"
    assert "sidecar command is not configured" in result.message


@pytest.mark.asyncio
async def test_start_incoming_sends_request_and_returns_offer(tmp_path):
    request_path = tmp_path / "request.json"
    port = SidecarMediaPort(
        command=_write_child(
            tmp_path,
            f"""
            import json
            import pathlib
            import sys

            line = sys.stdin.readline()
            pathlib.Path({str(request_path)!r}).write_text(line)
            sys.stdout.write(json.dumps({{
                "ok": True,
                "offer": {{
                    "rtcSession": "offer-b64",
                    "rtcIceCandidates": "ice-b64",
                    "capabilities": {{"encryption": True}},
                    "callDhPubKey": "dh-pub-b64",
                }},
            }}, separators=(",", ":")) + "\\n")
            sys.stdout.flush()
            """,
        )
    )

    result = await port.start_incoming(_request())

    assert result.ok is True
    assert result.offer is not None
    assert result.offer.rtc_session == "offer-b64"
    assert result.offer.rtc_ice_candidates == "ice-b64"
    assert result.offer.capabilities == {"encryption": True}
    assert result.offer.call_dh_pub_key == "dh-pub-b64"
    assert json.loads(request_path.read_text(encoding="utf-8")) == {
        "type": "start_incoming",
        "callId": "call_123",
        "contactId": "contact_456",
        "media": "audio",
        "encrypted": True,
        "sharedKey": "shared-secret",
    }
    await port.stop("call_123")


@pytest.mark.asyncio
async def test_start_outgoing_answer_sends_offer_and_returns_answer(tmp_path):
    request_path = tmp_path / "request.json"
    port = SidecarMediaPort(
        command=_write_child(
            tmp_path,
            f"""
            import json
            import pathlib
            import sys

            line = sys.stdin.readline()
            pathlib.Path({str(request_path)!r}).write_text(line)
            sys.stdout.write(json.dumps({{
                "ok": True,
                "answer": {{
                    "rtcSession": "answer-b64",
                    "rtcIceCandidates": "answer-ice-b64",
                }},
            }}, separators=(",", ":")) + "\\n")
            sys.stdout.flush()
            """,
        )
    )

    result = await port.start_outgoing_answer(_answer_request())

    assert result.ok is True
    assert result.answer is not None
    assert result.answer.rtc_session == "answer-b64"
    assert result.answer.rtc_ice_candidates == "answer-ice-b64"
    assert json.loads(request_path.read_text(encoding="utf-8")) == {
        "type": "start_outgoing_answer",
        "callId": "call_123",
        "contactId": "contact_456",
        "media": "audio",
        "encrypted": True,
        "sharedKey": "shared-secret",
        "offer": {"rtcSession": "offer-b64", "rtcIceCandidates": "offer-ice-b64"},
    }
    await port.stop("call_123")


@pytest.mark.asyncio
async def test_sidecar_stderr_is_drained_into_gateway_logs(tmp_path, caplog):
    port = SidecarMediaPort(
        command=_write_child(
            tmp_path,
            """
            import json
            import sys

            sys.stderr.write("sidecar diagnostic visible\\n")
            sys.stderr.flush()
            sys.stdin.readline()
            sys.stdout.write(json.dumps({
                "ok": True,
                "offer": {
                    "rtcSession": "offer-b64",
                    "rtcIceCandidates": "ice-b64",
                },
            }, separators=(",", ":")) + "\\n")
            sys.stdout.flush()
            sys.stdin.readline()
            """,
        ),
        timeout_seconds=0.5,
    )

    caplog.set_level(logging.INFO, logger="gateway.calls.native.sidecar")
    result = await port.start_incoming(_request())
    await port.stop("call_123")

    assert result.ok is True
    assert any(
        "sidecar diagnostic visible" in record.getMessage()
        and getattr(record, "call_id", None) == "call_123"
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_successful_start_keeps_sidecar_alive_until_stop(tmp_path):
    pid_path = tmp_path / "sidecar.pid"
    stop_path = tmp_path / "stop.json"
    port = SidecarMediaPort(
        command=_write_child(
            tmp_path,
            f"""
            import json
            import os
            import pathlib
            import sys

            pathlib.Path({str(pid_path)!r}).write_text(str(os.getpid()))
            sys.stdin.readline()
            sys.stdout.write(json.dumps({{
                "ok": True,
                "offer": {{
                    "rtcSession": "offer-b64",
                    "rtcIceCandidates": "ice-b64",
                }},
            }}, separators=(",", ":")) + "\\n")
            sys.stdout.flush()
            stop_line = sys.stdin.readline()
            if stop_line:
                pathlib.Path({str(stop_path)!r}).write_text(stop_line)
            """,
        ),
        timeout_seconds=0.5,
    )

    result = await port.start_incoming(_request())
    pid = int(pid_path.read_text(encoding="utf-8"))

    assert result.ok is True
    assert _process_exists(pid)

    await port.stop("call_123")

    assert json.loads(stop_path.read_text(encoding="utf-8")) == {
        "type": "stop",
        "callId": "call_123",
    }
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline and _process_exists(pid):
        time.sleep(0.01)
    assert not _process_exists(pid)


@pytest.mark.asyncio
async def test_stop_allows_sidecar_to_exit_gracefully(tmp_path):
    marker_path = tmp_path / "graceful.txt"
    port = SidecarMediaPort(
        command=_write_child(
            tmp_path,
            f"""
            import json
            import pathlib
            import sys
            import time

            sys.stdin.readline()
            sys.stdout.write(json.dumps({{
                "ok": True,
                "offer": {{
                    "rtcSession": "offer-b64",
                    "rtcIceCandidates": "ice-b64",
                }},
            }}, separators=(",", ":")) + "\\n")
            sys.stdout.flush()
            sys.stdin.readline()
            time.sleep(0.05)
            pathlib.Path({str(marker_path)!r}).write_text("graceful")
            """,
        ),
        timeout_seconds=0.5,
    )

    result = await port.start_incoming(_request())
    await port.stop("call_123")

    assert result.ok is True
    assert marker_path.read_text(encoding="utf-8") == "graceful"


@pytest.mark.asyncio
async def test_sidecar_accepts_answer_and_extra_ice_controls(tmp_path):
    answer_path = tmp_path / "answer.json"
    extra_path = tmp_path / "extra.json"
    port = SidecarMediaPort(
        command=_write_child(
            tmp_path,
            f"""
            import json
            import pathlib
            import sys

            sys.stdin.readline()
            sys.stdout.write(json.dumps({{
                "ok": True,
                "offer": {{
                    "rtcSession": "offer-b64",
                    "rtcIceCandidates": "ice-b64",
                }},
            }}, separators=(",", ":")) + "\\n")
            sys.stdout.flush()
            answer_line = sys.stdin.readline()
            pathlib.Path({str(answer_path)!r}).write_text(answer_line)
            extra_line = sys.stdin.readline()
            pathlib.Path({str(extra_path)!r}).write_text(extra_line)
            sys.stdin.readline()
            """,
        ),
        timeout_seconds=0.5,
    )

    result = await port.start_incoming(_request())
    answer_ok = await port.apply_answer(
        "call_123",
        {"rtcSession": "answer-b64", "rtcIceCandidates": "answer-ice-b64"},
    )
    extra_ok = await port.add_extra_ice(
        "call_123",
        {"rtcIceCandidates": "extra-ice-b64"},
    )
    await port.stop("call_123")

    assert result.ok is True
    assert answer_ok is True
    assert extra_ok is True
    assert json.loads(answer_path.read_text(encoding="utf-8")) == {
        "type": "apply_answer",
        "callId": "call_123",
        "answer": {
            "rtcSession": "answer-b64",
            "rtcIceCandidates": "answer-ice-b64",
        },
    }
    assert json.loads(extra_path.read_text(encoding="utf-8")) == {
        "type": "add_extra_ice",
        "callId": "call_123",
        "extra": {"rtcIceCandidates": "extra-ice-b64"},
    }


@pytest.mark.asyncio
async def test_sidecar_delivers_terminal_event_and_cleans_process(tmp_path):
    pid_path = tmp_path / "sidecar.pid"
    events: list[dict] = []
    port = SidecarMediaPort(
        command=_write_child(
            tmp_path,
            f"""
            import json
            import os
            import pathlib
            import sys
            import time

            pathlib.Path({str(pid_path)!r}).write_text(str(os.getpid()))
            sys.stdin.readline()
            sys.stdout.write(json.dumps({{
                "ok": True,
                "offer": {{
                    "rtcSession": "offer-b64",
                    "rtcIceCandidates": "ice-b64",
                }},
            }}, separators=(",", ":")) + "\\n")
            sys.stdout.flush()
            sys.stdout.write(json.dumps({{
                "type": "status",
                "callId": "call_123",
                "status": "failed",
                "reasonCode": "remote_audio_ended_before_first_frame",
                "details": {{"remoteAudioFrames": 0}},
            }}, separators=(",", ":")) + "\\n")
            sys.stdout.flush()
            time.sleep(10)
            """,
        ),
        timeout_seconds=0.5,
        on_event=events.append,
    )

    result = await port.start_incoming(_request())
    pid = int(pid_path.read_text(encoding="utf-8"))
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline and _process_exists(pid):
        await asyncio.sleep(0.01)

    assert result.ok is True
    assert events == [
        {
            "type": "status",
            "event": "status",
            "callId": "call_123",
            "status": "failed",
            "reasonCode": "remote_audio_ended_before_first_frame",
            "details": {"remoteAudioFrames": 0},
        }
    ]
    assert not _process_exists(pid)


@pytest.mark.asyncio
async def test_sidecar_debug_audio_ignores_interleaved_event(tmp_path):
    events: list[dict] = []
    port = SidecarMediaPort(
        command=_write_child(
            tmp_path,
            """
            import json
            import sys

            sys.stdin.readline()
            sys.stdout.write(json.dumps({
                "ok": True,
                "offer": {
                    "rtcSession": "offer-b64",
                    "rtcIceCandidates": "ice-b64",
                },
            }, separators=(",", ":")) + "\\n")
            sys.stdout.flush()
            sys.stdout.write(json.dumps({
                "type": "event",
                "event": "diagnostic",
                "callId": "call_123",
                "status": "connected",
            }, separators=(",", ":")) + "\\n")
            sys.stdout.flush()
            sys.stdin.readline()
            sys.stdout.write(json.dumps({
                "ok": True,
                "code": "call_voice_turn_completed",
                "message": "Voice turn completed.",
            }, separators=(",", ":")) + "\\n")
            sys.stdout.flush()
            sys.stdin.readline()
            """,
        ),
        timeout_seconds=0.5,
        on_event=events.append,
    )

    result = await port.start_incoming(_request())
    response = await port.debug_process_audio("call_123", "/tmp/audio.wav")
    await port.stop("call_123")

    assert result.ok is True
    assert events == [
        {
            "type": "event",
            "event": "diagnostic",
            "callId": "call_123",
            "status": "connected",
        }
    ]
    assert response["ok"] is True
    assert response["code"] == "call_voice_turn_completed"


@pytest.mark.asyncio
async def test_start_incoming_returns_protocol_failure_when_child_exits_without_output():
    port = SidecarMediaPort(command=[sys.executable, "-c", ""])

    result = await port.start_incoming(_request())

    assert result.ok is False
    assert result.code == "call_sidecar_protocol_failed"
    assert result.message


@pytest.mark.parametrize(
    ("line_expr", "raw_fragment"),
    [
        ("json.dumps([]) + '\\n'", "[]"),
        ("'not-json\\n'", "not-json"),
    ],
)
@pytest.mark.asyncio
async def test_start_incoming_returns_protocol_failure_for_invalid_response_shape(
    tmp_path,
    line_expr,
    raw_fragment,
    caplog,
):
    port = SidecarMediaPort(
        command=_write_child(
            tmp_path,
            f"""
            import json
            import sys

            sys.stdout.write({line_expr})
            sys.stdout.flush()
            """,
        )
    )

    caplog.set_level("WARNING", logger="gateway.calls.native.sidecar")
    result = await port.start_incoming(_request())

    assert result.ok is False
    assert result.code == "call_sidecar_protocol_failed"
    assert result.message
    assert any(
        record.reason == "invalid_response"
        for record in caplog.records
        if record.message == "SimpleX native call sidecar protocol failure"
    )
    assert raw_fragment not in caplog.text


@pytest.mark.asyncio
async def test_start_incoming_returns_protocol_failure_for_invalid_utf8_response(
    tmp_path,
    caplog,
):
    port = SidecarMediaPort(
        command=_write_child(
            tmp_path,
            """
            import sys

            sys.stdout.buffer.write(b"sidecar-secret\\xff\\n")
            sys.stdout.flush()
            """,
        )
    )

    caplog.set_level("WARNING", logger="gateway.calls.native.sidecar")
    result = await port.start_incoming(_request())

    assert result.ok is False
    assert result.code == "call_sidecar_protocol_failed"
    assert result.message
    assert any(
        record.reason == "invalid_response_encoding"
        for record in caplog.records
        if record.message == "SimpleX native call sidecar protocol failure"
    )
    assert "sidecar-secret" not in caplog.text
    assert "0xff" not in caplog.text


@pytest.mark.parametrize(
    "offer",
    [
        {"rtcSession": ["offer-b64"], "rtcIceCandidates": "ice-b64"},
        {"rtcSession": "offer-b64", "rtcIceCandidates": {"candidate": "ice-b64"}},
    ],
)
@pytest.mark.asyncio
async def test_start_incoming_returns_protocol_failure_for_wrong_offer_field_types(
    tmp_path,
    offer,
):
    port = SidecarMediaPort(
        command=_write_child(
            tmp_path,
            f"""
            import json
            import sys

            sys.stdout.write(json.dumps({{"ok": True, "offer": {offer!r}}}) + "\\n")
            sys.stdout.flush()
            """,
        )
    )

    result = await port.start_incoming(_request())

    assert result.ok is False
    assert result.code == "call_sidecar_protocol_failed"
    assert result.message


@pytest.mark.asyncio
async def test_start_incoming_defaults_safely_for_non_string_error_fields(
    tmp_path,
    caplog,
):
    port = SidecarMediaPort(
        command=_write_child(
            tmp_path,
            """
            import json
            import sys

            sys.stdout.write(json.dumps({
                "ok": False,
                "code": ["call_custom"],
                "message": {"detail": "failed"},
            }) + "\\n")
            sys.stdout.flush()
            """,
        )
    )

    caplog.set_level("WARNING", logger="gateway.calls.native.sidecar")
    result = await port.start_incoming(_request())

    assert result.ok is False
    assert result.code == "call_sidecar_protocol_failed"
    assert result.message == "call sidecar returned a failed response"
    assert any(
        record.reason == "invalid_error_response"
        for record in caplog.records
        if record.message == "SimpleX native call sidecar protocol failure"
    )
    assert "call_custom" not in caplog.text


@pytest.mark.asyncio
async def test_start_incoming_returns_timeout_and_reaps_child(tmp_path):
    pid_path = tmp_path / "sidecar.pid"
    port = SidecarMediaPort(
        command=_write_child(
            tmp_path,
            f"""
            import os
            import pathlib
            import time

            pathlib.Path({str(pid_path)!r}).write_text(str(os.getpid()))
            time.sleep(10)
            """,
        ),
        timeout_seconds=0.2,
    )

    result = await port.start_incoming(_request())
    pid = int(pid_path.read_text(encoding="utf-8"))

    assert result.ok is False
    assert result.code == "call_simplex_native_timeout"
    assert result.message
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline and _process_exists(pid):
        time.sleep(0.01)
    assert not _process_exists(pid)
