"""Regression tests for the empty credential pool bug (#28140).

Before the fix, an empty `auth.json` credential_pool entry (e.g.
``"minimax-cn": []``) left over after the user deleted their API-key env
var still caused the provider to appear authenticated in the `/model`
picker, because the check was a presence check on the dict key — not on
the array contents.

The fix lives in ``hermes_cli/model_switch.py::list_authenticated_providers``
inside the env-var fallback that consults the auth store.
"""

from unittest.mock import patch

import pytest

from hermes_cli.model_switch import list_authenticated_providers


# Models.dev mapping must include a provider that uses an env-var auth
# type (so we hit the fallback branch).  minimax-cn is the canonical
# example from the bug report.
_FAKE_MODELS_DEV = {
    "minimax-cn": {
        "id": "minimax-cn",
        "name": "MiniMax CN",
        "env": ["MINIMAX_CN_API_KEY"],
        "models": {
            "minimax-m2.7": {"id": "minimax-m2.7", "name": "MiniMax M2.7"},
        },
    },
}


def _isolate_env_and_overlays(monkeypatch):
    """Strip the test environment down to a clean slate.

    - Remove MINIMAX env vars so the fallback path is exercised.
    - Mock models.dev so the test needs no network.
    - Restrict PROVIDER_TO_MODELS_DEV to only minimax-cn so the loop is
      single-pass and predictable.
    """
    for key in ("MINIMAX_API_KEY", "MINIMAX_CN_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr("agent.models_dev.fetch_models_dev", lambda: _FAKE_MODELS_DEV)
    # PROVIDER_TO_MODELS_DEV lives on agent.models_dev and is imported into
    # model_switch via `from agent.models_dev import PROVIDER_TO_MODELS_DEV`
    # — the imported binding refers to the same dict object, so patching the
    # source module is enough.
    monkeypatch.setattr(
        "agent.models_dev.PROVIDER_TO_MODELS_DEV",
        {"minimax-cn": "minimax-cn"},
    )
    monkeypatch.setattr("hermes_cli.providers.HERMES_OVERLAYS", {})


def test_empty_credential_pool_does_not_authenticate_provider(monkeypatch):
    """Reproduces #28140: an empty pool array must not count as credentials."""
    _isolate_env_and_overlays(monkeypatch)

    # Simulate the leftover empty array: user deleted MINIMAX_CN_API_KEY
    # from .env but auth.json still has "minimax-cn": [] from earlier setup.
    with patch(
        "hermes_cli.auth._load_auth_store",
        return_value={"credential_pool": {"minimax-cn": []}},
    ):
        providers = list_authenticated_providers()

    slugs = [p.get("slug") for p in providers]
    assert "minimax-cn" not in slugs, (
        "Empty credential pool entry must not authenticate the provider — "
        "this is the #28140 regression."
    )


def test_populated_credential_pool_does_authenticate_provider(monkeypatch):
    """Sanity check: a real pool entry MUST still authenticate."""
    _isolate_env_and_overlays(monkeypatch)

    fake_entry = {"key": "test-key-value", "label": "test"}
    with patch(
        "hermes_cli.auth._load_auth_store",
        return_value={"credential_pool": {"minimax-cn": [fake_entry]}},
    ):
        providers = list_authenticated_providers()

    slugs = [p.get("slug") for p in providers]
    assert "minimax-cn" in slugs, (
        "A non-empty credential pool entry must still authenticate the provider — "
        "do not over-correct #28140."
    )


def test_missing_credential_pool_key_does_not_authenticate_provider(monkeypatch):
    """No env var, no pool entry at all → provider must be hidden."""
    _isolate_env_and_overlays(monkeypatch)

    with patch(
        "hermes_cli.auth._load_auth_store",
        return_value={"credential_pool": {}},
    ):
        providers = list_authenticated_providers()

    slugs = [p.get("slug") for p in providers]
    assert "minimax-cn" not in slugs


def test_env_var_still_authenticates_even_with_empty_pool(monkeypatch):
    """If the env var IS set, the pool state is irrelevant — provider shows up."""
    _isolate_env_and_overlays(monkeypatch)
    monkeypatch.setenv("MINIMAX_CN_API_KEY", "real-key-from-env")

    with patch(
        "hermes_cli.auth._load_auth_store",
        return_value={"credential_pool": {"minimax-cn": []}},
    ):
        providers = list_authenticated_providers()

    slugs = [p.get("slug") for p in providers]
    assert "minimax-cn" in slugs, (
        "Env-var auth must take precedence over auth-store state."
    )
