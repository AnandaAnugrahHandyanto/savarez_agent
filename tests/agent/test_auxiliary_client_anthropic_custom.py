"""Tests for agent.auxiliary_client._try_custom_endpoint's anthropic_messages branch.

When a user configures a custom endpoint with ``api_mode: anthropic_messages``
(e.g. MiniMax, Zhipu GLM, LiteLLM in Anthropic-proxy mode), auxiliary tasks
(compression, web_extract, session_search, title generation) must use the
native Anthropic transport rather than being silently downgraded to an
OpenAI-wire client that speaks the wrong protocol.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for key in (
        "OPENAI_API_KEY", "OPENAI_BASE_URL",
        "ANTHROPIC_API_KEY", "ANTHROPIC_TOKEN",
    ):
        monkeypatch.delenv(key, raising=False)


def _install_anthropic_adapter_mocks():
    """Patch build_anthropic_client so the test doesn't need the SDK."""
    fake_client = MagicMock(name="anthropic_client")
    return patch(
        "agent.anthropic_adapter.build_anthropic_client",
        return_value=fake_client,
    ), fake_client


def test_custom_endpoint_anthropic_messages_builds_anthropic_wrapper():
    """api_mode=anthropic_messages → returns AnthropicAuxiliaryClient, not OpenAI."""
    from agent.auxiliary_client import _try_custom_endpoint, AnthropicAuxiliaryClient

    with patch(
        "agent.auxiliary_client._resolve_custom_runtime",
        return_value=(
            "https://api.minimax.io/anthropic",
            "minimax-key",
            "anthropic_messages",
        ),
    ), patch(
        "agent.auxiliary_client._read_main_model",
        return_value="claude-sonnet-4-6",
    ):
        adapter_patch, fake_client = _install_anthropic_adapter_mocks()
        with adapter_patch:
            client, model = _try_custom_endpoint()

    assert isinstance(client, AnthropicAuxiliaryClient), (
        "Custom endpoint with api_mode=anthropic_messages must return the "
        f"native Anthropic wrapper, got {type(client).__name__}"
    )
    assert model == "claude-sonnet-4-6"
    # Wrapper should NOT be marked as OAuth — third-party endpoints are
    # always API-key authenticated.
    assert client.api_key == "minimax-key"
    assert client.base_url == "https://api.minimax.io/anthropic"


def test_custom_endpoint_anthropic_messages_falls_back_when_sdk_missing():
    """Graceful degradation when anthropic SDK is unavailable."""
    from agent.auxiliary_client import _try_custom_endpoint

    import_error = ImportError("anthropic package not installed")

    with patch(
        "agent.auxiliary_client._resolve_custom_runtime",
        return_value=("https://api.minimax.io/anthropic", "k", "anthropic_messages"),
    ), patch(
        "agent.auxiliary_client._read_main_model",
        return_value="claude-sonnet-4-6",
    ), patch(
        "agent.anthropic_adapter.build_anthropic_client",
        side_effect=import_error,
    ):
        client, model = _try_custom_endpoint()

    # Should fall back to an OpenAI-wire client rather than returning
    # (None, None) — the tool still needs to do *something*.
    assert client is not None
    assert model == "claude-sonnet-4-6"
    # OpenAI client, not AnthropicAuxiliaryClient.
    from agent.auxiliary_client import AnthropicAuxiliaryClient
    assert not isinstance(client, AnthropicAuxiliaryClient)


def test_custom_endpoint_chat_completions_still_uses_openai_wire():
    """Regression: default path (no api_mode) must remain OpenAI client."""
    from agent.auxiliary_client import _try_custom_endpoint, AnthropicAuxiliaryClient

    with patch(
        "agent.auxiliary_client._resolve_custom_runtime",
        return_value=("https://api.example.com/v1", "key", None),
    ), patch(
        "agent.auxiliary_client._read_main_model",
        return_value="my-model",
    ):
        client, model = _try_custom_endpoint()

    assert client is not None
    assert model == "my-model"
    assert not isinstance(client, AnthropicAuxiliaryClient)


def test_anthropic_completions_adapter_uses_stream_final_message():
    """Anthropic auxiliary calls must support streaming-only endpoints."""
    from agent.auxiliary_client import _AnthropicCompletionsAdapter

    final_message = SimpleNamespace(
        usage=SimpleNamespace(input_tokens=11, output_tokens=7)
    )
    normalized = SimpleNamespace(
        content="streamed final",
        tool_calls=[],
        reasoning=None,
        finish_reason="end_turn",
    )
    client = MagicMock()
    stream_ctx = MagicMock()
    stream_obj = MagicMock()
    stream_obj.get_final_message.return_value = final_message
    stream_ctx.__enter__.return_value = stream_obj
    stream_ctx.__exit__.return_value = None
    client.messages.stream.return_value = stream_ctx
    transport = SimpleNamespace(normalize_response=MagicMock(return_value=normalized))

    with patch(
        "agent.anthropic_adapter.build_anthropic_kwargs",
        return_value={"model": "claude", "messages": [], "stream": False},
    ), patch(
        "agent.transports.get_transport",
        return_value=transport,
    ):
        result = _AnthropicCompletionsAdapter(client, "claude").create(model="claude")

    client.messages.create.assert_not_called()
    client.messages.stream.assert_called_once_with(model="claude", messages=[])
    transport.normalize_response.assert_called_once_with(
        final_message, strip_tool_prefix=False
    )
    assert result.choices[0].message.content == "streamed final"
    assert result.choices[0].finish_reason == "end_turn"
    assert result.usage.prompt_tokens == 11
    assert result.usage.completion_tokens == 7
    assert result.usage.total_tokens == 18
