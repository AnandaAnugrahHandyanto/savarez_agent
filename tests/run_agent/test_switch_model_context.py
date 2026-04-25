"""Tests that switch_model preserves config_context_length."""

from unittest.mock import MagicMock, patch

from run_agent import AIAgent
from agent.context_compressor import ContextCompressor


def _make_agent_with_compressor(config_context_length=None) -> AIAgent:
    """Build a minimal AIAgent with a context_compressor, skipping __init__."""
    agent = AIAgent.__new__(AIAgent)

    # Primary model settings
    agent.model = "primary-model"
    agent.provider = "openrouter"
    agent.base_url = "https://openrouter.ai/api/v1"
    agent.api_key = "sk-primary"
    agent.api_mode = "chat_completions"
    agent.client = MagicMock()
    agent.quiet_mode = True

    # Store config_context_length for later use in switch_model
    agent._config_context_length = config_context_length

    # Context compressor with primary model values
    compressor = ContextCompressor(
        model="primary-model",
        threshold_percent=0.50,
        base_url="https://openrouter.ai/api/v1",
        api_key="sk-primary",
        provider="openrouter",
        quiet_mode=True,
        config_context_length=config_context_length,
    )
    agent.context_compressor = compressor

    # For switch_model
    agent._primary_runtime = {}

    return agent


@patch("agent.model_metadata.get_model_context_length", return_value=131_072)
def test_switch_model_uses_custom_provider_context_length(mock_ctx_len):
    """When switching to a model with a custom_providers entry, that entry's context_length
    must be passed to get_model_context_length — not the startup value from the old model."""
    agent = _make_agent_with_compressor(config_context_length=32_768)

    assert agent.context_compressor.model == "primary-model"
    assert agent.context_compressor.context_length == 32_768

    _custom_providers = [
        {
            "base_url": "https://openrouter.ai/api/v1",
            "models": {"new-model": {"context_length": 200_000}},
        }
    ]
    with patch(
        "hermes_cli.config.get_compatible_custom_providers",
        return_value=_custom_providers,
    ):
        agent.switch_model(
            "new-model", "openrouter", api_key="sk-new", base_url="https://openrouter.ai/api/v1"
        )

    mock_ctx_len.assert_called_once()
    call_kwargs = mock_ctx_len.call_args.kwargs
    assert call_kwargs.get("config_context_length") == 200_000

    assert agent.context_compressor.model == "new-model"


def test_switch_model_without_config_context_length():
    """When switching to a model with no custom_providers entry, config_context_length is None."""
    agent = _make_agent_with_compressor(config_context_length=None)

    with (
        patch("agent.model_metadata.get_model_context_length", return_value=128_000) as mock_ctx_len,
        patch("hermes_cli.config.get_compatible_custom_providers", return_value=[]),
    ):
        agent.switch_model("new-model", "openrouter", api_key="sk-new", base_url="https://openrouter.ai/api/v1")

        mock_ctx_len.assert_called_once()
        call_kwargs = mock_ctx_len.call_args.kwargs
        assert call_kwargs.get("config_context_length") is None


def test_switch_model_resets_stale_custom_provider_limit():
    """Switching away from a custom provider to one with no entry must reset to None.

    Old behavior (bug): the startup _config_context_length from provider A was
    carried over to provider B, potentially capping context at A's limit.
    """
    agent = _make_agent_with_compressor(config_context_length=500_000)

    with (
        patch("agent.model_metadata.get_model_context_length", return_value=128_000) as mock_ctx_len,
        patch("hermes_cli.config.get_compatible_custom_providers", return_value=[]),
    ):
        agent.switch_model(
            "new-model", "openrouter", api_key="sk-new", base_url="https://openrouter.ai/api/v1"
        )

    mock_ctx_len.assert_called_once()
    call_kwargs = mock_ctx_len.call_args.kwargs
    assert call_kwargs.get("config_context_length") is None
    assert agent._config_context_length is None
