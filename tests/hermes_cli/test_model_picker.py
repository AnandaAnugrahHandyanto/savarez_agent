"""Tests for hermes_cli.model_picker module."""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock


class TestProviderOrder:
    """Tests for PROVIDER_ORDER consistency."""

    def test_provider_order_matches_config(self):
        """PROVIDER_ORDER should match model_picker_config.py."""
        from hermes_cli import model_picker
        from hermes_cli import model_picker_config

        # model_picker should start with the same items as model_picker_config defaults
        default_order = model_picker_config._DEFAULT_PROVIDER_ORDER
        assert model_picker.PROVIDER_ORDER[: len(default_order)] == default_order


class TestGetProviderList:
    """Tests for get_provider_list function."""

    def test_returns_providers_with_current_marked(self):
        """Should mark the current provider."""
        with patch(
            "hermes_cli.models._PROVIDER_LABELS",
            {
                "anthropic": "Anthropic",
                "openrouter": "OpenRouter",
            },
        ):
            from hermes_cli.model_picker import get_provider_list, ProviderOption

            providers = get_provider_list("anthropic")
            current_providers = [p for p in providers if p.is_current]

            assert len(current_providers) == 1
            assert current_providers[0].id == "anthropic"
            assert current_providers[0].label == "Anthropic"

    def test_current_provider_first_in_list(self):
        """Current provider should appear first."""
        with patch(
            "hermes_cli.models._PROVIDER_LABELS",
            {
                "anthropic": "Anthropic",
                "openrouter": "OpenRouter",
            },
        ):
            from hermes_cli.model_picker import get_provider_list

            providers = get_provider_list("anthropic")
            assert providers[0].id == "anthropic"


class TestGetModelList:
    """Tests for get_model_list function."""

    def test_returns_models_for_provider(self):
        """Should return models for the specified provider."""
        with patch(
            "hermes_cli.models._PROVIDER_MODELS",
            {
                "anthropic": ["claude-opus-4-6", "claude-sonnet-4-6"],
                "openrouter": ["gpt-5.4"],
            },
        ):
            from hermes_cli.model_picker import get_model_list

            models = get_model_list("anthropic")
            assert len(models) == 2
            assert models[0].id == "claude-opus-4-6"

    def test_marks_current_model(self):
        """Should mark the current model."""
        with patch(
            "hermes_cli.models._PROVIDER_MODELS",
            {
                "anthropic": ["claude-opus-4-6", "claude-sonnet-4-6"],
            },
        ):
            from hermes_cli.model_picker import get_model_list

            models = get_model_list("anthropic", current_model="claude-sonnet-4-6")
            current_models = [m for m in models if m.is_current]

            assert len(current_models) == 1
            assert current_models[0].id == "claude-sonnet-4-6"


class TestFormatProviderSelection:
    """Tests for format_provider_selection function."""

    def test_formats_for_discord(self):
        """Should format with numbers for Discord."""
        from hermes_cli.model_picker import format_provider_selection, ProviderOption

        providers = [
            ProviderOption(id="anthropic", label="Anthropic", is_current=True),
            ProviderOption(id="openrouter", label="OpenRouter", is_current=False),
        ]

        result = format_provider_selection(providers, "discord")

        assert "**Select provider:**" in result
        assert "1. Anthropic *(current)*" in result
        assert "2. OpenRouter" in result

    def test_formats_for_cli(self):
        """Should format with markers for CLI."""
        from hermes_cli.model_picker import format_provider_selection, ProviderOption

        providers = [
            ProviderOption(id="anthropic", label="Anthropic", is_current=True),
            ProviderOption(id="openrouter", label="OpenRouter", is_current=False),
        ]

        result = format_provider_selection(providers, "cli")

        assert "-> Anthropic *(current)*" in result
        assert "   OpenRouter" in result


class TestFormatModelSelection:
    """Tests for format_model_selection function."""

    def test_formats_for_discord(self):
        """Should format with numbers for Discord."""
        from hermes_cli.model_picker import format_model_selection, ModelOption

        models = [
            ModelOption(id="claude-opus-4-6", label="claude-opus-4-6", is_current=True),
            ModelOption(
                id="claude-sonnet-4-6", label="claude-sonnet-4-6", is_current=False
            ),
        ]

        result = format_model_selection("anthropic", "Anthropic", models, "discord")

        assert "**Models for Anthropic:**" in result
        assert "1. claude-opus-4-6 (current)" in result
        assert "2. claude-sonnet-4-6" in result
