"""Tests for the interactive CLI /model picker (provider → model drill-down).

These tests verify the two new helper methods on HermesCLI:
- _interactive_provider_selection()
- _interactive_model_selection()
"""

from unittest.mock import MagicMock, patch, PropertyMock

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_providers():
    """Minimal provider list matching list_authenticated_providers output."""
    return [
        {
            "slug": "openrouter",
            "name": "OpenRouter",
            "is_current": False,
            "is_user_defined": False,
            "models": ["anthropic/claude-opus-4.6", "openai/gpt-5.4"],
            "total_models": 2,
            "source": "built-in",
        },
        {
            "slug": "anthropic",
            "name": "Anthropic",
            "is_current": True,
            "is_user_defined": False,
            "models": ["claude-opus-4.6", "claude-sonnet-4.6"],
            "total_models": 2,
            "source": "built-in",
        },
        {
            "slug": "custom:my-ollama",
            "name": "My Ollama",
            "is_current": False,
            "is_user_defined": True,
            "models": ["llama3", "mistral"],
            "total_models": 2,
            "source": "user-config",
            "api_url": "http://localhost:11434/v1",
        },
    ]


def _make_cli_mock(picker_return_value):
    """Create a MagicMock of HermesCLI with _run_curses_picker returning given value."""
    cli = MagicMock()
    cli._run_curses_picker = MagicMock(return_value=picker_return_value)
    cli._app = MagicMock()
    cli._status_bar_visible = True
    return cli


# ---------------------------------------------------------------------------
# Provider selection
# ---------------------------------------------------------------------------

def test_provider_selection_returns_slug_on_choice():
    """_run_curses_picker returns index → slug."""
    providers = _make_providers()
    cli = _make_cli_mock(1)
    from cli import HermesCLI

    result = HermesCLI._interactive_provider_selection(cli, providers, "gpt-5.4", "OpenRouter")
    assert result == "anthropic"
    cli._run_curses_picker.assert_called_once()


def test_provider_selection_returns_none_on_cancel():
    """_run_curses_picker returns None → cancel."""
    providers = _make_providers()
    cli = _make_cli_mock(None)
    from cli import HermesCLI

    result = HermesCLI._interactive_provider_selection(cli, providers, "gpt-5.4", "OpenRouter")
    assert result is None


def test_provider_selection_default_is_current():
    """Default index should be the current provider."""
    providers = _make_providers()
    cli = _make_cli_mock(0)
    from cli import HermesCLI

    HermesCLI._interactive_provider_selection(cli, providers, "gpt-5.4", "Anthropic")
    cli._run_curses_picker.assert_called_once()
    kwargs = cli._run_curses_picker.call_args
    assert kwargs[1]["default_index"] == 1  # Anthropic is index 1


# ---------------------------------------------------------------------------
# Model selection
# ---------------------------------------------------------------------------

def test_model_selection_returns_model_on_choice():
    """Select a model by index."""
    providers = _make_providers()
    provider_data = providers[0]
    cli = _make_cli_mock(0)
    from cli import HermesCLI

    result = HermesCLI._interactive_model_selection(cli, provider_data["models"], provider_data)
    assert result == "anthropic/claude-opus-4.6"


def test_model_selection_returns_none_on_cancel():
    """Cancel returns None."""
    providers = _make_providers()
    provider_data = providers[0]
    cli = _make_cli_mock(None)
    from cli import HermesCLI

    result = HermesCLI._interactive_model_selection(cli, provider_data["models"], provider_data)
    assert result is None


def test_model_selection_custom_entry():
    """Selecting 'Enter custom model name' prompts for input."""
    providers = _make_providers()
    provider_data = providers[0]
    cli = _make_cli_mock(2)  # index 2 = "Enter custom model name"
    cli._app = None  # skip run_in_terminal for test simplicity
    from cli import HermesCLI

    with patch("builtins.input", return_value="my-custom-model"):
        result = HermesCLI._interactive_model_selection(cli, provider_data["models"], provider_data)
    assert result == "my-custom-model"


def test_model_selection_empty_prompts_manual():
    """When model_list is empty, prompts for manual input."""
    provider_data = {
        "slug": "custom:empty",
        "name": "Empty Provider",
        "models": [],
        "total_models": 0,
    }
    cli = _make_cli_mock(None)
    from cli import HermesCLI

    with patch("builtins.input", return_value="my-model"):
        result = HermesCLI._interactive_model_selection(cli, [], provider_data)
    assert result == "my-model"


def test_model_selection_empty_cancel():
    """When model_list is empty and user enters nothing, returns None."""
    provider_data = {
        "slug": "custom:empty",
        "name": "Empty Provider",
        "models": [],
        "total_models": 0,
    }
    cli = _make_cli_mock(None)
    from cli import HermesCLI

    with patch("builtins.input", return_value=""):
        result = HermesCLI._interactive_model_selection(cli, [], provider_data)
    assert result is None
