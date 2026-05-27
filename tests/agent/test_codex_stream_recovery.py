"""Regression tests for malformed Responses streaming terminal events."""

from __future__ import annotations

from types import SimpleNamespace


class _MalformedTerminalStream:
    """Yields valid content, then fails like the SDK parser can on completion."""

    def __init__(self, events):
        self._events = list(events)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def __iter__(self):
        yield from self._events
        raise TypeError("'NoneType' object is not iterable")

    def get_final_response(self):
        raise AssertionError("iteration failure should recover before final response")


def _message_item(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        type="message",
        status="completed",
        content=[SimpleNamespace(type="output_text", text=text)],
        role="assistant",
    )


def test_codex_stream_recovers_when_terminal_event_omits_output():
    from agent.codex_runtime import run_codex_stream

    item = _message_item("pong")
    events = [SimpleNamespace(type="response.output_item.done", item=item)]
    client = SimpleNamespace(
        responses=SimpleNamespace(
            stream=lambda **kwargs: _MalformedTerminalStream(events)
        )
    )
    agent = SimpleNamespace(
        _interrupt_requested=False,
        _codex_stream_last_event_ts=None,
        _touch_activity=lambda *args, **kwargs: None,
        _fire_stream_delta=lambda *args, **kwargs: None,
        _fire_reasoning_delta=lambda *args, **kwargs: None,
        _client_log_context=lambda: "provider=custom model=gpt-5.5",
    )

    response = run_codex_stream(agent, {"model": "gpt-5.5"}, client=client)

    assert response.output == [item]


def test_codex_auxiliary_recovers_when_terminal_event_omits_output():
    from agent.auxiliary_client import _CodexCompletionsAdapter

    item = _message_item("pong")
    events = [SimpleNamespace(type="response.output_item.done", item=item)]
    client = SimpleNamespace(
        responses=SimpleNamespace(
            stream=lambda **kwargs: _MalformedTerminalStream(events)
        )
    )

    response = _CodexCompletionsAdapter(client, "gpt-5.5").create(
        messages=[{"role": "user", "content": "ping"}]
    )

    assert response.choices[0].message.content == "pong"
