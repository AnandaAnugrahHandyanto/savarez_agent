"""Slice 7 carry-in fix #2: direct-feed accumulator sample-rate threading.

These unit-test ``_DirectFeedAccumulator`` directly — no aiortc/av needed —
so they run in CI (no ``importorskip`` guard).
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


class _SpyPipeline:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def process_pcm16(self, *, call_id, pcm16, sample_rate):
        self.calls.append(
            {"call_id": call_id, "pcm16": pcm16, "sample_rate": sample_rate}
        )
        return object()  # ack ignored


async def test_accept_pcm16_threads_frame_rate():
    from gateway.calls.native.aiortc_engine import _DirectFeedAccumulator

    pipeline = _SpyPipeline()
    acc = _DirectFeedAccumulator(pipeline, call_id="c", native_rate=48000)
    await acc.accept_pcm16(b"\x00\x00", sample_rate=16000)

    assert len(pipeline.calls) == 1
    assert pipeline.calls[0]["sample_rate"] == 16000


async def test_accept_pcm16_defaults_to_native_rate():
    from gateway.calls.native.aiortc_engine import _DirectFeedAccumulator

    pipeline = _SpyPipeline()
    acc = _DirectFeedAccumulator(pipeline, call_id="c", native_rate=48000)
    await acc.accept_pcm16(b"\x00\x00")

    assert len(pipeline.calls) == 1
    assert pipeline.calls[0]["sample_rate"] == 48000
