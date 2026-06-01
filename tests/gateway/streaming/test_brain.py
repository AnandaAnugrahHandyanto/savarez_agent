"""Tests for gateway/calls/native/streaming/brain.py (WP5).

TDD: written before brain.py exists. Drive the HermesSyncBrain through a
FakeAgent so no real model is ever called.
"""
from __future__ import annotations

import pytest

from gateway.calls.native.streaming.cancellation import CancellationScope
from gateway.calls.native.streaming.types import (
    BrainEventKind,
    MediaFormat,
    StreamingCallContext,
    TranscriptEvent,
    TranscriptKind,
)

pytestmark = pytest.mark.asyncio

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MEDIA = MediaFormat(sample_rate=16000, channels=1, frame_ms=20)
CALL_ID = "call-brain-test"


def make_ctx() -> StreamingCallContext:
    return StreamingCallContext(
        call_id=CALL_ID,
        contact_id="contact-1",
        session_id="session-brain-1",
        media=MEDIA,
    )


def make_turn(text: str = "hello world") -> TranscriptEvent:
    return TranscriptEvent(call_id=CALL_ID, kind=TranscriptKind.FINAL, text=text)


# ---------------------------------------------------------------------------
# FakeAgent — used by all tests except the factory test
# ---------------------------------------------------------------------------


class FakeAgent:
    def __init__(self, response: str = "hello", *, raises: bool = False, on_run=None):
        self.response = response
        self.raises = raises
        self.interrupted_with = None
        self.skip_memory = True
        self.run_called = False
        self._on_run = on_run  # optional callback to simulate work/cancellation

    def run_conversation(self, user_message, **kw):
        self.run_called = True
        if self._on_run:
            self._on_run()
        if self.raises:
            raise RuntimeError("boom")
        return {"final_response": self.response}

    def interrupt(self, message=None):
        self.interrupted_with = message


async def _collect(brain, turn, ctx, scope):
    """Drain the brain.respond() async generator into a list."""
    from gateway.calls.native.streaming.brain import HermesSyncBrain  # noqa: F401

    events = []
    async for event in brain.respond(turn, ctx, scope):
        events.append(event)
    return events


# ---------------------------------------------------------------------------
# Test 1: normal happy path
# ---------------------------------------------------------------------------


async def test_normal_yields_final_text():
    """Normal (no cancel, no error) → one FINAL_TEXT event with the response text."""
    from gateway.calls.native.streaming.brain import HermesSyncBrain

    agent = FakeAgent(response="hello there")
    brain = HermesSyncBrain(agent_factory=lambda ctx: agent)
    scope = CancellationScope()
    turn = make_turn("hi")
    ctx = make_ctx()

    events = await _collect(brain, turn, ctx, scope)

    assert agent.run_called is True
    assert len(events) == 1
    assert events[0].kind == BrainEventKind.FINAL_TEXT
    assert events[0].text == "hello there"
    assert events[0].call_id == CALL_ID
    assert brain.abandoned is False


# ---------------------------------------------------------------------------
# Test 2: cancelled before run_conversation returns (barge-in race)
# ---------------------------------------------------------------------------


async def test_cancelled_before_return_abandons():
    """on_run cancels the scope mid-conversation → no events, abandoned=True,
    agent.interrupted_with == the cancel reason (listener fired)."""
    from gateway.calls.native.streaming.brain import HermesSyncBrain

    scope = CancellationScope()
    agent = FakeAgent(on_run=lambda: scope.cancel("barge_in"))
    brain = HermesSyncBrain(agent_factory=lambda ctx: agent)
    turn = make_turn("say something")
    ctx = make_ctx()

    events = await _collect(brain, turn, ctx, scope)

    assert events == [], f"Expected no events, got: {events}"
    assert brain.abandoned is True
    assert agent.interrupted_with == "barge_in"


# ---------------------------------------------------------------------------
# Test 3: agent raises, scope NOT cancelled → ERROR event
# ---------------------------------------------------------------------------


async def test_error_yields_brain_error_event():
    """Agent raises RuntimeError, scope not cancelled → one ERROR BrainEvent."""
    from gateway.calls.native.streaming.brain import HermesSyncBrain

    agent = FakeAgent(raises=True)
    brain = HermesSyncBrain(agent_factory=lambda ctx: agent)
    scope = CancellationScope()
    turn = make_turn("oops")
    ctx = make_ctx()

    events = await _collect(brain, turn, ctx, scope)

    assert len(events) == 1
    assert events[0].kind == BrainEventKind.ERROR
    assert events[0].error_code == "RuntimeError"
    assert brain.abandoned is False


# ---------------------------------------------------------------------------
# Test 4: agent raises AND scope is cancelled → no event, abandoned=True
# ---------------------------------------------------------------------------


async def test_error_while_cancelled_abandons():
    """Agent raises AND scope is cancelled during run → no events, abandoned=True."""
    from gateway.calls.native.streaming.brain import HermesSyncBrain

    scope = CancellationScope()

    def _run_and_cancel():
        scope.cancel("barge_in_concurrent")

    agent = FakeAgent(raises=True, on_run=_run_and_cancel)
    brain = HermesSyncBrain(agent_factory=lambda ctx: agent)
    turn = make_turn("boom please")
    ctx = make_ctx()

    events = await _collect(brain, turn, ctx, scope)

    assert events == [], f"Expected no events on cancelled+error, got: {events}"
    assert brain.abandoned is True


# ---------------------------------------------------------------------------
# Test 5: production factory sets skip_memory=True
# ---------------------------------------------------------------------------


async def test_build_call_agent_factory_sets_skip_memory(monkeypatch):
    """build_call_agent_factory() → the factory passes skip_memory=True to AIAgent."""
    import gateway.calls.native.voice_turn as vt
    import sys

    captured_kwargs: dict = {}

    class MockAIAgent:
        def __init__(self, **kwargs):
            captured_kwargs.update(kwargs)

    # Patch run_agent.AIAgent
    import types

    fake_run_agent = types.ModuleType("run_agent")
    fake_run_agent.AIAgent = MockAIAgent  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "run_agent", fake_run_agent)

    # Patch _call_agent_kwargs to return a minimal dict
    monkeypatch.setattr(
        vt,
        "_call_agent_kwargs",
        lambda call_id: {
            "platform": "simplex_call",
            "session_id": f"simplex-native-call:{call_id}",
            "quiet_mode": True,
            "skip_memory": False,  # deliberately False — factory must override
        },
    )

    from gateway.calls.native.streaming.brain import build_call_agent_factory

    factory = build_call_agent_factory()
    ctx = make_ctx()
    factory(ctx)  # constructs MockAIAgent(**kwargs)

    assert captured_kwargs.get("skip_memory") is True, (
        f"Expected skip_memory=True but got {captured_kwargs}"
    )
