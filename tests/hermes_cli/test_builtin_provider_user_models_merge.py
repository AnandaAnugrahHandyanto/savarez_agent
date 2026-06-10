"""Tests for merging user-configured models into built-in providers.

Regression test for issue #43528: Desktop model picker ignores user-configured
models in providers.*.models. When a built-in provider (e.g. alibaba) has
custom models configured under providers.<name>.models in config.yaml, those
models should appear in the picker alongside the curated built-in list.
"""

import os
import pytest
from unittest.mock import patch, MagicMock


# =============================================================================
# Helpers
# =============================================================================

_FAKE_MODELS_DEV = {
    "alibaba-cloud": {
        "name": "Alibaba Cloud",
        "env": ["ALIBABA_API_KEY"],
    },
    "openai": {
        "name": "OpenAI",
        "env": ["OPENAI_API_KEY"],
    },
}

_FAKE_PROVIDER_TO_MODELS_DEV = {
    "alibaba": "alibaba-cloud",
    "openai": "openai",
}

_FAKE_PROVIDER_MODELS = {
    "alibaba": ["qwen-max", "qwen-plus", "qwen-turbo"],
    "openai": ["gpt-4o", "gpt-4o-mini"],
}


def _make_mock_registry():
    """Build a fake PROVIDER_REGISTRY where each provider has api_key_env_vars."""
    registry = {}
    for hermes_id, mdev_id in _FAKE_PROVIDER_TO_MODELS_DEV.items():
        mdev_data = _FAKE_MODELS_DEV.get(mdev_id, {})
        mock_cfg = MagicMock()
        mock_cfg.auth_type = "api_key"
        mock_cfg.api_key_env_vars = mdev_data.get("env", [])
        mock_cfg.base_url_env_var = f"{hermes_id.upper()}_BASE_URL"
        registry[hermes_id] = mock_cfg
    return registry


def _run_list_authenticated_providers(user_providers, **kwargs):
    """Run list_authenticated_providers with controlled mocks."""
    from hermes_cli.model_switch import list_authenticated_providers

    env = {"ALIBABA_API_KEY": "test-key-123"}
    env.update(kwargs.get("extra_env", {}))

    with (
        patch("agent.models_dev.fetch_models_dev", return_value=_FAKE_MODELS_DEV),
        patch("agent.models_dev.PROVIDER_TO_MODELS_DEV", _FAKE_PROVIDER_TO_MODELS_DEV),
        patch("hermes_cli.models._PROVIDER_MODELS", _FAKE_PROVIDER_MODELS),
        patch("hermes_cli.models.cached_provider_model_ids", return_value=[]),
        patch("hermes_cli.models._AGGREGATOR_PROVIDERS", set()),
        patch("hermes_cli.models._MODELS_DEV_PREFERRED", {}),
        patch("hermes_cli.models._merge_with_models_dev", lambda pid, m: m),
        patch("hermes_cli.models.OPENROUTER_MODELS", []),
        patch("hermes_cli.models.get_curated_nous_model_ids", return_value=[]),
        patch("hermes_cli.providers.HERMES_OVERLAYS", {}),
        patch("hermes_cli.providers.ALIASES", {}),
        patch("hermes_cli.auth.PROVIDER_REGISTRY", _make_mock_registry()),
        patch("hermes_cli.auth._load_auth_store", return_value={}),
        patch.dict(os.environ, env, clear=False),
    ):
        return list_authenticated_providers(
            current_provider=kwargs.get("current_provider", "alibaba"),
            user_providers=user_providers,
            custom_providers=kwargs.get("custom_providers", []),
            max_models=kwargs.get("max_models", 50),
        )


# =============================================================================
# Tests: user-configured models merged into built-in providers
# =============================================================================

class TestUserModelsMergeIntoBuiltIn:
    """When providers.*.models adds models to a built-in provider, they should
    appear in the picker alongside the curated list."""

    def test_custom_models_merged_into_builtin_provider(self):
        """User-configured models for a built-in provider are merged, not dropped."""
        user_providers = {
            "alibaba": {
                "name": "Alibaba Cloud",
                "models": {
                    "kimi-k2.6": {},
                    "glm-5.1": {},
                    "deepseek-v4-pro": {},
                },
            }
        }

        providers = _run_list_authenticated_providers(user_providers)

        # Find the alibaba provider
        ali = next(
            (p for p in providers if p["slug"] == "alibaba"),
            None,
        )
        assert ali is not None, "alibaba provider should be in results"

        # Curated models should still be present
        assert "qwen-max" in ali["models"]
        assert "qwen-plus" in ali["models"]
        assert "qwen-turbo" in ali["models"]

        # User-configured models should be merged in
        assert "kimi-k2.6" in ali["models"], "User model kimi-k2.6 should be merged"
        assert "glm-5.1" in ali["models"], "User model glm-5.1 should be merged"
        assert "deepseek-v4-pro" in ali["models"], "User model deepseek-v4-pro should be merged"

        # total_models should reflect the merged count
        assert ali["total_models"] == 6, f"Expected 6 models, got {ali['total_models']}"

        # Entry should be marked as user-defined since user customized it
        assert ali["is_user_defined"] is True

    def test_no_duplicate_models_on_merge(self):
        """When user configures a model already in curated list, don't duplicate."""
        user_providers = {
            "alibaba": {
                "models": {
                    "qwen-max": {},  # already in curated
                    "my-custom-model": {},
                },
            }
        }

        providers = _run_list_authenticated_providers(user_providers)

        ali = next(p for p in providers if p["slug"] == "alibaba")
        # qwen-max should appear exactly once
        assert ali["models"].count("qwen-max") == 1, "No duplicate qwen-max"
        assert "my-custom-model" in ali["models"]
        assert ali["total_models"] == 4  # 3 curated + 1 custom (qwen-max deduped)

    def test_user_providers_without_models_still_returns_builtin(self):
        """When user_providers has a built-in provider name but no models,
        the built-in entry from Section 1 is preserved."""
        user_providers = {
            "alibaba": {
                "name": "Alibaba Cloud",
                # No models key — user just set the name
            }
        }

        providers = _run_list_authenticated_providers(user_providers)

        ali = next(p for p in providers if p["slug"] == "alibaba")
        # Should still have curated models from Section 1
        assert "qwen-max" in ali["models"]
        # Should NOT be marked user-defined since no models were configured
        assert ali.get("is_user_defined") is False

    def test_non_builtin_user_provider_unaffected(self):
        """User providers that are NOT built-in should still work as before."""
        user_providers = {
            "my-custom-llm": {
                "name": "My Custom LLM",
                "api": "http://localhost:8080/v1",
                "models": ["model-a", "model-b"],
            }
        }

        providers = _run_list_authenticated_providers(
            user_providers,
            current_provider="my-custom-llm",
        )

        custom = next(
            (p for p in providers if p["slug"] == "my-custom-llm"),
            None,
        )
        assert custom is not None
        assert custom["is_user_defined"] is True
        assert "model-a" in custom["models"]
        assert "model-b" in custom["models"]

    def test_models_list_format_dict_keyed(self):
        """Models as dict keys (hermes format) are properly extracted."""
        user_providers = {
            "alibaba": {
                "models": {
                    "custom-v1": {"label": "Custom V1"},
                    "custom-v2": {"label": "Custom V2"},
                },
            }
        }

        providers = _run_list_authenticated_providers(user_providers)

        ali = next(p for p in providers if p["slug"] == "alibaba")
        assert "custom-v1" in ali["models"]
        assert "custom-v2" in ali["models"]

    def test_models_list_format_plain_list(self):
        """Models as plain list (legacy format) are properly extracted."""
        user_providers = {
            "alibaba": {
                "models": ["custom-v1", "custom-v2"],
            }
        }

        providers = _run_list_authenticated_providers(user_providers)

        ali = next(p for p in providers if p["slug"] == "alibaba")
        assert "custom-v1" in ali["models"]
        assert "custom-v2" in ali["models"]
