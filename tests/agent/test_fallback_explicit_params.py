"""Tests that the fallback provider chain passes explicit base_url and api_key to resolve_provider_client.

This prevents the fallback from accidentally routing through a misconfigured local proxy
(e.g., Crosby's OpenRouter instance) instead of the intended fallback endpoint.
"""
from unittest.mock import MagicMock, patch

from run_agent import AIAgent


def _make_agent_with_fallback(fb_model=None) -> AIAgent:
    """Build a minimal AIAgent configured for fallback testing."""
    agent = AIAgent.__new__(AIAgent)
    agent.model = "primary-model"
    agent.provider = "openrouter"
    agent.base_url = "https://openrouter.ai/api/v1"
    agent.api_key = "sk-primary"
    agent.api_mode = "chat_completions"
    agent.client = MagicMock()
    agent.quiet_mode = True
    agent._fallback_activated = False
    agent._fallback_model = fb_model or {
        "provider": "openrouter",
        "model": "qwen3.6-plus-preview:free",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": "sk-or-v1-fb-key",
    }
    agent._fallback_chain = [agent._fallback_model]
    agent._fallback_index = 0
    agent._is_direct_openai_url = lambda url: False
    agent._emit_status = lambda msg: None
    return agent


@patch("agent.auxiliary_client.resolve_provider_client")
@patch("agent.model_metadata.get_model_context_length", return_value=128_000)
def test_fallback_passes_explicit_base_url_and_api_key(mock_ctx_len, mock_resolve):
    """Fallback activation must pass explicit base_url and api_key to resolve_provider_client.

    Without these parameters, resolve_provider_client falls back to ambient env vars
    (OPENAI_BASE_URL, OPENROUTER_API_KEY, etc.), which may point at an offline or
    unauthorized local proxy. The fallback chain defines its own endpoint and credentials
    and those must be honored.
    """
    agent = _make_agent_with_fallback(
        fb_model={
            "provider": "openrouter",
            "model": "qwen3.6-plus-preview:free",
            "base_url": "https://openrouter.ai/api/v1",
            "api_key": "sk-or-v1-explicit-fb-key",
        }
    )

    fb_client = MagicMock()
    fb_client.base_url = "https://openrouter.ai/api/v1"
    fb_client.api_key = "sk-or-v1-explicit-fb-key"
    mock_resolve.return_value = (fb_client, "qwen3.6-plus-preview:free")

    result = agent._try_activate_fallback()

    assert result is True
    mock_resolve.assert_called_once()
    call_kwargs = mock_resolve.call_args.kwargs
    assert call_kwargs["explicit_base_url"] == "https://openrouter.ai/api/v1"
    assert call_kwargs["explicit_api_key"] == "sk-or-v1-explicit-fb-key"
    assert call_kwargs["model"] == "qwen3.6-plus-preview:free"
    assert call_kwargs["raw_codex"] is True


@patch("agent.auxiliary_client.resolve_provider_client")
@patch("agent.model_metadata.get_model_context_length", return_value=128_000)
def test_fallback_with_no_base_url_still_works(mock_ctx_len, mock_resolve):
    """Fallback entries without explicit base_url/api_key should still resolve cleanly."""
    agent = _make_agent_with_fallback(
        fb_model={
            "provider": "openrouter",
            "model": "qwen3.6-plus-preview:free",
        }
    )

    fb_client = MagicMock()
    fb_client.base_url = "https://openrouter.ai/api/v1"
    fb_client.api_key = "sk-or-v1"
    mock_resolve.return_value = (fb_client, "qwen3.6-plus-preview:free")

    result = agent._try_activate_fallback()

    assert result is True
    call_kwargs = mock_resolve.call_args.kwargs
    assert call_kwargs["explicit_base_url"] is None
    assert call_kwargs["explicit_api_key"] is None
