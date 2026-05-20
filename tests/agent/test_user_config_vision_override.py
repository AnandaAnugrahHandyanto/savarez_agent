"""Tests for user-config vision override — the fallback path for custom providers.

Covers:
* ``get_user_config_vision_override`` — reads supports_vision from config.yaml
  provider entry when models.dev has no entry for the provider.
* ``_lookup_supports_vision`` — falls back to user config when models.dev
  returns None.
* ``decide_image_input_mode`` — resolves to "native" for a custom provider
  with supports_vision: true in config, even when models.dev is unaware.
* ``_model_supports_vision`` on AIAgent — same fallback via lazy load_config.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from agent.models_dev import get_user_config_vision_override
from agent.image_routing import _lookup_supports_vision, decide_image_input_mode


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CUSTOM_PROVIDER_CFG = {
    "providers": {
        "my-custom-provider": {
            "models": {
                "my-vision-model": {
                    "context_length": 128000,
                    "supports_vision": True,
                },
                "my-text-model": {
                    "context_length": 128000,
                    "supports_vision": False,
                },
                "my-model-no-flag": {
                    "context_length": 128000,
                },
            }
        }
    }
}


# ---------------------------------------------------------------------------
# get_user_config_vision_override
# ---------------------------------------------------------------------------


class TestGetUserConfigVisionOverride:
    def test_returns_true_when_set(self):
        result = get_user_config_vision_override(
            "my-custom-provider", "my-vision-model", CUSTOM_PROVIDER_CFG
        )
        assert result is True

    def test_returns_false_when_explicitly_false(self):
        result = get_user_config_vision_override(
            "my-custom-provider", "my-text-model", CUSTOM_PROVIDER_CFG
        )
        assert result is False

    def test_returns_none_when_flag_absent(self):
        result = get_user_config_vision_override(
            "my-custom-provider", "my-model-no-flag", CUSTOM_PROVIDER_CFG
        )
        assert result is None

    def test_returns_none_when_provider_missing(self):
        result = get_user_config_vision_override(
            "unknown-provider", "some-model", CUSTOM_PROVIDER_CFG
        )
        assert result is None

    def test_returns_none_when_model_missing(self):
        result = get_user_config_vision_override(
            "my-custom-provider", "nonexistent-model", CUSTOM_PROVIDER_CFG
        )
        assert result is None

    def test_returns_none_when_cfg_is_none(self):
        result = get_user_config_vision_override("my-custom-provider", "my-vision-model", None)
        assert result is None

    def test_returns_none_when_cfg_is_empty(self):
        result = get_user_config_vision_override("my-custom-provider", "my-vision-model", {})
        assert result is None

    def test_returns_none_when_provider_or_model_empty(self):
        assert get_user_config_vision_override("", "my-vision-model", CUSTOM_PROVIDER_CFG) is None
        assert get_user_config_vision_override("my-custom-provider", "", CUSTOM_PROVIDER_CFG) is None


# ---------------------------------------------------------------------------
# _lookup_supports_vision — user config fallback
# ---------------------------------------------------------------------------


class TestLookupSupportsVisionUserConfigFallback:
    """When models.dev returns None (unknown provider), fall back to user config."""

    def test_custom_provider_vision_true(self):
        with patch("agent.models_dev.get_model_capabilities", return_value=None):
            result = _lookup_supports_vision(
                "my-custom-provider", "my-vision-model", CUSTOM_PROVIDER_CFG
            )
        assert result is True

    def test_custom_provider_vision_false(self):
        with patch("agent.models_dev.get_model_capabilities", return_value=None):
            result = _lookup_supports_vision(
                "my-custom-provider", "my-text-model", CUSTOM_PROVIDER_CFG
            )
        assert result is False

    def test_custom_provider_no_flag_returns_none(self):
        with patch("agent.models_dev.get_model_capabilities", return_value=None):
            result = _lookup_supports_vision(
                "my-custom-provider", "my-model-no-flag", CUSTOM_PROVIDER_CFG
            )
        assert result is None

    def test_models_dev_result_takes_precedence(self):
        """If models.dev has an entry, user config is NOT consulted."""
        fake_caps = MagicMock()
        fake_caps.supports_vision = False  # models.dev says no vision
        with patch("agent.models_dev.get_model_capabilities", return_value=fake_caps):
            # Even though user config says True, models.dev wins
            result = _lookup_supports_vision(
                "my-custom-provider", "my-vision-model", CUSTOM_PROVIDER_CFG
            )
        assert result is False

    def test_no_cfg_returns_none_for_unknown_provider(self):
        with patch("agent.models_dev.get_model_capabilities", return_value=None):
            result = _lookup_supports_vision("my-custom-provider", "my-vision-model", None)
        assert result is None


# ---------------------------------------------------------------------------
# decide_image_input_mode — end-to-end for custom provider
# ---------------------------------------------------------------------------


class TestDecideImageInputModeCustomProvider:
    def test_auto_mode_custom_provider_vision_true_returns_native(self):
        cfg = {**CUSTOM_PROVIDER_CFG, "agent": {"image_input_mode": "auto"}}
        with patch("agent.models_dev.get_model_capabilities", return_value=None):
            mode = decide_image_input_mode("my-custom-provider", "my-vision-model", cfg)
        assert mode == "native"

    def test_auto_mode_custom_provider_vision_false_returns_text(self):
        cfg = {**CUSTOM_PROVIDER_CFG, "agent": {"image_input_mode": "auto"}}
        with patch("agent.models_dev.get_model_capabilities", return_value=None):
            mode = decide_image_input_mode("my-custom-provider", "my-text-model", cfg)
        assert mode == "text"

    def test_explicit_native_ignores_caps(self):
        cfg = {**CUSTOM_PROVIDER_CFG, "agent": {"image_input_mode": "native"}}
        with patch("agent.models_dev.get_model_capabilities", return_value=None):
            mode = decide_image_input_mode("my-custom-provider", "my-text-model", cfg)
        assert mode == "native"

    def test_explicit_text_ignores_caps(self):
        cfg = {**CUSTOM_PROVIDER_CFG, "agent": {"image_input_mode": "text"}}
        with patch("agent.models_dev.get_model_capabilities", return_value=None):
            mode = decide_image_input_mode("my-custom-provider", "my-vision-model", cfg)
        assert mode == "text"


# ---------------------------------------------------------------------------
# AIAgent._model_supports_vision — user config fallback via load_config
# ---------------------------------------------------------------------------


class TestAgentModelSupportsVisionUserConfigFallback:
    def _make_agent(self):
        from run_agent import AIAgent
        agent = object.__new__(AIAgent)
        agent.provider = "my-custom-provider"
        agent.model = "my-vision-model"
        agent._anthropic_image_fallback_cache = {}
        return agent

    def test_custom_provider_vision_true_via_config(self):
        agent = self._make_agent()
        with patch("agent.models_dev.get_model_capabilities", return_value=None), \
             patch("hermes_cli.config.load_config", return_value=CUSTOM_PROVIDER_CFG):
            assert agent._model_supports_vision() is True

    def test_custom_provider_vision_false_via_config(self):
        agent = self._make_agent()
        agent.model = "my-text-model"
        with patch("agent.models_dev.get_model_capabilities", return_value=None), \
             patch("hermes_cli.config.load_config", return_value=CUSTOM_PROVIDER_CFG):
            assert agent._model_supports_vision() is False

    def test_custom_provider_no_flag_returns_false(self):
        agent = self._make_agent()
        agent.model = "my-model-no-flag"
        with patch("agent.models_dev.get_model_capabilities", return_value=None), \
             patch("hermes_cli.config.load_config", return_value=CUSTOM_PROVIDER_CFG):
            assert agent._model_supports_vision() is False

    def test_load_config_failure_returns_false(self):
        agent = self._make_agent()
        with patch("agent.models_dev.get_model_capabilities", return_value=None), \
             patch("hermes_cli.config.load_config", side_effect=RuntimeError("no config")):
            assert agent._model_supports_vision() is False

    def test_none_caps_and_no_config_returns_false(self):
        agent = self._make_agent()
        with patch("agent.models_dev.get_model_capabilities", return_value=None), \
             patch("hermes_cli.config.load_config", return_value={}):
            assert agent._model_supports_vision() is False
