"""Regression tests for token format validation in /model provider picker.

When GITHUB_TOKEN is set to a classic PAT (ghp_*), the Copilot provider
should NOT appear as authenticated in the /model picker, because classic
PATs are not supported by the Copilot API.

See: https://github.com/NousResearch/hermes-agent/issues/8826
"""

import os
from unittest.mock import patch, MagicMock

import pytest

from hermes_cli.model_switch import list_authenticated_providers


def _no_creds_pool():
    """Mock credential pool with no credentials."""
    m = MagicMock()
    m.has_credentials.return_value = False
    return m


def _empty_auth_store():
    """Mock auth store with no providers or pool entries."""
    return {"version": 1, "providers": {}, "credential_pool": {}}


# -- Classic PAT (ghp_*) should be rejected -----------------------------------

@patch("hermes_cli.auth._load_auth_store", _empty_auth_store)
@patch("agent.credential_pool.load_pool", return_value=_no_creds_pool())
@patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_abc123classicPAT"}, clear=False)
def test_copilot_classic_pat_not_shown(mock_pool):
    """Copilot with ghp_* token must NOT appear in provider list."""
    for ev in ("COPILOT_GITHUB_TOKEN", "GH_TOKEN"):
        os.environ.pop(ev, None)

    providers = list_authenticated_providers()
    copilot_entries = [p for p in providers if p.get("slug") == "copilot"]
    assert len(copilot_entries) == 0, (
        f"Copilot should NOT appear with classic PAT, but got: {copilot_entries}"
    )


@patch("hermes_cli.auth._load_auth_store", _empty_auth_store)
@patch("agent.credential_pool.load_pool", return_value=_no_creds_pool())
@patch.dict(
    os.environ,
    {"COPILOT_GITHUB_TOKEN": "ghp_classic", "GH_TOKEN": "ghp_also_classic"},
    clear=False,
)
def test_copilot_all_env_vars_classic_pat_not_shown(mock_pool):
    """Even when all three copilot env vars hold ghp_* tokens, hide the provider."""
    os.environ.pop("GITHUB_TOKEN", None)

    providers = list_authenticated_providers()
    copilot_entries = [p for p in providers if p.get("slug") == "copilot"]
    assert len(copilot_entries) == 0


# -- Valid tokens (gho_*, github_pat_*) should still work ---------------------

@patch.dict(os.environ, {"COPILOT_GITHUB_TOKEN": "gho_valid_oauth"}, clear=False)
def test_copilot_oauth_token_shown():
    """Copilot with gho_* token SHOULD appear in provider list."""
    for ev in ("GH_TOKEN", "GITHUB_TOKEN"):
        os.environ.pop(ev, None)

    providers = list_authenticated_providers(current_provider="copilot")
    copilot = next((p for p in providers if p.get("slug") == "copilot"), None)
    assert copilot is not None, "Copilot SHOULD appear with valid OAuth token"
    assert copilot["total_models"] > 0


@patch.dict(
    os.environ,
    {"GITHUB_TOKEN": "github_pat_fine_grained_token"},
    clear=False,
)
def test_copilot_fine_grained_pat_shown():
    """Copilot with github_pat_* token SHOULD appear in provider list."""
    for ev in ("COPILOT_GITHUB_TOKEN", "GH_TOKEN"):
        os.environ.pop(ev, None)

    providers = list_authenticated_providers(current_provider="copilot")
    copilot = next((p for p in providers if p.get("slug") == "copilot"), None)
    assert copilot is not None, "Copilot SHOULD appear with fine-grained PAT"


# -- Non-copilot providers unaffected -----------------------------------------

@patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test123"}, clear=False)
def test_non_copilot_provider_unaffected():
    """Non-copilot providers should not be affected by token validation."""
    for ev in ("GITHUB_TOKEN", "COPILOT_GITHUB_TOKEN", "GH_TOKEN"):
        os.environ.pop(ev, None)

    providers = list_authenticated_providers()
    assert isinstance(providers, list)


# -- Mixed: valid token in one env var overrides invalid in another -----------

@patch("hermes_cli.auth._load_auth_store", _empty_auth_store)
@patch("agent.credential_pool.load_pool", return_value=_no_creds_pool())
@patch.dict(
    os.environ,
    {"GITHUB_TOKEN": "ghp_invalid", "GH_TOKEN": "gho_valid"},
    clear=False,
)
def test_copilot_mixed_tokens_valid_wins(mock_pool):
    """If at least one env var has a valid token, copilot should appear."""
    os.environ.pop("COPILOT_GITHUB_TOKEN", None)

    providers = list_authenticated_providers(current_provider="copilot")
    copilot = next((p for p in providers if p.get("slug") == "copilot"), None)
    assert copilot is not None, (
        "Copilot SHOULD appear when at least one env var has a valid token"
    )
