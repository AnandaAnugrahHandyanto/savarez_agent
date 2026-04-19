"""Regression tests for temperature retry + memoization in the Anthropic aux client.

The static `_forbids_sampling_params` list in `agent/anthropic_adapter.py` only
covers model families known to reject sampling params at the time of writing
(Opus 4.7+). Newer restricted families — Haiku 4.5, Opus 4.6 — 400 with
"`temperature` is deprecated for this model." when the param is forwarded.

These tests exercise the runtime defense: catch that specific 400, retry once
without `temperature`, and memoize the model so subsequent calls skip the
param pre-emptively.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
import pytest

import anthropic

from agent.auxiliary_client import _AnthropicCompletionsAdapter
import agent.auxiliary_client as aux_mod


def _temperature_deprecated_error() -> anthropic.BadRequestError:
    resp = httpx.Response(400, request=httpx.Request("POST", "http://x"))
    body = {"error": {"type": "invalid_request_error",
                      "message": "`temperature` is deprecated for this model."}}
    return anthropic.BadRequestError(
        message="Error code: 400 - {'error': {'message': "
                "'`temperature` is deprecated for this model.'}}",
        response=resp,
        body=body,
    )


def _unrelated_bad_request() -> anthropic.BadRequestError:
    resp = httpx.Response(400, request=httpx.Request("POST", "http://x"))
    body = {"error": {"type": "invalid_request_error",
                      "message": "messages: roles must alternate"}}
    return anthropic.BadRequestError(
        message="Error code: 400 - messages: roles must alternate",
        response=resp,
        body=body,
    )


def _ok_response() -> SimpleNamespace:
    """Minimal shape normalize_anthropic_response can consume."""
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text="ok")],
        stop_reason="end_turn",
        usage=SimpleNamespace(input_tokens=1, output_tokens=1, total_tokens=2),
    )


@pytest.fixture
def patched_adapter():
    """Wire up an adapter with build_anthropic_kwargs passing temperature
    straight through, and normalize_anthropic_response returning a minimal
    assistant message. Focuses the tests on retry behaviour, not the adapter's
    argument plumbing or response parsing (covered elsewhere).
    """
    def fake_build(**kwargs):
        out = {"model": kwargs["model"],
               "messages": kwargs["messages"],
               "max_tokens": kwargs.get("max_tokens", 2000)}
        return out

    def fake_normalize(response):
        return SimpleNamespace(role="assistant", content="ok", tool_calls=None), "stop"

    with patch("agent.anthropic_adapter.build_anthropic_kwargs", fake_build), \
         patch("agent.anthropic_adapter.normalize_anthropic_response", fake_normalize), \
         patch("agent.anthropic_adapter._forbids_sampling_params", return_value=False):
        yield


@pytest.fixture(autouse=True)
def _reset_temp_cache():
    """Clear the module-level memoization before/after each test."""
    aux_mod._TEMP_UNSUPPORTED_MODELS.clear()
    yield
    aux_mod._TEMP_UNSUPPORTED_MODELS.clear()


def test_temperature_rejection_retried_without_param(patched_adapter):
    """First call raises the deprecated-temperature 400; retry without
    temperature succeeds and returns a normalized response."""
    client = MagicMock()
    client.messages.create.side_effect = [_temperature_deprecated_error(), _ok_response()]

    adapter = _AnthropicCompletionsAdapter(client, model="haiku-4-5")
    result = adapter.create(messages=[{"role": "user", "content": "hi"}], temperature=0.1)

    assert client.messages.create.call_count == 2
    first_call = client.messages.create.call_args_list[0].kwargs
    retry_call = client.messages.create.call_args_list[1].kwargs
    assert first_call.get("temperature") == 0.1
    assert "temperature" not in retry_call
    assert result.choices[0].message.content == "ok"


def test_rejecting_model_is_memoized(patched_adapter):
    """After a rejection, the same model's next call strips temperature
    before hitting the API — no second retry needed."""
    client = MagicMock()
    client.messages.create.side_effect = [
        _temperature_deprecated_error(),
        _ok_response(),   # retry of first call
        _ok_response(),   # second invocation, first attempt
    ]

    adapter = _AnthropicCompletionsAdapter(client, model="haiku-4-5")
    adapter.create(messages=[{"role": "user", "content": "a"}], temperature=0.1)
    adapter.create(messages=[{"role": "user", "content": "b"}], temperature=0.1)

    # Three total: rejection + retry + second call's single attempt
    assert client.messages.create.call_count == 3
    third_call = client.messages.create.call_args_list[2].kwargs
    assert "temperature" not in third_call
    assert "haiku-4-5" in aux_mod._TEMP_UNSUPPORTED_MODELS


def test_unrelated_bad_request_is_not_retried(patched_adapter):
    """A 400 that isn't about temperature must propagate unchanged and must
    not add the model to the unsupported set."""
    client = MagicMock()
    client.messages.create.side_effect = _unrelated_bad_request()

    adapter = _AnthropicCompletionsAdapter(client, model="haiku-4-5")

    with pytest.raises(anthropic.BadRequestError):
        adapter.create(messages=[{"role": "user", "content": "hi"}], temperature=0.1)

    assert client.messages.create.call_count == 1
    assert "haiku-4-5" not in aux_mod._TEMP_UNSUPPORTED_MODELS


def test_call_without_temperature_is_not_retried(patched_adapter):
    """If temperature wasn't sent in the first place, the deprecated-temperature
    error (if it somehow still fires) should propagate rather than infinite-loop."""
    client = MagicMock()
    client.messages.create.side_effect = _temperature_deprecated_error()

    adapter = _AnthropicCompletionsAdapter(client, model="haiku-4-5")

    with pytest.raises(anthropic.BadRequestError):
        adapter.create(messages=[{"role": "user", "content": "hi"}])  # no temperature

    assert client.messages.create.call_count == 1
