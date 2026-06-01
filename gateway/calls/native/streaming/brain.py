"""HermesSyncBrain — HermesBrainPort adapter for the streaming voice slice (WP5).

Wraps the synchronous AIAgent.run_conversation off-thread with asyncio.to_thread,
drives cooperative AIAgent.interrupt() on cancellation, and never yields or
persists an abandoned result (Decision C: skip_memory=True, no FINAL_TEXT on cancel).
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from typing import Any

from .cancellation import CancellationScope
from .types import BrainEvent, BrainEventKind, StreamingCallContext, TranscriptEvent

AgentFactory = Callable[[StreamingCallContext], Any]


class HermesSyncBrain:
    """HermesBrainPort adapter: wraps synchronous AIAgent.run_conversation off-thread,
    with cooperative interrupt + abandon-on-cancel (no persistence of abandoned text)."""

    def __init__(self, agent_factory: AgentFactory) -> None:
        self._agent_factory = agent_factory
        self.abandoned = False  # observable for tests/tracing

    def respond(
        self, turn: TranscriptEvent, ctx: StreamingCallContext, scope: CancellationScope
    ) -> AsyncIterator[BrainEvent]:
        return self._respond_gen(turn, ctx, scope)

    async def _respond_gen(
        self, turn: TranscriptEvent, ctx: StreamingCallContext, scope: CancellationScope
    ) -> AsyncIterator[BrainEvent]:
        agent = self._agent_factory(ctx)
        # Cooperative interrupt: when the scope cancels, ask the running agent to stop.
        # Register BEFORE awaiting run_conversation so a cancel during the call fires interrupt().
        scope.add_listener(lambda reason: _safe_interrupt(agent, reason))

        try:
            result = await asyncio.to_thread(agent.run_conversation, turn.text)
        except Exception as exc:  # brain failed
            if scope.cancelled:
                self.abandoned = True
                return
            yield BrainEvent(
                call_id=ctx.call_id,
                kind=BrainEventKind.ERROR,
                error_code=type(exc).__name__,
            )
            return

        if scope.cancelled:
            # Barge-in won the race: discard, do not yield, do not persist.
            self.abandoned = True
            return

        text = ""
        if isinstance(result, dict):
            text = str(result.get("final_response") or "")
        yield BrainEvent(call_id=ctx.call_id, kind=BrainEventKind.FINAL_TEXT, text=text)


def _safe_interrupt(agent: Any, reason: str) -> None:
    interrupt = getattr(agent, "interrupt", None)
    if callable(interrupt):
        try:
            interrupt(reason)
        except Exception:
            pass


def build_call_agent_factory() -> AgentFactory:
    """Production factory: builds the real call AIAgent with memory persistence OFF.
    Mirrors gateway/calls/native/voice_turn.py::_call_agent_kwargs but forces skip_memory."""

    def factory(ctx: StreamingCallContext) -> Any:
        from run_agent import AIAgent
        from gateway.calls.native.voice_turn import _call_agent_kwargs

        kwargs = dict(_call_agent_kwargs(ctx.call_id))
        kwargs["skip_memory"] = True  # hard requirement: never persist abandoned turns
        return AIAgent(**kwargs)

    return factory
