"""Test that overlay providers with mismatched models.dev keys resolve correctly.

HERMES_OVERLAYS keys may be models.dev IDs (e.g. "github-copilot") while
_PROVIDER_MODELS and config.yaml use Hermes IDs ("copilot").  The slug
resolution in list_authenticated_providers() Section 2 must bridge this gap.

Covers: #5223, #6492
"""

import json
import os
from unittest.mock import patch

import pytest

from hermes_cli.model_switch import list_authenticated_providers


# -- Copilot slug resolution (env var path) ----------------------------------

@patch.dict(os.environ, {"COPILOT_GITHUB_TOKEN": "fake-ghu"}, clear=False)
def test_copilot_uses_hermes_slug():
    """github-copilot overlay should resolve to slug='copilot' with curated models."""
    providers = list_authenticated_providers(current_provider="copilot")

    copilot = next((p for p in providers if p["slug"] == "copilot"), None)
    assert copilot is not None, "copilot should appear when COPILOT_GITHUB_TOKEN is set"
    assert copilot["total_models"] > 0, "copilot should have curated models"
    assert copilot["is_current"] is True

    # Must NOT appear under the models.dev key
    gh_copilot = next((p for p in providers if p["slug"] == "github-copilot"), None)
    assert gh_copilot is None, "github-copilot slug should not appear (resolved to copilot)"


@patch.dict(os.environ, {"COPILOT_GITHUB_TOKEN": "fake-ghu"}, clear=False)
def test_copilot_no_duplicate_entries():
    """Copilot must appear only once — not as both 'copilot' (section 1) and 'github-copilot' (section 2)."""
    providers = list_authenticated_providers(current_provider="copilot")

    copilot_slugs = [p["slug"] for p in providers if "copilot" in p["slug"]]
    # Should have at most one copilot entry (may also have copilot-acp if creds exist)
    copilot_main = [s for s in copilot_slugs if s == "copilot"]
    assert len(copilot_main) == 1, f"Expected exactly one 'copilot' entry, got {copilot_main}"


# -- kimi-for-coding alias in auth.py ----------------------------------------

def test_kimi_for_coding_alias():
    """resolve_provider('kimi-for-coding') should return 'kimi-coding'."""
    from hermes_cli.auth import resolve_provider

    result = resolve_provider("kimi-for-coding")
    assert result == "kimi-coding"


# -- Generic slug mismatch providers -----------------------------------------

@patch.dict(os.environ, {"KIMI_API_KEY": "fake-key"}, clear=False)
def test_kimi_for_coding_overlay_uses_hermes_slug():
    """kimi-for-coding overlay should resolve to slug='kimi-coding'."""
    providers = list_authenticated_providers(current_provider="kimi-coding")

    kimi = next((p for p in providers if p["slug"] == "kimi-coding"), None)
    assert kimi is not None, "kimi-coding should appear when KIMI_API_KEY is set"
    assert kimi["is_current"] is True

    # Must NOT appear under the models.dev key
    kimi_mdev = next((p for p in providers if p["slug"] == "kimi-for-coding"), None)
    assert kimi_mdev is None, "kimi-for-coding slug should not appear (resolved to kimi-coding)"


@patch.dict(os.environ, {"KILOCODE_API_KEY": "fake-key"}, clear=False)
def test_kilo_overlay_uses_hermes_slug():
    """kilo overlay should resolve to slug='kilocode'."""
    providers = list_authenticated_providers(current_provider="kilocode")

    kilo = next((p for p in providers if p["slug"] == "kilocode"), None)
    assert kilo is not None, "kilocode should appear when KILOCODE_API_KEY is set"
    assert kilo["is_current"] is True

    kilo_mdev = next((p for p in providers if p["slug"] == "kilo"), None)
    assert kilo_mdev is None, "kilo slug should not appear (resolved to kilocode)"



def test_mapped_provider_credential_pool_visibility(monkeypatch):
    """Mapped providers should appear when credentials live only in auth-store credential_pool."""
    monkeypatch.setattr("agent.models_dev.fetch_models_dev", lambda: {"google-ai-studio": {"env": ["GEMINI_API_KEY"]}})
    monkeypatch.setattr("agent.models_dev.PROVIDER_TO_MODELS_DEV", {"gemini": "google-ai-studio"})
    monkeypatch.setattr(
        "hermes_cli.auth._load_auth_store",
        lambda: {"providers": {}, "credential_pool": {"gemini": {"token": "fake"}}},
    )
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    providers = list_authenticated_providers(current_provider="gemini")

    gemini = next((p for p in providers if p["slug"] == "gemini"), None)
    assert gemini is not None, "gemini should appear when auth-store credential_pool has creds"
    assert gemini["is_current"] is True
    assert gemini["total_models"] > 0


# -- opencode-go models.dev merge in HERMES_OVERLAYS section -----------------

def test_opencode_go_merge_key_uses_pid_when_hermes_slug_not_in_preferred():
    """The _mdev_to_hermes reversal maps "opencode-go" → "go", but
    _MODELS_DEV_PREFERRED uses "opencode-go". The merge must fall back to
    pid when hermes_slug is not in _MODELS_DEV_PREFERRED.

    Regression test for the bug where opencode-go models.dev entries were
    silently skipped in the TUI /model picker because the slug resolution
    produced "go" which isn't in _MODELS_DEV_PREFERRED.
    """
    from hermes_cli.models import _MODELS_DEV_PREFERRED, _merge_with_models_dev

    # Verify the root cause: "go" is NOT in _MODELS_DEV_PREFERRED
    assert "go" not in _MODELS_DEV_PREFERRED, "alias 'go' should not be in _MODELS_DEV_PREFERRED"
    # But "opencode-go" IS in _MODELS_DEV_PREFERRED
    assert "opencode-go" in _MODELS_DEV_PREFERRED, "canonical 'opencode-go' should be in _MODELS_DEV_PREFERRED"

    # The merge should work when using the correct key
    mdev = ["mimo-v2.5-pro", "mimo-v2-pro", "kimi-k2.6"]
    with patch("agent.models_dev.list_agentic_models", return_value=mdev):
        # Using "go" would fail to find models.dev entries
        # Using "opencode-go" should succeed
        out = _merge_with_models_dev("opencode-go", ["mimo-v2-pro", "kimi-k2.6"])
    assert "mimo-v2.5-pro" in out, "models.dev entry should appear when using correct merge key"


@patch.dict(os.environ, {"OPENCODE_GO_API_KEY": "test-key"}, clear=False)
def test_opencode_go_overlay_merges_models_dev_entries():
    """When opencode-go appears via HERMES_OVERLAYS (Section 2), its models
    list should include models.dev entries, not just the curated floor.
    """
    mdev = ["mimo-v2.5-pro", "mimo-v2-pro", "kimi-k2.6", "glm-5"]
    with patch("agent.models_dev.list_agentic_models", return_value=mdev):
        providers = list_authenticated_providers(current_provider="openrouter")

    opencode_go = next((p for p in providers if p["slug"] == "opencode-go"), None)
    assert opencode_go is not None, "opencode-go should appear in Section 2 when API key is set"

    # The models.dev entries should be present (not just curated floor)
    present = set(opencode_go["models"])
    assert "mimo-v2.5-pro" in present, (
        f"models.dev entry mimo-v2.5-pro should appear; got models: {opencode_go['models']}"
    )
