"""Tests for runtime context_length overrides in AIAgent."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from agent.context_compressor import ContextCompressor
from run_agent import AIAgent


CUSTOM_BASE_URL = "http://localhost:4000/v1"


def _make_agent_with_compressor(
    config_context_length=None,
    agent_config=None,
    model="primary-model",
    provider="openrouter",
    base_url="https://openrouter.ai/api/v1",
) -> AIAgent:
    """Build a minimal AIAgent with a context_compressor, skipping __init__."""
    agent = AIAgent.__new__(AIAgent)

    agent.model = model
    agent.provider = provider
    agent.base_url = base_url
    agent.api_key = "sk-primary"
    agent.api_mode = "chat_completions"
    agent.client = MagicMock()
    agent.quiet_mode = True
    agent._agent_config = agent_config or {}
    agent._config_context_length = config_context_length
    agent._client_kwargs = {}
    agent._use_prompt_caching = False
    agent._cached_system_prompt = None
    agent._create_openai_client = MagicMock(return_value=MagicMock())

    compressor = ContextCompressor(
        model=model,
        threshold_percent=0.50,
        base_url=base_url,
        api_key="sk-primary",
        provider=provider,
        quiet_mode=True,
        config_context_length=config_context_length,
    )
    agent.context_compressor = compressor
    agent._primary_runtime = {}

    return agent


@patch("run_agent.AIAgent._check_compression_model_feasibility")
@patch("run_agent.ContextCompressor")
@patch("run_agent.get_tool_definitions", return_value=[])
@patch("run_agent.check_toolset_requirements", return_value={})
@patch("run_agent.AIAgent._create_openai_client", return_value=MagicMock())
@patch("hermes_cli.config.load_config")
def test_init_stores_custom_provider_context_override(
    mock_load_config,
    _mock_create_client,
    _mock_requirements,
    _mock_get_tools,
    mock_context_compressor,
    _mock_feasibility,
):
    """__init__ should store and pass the custom_providers per-model override."""
    mock_load_config.return_value = {
        "model": {
            "default": "gpt-5.4",
            "provider": "custom",
            "base_url": CUSTOM_BASE_URL,
        },
        "compression": {"enabled": False},
        "custom_providers": [
            {
                "base_url": CUSTOM_BASE_URL,
                "models": {
                    "gpt-5.4": {"context_length": 500_000},
                },
            }
        ],
    }

    fake_compressor = MagicMock()
    fake_compressor.context_length = 500_000
    fake_compressor.threshold_tokens = 250_000
    fake_compressor.get_tool_schemas.return_value = []
    mock_context_compressor.return_value = fake_compressor

    agent = AIAgent(
        model="gpt-5.4",
        provider="custom",
        base_url=CUSTOM_BASE_URL,
        api_key="sk-test",
        quiet_mode=True,
        skip_memory=True,
    )

    assert agent._config_context_length == 500_000
    assert mock_context_compressor.call_args.kwargs["config_context_length"] == 500_000


@patch("agent.model_metadata.get_model_context_length", return_value=262_144)
def test_switch_model_refreshes_context_override_from_agent_config(mock_ctx_len):
    """switch_model() should resolve the new runtime's config override before lookup."""
    agent = _make_agent_with_compressor(
        config_context_length=128_000,
        agent_config={
            "custom_providers": [
                {
                    "base_url": CUSTOM_BASE_URL,
                    "models": {
                        "new-model": {"context_length": 262_144},
                    },
                }
            ]
        },
        provider="custom",
        base_url=CUSTOM_BASE_URL,
    )

    agent.switch_model(
        "new-model",
        "custom",
        api_key="sk-new",
        base_url=CUSTOM_BASE_URL,
        api_mode="chat_completions",
    )

    mock_ctx_len.assert_called_once()
    call_kwargs = mock_ctx_len.call_args.kwargs
    assert call_kwargs["config_context_length"] == 262_144
    assert agent._config_context_length == 262_144
    assert agent.context_compressor.model == "new-model"


@patch("agent.model_metadata.get_model_context_length", return_value=64_000)
def test_switch_model_clears_context_override_when_new_model_has_none(mock_ctx_len):
    """switch_model() should clear stale overrides when the new model has none."""
    agent = _make_agent_with_compressor(
        config_context_length=128_000,
        agent_config={
            "custom_providers": [
                {
                    "base_url": CUSTOM_BASE_URL,
                    "models": {
                        "primary-model": {"context_length": 128_000},
                    },
                }
            ]
        },
        provider="custom",
        base_url=CUSTOM_BASE_URL,
    )

    agent.switch_model(
        "model-without-override",
        "custom",
        api_key="sk-new",
        base_url=CUSTOM_BASE_URL,
        api_mode="chat_completions",
    )

    mock_ctx_len.assert_called_once()
    call_kwargs = mock_ctx_len.call_args.kwargs
    assert call_kwargs["config_context_length"] is None
    assert agent._config_context_length is None
    assert agent.context_compressor.model == "model-without-override"


@patch("agent.model_metadata.get_model_context_length", return_value=262_144)
@patch("agent.auxiliary_client.resolve_provider_client")
def test_fallback_refreshes_context_override_from_agent_config(
    mock_resolve_provider_client,
    mock_ctx_len,
):
    """Fallback activation should reuse the shared override resolver."""
    agent = _make_agent_with_compressor(
        config_context_length=128_000,
        agent_config={
            "custom_providers": [
                {
                    "base_url": CUSTOM_BASE_URL,
                    "models": {
                        "fallback-model": {"context_length": 262_144},
                    },
                }
            ]
        },
        provider="custom",
        base_url=CUSTOM_BASE_URL,
    )
    agent._fallback_chain = [
        {
            "provider": "custom",
            "model": "fallback-model",
            "base_url": CUSTOM_BASE_URL,
            "api_key": "sk-fallback",
        }
    ]
    agent._fallback_index = 0
    agent._fallback_activated = False
    agent._emit_status = MagicMock()

    fallback_client = MagicMock()
    fallback_client.api_key = "sk-fallback"
    fallback_client.base_url = CUSTOM_BASE_URL
    mock_resolve_provider_client.return_value = (fallback_client, "fallback-model")

    assert agent._try_activate_fallback() is True

    mock_ctx_len.assert_called_once()
    call_kwargs = mock_ctx_len.call_args.kwargs
    assert call_kwargs["config_context_length"] == 262_144
    assert agent._config_context_length == 262_144
    assert agent.context_compressor.model == "fallback-model"


@patch("agent.model_metadata.get_model_context_length", return_value=500_000)
@patch("agent.auxiliary_client.get_text_auxiliary_client")
def test_compression_feasibility_uses_context_override_for_aux_model(
    mock_get_aux_client,
    mock_ctx_len,
):
    """Compression feasibility should reuse the same override resolution logic."""
    agent = AIAgent.__new__(AIAgent)
    agent.model = "gpt-5.4"
    agent.base_url = CUSTOM_BASE_URL
    agent.api_key = "sk-main"
    agent.api_mode = "chat_completions"
    agent.provider = "custom"
    agent.compression_enabled = True
    agent.context_compressor = SimpleNamespace(
        threshold_tokens=250_000,
        context_length=500_000,
    )
    agent._agent_config = {
        "custom_providers": [
            {
                "base_url": CUSTOM_BASE_URL,
                "models": {
                    "gpt-5.4": {"context_length": 500_000},
                },
            }
        ]
    }
    agent._compression_warning = None
    agent._emit_status = MagicMock()
    agent._current_main_runtime = MagicMock(
        return_value={
            "model": "gpt-5.4",
            "provider": "custom",
            "base_url": CUSTOM_BASE_URL,
            "api_key": "sk-main",
            "api_mode": "chat_completions",
        }
    )

    mock_get_aux_client.return_value = (
        SimpleNamespace(base_url=CUSTOM_BASE_URL, api_key="sk-aux"),
        "gpt-5.4",
    )

    agent._check_compression_model_feasibility()

    mock_ctx_len.assert_called_once()
    call_kwargs = mock_ctx_len.call_args.kwargs
    assert call_kwargs["config_context_length"] == 500_000
    agent._emit_status.assert_not_called()
    assert agent._compression_warning is None
