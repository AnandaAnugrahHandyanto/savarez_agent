"""Regression tests for model switch context-length alignment.

Covers three layers fixed by the 2026-04-17 patch:
1. /model switch result should expose a unified display_context_length.
2. Runtime context override priority should prefer matching custom provider
   per-model context_length over global model.context_length.
3. AIAgent.switch_model() must refresh _config_context_length when a model is
   switched mid-session so the context engine gets the new override.
"""

from unittest.mock import MagicMock, patch

from hermes_cli.model_switch import switch_model


_MOCK_VALIDATION = {
    "accepted": True,
    "persist": True,
    "recognized": True,
    "message": None,
}


def test_switch_model_uses_custom_provider_context_for_display():
    """Custom provider per-model context_length should win for display metadata."""
    custom_providers = [
        {
            "name": "yunfeiplus",
            "base_url": "https://api.yunfeiplus.com/v1",
            "models": {
                "gpt-5.4": {
                    "context_length": 524288,
                }
            },
        }
    ]

    with (
        patch("hermes_cli.model_switch.resolve_alias", return_value=None),
        patch("hermes_cli.model_switch.list_provider_models", return_value=[]),
        patch(
            "hermes_cli.runtime_provider.resolve_runtime_provider",
            return_value={
                "api_key": "***",
                "base_url": "https://api.yunfeiplus.com/v1",
                "api_mode": "chat_completions",
            },
        ),
        patch("hermes_cli.models.validate_requested_model", return_value=_MOCK_VALIDATION),
        patch("hermes_cli.model_switch.get_model_info", return_value=None),
        patch("hermes_cli.model_switch.get_model_capabilities", return_value=None),
        patch("hermes_cli.models.detect_provider_for_model", return_value=None),
    ):
        result = switch_model(
            raw_input="gpt-5.4",
            current_provider="openrouter",
            current_model="glm-5",
            current_base_url="https://openrouter.ai/api/v1",
            current_api_key="***",
            explicit_provider="yunfeiplus",
            custom_providers=custom_providers,
        )

    assert result.success, result.error_message
    assert result.target_provider == "custom:yunfeiplus"
    assert result.display_context_length == 524288


def test_runtime_context_prefers_custom_provider_override_over_global_default():
    """Runtime context lookup should prefer matching custom provider override."""
    from run_agent import _resolve_runtime_config_context_length

    agent_cfg = {
        "model": {"context_length": 200000},
        "custom_providers": [
            {
                "name": "yunfeiplus",
                "base_url": "https://api.yunfeiplus.com/v1",
                "models": {
                    "gpt-5.4": {"context_length": 524288},
                },
            }
        ],
    }

    resolved = _resolve_runtime_config_context_length(
        model="gpt-5.4",
        provider="custom:yunfeiplus",
        base_url="https://api.yunfeiplus.com/v1",
        agent_cfg=agent_cfg,
    )

    assert resolved == 524288


def test_runtime_context_falls_back_to_global_default_when_no_matching_custom_provider():
    """Global model.context_length should still apply when no custom override matches."""
    from run_agent import _resolve_runtime_config_context_length

    agent_cfg = {
        "model": {"context_length": 200000},
        "custom_providers": [
            {
                "name": "yunfeiplus",
                "base_url": "https://api.yunfeiplus.com/v1",
                "models": {
                    "gpt-5.4": {"context_length": 524288},
                },
            }
        ],
    }

    resolved = _resolve_runtime_config_context_length(
        model="gpt-5.4",
        provider="openrouter",
        base_url="https://openrouter.ai/api/v1",
        agent_cfg=agent_cfg,
    )

    assert resolved == 200000


def test_runtime_context_ignores_non_positive_global_override():
    """Non-positive global overrides should be treated as unset."""
    from run_agent import _resolve_runtime_config_context_length

    agent_cfg = {
        "model": {"context_length": -1},
        "custom_providers": [],
    }

    resolved = _resolve_runtime_config_context_length(
        model="gpt-5.4",
        provider="openrouter",
        base_url="https://openrouter.ai/api/v1",
        agent_cfg=agent_cfg,
    )

    assert resolved is None


def test_runtime_context_does_not_apply_name_collision_to_builtin_provider():
    """Custom provider names colliding with built-ins must not hijack built-in provider context."""
    from run_agent import _resolve_runtime_config_context_length

    agent_cfg = {
        "model": {"context_length": 200000},
        "custom_providers": [
            {
                "name": "anthropic",
                "base_url": "https://custom.example/v1",
                "models": {
                    "claude-sonnet-4-5": {"context_length": 777777},
                },
            }
        ],
    }

    resolved = _resolve_runtime_config_context_length(
        model="claude-sonnet-4-5",
        provider="anthropic",
        base_url="https://api.anthropic.com",
        agent_cfg=agent_cfg,
    )

    assert resolved == 200000


def test_switch_model_uses_global_config_context_for_display_when_no_custom_override():
    """Display context should align with global model.context_length fallback."""
    with (
        patch("hermes_cli.model_switch.resolve_alias", return_value=None),
        patch("hermes_cli.model_switch.list_provider_models", return_value=[]),
        patch(
            "hermes_cli.runtime_provider.resolve_runtime_provider",
            return_value={
                "api_key": "***",
                "base_url": "https://openrouter.ai/api/v1",
                "api_mode": "chat_completions",
            },
        ),
        patch("hermes_cli.models.validate_requested_model", return_value=_MOCK_VALIDATION),
        patch("hermes_cli.model_switch.get_model_info", return_value=None),
        patch("hermes_cli.model_switch.get_model_capabilities", return_value=None),
        patch("hermes_cli.models.detect_provider_for_model", return_value=None),
    ):
        result = switch_model(
            raw_input="gpt-5.4",
            current_provider="openrouter",
            current_model="glm-5",
            current_base_url="https://openrouter.ai/api/v1",
            current_api_key="***",
            config_context_length=200000,
        )

    assert result.success, result.error_message
    assert result.target_provider == "openrouter"
    assert result.display_context_length == 200000


def test_switch_model_ignores_non_positive_global_display_override():
    """Display context should ignore invalid non-positive global overrides."""
    with (
        patch("hermes_cli.model_switch.resolve_alias", return_value=None),
        patch("hermes_cli.model_switch.list_provider_models", return_value=[]),
        patch(
            "hermes_cli.runtime_provider.resolve_runtime_provider",
            return_value={
                "api_key": "***",
                "base_url": "https://openrouter.ai/api/v1",
                "api_mode": "chat_completions",
            },
        ),
        patch("hermes_cli.models.validate_requested_model", return_value=_MOCK_VALIDATION),
        patch("hermes_cli.model_switch.get_model_info", return_value=None),
        patch("hermes_cli.model_switch.get_model_capabilities", return_value=None),
        patch("hermes_cli.models.detect_provider_for_model", return_value=None),
        patch("agent.model_metadata.get_model_context_length", return_value=128000),
    ):
        result = switch_model(
            raw_input="gpt-5.4",
            current_provider="openrouter",
            current_model="glm-5",
            current_base_url="https://openrouter.ai/api/v1",
            current_api_key="***",
            config_context_length=-1,
        )

    assert result.success, result.error_message
    assert result.display_context_length == 128000


def test_switch_model_does_not_apply_name_collision_to_builtin_provider_display():
    """Display resolver must not treat built-in provider slug collisions as custom matches."""
    with (
        patch("hermes_cli.model_switch.resolve_alias", return_value=None),
        patch("hermes_cli.model_switch.list_provider_models", return_value=[]),
        patch(
            "hermes_cli.runtime_provider.resolve_runtime_provider",
            return_value={
                "api_key": "***",
                "base_url": "https://api.anthropic.com",
                "api_mode": "anthropic_messages",
            },
        ),
        patch("hermes_cli.models.validate_requested_model", return_value=_MOCK_VALIDATION),
        patch("hermes_cli.model_switch.get_model_info", return_value=None),
        patch("hermes_cli.model_switch.get_model_capabilities", return_value=None),
        patch("hermes_cli.models.detect_provider_for_model", return_value=None),
    ):
        result = switch_model(
            raw_input="claude-sonnet-4-5",
            current_provider="anthropic",
            current_model="claude-3-5-sonnet",
            current_base_url="https://api.anthropic.com",
            current_api_key="***",
            custom_providers=[
                {
                    "name": "anthropic",
                    "base_url": "https://custom.example/v1",
                    "models": {
                        "claude-sonnet-4-5": {"context_length": 777777},
                    },
                }
            ],
            config_context_length=200000,
        )

    assert result.success, result.error_message
    assert result.display_context_length == 200000


def test_agent_switch_model_preserves_existing_context_override_when_config_reload_fails():
    """Switch should keep the active override if config reload temporarily fails."""
    from run_agent import AIAgent

    agent = AIAgent.__new__(AIAgent)
    agent.model = "glm-5"
    agent.provider = "openrouter"
    agent.base_url = "https://openrouter.ai/api/v1"
    agent.api_key = "***"
    agent.api_mode = "chat_completions"
    agent._client_kwargs = {}
    agent._cached_system_prompt = None
    agent._use_prompt_caching = False
    agent._config_context_length = 200000
    agent.context_compressor = MagicMock()
    agent._create_openai_client = MagicMock(return_value=object())

    def _fake_get_model_context_length(
        model,
        *,
        base_url,
        api_key,
        provider,
        config_context_length=None,
    ):
        return config_context_length

    with (
        patch("hermes_cli.config.load_config", side_effect=RuntimeError("boom")),
        patch(
            "agent.model_metadata.get_model_context_length",
            side_effect=_fake_get_model_context_length,
        ),
    ):
        agent.switch_model(
            new_model="gpt-5.4",
            new_provider="custom:yunfeiplus",
            api_key="***",
            base_url="https://api.yunfeiplus.com/v1",
            api_mode="chat_completions",
        )

    assert agent._config_context_length == 200000
    _, kwargs = agent.context_compressor.update_model.call_args
    assert kwargs["context_length"] == 200000


def test_agent_switch_model_refreshes_context_override_before_updating_context_engine():
    """Mid-session switch should refresh _config_context_length for the new model."""
    from run_agent import AIAgent

    agent = AIAgent.__new__(AIAgent)
    agent.model = "glm-5"
    agent.provider = "openrouter"
    agent.base_url = "https://openrouter.ai/api/v1"
    agent.api_key = "***"
    agent.api_mode = "chat_completions"
    agent._client_kwargs = {}
    agent._cached_system_prompt = None
    agent._use_prompt_caching = False
    agent._config_context_length = 200000
    agent.context_compressor = MagicMock()
    agent.context_compressor.context_length = 524288
    agent.context_compressor.threshold_tokens = 393216
    agent.context_compressor.model = "gpt-5.4"
    agent.context_compressor.base_url = "https://api.yunfeiplus.com/v1"
    agent.context_compressor.api_key = "***"
    agent.context_compressor.provider = "custom:yunfeiplus"
    agent._create_openai_client = MagicMock(return_value=object())

    cfg = {
        "model": {"context_length": 200000},
        "custom_providers": [
            {
                "name": "yunfeiplus",
                "base_url": "https://api.yunfeiplus.com/v1",
                "models": {
                    "gpt-5.4": {"context_length": 524288},
                },
            }
        ],
    }

    def _fake_get_model_context_length(
        model,
        *,
        base_url,
        api_key,
        provider,
        config_context_length=None,
    ):
        return config_context_length

    with (
        patch("hermes_cli.config.load_config", return_value=cfg),
        patch(
            "agent.model_metadata.get_model_context_length",
            side_effect=_fake_get_model_context_length,
        ),
    ):
        agent.switch_model(
            new_model="gpt-5.4",
            new_provider="custom:yunfeiplus",
            api_key="***",
            base_url="https://api.yunfeiplus.com/v1",
            api_mode="chat_completions",
        )

    assert agent._config_context_length == 524288
    agent.context_compressor.update_model.assert_called_once()
    _, kwargs = agent.context_compressor.update_model.call_args
    assert kwargs["context_length"] == 524288
