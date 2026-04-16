import sys
import threading
import types
from types import SimpleNamespace

import httpx
import pytest
from openai import APIConnectionError
from openai._constants import DEFAULT_TIMEOUT

sys.modules.setdefault("fire", types.SimpleNamespace(Fire=lambda *a, **k: None))
sys.modules.setdefault("firecrawl", types.SimpleNamespace(Firecrawl=object))
sys.modules.setdefault("fal_client", types.SimpleNamespace())

import run_agent


class FakeRequestClient:
    def __init__(self, responder):
        self._responder = responder
        self._client = SimpleNamespace(is_closed=False)
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create)
        )
        self.responses = SimpleNamespace()
        self.close_calls = 0

    def _create(self, **kwargs):
        return self._responder(**kwargs)

    def close(self):
        self.close_calls += 1
        self._client.is_closed = True


class FakeSharedClient(FakeRequestClient):
    pass


class OpenAIFactory:
    def __init__(self, clients):
        self._clients = list(clients)
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(dict(kwargs))
        if not self._clients:
            raise AssertionError("OpenAI factory exhausted")
        return self._clients.pop(0)


def _build_agent(shared_client=None):
    agent = run_agent.AIAgent.__new__(run_agent.AIAgent)
    agent.api_mode = "chat_completions"
    agent.provider = "openai-codex"
    agent.base_url = "https://chatgpt.com/backend-api/codex"
    agent.model = "gpt-5-codex"
    agent.log_prefix = ""
    agent.quiet_mode = True
    agent._interrupt_requested = False
    agent._interrupt_message = None
    agent._client_lock = threading.RLock()
    agent._client_kwargs = {"api_key": "***", "base_url": agent.base_url}
    agent.client = shared_client or FakeSharedClient(lambda **kwargs: {"shared": True})
    agent.stream_delta_callback = None
    agent._stream_callback = None
    agent.reasoning_callback = None
    return agent


def _connection_error():
    return APIConnectionError(
        message="Connection error.",
        request=httpx.Request("POST", "https://example.com/v1/chat/completions"),
    )


def test_retry_after_api_connection_error_recreates_request_client(monkeypatch):
    first_request = FakeRequestClient(lambda **kwargs: (_ for _ in ()).throw(_connection_error()))
    second_request = FakeRequestClient(lambda **kwargs: {"ok": True})
    factory = OpenAIFactory([first_request, second_request])
    monkeypatch.setattr(run_agent, "OpenAI", factory)

    agent = _build_agent()

    with pytest.raises(APIConnectionError):
        agent._interruptible_api_call({"model": agent.model, "messages": []})

    result = agent._interruptible_api_call({"model": agent.model, "messages": []})

    assert result == {"ok": True}
    assert len(factory.calls) == 2
    assert first_request.close_calls >= 1
    assert second_request.close_calls >= 1


def test_closed_shared_client_is_recreated_before_request(monkeypatch):
    stale_shared = FakeSharedClient(lambda **kwargs: (_ for _ in ()).throw(AssertionError("stale shared client used")))
    stale_shared._client.is_closed = True

    replacement_shared = FakeSharedClient(lambda **kwargs: {"replacement": True})
    request_client = FakeRequestClient(lambda **kwargs: {"ok": "fresh-request-client"})
    factory = OpenAIFactory([replacement_shared, request_client])
    monkeypatch.setattr(run_agent, "OpenAI", factory)

    agent = _build_agent(shared_client=stale_shared)
    result = agent._interruptible_api_call({"model": agent.model, "messages": []})

    assert result == {"ok": "fresh-request-client"}
    assert agent.client is replacement_shared
    assert stale_shared.close_calls >= 1
    assert replacement_shared.close_calls == 0
    assert len(factory.calls) == 2


def test_concurrent_requests_do_not_break_each_other_when_one_client_closes(monkeypatch):
    first_started = threading.Event()
    first_closed = threading.Event()

    def first_responder(**kwargs):
        first_started.set()
        first_client.close()
        first_closed.set()
        raise _connection_error()

    def second_responder(**kwargs):
        assert first_started.wait(timeout=2)
        assert first_closed.wait(timeout=2)
        return {"ok": "second"}

    first_client = FakeRequestClient(first_responder)
    second_client = FakeRequestClient(second_responder)
    factory = OpenAIFactory([first_client, second_client])
    monkeypatch.setattr(run_agent, "OpenAI", factory)

    agent = _build_agent()
    results = {}

    def run_call(name):
        try:
            results[name] = agent._interruptible_api_call({"model": agent.model, "messages": []})
        except Exception as exc:  # noqa: BLE001 - asserting exact type below
            results[name] = exc

    thread_one = threading.Thread(target=run_call, args=("first",), daemon=True)
    thread_two = threading.Thread(target=run_call, args=("second",), daemon=True)
    thread_one.start()
    thread_two.start()
    thread_one.join(timeout=5)
    thread_two.join(timeout=5)

    values = list(results.values())
    assert sum(isinstance(value, APIConnectionError) for value in values) == 1
    assert values.count({"ok": "second"}) == 1
    assert len(factory.calls) == 2


def test_keepalive_http_client_preserves_openai_default_timeout(monkeypatch):
    factory = OpenAIFactory([FakeSharedClient(lambda **kwargs: {"ok": True})])
    monkeypatch.setattr(run_agent, "OpenAI", factory)

    agent = _build_agent()
    _ = agent._create_openai_client(dict(agent._client_kwargs), reason="test_keepalive", shared=True)

    assert len(factory.calls) == 1
    http_client = factory.calls[0]["http_client"]
    assert isinstance(http_client, httpx.Client)
    assert http_client.timeout == DEFAULT_TIMEOUT
    assert http_client.timeout != httpx.Timeout(5.0)
    http_client.close()


def test_keepalive_http_client_does_not_mutate_stored_client_kwargs(monkeypatch):
    factory = OpenAIFactory([FakeSharedClient(lambda **kwargs: {"ok": True})])
    monkeypatch.setattr(run_agent, "OpenAI", factory)

    agent = _build_agent()
    original = dict(agent._client_kwargs)
    _ = agent._create_openai_client(agent._client_kwargs, reason="test_kwargs_immutability", shared=True)

    assert agent._client_kwargs == original
    assert "http_client" not in agent._client_kwargs
    factory.calls[0]["http_client"].close()


def test_request_client_gets_fresh_http_client_after_shared_client_creation(monkeypatch):
    shared_client = FakeSharedClient(lambda **kwargs: {"shared": True})
    request_client = FakeRequestClient(lambda **kwargs: {"ok": True})
    factory = OpenAIFactory([shared_client, request_client])
    monkeypatch.setattr(run_agent, "OpenAI", factory)

    agent = _build_agent()
    shared = agent._create_openai_client(agent._client_kwargs, reason="shared", shared=True)
    agent.client = shared
    req = agent._create_request_openai_client(reason="request")

    assert len(factory.calls) == 2
    assert factory.calls[0]["http_client"] is not factory.calls[1]["http_client"]
    factory.calls[0]["http_client"].close()
    factory.calls[1]["http_client"].close()
    agent._close_request_openai_client(req, reason="test_cleanup")



def test_streaming_call_recreates_closed_shared_client_before_request(monkeypatch):
    chunks = iter([
        SimpleNamespace(
            model="gpt-5-codex",
            choices=[SimpleNamespace(delta=SimpleNamespace(content="Hello", tool_calls=None), finish_reason=None)],
        ),
        SimpleNamespace(
            model="gpt-5-codex",
            choices=[SimpleNamespace(delta=SimpleNamespace(content=" world", tool_calls=None), finish_reason="stop")],
        ),
    ])

    stale_shared = FakeSharedClient(lambda **kwargs: (_ for _ in ()).throw(AssertionError("stale shared client used")))
    stale_shared._client.is_closed = True

    replacement_shared = FakeSharedClient(lambda **kwargs: {"replacement": True})
    request_client = FakeRequestClient(lambda **kwargs: chunks)
    factory = OpenAIFactory([replacement_shared, request_client])
    monkeypatch.setattr(run_agent, "OpenAI", factory)

    agent = _build_agent(shared_client=stale_shared)
    agent.stream_delta_callback = lambda _delta: None
    # Force chat_completions mode so the streaming path uses
    # chat.completions.create(stream=True) instead of Codex responses.stream()
    agent.api_mode = "chat_completions"
    response = agent._interruptible_streaming_api_call({"model": agent.model, "messages": []})

    assert response.choices[0].message.content == "Hello world"
    assert agent.client is replacement_shared
    assert stale_shared.close_calls >= 1
    assert request_client.close_calls >= 1
    assert len(factory.calls) == 2
