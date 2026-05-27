from types import SimpleNamespace

from agent.codex_runtime import run_codex_stream
from agent.auxiliary_client import _CodexCompletionsAdapter


class _NullOutputCompletedStream:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def __iter__(self):
        yield SimpleNamespace(type="response.output_text.delta", delta="hello ")
        yield SimpleNamespace(type="response.output_text.delta", delta="world")
        raise TypeError("'NoneType' object is not iterable")

    def get_final_response(self):
        raise AssertionError("stream iteration should fail before final response")


class _DirectNullOutputCompletedStream:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def __iter__(self):
        yield SimpleNamespace(type="response.output_text.delta", delta="direct ")
        yield SimpleNamespace(type="response.output_text.delta", delta="ok")

    def get_final_response(self):
        return SimpleNamespace(status="completed", output=None, usage=None)


class _FakeResponses:
    def stream(self, **kwargs):
        return _NullOutputCompletedStream()


class _FakeDirectNullResponses:
    def stream(self, **kwargs):
        return _DirectNullOutputCompletedStream()


def _fake_agent(responses):
    return SimpleNamespace(
        _interrupt_requested=False,
        _codex_stream_last_event_ts=None,
        _codex_streamed_text_parts=[],
        _ensure_primary_openai_client=lambda reason: SimpleNamespace(responses=responses),
        _touch_activity=lambda message: None,
        _fire_stream_delta=lambda text: None,
        _fire_reasoning_delta=lambda text: None,
        _client_log_context=lambda: "provider=openai-codex model=gpt-5.5",
    )


def test_codex_stream_recovers_from_completed_null_output():
    agent = _fake_agent(_FakeResponses())

    response = run_codex_stream(agent, {"model": "gpt-5.5"})

    assert response.status == "completed"
    assert response.output[0].content[0].text == "hello world"


def test_codex_stream_backfills_direct_null_final_output():
    agent = _fake_agent(_FakeDirectNullResponses())

    response = run_codex_stream(agent, {"model": "gpt-5.5"})

    assert response.status == "completed"
    assert response.output[0].content[0].text == "direct ok"


def test_codex_auxiliary_recovers_from_completed_null_output():
    fake_client = SimpleNamespace(responses=_FakeResponses())
    adapter = _CodexCompletionsAdapter(fake_client, "gpt-5.5")

    response = adapter.create(messages=[{"role": "user", "content": "hi"}])

    assert response.choices[0].message.content == "hello world"


def test_codex_auxiliary_backfills_direct_null_final_output():
    fake_client = SimpleNamespace(responses=_FakeDirectNullResponses())
    adapter = _CodexCompletionsAdapter(fake_client, "gpt-5.5")

    response = adapter.create(messages=[{"role": "user", "content": "hi"}])

    assert response.choices[0].message.content == "direct ok"
