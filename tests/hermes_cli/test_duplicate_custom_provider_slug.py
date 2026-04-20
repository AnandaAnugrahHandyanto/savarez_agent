"""Regression tests for duplicate custom provider entries (issue #12293).

Section 3 (user_providers) and Section 4 (custom_providers) used different
slug formats when tracking duplicates. Section 3 added the plain key
(e.g. "modal-direct") while Section 4 generated a "custom:"-prefixed slug
(e.g. "custom:modal-direct"), causing the same provider to appear twice.

The _section3_emitted_pairs dedup provides a partial workaround when both
name and base_url match, but the seen_slugs check is the authoritative
defense — and it was broken because of the slug format mismatch.
"""

import hermes_cli.providers as providers_mod
from hermes_cli.model_switch import list_authenticated_providers


def _no_external_calls(monkeypatch):
    """Monkeypatch external API calls for isolation."""
    monkeypatch.setattr("agent.models_dev.fetch_models_dev", lambda: {})
    monkeypatch.setattr(providers_mod, "HERMES_OVERLAYS", {})


class TestDuplicateCustomProviderSlug:
    """Verify that the same provider in user_providers and custom_providers
    produces only one entry in the /model list."""

    def test_no_duplicate_when_base_url_missing_from_user_providers(self, monkeypatch):
        """When user_providers entry has no base_url, _section3_emitted_pairs
        can't catch the duplicate (pair requires both name and url).
        Only the seen_slugs slug-based check prevents the duplicate.

        This is the core regression test for issue #12293.
        Without the fix, Section 4 generates custom:-prefixed slug which
        doesn't match the plain slug Section 3 added.
        """
        _no_external_calls(monkeypatch)

        providers = list_authenticated_providers(
            current_provider="openrouter",
            user_providers={
                "modal-direct": {
                    "name": "Modal Direct",
                    # No base_url — _section3_emitted_pairs won't capture this
                    "model": "llama3",
                },
            },
            custom_providers=[
                {
                    "name": "Modal Direct",
                    "base_url": "https://api.us-west-2.modal.direct/v1",
                    "model": "qwen3",
                },
            ],
            max_models=50,
        )

        modal_rows = [p for p in providers if p["name"] == "Modal Direct"]
        assert len(modal_rows) == 1, (
            f"Expected 1 Modal Direct row, got {len(modal_rows)}: "
            f"{[r['slug'] for r in modal_rows]}"
        )

    def test_matching_name_and_url_no_duplicate(self, monkeypatch):
        """When user_providers and custom_providers share the same
        display name and base URL, only one picker row should appear."""
        _no_external_calls(monkeypatch)

        providers = list_authenticated_providers(
            current_provider="openrouter",
            user_providers={
                "modal-direct": {
                    "name": "Modal Direct",
                    "base_url": "https://api.us-west-2.modal.direct/v1",
                    "model": "llama3",
                },
            },
            custom_providers=[
                {
                    "name": "Modal Direct",
                    "base_url": "https://api.us-west-2.modal.direct/v1",
                    "model": "qwen3",
                },
            ],
            max_models=50,
        )

        modal_rows = [p for p in providers if p["name"] == "Modal Direct"]
        assert len(modal_rows) == 1, (
            f"Expected 1 Modal Direct row, got {len(modal_rows)}: "
            f"{[r['slug'] for r in modal_rows]}"
        )

    def test_distinct_providers_both_appear(self, monkeypatch):
        """When user_providers and custom_providers have genuinely different
        providers, both should appear."""
        _no_external_calls(monkeypatch)

        providers = list_authenticated_providers(
            current_provider="openrouter",
            user_providers={
                "my-local": {
                    "name": "My Local",
                    "base_url": "http://localhost:1234/v1",
                    "model": "llama3",
                },
            },
            custom_providers=[
                {
                    "name": "Cloud Provider",
                    "base_url": "https://api.mistral.ai/v1",
                    "model": "mistral-large",
                },
            ],
            max_models=50,
        )

        names = [p["name"] for p in providers]
        assert "My Local" in names
        assert "Cloud Provider" in names
        assert len(providers) == 2

    def test_custom_providers_only_still_works(self, monkeypatch):
        """When only custom_providers is passed (no user_providers),
        entries should still appear normally."""
        _no_external_calls(monkeypatch)

        providers = list_authenticated_providers(
            current_provider="openrouter",
            user_providers={},
            custom_providers=[
                {
                    "name": "Standalone",
                    "base_url": "https://api.standalone.example/v1",
                    "model": "model-a",
                },
            ],
            max_models=50,
        )

        names = [p["name"] for p in providers]
        assert "Standalone" in names

    def test_user_providers_only_still_works(self, monkeypatch):
        """When only user_providers is passed (no custom_providers),
        entries should still appear normally."""
        _no_external_calls(monkeypatch)

        providers = list_authenticated_providers(
            current_provider="openrouter",
            user_providers={
                "my-provider": {
                    "name": "My Provider",
                    "base_url": "https://api.my-provider.example/v1",
                    "model": "model-a",
                },
            },
            custom_providers=None,
            max_models=50,
        )

        names = [p["name"] for p in providers]
        assert "My Provider" in names
