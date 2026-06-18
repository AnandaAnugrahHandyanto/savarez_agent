"""Regression tests for keeping the active model visible in picker rows."""

from unittest.mock import patch

from hermes_cli.model_switch import list_authenticated_providers


def test_nous_picker_keeps_current_model_when_catalog_lags(monkeypatch):
    """If the current Nous model is newer than the curated catalog, keep it
    selectable in the current provider row."""
    current_model = "qwen/qwen3-235b-a22b-2507"

    with patch("agent.models_dev.fetch_models_dev", return_value={}), \
         patch(
             "hermes_cli.auth._load_auth_store",
             return_value={"providers": {"nous": {}}},
         ), \
         patch(
             "hermes_cli.models.get_curated_nous_model_ids",
             return_value=["anthropic/claude-opus-4.7"],
         ), \
         patch("hermes_cli.models.get_pricing_for_provider", return_value={}), \
         patch("hermes_cli.models.check_nous_free_tier", return_value=False), \
         patch(
             "hermes_cli.models.union_with_portal_paid_recommendations",
             side_effect=lambda models, pricing, portal: (models, []),
         ):
        providers = list_authenticated_providers(
            current_provider="nous",
            current_model=current_model,
            max_models=50,
        )

    nous = next((p for p in providers if p["slug"] == "nous"), None)
    assert nous is not None
    assert nous["is_current"] is True
    assert nous["models"][0] == current_model
    assert "anthropic/claude-opus-4.7" in nous["models"]
    assert nous["total_models"] == 2
