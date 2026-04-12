"""Tests for SSE client disconnect → agent task cancellation.

When a streaming /v1/chat/completions client disconnects mid-stream
(network drop, browser tab close), the agent is interrupted via
agent.interrupt() so it stops making LLM API calls, and the asyncio
task wrapper is cancelled.

These tests drive `_write_sse_chat_completion()` by consuming the
inner async generator returned via `StreamingResponse.body_iterator`
and toggling `request.is_disconnected()` to simulate the client drop.
"""

import asyncio
import queue
from unittest.mock import AsyncMock, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_adapter():
    """Build a minimal APIServerAdapter with mocked internals."""
    from gateway.platforms.api_server import APIServerAdapter
    from gateway.config import PlatformConfig

    config = PlatformConfig(enabled=True, token="test-key")
    return APIServerAdapter(config)


def _make_request(disconnect_after: int = 0):
    """Build a mock FastAPI-style request.

    disconnect_after: number of `is_disconnected()` polls to return False for
    before returning True. 0 = disconnected immediately on first poll.
    """
    req = MagicMock()
    req.headers = {}
    req.path_params = {}

    state = {"polls": 0, "disconnect_after": disconnect_after}

    async def _is_disconnected():
        state["polls"] += 1
        return state["polls"] > state["disconnect_after"]

    req.is_disconnected = _is_disconnected
    return req


async def _drain_body(response, limit: int = 200):
    """Consume a StreamingResponse's body_iterator up to `limit` chunks.

    Swallows CancelledError: the generator awaits the agent_task internally
    after detecting disconnect, and once the task is cancelled that await
    raises CancelledError — which is the expected outcome of this path,
    not a test failure.
    """
    out = []
    try:
        async for chunk in response.body_iterator:
            out.append(chunk)
            if len(out) >= limit:
                break
    except asyncio.CancelledError:
        pass
    return out


async def _never_returning_agent():
    # Runs until cancelled; used to simulate an in-flight agent.
    await asyncio.Event().wait()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSSEAgentCancelOnDisconnect:
    """gateway/platforms/api_server.py — _write_sse_chat_completion()"""

    @pytest.mark.asyncio
    async def test_agent_task_cancelled_on_client_disconnect(self):
        """Generator detects disconnect and cancels the agent task."""
        adapter = _make_adapter()
        stream_q = queue.Queue()

        agent_task = asyncio.ensure_future(_never_returning_agent())
        agent_ref = MagicMock()

        response = await adapter._write_sse_chat_completion(
            _make_request(disconnect_after=0),
            "cmpl-1", "gpt-4", 1234567890,
            stream_q, agent_task, agent_ref=agent_ref,
        )

        await _drain_body(response)
        # Give the cancellation a tick to propagate.
        for _ in range(5):
            if agent_task.cancelled() or agent_task.done():
                break
            await asyncio.sleep(0)
        assert agent_task.cancelled() or agent_task.done()

    @pytest.mark.asyncio
    async def test_agent_task_not_cancelled_on_normal_completion(self):
        """On normal completion (agent done, sentinel received), don't cancel."""
        adapter = _make_adapter()
        stream_q = queue.Queue()

        # Agent that returns immediately (no cancel needed).
        async def done_agent():
            return ({"final_response": "ok", "messages": []},
                    {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2})

        agent_task = asyncio.ensure_future(done_agent())
        await agent_task  # make sure it's done before we start iterating

        # Feed a single delta then the sentinel so the generator exits.
        stream_q.put("hello")
        stream_q.put(None)

        response = await adapter._write_sse_chat_completion(
            _make_request(disconnect_after=1000),
            "cmpl-2", "gpt-4", 1234567890,
            stream_q, agent_task,
        )
        await _drain_body(response)
        assert agent_task.done()
        assert not agent_task.cancelled()

    @pytest.mark.asyncio
    async def test_broken_pipe_also_cancels_agent(self):
        """Explicit disconnect poll triggers interrupt + cancel."""
        adapter = _make_adapter()
        stream_q = queue.Queue()

        agent_task = asyncio.ensure_future(_never_returning_agent())
        agent_ref = MagicMock()

        response = await adapter._write_sse_chat_completion(
            _make_request(disconnect_after=0),
            "cmpl-3", "gpt-4", 1234567890,
            stream_q, agent_task, agent_ref=agent_ref,
        )
        await _drain_body(response)
        for _ in range(5):
            if agent_task.cancelled() or agent_task.done():
                break
            await asyncio.sleep(0)
        assert agent_task.cancelled() or agent_task.done()

    @pytest.mark.asyncio
    async def test_already_done_task_not_cancelled_on_disconnect(self):
        """If the agent task already finished, disconnect must not double-cancel."""
        adapter = _make_adapter()
        stream_q = queue.Queue()

        async def quick_agent():
            return ({"final_response": "done", "messages": []},
                    {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0})

        agent_task = asyncio.ensure_future(quick_agent())
        await agent_task

        stream_q.put(None)  # immediately end stream
        response = await adapter._write_sse_chat_completion(
            _make_request(disconnect_after=0),
            "cmpl-4", "gpt-4", 1234567890,
            stream_q, agent_task,
        )
        await _drain_body(response)
        # done tasks must never appear cancelled
        assert agent_task.done()
        assert not agent_task.cancelled()

    @pytest.mark.asyncio
    async def test_agent_interrupt_called_on_disconnect(self):
        """agent_ref.interrupt() is invoked when disconnect detected."""
        adapter = _make_adapter()
        stream_q = queue.Queue()

        agent_task = asyncio.ensure_future(_never_returning_agent())
        agent_ref = MagicMock()

        response = await adapter._write_sse_chat_completion(
            _make_request(disconnect_after=0),
            "cmpl-5", "gpt-4", 1234567890,
            stream_q, agent_task, agent_ref=agent_ref,
        )
        await _drain_body(response)
        # Let the cancellation propagate.
        for _ in range(5):
            if agent_ref.interrupt.called:
                break
            await asyncio.sleep(0)
        agent_ref.interrupt.assert_called()

    @pytest.mark.asyncio
    async def test_agent_ref_none_still_cancels_task(self):
        """Missing agent_ref must not prevent task cancellation on disconnect."""
        adapter = _make_adapter()
        stream_q = queue.Queue()

        agent_task = asyncio.ensure_future(_never_returning_agent())

        response = await adapter._write_sse_chat_completion(
            _make_request(disconnect_after=0),
            "cmpl-6", "gpt-4", 1234567890,
            stream_q, agent_task, agent_ref=None,
        )
        await _drain_body(response)
        for _ in range(5):
            if agent_task.cancelled() or agent_task.done():
                break
            await asyncio.sleep(0)
        assert agent_task.cancelled() or agent_task.done()
