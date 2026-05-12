"""Tests for GitHub Copilot entries shown in the /model picker."""

import os
from unittest.mock import patch

from hermes_cli.model_switch import list_authenticated_providers


@patch.dict(os.environ, {"GH_TOKEN": "test-key"}, clear=False)
def test_copilot_picker_keeps_curated_copilot_models_when_live_catalog_unavailable():
    with patch("agent.models_dev.fetch_models_dev", return_value={}), \
         patch("hermes_cli.models._resolve_copilot_catalog_api_key", return_value="gh-token"), \
         patch("hermes_cli.models._fetch_github_models", return_value=None):
        providers = list_authenticated_providers(current_provider="openrouter", max_models=50)

    copilot = next((p for p in providers if p["slug"] == "copilot"), None)

    assert copilot is not None
    assert "gpt-5.4" in copilot["models"]
    assert "claude-sonnet-4.6" in copilot["models"]
    assert "claude-sonnet-4" in copilot["models"]
    assert "claude-sonnet-4.5" in copilot["models"]
    assert "claude-haiku-4.5" in copilot["models"]
    assert "gemini-3.1-pro-preview" in copilot["models"]
    assert "claude-opus-4.6" not in copilot["models"]


@patch.dict(os.environ, {"GH_TOKEN": "test-key"}, clear=False)
def test_copilot_picker_uses_live_catalog_when_available():
    live_models = ["gpt-5.4", "claude-sonnet-4.6", "gemini-3.1-pro-preview"]

    with patch("agent.models_dev.fetch_models_dev", return_value={}), \
         patch("hermes_cli.models._resolve_copilot_catalog_api_key", return_value="gh-token"), \
         patch("hermes_cli.models._fetch_github_models", return_value=live_models):
        providers = list_authenticated_providers(current_provider="openrouter", max_models=50)

    copilot = next((p for p in providers if p["slug"] == "copilot"), None)

    assert copilot is not None
    assert copilot["models"] == live_models
    assert copilot["total_models"] == len(live_models)


@patch.dict(os.environ, {"GH_TOKEN": "test-key"}, clear=False)
def test_copilot_picker_uses_live_catalog_even_when_models_dev_has_github_copilot():
    """Regression: when models.dev exposes ``github-copilot``, the picker
    used to short-circuit in Section 1 and emit the curated list before
    Section 2's live ``provider_model_ids`` dispatch had a chance to run.

    The live catalog must win because (a) GitHub adds models faster than
    Hermes releases (e.g. ``claude-opus-4.7``, ``gpt-5.5``), and (b) the
    available models depend on the account's subscription tier.
    """
    # models.dev DOES include github-copilot in production. Mock its return
    # so credential detection in Section 1 still succeeds (would short-circuit
    # to the curated list under the bug).
    fake_models_dev = {
        "github-copilot": {
            "id": "github-copilot",
            "name": "GitHub Copilot",
            "env": ["GITHUB_TOKEN"],
        },
    }
    live_models = [
        "gpt-5.4",
        "gpt-5.5",
        "claude-opus-4.6",
        "claude-opus-4.7",
        "claude-sonnet-4.6",
    ]

    with patch("agent.models_dev.fetch_models_dev", return_value=fake_models_dev), \
         patch("hermes_cli.models._resolve_copilot_catalog_api_key", return_value="gh-token"), \
         patch("hermes_cli.models._fetch_github_models", return_value=live_models):
        providers = list_authenticated_providers(current_provider="openrouter", max_models=50)

    copilot = next((p for p in providers if p["slug"] == "copilot"), None)

    assert copilot is not None, "copilot must be in the picker when credentials are present"
    assert copilot["models"] == live_models, (
        f"expected live catalog, got curated/static list: {copilot['models']!r}"
    )
    assert copilot["total_models"] == len(live_models)
    # And no duplicate copilot entry should slip in from a later section.
    copilot_entries = [p for p in providers if p["slug"] == "copilot"]
    assert len(copilot_entries) == 1, f"got {len(copilot_entries)} copilot entries"
