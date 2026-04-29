"""Tests for custom provider slug assignment in list_authenticated_providers."""

import os
from unittest.mock import patch

from hermes_cli.model_switch import list_authenticated_providers
from hermes_cli.providers import custom_provider_slug


class TestCustomProviderSlugAssignment:
    """When current_provider is the literal 'custom', it must not be used as a slug.

    Regression test for #17478: a prior failed switch writes ``provider: custom``
    to config.yaml.  On the next picker run, ``list_authenticated_providers()``
    assigns ``slug = 'custom'`` (the literal string) instead of the canonical
    ``custom:<name>`` slug, which causes ``resolve_provider_full('custom', ...)``
    to return None → ``Unknown provider 'custom'`` error.
    """

    CUSTOM_PROVIDERS = [
        {
            "name": "xiaomi-coding",
            "base_url": "https://token-plan-sgp.xiaomimimo.com/v1",
            "api_key": "sk-test123",
        }
    ]

    def _call_with_custom(self, current_provider: str, current_base_url: str = "") -> str:
        """Call list_authenticated_providers and extract the slug for our custom provider."""
        with (
            patch("agent.models_dev.fetch_models_dev", return_value={}),
            patch("os.getenv", return_value=""),
            patch("os.path.exists", return_value=False),
        ):
            results = list_authenticated_providers(
                current_provider=current_provider,
                current_base_url=current_base_url,
                custom_providers=self.CUSTOM_PROVIDERS,
            )

        # Find our custom provider entry
        for r in results:
            if "xiaomi" in r.get("name", "").lower():
                return r["slug"]
        return ""

    def test_when_current_provider_is_custom_literal_uses_canonical_slug(self):
        """current_provider='custom' should NOT produce slug='custom'."""
        slug = self._call_with_custom(
            current_provider="custom",
            current_base_url="https://token-plan-sgp.xiaomimimo.com/v1",
        )
        assert slug == "custom:xiaomi-coding", (
            f"Expected 'custom:xiaomi-coding', got '{slug}'"
        )

    def test_when_current_provider_is_empty_uses_canonical_slug(self):
        """Empty current_provider should fall through to custom_provider_slug."""
        slug = self._call_with_custom(
            current_provider="",
            current_base_url="https://token-plan-sgp.xiaomimimo.com/v1",
        )
        assert slug == "custom:xiaomi-coding"

    def test_when_base_url_does_not_match_uses_canonical_slug(self):
        """Non-matching base_url should always fall through to canonical slug."""
        slug = self._call_with_custom(
            current_provider="custom",
            current_base_url="https://some-other-url.com/v1",
        )
        assert slug == "custom:xiaomi-coding", (
            f"Expected fallback slug 'custom:xiaomi-coding', got '{slug}'"
        )

    def test_custom_provider_slug_format(self):
        """custom_provider_slug must produce 'custom:<lowercase-name>' format."""
        assert custom_provider_slug("xiaomi-coding") == "custom:xiaomi-coding"
        assert custom_provider_slug("My Provider") == "custom:my-provider"
