"""Streaming SimpleX voice reflex foundation (Slice 1).

Sibling to the turn-based native call path. Hermes stays the brain; Pipecat
supplies reflexes. See docs/plans/2026-05-31-simplex-streaming-voice-reflexes-design.md.
"""
from __future__ import annotations

from .brain import HermesSyncBrain, build_call_agent_factory
from .cancellation import CallTurnCancelled, CancellationScope
from .clock import Clock, MonotonicClock, VirtualClock
from .engine import STREAMING, TURN_BASED, select_call_engine
from .interruption import InterruptionPolicy
from .ledger import HeardSpanLedger
from .session import StreamingCallSession
from .tracer import StreamingCallTracer
from .types import (
    AudioFrame,
    BrainEvent,
    BrainEventKind,
    CallTurnRecord,
    EndpointParams,
    FlushResult,
    InterruptionAction,
    InterruptionDecision,
    InterruptionParams,
    InterruptionSignal,
    MediaFormat,
    PlaybackMark,
    StreamingCallContext,
    TranscriptEvent,
    TranscriptKind,
    TtsAudioEvent,
    TtsEventKind,
    TurnEndReason,
    TurnEvent,
    TurnEventKind,
)

__all__ = [
    "AudioFrame",
    "BrainEvent",
    "BrainEventKind",
    "CallTurnCancelled",
    "CallTurnRecord",
    "CancellationScope",
    "Clock",
    "EndpointParams",
    "FlushResult",
    "HeardSpanLedger",
    "HermesSyncBrain",
    "InterruptionAction",
    "InterruptionDecision",
    "InterruptionParams",
    "InterruptionPolicy",
    "InterruptionSignal",
    "MediaFormat",
    "MonotonicClock",
    "PlaybackMark",
    "STREAMING",
    "StreamingCallContext",
    "StreamingCallSession",
    "StreamingCallTracer",
    "TURN_BASED",
    "TranscriptEvent",
    "TranscriptKind",
    "TtsAudioEvent",
    "TtsEventKind",
    "TurnEndReason",
    "TurnEvent",
    "TurnEventKind",
    "VirtualClock",
    "build_call_agent_factory",
    "select_call_engine",
]
