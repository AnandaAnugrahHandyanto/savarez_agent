"""TDD tests for gateway/calls/native/streaming/tracer.py (WP6).

Written BEFORE the implementation exists (red phase).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from gateway.calls.native.tracing import NativeCallTraceWriter
from gateway.calls.native.voice_turn import VoiceDebugTracePolicy
from gateway.calls.native.streaming.types import (
    BrainEvent,
    BrainEventKind,
    CallTurnRecord,
    InterruptionAction,
    InterruptionDecision,
    PlaybackMark,
    TranscriptEvent,
    TranscriptKind,
    TurnEndReason,
    TurnEvent,
    TurnEventKind,
)
from gateway.calls.native.streaming.ports import StreamingCallTracerPort


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CALL_ID = "call-test-123"


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().strip().splitlines()]


def _last_event(tmp_path: Path, call_id: str = CALL_ID) -> dict:
    from gateway.calls.native.tracing import _safe_call_id
    log_path = tmp_path / f"{_safe_call_id(call_id)}.jsonl"
    rows = _read_jsonl(log_path)
    return rows[-1]


def _all_events(tmp_path: Path, call_id: str = CALL_ID) -> list[dict]:
    from gateway.calls.native.tracing import _safe_call_id
    log_path = tmp_path / f"{_safe_call_id(call_id)}.jsonl"
    return _read_jsonl(log_path)


def _make_tracer(tmp_path: Path, policy: VoiceDebugTracePolicy | None = None):
    from gateway.calls.native.streaming.tracer import StreamingCallTracer
    writer = NativeCallTraceWriter(root=tmp_path)
    return StreamingCallTracer(CALL_ID, policy=policy, writer=writer)


def _make_transcript(text: str = "hello world") -> TranscriptEvent:
    return TranscriptEvent(
        call_id=CALL_ID,
        kind=TranscriptKind.FINAL,
        text=text,
        provider="deepgram",
    )


def _make_turn() -> TurnEvent:
    return TurnEvent(
        call_id=CALL_ID,
        kind=TurnEventKind.ENDPOINT_DETECTED,
        at_ms=1200,
        speech_duration_ms=800,
        vad_confidence=0.9,
        endpoint_confidence=0.85,
        source="vad",
    )


def _make_brain(text: str = "Let me help you.") -> BrainEvent:
    return BrainEvent(call_id=CALL_ID, kind=BrainEventKind.FINAL_TEXT, text=text)


def _make_playback_mark(text_so_far: str = "Let me") -> PlaybackMark:
    return PlaybackMark(
        call_id=CALL_ID,
        char_offset=len(text_so_far),
        text_so_far=text_so_far,
        at_ms=300,
        boundary="word",
    )


def _make_decision() -> InterruptionDecision:
    return InterruptionDecision(
        action=InterruptionAction.INTERRUPT,
        reason="barge_in",
        at_ms=500,
    )


def _make_turn_record(
    heard: str = "I can help you.",
    abandoned: str = "Would you like me to",
    user: str = "What time is it?",
) -> CallTurnRecord:
    return CallTurnRecord(
        call_id=CALL_ID,
        turn_index=2,
        user_transcript=user,
        assistant_heard_text=heard,
        assistant_abandoned_text=abandoned,
        interrupted=True,
        ended_reason=TurnEndReason.BARGED_IN,
    )


# ---------------------------------------------------------------------------
# 1. Previews OFF (default policy): no raw text emitted
# ---------------------------------------------------------------------------


def test_transcript_previews_off_no_preview_key(tmp_path):
    """Default policy: transcript() writes stream_transcript with chars but no preview/sensitive."""
    tracer = _make_tracer(tmp_path)
    tracer.transcript(_make_transcript("hello world"))

    row = _last_event(tmp_path)
    assert row["event"] == "stream_transcript"
    assert row["chars"] == 11
    assert "preview" not in row
    assert "sensitive" not in row


def test_transcript_previews_off_structural_fields_present(tmp_path):
    """Structural fields (kind, stability, provider) are always present."""
    tracer = _make_tracer(tmp_path)
    tracer.transcript(_make_transcript("hello world"))

    row = _last_event(tmp_path)
    assert row["kind"] == "final"
    assert row["provider"] == "deepgram"
    assert "stability" in row


# ---------------------------------------------------------------------------
# 2. Previews ON: preview + sensitive present
# ---------------------------------------------------------------------------


def test_transcript_previews_on_has_preview_and_sensitive(tmp_path):
    """previews ON: transcript() includes preview and sensitive==True."""
    policy = VoiceDebugTracePolicy(transcript_previews=True, max_preview_chars=240)
    tracer = _make_tracer(tmp_path, policy=policy)
    tracer.transcript(_make_transcript("hello world"))

    row = _last_event(tmp_path)
    assert row["event"] == "stream_transcript"
    assert row["chars"] == 11
    assert "preview" in row
    assert row.get("sensitive") is True


def test_brain_previews_on_has_preview(tmp_path):
    """previews ON: brain() includes preview and sensitive==True."""
    policy = VoiceDebugTracePolicy(transcript_previews=True, max_preview_chars=240)
    tracer = _make_tracer(tmp_path, policy=policy)
    tracer.brain(_make_brain("Let me help you."))

    row = _last_event(tmp_path)
    assert row["event"] == "stream_brain"
    assert row["chars"] == len("Let me help you.")
    assert "preview" in row
    assert row.get("sensitive") is True


def test_brain_previews_off_no_preview(tmp_path):
    """previews OFF (default): brain() no preview or sensitive key."""
    tracer = _make_tracer(tmp_path)
    tracer.brain(_make_brain("Let me help you."))

    row = _last_event(tmp_path)
    assert row["event"] == "stream_brain"
    assert "preview" not in row
    assert "sensitive" not in row


# ---------------------------------------------------------------------------
# 3. Redaction guard test (proves NativeCallTraceWriter redaction works)
# ---------------------------------------------------------------------------


def test_redaction_of_sensitive_key(tmp_path):
    """NativeCallTraceWriter redacts rawAudio to [REDACTED] — guard for tracer reuse."""
    writer = NativeCallTraceWriter(root=tmp_path)
    writer.record("c", "x", rawAudio="secretbytes")

    from gateway.calls.native.tracing import _safe_call_id
    log_path = tmp_path / f"{_safe_call_id('c')}.jsonl"
    rows = _read_jsonl(log_path)
    assert rows[0]["rawAudio"] == "[REDACTED]"


def test_redaction_of_token_key(tmp_path):
    """NativeCallTraceWriter redacts 'token' field."""
    writer = NativeCallTraceWriter(root=tmp_path)
    writer.record("c", "y", token="mytoken123")

    from gateway.calls.native.tracing import _safe_call_id
    log_path = tmp_path / f"{_safe_call_id('c')}.jsonl"
    rows = _read_jsonl(log_path)
    assert rows[0]["token"] == "[REDACTED]"


# ---------------------------------------------------------------------------
# 4. Interruption gating
# ---------------------------------------------------------------------------


def test_interruption_previews_off_no_preview(tmp_path):
    """previews OFF: stream_interruption has heard_chars/abandoned_chars, no heard_preview."""
    tracer = _make_tracer(tmp_path)
    tracer.interruption(_make_decision(), heard="I can help you.", abandoned="Would you like")

    row = _last_event(tmp_path)
    assert row["event"] == "stream_interruption"
    assert row["heard_chars"] == len("I can help you.")
    assert row["abandoned_chars"] == len("Would you like")
    assert "heard_preview" not in row
    assert "abandoned_preview" not in row
    assert "sensitive" not in row


def test_interruption_previews_on_has_previews(tmp_path):
    """previews ON: stream_interruption has heard_preview, abandoned_preview, sensitive."""
    policy = VoiceDebugTracePolicy(transcript_previews=True, max_preview_chars=240)
    tracer = _make_tracer(tmp_path, policy=policy)
    tracer.interruption(_make_decision(), heard="I can help you.", abandoned="Would you like")

    row = _last_event(tmp_path)
    assert row["event"] == "stream_interruption"
    assert "heard_preview" in row
    assert "abandoned_preview" in row
    assert row.get("sensitive") is True
    # structural fields still present
    assert row["heard_chars"] == len("I can help you.")
    assert row["abandoned_chars"] == len("Would you like")
    assert row["action"] == "interrupt"
    assert row["reason"] == "barge_in"
    assert row["at_ms"] == 500


# ---------------------------------------------------------------------------
# 5. turn_committed structural fields always present
# ---------------------------------------------------------------------------


def test_turn_committed_structural_fields_previews_off(tmp_path):
    """turn_committed always emits structural fields regardless of policy."""
    tracer = _make_tracer(tmp_path)
    record = _make_turn_record()
    tracer.turn_committed(record)

    row = _last_event(tmp_path)
    assert row["event"] == "stream_turn_committed"
    assert row["turn_index"] == 2
    assert row["ended_reason"] == "barged_in"
    assert row["interrupted"] is True
    assert row["heard_chars"] == len("I can help you.")
    assert row["abandoned_chars"] == len("Would you like me to")
    assert row["user_chars"] == len("What time is it?")
    # no preview fields
    assert "heard_preview" not in row
    assert "abandoned_preview" not in row
    assert "user_preview" not in row
    assert "sensitive" not in row


def test_turn_committed_previews_on_has_all_preview_fields(tmp_path):
    """turn_committed with previews ON emits all three preview fields + sensitive."""
    policy = VoiceDebugTracePolicy(transcript_previews=True, max_preview_chars=240)
    tracer = _make_tracer(tmp_path, policy=policy)
    record = _make_turn_record()
    tracer.turn_committed(record)

    row = _last_event(tmp_path)
    assert "heard_preview" in row
    assert "abandoned_preview" in row
    assert "user_preview" in row
    assert row.get("sensitive") is True
    # structural fields still present
    assert row["turn_index"] == 2
    assert row["ended_reason"] == "barged_in"


# ---------------------------------------------------------------------------
# 6. isinstance check: runtime_checkable Protocol
# ---------------------------------------------------------------------------


def test_isinstance_satisfies_port():
    """StreamingCallTracer satisfies StreamingCallTracerPort at runtime."""
    from gateway.calls.native.streaming.tracer import StreamingCallTracer
    tracer = StreamingCallTracer(CALL_ID)
    assert isinstance(tracer, StreamingCallTracerPort)


# ---------------------------------------------------------------------------
# 7. turn() method emits correct event
# ---------------------------------------------------------------------------


def test_turn_emits_stream_turn(tmp_path):
    """turn() emits stream_turn with structural fields."""
    tracer = _make_tracer(tmp_path)
    tracer.turn(_make_turn())

    row = _last_event(tmp_path)
    assert row["event"] == "stream_turn"
    assert row["kind"] == "endpoint_detected"
    assert row["at_ms"] == 1200
    assert row["speech_duration_ms"] == 800
    assert row["vad_confidence"] == pytest.approx(0.9)
    assert row["endpoint_confidence"] == pytest.approx(0.85)
    assert row["source"] == "vad"


# ---------------------------------------------------------------------------
# 8. playback() method: gated preview on mark.text_so_far
# ---------------------------------------------------------------------------


def test_playback_previews_off_no_preview(tmp_path):
    """playback() without preview policy emits only structural fields."""
    tracer = _make_tracer(tmp_path)
    tracer.playback(_make_playback_mark("Let me"))

    row = _last_event(tmp_path)
    assert row["event"] == "stream_playback"
    assert row["char_offset"] == len("Let me")
    assert row["at_ms"] == 300
    assert row["boundary"] == "word"
    assert "preview" not in row
    assert "sensitive" not in row


def test_playback_previews_on_has_preview(tmp_path):
    """playback() with previews ON includes preview and sensitive."""
    policy = VoiceDebugTracePolicy(transcript_previews=True, max_preview_chars=240)
    tracer = _make_tracer(tmp_path, policy=policy)
    tracer.playback(_make_playback_mark("Let me"))

    row = _last_event(tmp_path)
    assert row["event"] == "stream_playback"
    assert "preview" in row
    assert row.get("sensitive") is True


# ---------------------------------------------------------------------------
# 9. Preview truncation uses _preview_text (word-boundary aware)
# ---------------------------------------------------------------------------


def test_preview_truncated_at_word_boundary(tmp_path):
    """Long text is truncated at word boundary with ellipsis by _preview_text."""
    from gateway.calls.native.voice_turn import _preview_text

    long_text = ("word " * 100).strip()
    policy = VoiceDebugTracePolicy(transcript_previews=True, max_preview_chars=30)
    tracer = _make_tracer(tmp_path, policy=policy)
    tracer.transcript(_make_transcript(long_text))

    row = _last_event(tmp_path)
    expected = _preview_text(long_text, 30)
    assert row["preview"] == expected
    assert row["preview"].endswith("...")
    assert len(row["preview"]) <= 50  # well under full length
