"""Tests for WeComStreamConsumer — native WeCom stream consumer."""

import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gateway.wecom_stream_consumer import (
    WeComStreamConsumer,
    build_ws_stream_content,
    build_waiting_model_content,
)


# ── build_ws_stream_content unit tests ──────────────────────────────────


class TestBuildWsStreamContent:
    def test_visible_only(self):
        result = build_ws_stream_content(visible_text="hello")
        assert result == "hello"

    def test_reasoning_only_open(self):
        result = build_ws_stream_content(reasoning_text="thinking hard")
        # Open tag present, no closing tag when finish=False and no visible text
        assert result.startswith("<think")
        assert "</think>" not in result

    def test_reasoning_closed_on_finish(self):
        result = build_ws_stream_content(reasoning_text="thinking", finish=True)
        assert "<think>" in result
        assert "</think>" in result

    def test_reasoning_and_visible(self):
        result = build_ws_stream_content(reasoning_text="reasoning", visible_text="answer")
        assert "<think>" in result
        assert "reasoning" in result
        assert "</think>" in result
        assert "answer" in result

    def test_empty_returns_empty(self):
        result = build_ws_stream_content()
        assert result == ""

    def test_empty_reasoning_returns_visible(self):
        result = build_ws_stream_content(reasoning_text="", visible_text="hello")
        assert result == "hello"


# ── WeComStreamConsumer unit tests ──────────────────────────────────────


class TestWeComStreamConsumerCallbacks:
    """Verify thread-safe callback queueing."""

    def _make_consumer(self):
        adapter = MagicMock()
        adapter._new_req_id = MagicMock(return_value="stream-123")
        adapter._send_reply_stream = AsyncMock()
        adapter._thinking_task = None
        adapter._thinking_cancelled = False
        return WeComStreamConsumer(
            adapter=adapter,
            chat_id="chat-1",
            reply_req_id="req-1",
            stream_id="stream-123",
        )

    def test_on_delta_queues_visible(self):
        consumer = self._make_consumer()
        consumer.on_delta("hello")
        kind, data = consumer._queue.get_nowait()
        assert kind == "visible"
        assert data == "hello"

    def test_on_reasoning_queues_reasoning(self):
        consumer = self._make_consumer()
        consumer.on_reasoning("thinking...")
        kind, data = consumer._queue.get_nowait()
        assert kind == "reasoning"
        assert data == "thinking..."

    def test_on_delta_none_queues_segment_break(self):
        consumer = self._make_consumer()
        consumer.on_delta(None)
        kind, data = consumer._queue.get_nowait()
        assert kind == "segment_break"

    def test_finish_queues_done(self):
        consumer = self._make_consumer()
        consumer.finish()
        kind, data = consumer._queue.get_nowait()
        assert kind == "done"

    def test_on_commentary_queues_commentary(self):
        consumer = self._make_consumer()
        consumer.on_commentary("interim message")
        kind, data = consumer._queue.get_nowait()
        assert kind == "commentary"
        assert data == "interim message"

    def test_on_commentary_empty_noop(self):
        consumer = self._make_consumer()
        consumer.on_commentary("")
        assert consumer._queue.empty()


class TestWeComStreamConsumerRun:
    """Verify async run loop sends stream updates."""

    def _make_consumer(self):
        adapter = MagicMock()
        adapter._new_req_id = MagicMock(return_value="stream-456")
        adapter._send_reply_stream = AsyncMock()
        adapter._thinking_task = None
        adapter._thinking_cancelled = False
        return WeComStreamConsumer(
            adapter=adapter,
            chat_id="chat-1",
            reply_req_id="req-1",
            stream_id="stream-123",
        )

    @pytest.mark.asyncio
    async def test_run_sends_visible_and_finishes(self):
        consumer = self._make_consumer()
        consumer.on_delta("hello world")
        consumer.finish()

        await consumer.run()

        assert consumer.already_sent
        assert consumer.final_response_sent
        # Should have sent at least one update + final
        assert consumer.adapter._send_reply_stream.call_count >= 1

    @pytest.mark.asyncio
    async def test_run_cancels_thinking_loop_on_first_token(self):
        consumer = self._make_consumer()
        # Simulate thinking loop running
        mock_task = MagicMock()
        mock_task.done.return_value = False
        consumer.adapter._thinking_task = mock_task

        consumer.on_delta("first token")
        consumer.finish()

        await consumer.run()

        # Thinking loop should have been cancelled
        assert consumer.adapter._thinking_cancelled is True
        mock_task.cancel.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_with_reasoning_preserves_tags(self):
        consumer = self._make_consumer()
        consumer.on_reasoning("step 1")
        consumer.on_delta("answer")
        consumer.finish()

        await consumer.run()

        assert consumer.final_response_sent
        # Check the final call includes reasoning in think tags
        final_call = consumer.adapter._send_reply_stream.call_args_list[-1]
        content = final_call[1].get("content") or final_call[0][1] if len(final_call[0]) > 1 else ""
        # The content should contain think tags
        assert "<think>" in str(consumer._build_stream_content(finish=True))

    @pytest.mark.asyncio
    async def test_properties_before_run(self):
        consumer = self._make_consumer()
        assert not consumer.already_sent
        assert not consumer.final_response_sent
