"""Tests for agent/codex_runtime.py — Codex stream recovery paths."""
from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, ".")
from agent.codex_runtime import run_codex_stream


class _FakeAgent:
    """Minimal fake agent with attributes needed by run_codex_stream."""

    def __init__(self):
        self._interrupt_requested = False
        self._codex_streamed_text_parts: list = []
        self._codex_stream_last_event_ts = None
        # Fire callbacks are no-ops for tests
        self._fire_stream_delta = lambda text: None
        self._fire_reasoning_delta = lambda text: None
        self._fire_tool_gen_started = lambda name: None
        self._touch_activity = lambda msg: None
        self.log_prefix = "[test] "
        self._client_log_context = lambda: "test_context"
        self.verbose_logging = False
        # Fallback hooks
        self._run_codex_create_stream_fallback = MagicMock()

    def _ensure_primary_openai_client(self, *, reason: str):
        return MagicMock()

    def _get_transport(self):
        t = MagicMock()
        t.preflight_kwargs = lambda kwargs, allow_stream=False: kwargs
        return t


class _FakeStream:
    """Iterable stream mock — __iter__ on the class so Python resolves it.
    Not a MagicMock because MagicMock fabricates an "output" attribute
    which causes run_codex_create_stream_fallback to hit the early-return
    compatibility shim instead of iterating events."""

    def __init__(self, events):
        self._events = events

    def __iter__(self):
        return iter(self._events)

    def close(self):
        pass


def _make_stream_with_crash(events):
    """Return a stream that iterates `events` then crashes get_final_response()."""
    mock_stream = MagicMock()
    mock_stream.__iter__ = lambda self: iter(events)
    mock_stream.get_final_response = MagicMock(
        side_effect=TypeError("'NoneType' object is not iterable")
    )
    return mock_stream


def test_run_codex_stream_recovers_from_none_output():
    """When get_final_response() crashes with TypeError (response.output is None),
    run_codex_stream should recover by reconstructing from collected output items."""
    agent = _FakeAgent()

    text_content = [SimpleNamespace(type="output_text", text="Hello from codex")]
    output_item = SimpleNamespace(
        type="message",
        role="assistant",
        status="completed",
        content=text_content,
    )

    # Build events that the real codex backend emits
    events = [
        SimpleNamespace(type="response.created"),
        SimpleNamespace(type="response.in_progress"),
        SimpleNamespace(type="response.output_item.added"),
        SimpleNamespace(type="response.content_part.added"),
        SimpleNamespace(
            type="response.output_text.delta", delta="Hello from codex",
        ),
        SimpleNamespace(type="response.output_text.done"),
        SimpleNamespace(type="response.content_part.done"),
        SimpleNamespace(type="response.output_item.done", item=output_item),
    ]

    mock_stream = _make_stream_with_crash(events)

    fake_client = MagicMock()
    fake_client.responses.stream.return_value.__enter__ = lambda self: mock_stream
    fake_client.responses.stream.return_value.__exit__ = lambda *a: None

    agent._ensure_primary_openai_client = lambda reason="": fake_client

    result = run_codex_stream(
        agent,
        api_kwargs={"model": "gpt-5.5", "instructions": "Hi", "input": []},
        client=fake_client,
    )

    assert result is not None
    assert hasattr(result, "output")
    assert isinstance(result.output, list)
    assert len(result.output) > 0
    assert result.output[0].content[0].text == "Hello from codex"


def test_run_codex_stream_recovers_from_deltas_when_no_items():
    """When no output_item.done events were collected but text deltas exist,
    run_codex_stream should synthesize output from deltas."""
    agent = _FakeAgent()

    events = [
        SimpleNamespace(type="response.created"),
        SimpleNamespace(type="response.in_progress"),
        SimpleNamespace(type="response.output_text.delta", delta="Hello"),
        SimpleNamespace(type="response.output_text.done"),
        SimpleNamespace(type="response.output_text.delta", delta=" world"),
        SimpleNamespace(type="response.output_text.done"),
    ]

    mock_stream = _make_stream_with_crash(events)

    fake_client = MagicMock()
    fake_client.responses.stream.return_value.__enter__ = lambda self: mock_stream
    fake_client.responses.stream.return_value.__exit__ = lambda *a: None

    agent._ensure_primary_openai_client = lambda reason="": fake_client

    result = run_codex_stream(
        agent,
        api_kwargs={"model": "gpt-5.5", "instructions": "Hi", "input": []},
        client=fake_client,
    )

    assert result is not None
    assert hasattr(result, "output")
    assert isinstance(result.output, list)
    assert result.output[0].content[0].text == "Hello world"


def test_run_codex_create_stream_fallback_recovers_from_no_terminal_event():
    """When the fallback stream emits no terminal event but has collected items,
    it should reconstruct the response from them."""
    from agent.codex_runtime import run_codex_create_stream_fallback

    agent = _FakeAgent()

    text_content = [SimpleNamespace(type="output_text", text="fallback text")]
    output_item = SimpleNamespace(
        type="message", role="assistant", status="completed",
        content=text_content,
    )

    events = [
        SimpleNamespace(type="response.output_item.done", item=output_item),
    ]

    mock_stream = _FakeStream(events)

    fake_client = MagicMock()
    fake_client.responses.create.return_value = mock_stream

    agent._ensure_primary_openai_client = lambda reason="": fake_client

    result = run_codex_create_stream_fallback(
        agent,
        api_kwargs={"model": "gpt-5.5", "instructions": "Hi", "input": [], "stream": True},
        client=fake_client,
    )

    assert result is not None
    assert hasattr(result, "output")
    assert isinstance(result.output, list)
    assert result.output[0].content[0].text == "fallback text"
