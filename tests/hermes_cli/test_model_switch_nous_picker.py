"""Regression tests for Nous Portal model rows in /model pickers."""

from unittest.mock import patch

import hermes_cli.models as models_mod
import hermes_cli.providers as providers_mod
from hermes_cli.model_switch import list_authenticated_providers
from hermes_cli.models import ProviderEntry


_PAID = {"prompt": "0.000003", "completion": "0.000015"}
_FREE = {"prompt": "0", "completion": "0"}


def _list_only_nous(monkeypatch, *, free_tier: bool):
    """Return the authenticated Nous row with external catalogs/auth patched."""
    original_overlays = providers_mod.HERMES_OVERLAYS
    monkeypatch.setattr(
        providers_mod,
        "HERMES_OVERLAYS",
        {"nous": original_overlays["nous"]},
    )
    monkeypatch.setattr(
        models_mod,
        "CANONICAL_PROVIDERS",
        [ProviderEntry("nous", "Nous Portal", "Nous Portal")],
    )

    recommended_payload = {
        "freeRecommendedModels": [
            {"modelName": "deepseek/deepseek-v4-flash:free"},
        ],
        "paidRecommendedModels": [
            {"modelName": "openai/gpt-5.5"},
        ],
    }
    curated_models = [
        "anthropic/claude-opus-4.7",
        "stepfun/step-3.5-flash",
    ]
    pricing = {
        "anthropic/claude-opus-4.7": _PAID,
        "stepfun/step-3.5-flash": _FREE,
    }

    with patch("agent.models_dev.fetch_models_dev", return_value={}), \
         patch(
             "hermes_cli.auth._load_auth_store",
             return_value={"providers": {"nous": {"access_token": "tok"}}},
         ), \
         patch("hermes_cli.models.get_curated_nous_model_ids", return_value=curated_models), \
         patch("hermes_cli.models.get_pricing_for_provider", return_value=pricing), \
         patch("hermes_cli.models.check_nous_free_tier", return_value=free_tier), \
         patch("hermes_cli.models.fetch_nous_recommended_models", return_value=recommended_payload):
        rows = list_authenticated_providers(max_models=20)

    nous_rows = [row for row in rows if row["slug"] == "nous"]
    assert len(nous_rows) == 1
    return nous_rows[0]


def test_nous_picker_free_tier_unions_portal_free_models_and_hides_paid(monkeypatch):
    """Free-tier /model row uses Portal free recommendations, not stale curated-only data."""
    row = _list_only_nous(monkeypatch, free_tier=True)

    assert row["models"] == [
        "deepseek/deepseek-v4-flash:free",
        "stepfun/step-3.5-flash",
    ]
    assert row["total_models"] == 2
    assert "anthropic/claude-opus-4.7" not in row["models"]


def test_nous_picker_paid_tier_unions_portal_paid_models(monkeypatch):
    """Paid-tier /model row surfaces newly recommended Portal paid models too."""
    row = _list_only_nous(monkeypatch, free_tier=False)

    assert row["models"][:3] == [
        "openai/gpt-5.5",
        "anthropic/claude-opus-4.7",
        "stepfun/step-3.5-flash",
    ]
    assert row["total_models"] == 3
