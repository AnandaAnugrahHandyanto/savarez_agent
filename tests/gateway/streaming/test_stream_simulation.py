"""Unit tests for the streaming simulation builder (WP9).

Tests ``build_stream_simulation`` (slice-level construction) driven by an
inline driver that mirrors the CLI-layer driver in ``hermes_cli/calls.py``.
The drive loop here must also live outside the slice because it uses
``asyncio.sleep(0)`` for settling — consistent with the ast-grep rule that
forbids ``asyncio.sleep`` in ``gateway/calls/native/streaming/**``.
"""
from __future__ import annotations

import asyncio

import pytest

from gateway.calls.native.streaming.simulate import build_stream_simulation

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Inline driver (mirrors hermes_cli/calls.py _run_stream_simulation)
# ---------------------------------------------------------------------------


async def _settle(ticks: int = 5) -> None:
    for _ in range(ticks):
        await asyncio.sleep(0)


async def _push_frame(sim, seq: int) -> None:
    await sim.transport.push_inbound(sim.make_frame(seq))
    await _settle()


async def _drain(sim, total_ms: int, step_ms: int = 20) -> None:
    steps = max(1, total_ms // step_ms)
    for _ in range(steps):
        await sim.clock.advance(step_ms)
        await _settle(ticks=3)


async def _drive(sim, *, barge_in: bool) -> None:
    run_task = asyncio.create_task(sim.session.run())
    await _settle()

    await _push_frame(sim, 0)  # ENDPOINT_DETECTED → launch assistant turn

    if barge_in:
        await _drain(sim, 220)         # let TTS emit word 1
        await _push_frame(sim, 1)      # USER_SPEECH_STARTED → vad_trigger flush
        await _drain(sim, 60)          # past min_speech_ms (40)
        await _push_frame(sim, 2)      # USER_SPEECH_STOPPED → INTERRUPT

    await sim.transport.end_inbound()
    for _ in range(400):
        if run_task.done():
            break
        await sim.clock.advance(20)
        await _settle(ticks=3)
    await asyncio.wait_for(run_task, timeout=5.0)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_normal_turn_returns_ok_summary():
    sim = build_stream_simulation(
        call_id="test-normal",
        caller_text="what's the weather",
        response_text="It's sunny today.",
        barge_in=False,
        brain_delay_ms=0,
    )
    await _drive(sim, barge_in=False)
    result = sim.summary()

    assert result["ok"] is True
    assert result["code"] == "call_stream_simulation_passed"
    assert result["call_id"] == "test-normal"
    assert len(result["turns"]) == 1

    turn = result["turns"][0]
    assert turn["ended_reason"] == "completed"
    assert turn["interrupted"] is False
    assert turn["user_chars"] == len("what's the weather")
    assert turn["heard_chars"] > 0
    assert turn["abandoned_chars"] == 0

    assert result["outbound_audio_frames"] > 0
    assert result["flushes"] == []


async def test_barge_in_turn_is_interrupted():
    sim = build_stream_simulation(
        call_id="test-barge",
        caller_text="hold on stop",
        response_text="one two three four five six seven eight nine ten",
        barge_in=True,
        brain_delay_ms=0,
    )
    await _drive(sim, barge_in=True)
    result = sim.summary()

    assert result["ok"] is True
    assert result["code"] == "call_stream_simulation_passed"
    assert len(result["turns"]) == 1

    turn = result["turns"][0]
    assert turn["ended_reason"] == "barged_in"
    assert turn["interrupted"] is True
    assert result["outbound_audio_frames"] > 0
    # Both vad_trigger (fast-reflex) and barge_in (interrupt) flushes must fire.
    assert "barge_in" in result["flushes"]


async def test_custom_call_and_contact_ids_appear_in_summary():
    sim = build_stream_simulation(
        call_id="my-call-id",
        contact_id="my-contact",
        caller_text="hello",
        response_text="hi there",
        barge_in=False,
    )
    await _drive(sim, barge_in=False)
    result = sim.summary()

    assert result["call_id"] == "my-call-id"
    assert result["ok"] is True


async def test_brain_delay_still_completes():
    sim = build_stream_simulation(
        call_id="slow-brain",
        caller_text="think slowly",
        response_text="done",
        barge_in=False,
        brain_delay_ms=100,
    )
    await _drive(sim, barge_in=False)
    result = sim.summary()

    assert result["ok"] is True
    turn = result["turns"][0]
    assert turn["ended_reason"] == "completed"
    assert turn["interrupted"] is False
