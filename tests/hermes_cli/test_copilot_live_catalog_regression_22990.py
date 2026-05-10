"""
Regression tests for Copilot live catalog in /model picker (issue #22990).

The /model picker previously showed a static 17-model list for Copilot,
ignoring the live GitHub Copilot catalog which varies by user tier
(Pro/Business/Enterprise) and current rollout.
"""

import json
from unittest.mock import patch, MagicMock

import pytest


class TestCopilotLiveCatalogInPicker:
    """Tests that list_authenticated_providers uses live catalog for Copilot."""

    @patch("hermes_cli.model_switch.provider_model_ids")
    @patch("hermes_cli.model_switch.PROVIDER_TO_MODELS_DEV")
    @patch("hermes_cli.model_switch.PROVIDER_REGISTRY")
    def test_copilot_uses_live_catalog(
        self,
        mock_registry,
        mock_mdev_map,
        mock_provider_model_ids,
    ):
        """Copilot should call provider_model_ids() for live catalog."""
        from hermes_cli.model_switch import list_authenticated_providers

        # Setup mocks
        mock_mdev_map.items.return_value = [("copilot", "github-copilot")]
        mock_registry.get.return_value = MagicMock(
            auth_type="api_key",
            api_key_env_vars=["GITHUB_TOKEN"],
        )
        mock_provider_model_ids.return_value = [
            "gpt-5.5", "gpt-5.2", "claude-opus-4.7",
        ]

        with patch.dict("os.environ", {"GITHUB_TOKEN": "test-token"}):
            providers = list_authenticated_providers()

        copilot = next((p for p in providers if p["slug"] == "copilot"), None)
        assert copilot is not None, "Copilot provider not found"
        assert copilot["total_models"] == 3
        assert "gpt-5.5" in copilot["models"]
        assert "claude-opus-4.7" in copilot["models"]
        mock_provider_model_ids.assert_called_once_with("copilot")

    @patch("hermes_cli.model_switch.provider_model_ids")
    @patch("hermes_cli.model_switch.PROVIDER_TO_MODELS_DEV")
    @patch("hermes_cli.model_switch.PROVIDER_REGISTRY")
    def test_copilot_acp_uses_live_catalog(
        self,
        mock_registry,
        mock_mdev_map,
        mock_provider_model_ids,
    ):
        """Copilot-acp should also call provider_model_ids()."""
        from hermes_cli.model_switch import list_authenticated_providers

        mock_mdev_map.items.return_value = [("copilot-acp", "github-copilot-acp")]
        mock_registry.get.return_value = MagicMock(
            auth_type="api_key",
            api_key_env_vars=["GITHUB_TOKEN"],
        )
        mock_provider_model_ids.return_value = ["gpt-5.5"]

        with patch.dict("os.environ", {"GITHUB_TOKEN": "test-token"}):
            providers = list_authenticated_providers()

        copilot_acp = next((p for p in providers if p["slug"] == "copilot-acp"), None)
        assert copilot_acp is not None
        mock_provider_model_ids.assert_called_once_with("copilot-acp")

    @patch("hermes_cli.model_switch.provider_model_ids")
    @patch("hermes_cli.model_switch.PROVIDER_TO_MODELS_DEV")
    @patch("hermes_cli.model_switch.PROVIDER_REGISTRY")
    def test_copilot_fallback_to_static_on_network_error(
        self,
        mock_registry,
        mock_mdev_map,
        mock_provider_model_ids,
    ):
        """When live catalog fails, should fall back to static list."""
        from hermes_cli.model_switch import list_authenticated_providers

        mock_mdev_map.items.return_value = [("copilot", "github-copilot")]
        mock_registry.get.return_value = MagicMock(
            auth_type="api_key",
            api_key_env_vars=["GITHUB_TOKEN"],
        )
        # Simulate network failure → fallback to static list
        mock_provider_model_ids.return_value = [
            "gpt-4o", "gpt-4o-mini", "claude-3.5-sonnet",
        ]

        with patch.dict("os.environ", {"GITHUB_TOKEN": "test-token"}):
            providers = list_authenticated_providers()

        copilot = next((p for p in providers if p["slug"] == "copilot"), None)
        assert copilot is not None
        assert copilot["total_models"] == 3

    @patch("hermes_cli.model_switch.provider_model_ids")
    @patch("hermes_cli.model_switch.PROVIDER_TO_MODELS_DEV")
    @patch("hermes_cli.model_switch.PROVIDER_REGISTRY")
    def test_other_providers_still_use_static_list(
        self,
        mock_registry,
        mock_mdev_map,
        mock_provider_model_ids,
    ):
        """Non-Copilot providers should still use the static curated list."""
        from hermes_cli.model_switch import list_authenticated_providers

        mock_mdev_map.items.return_value = [("openrouter", "openrouter")]
        mock_registry.get.return_value = MagicMock(
            auth_type="api_key",
            api_key_env_vars=["OPENROUTER_API_KEY"],
        )

        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}):
            providers = list_authenticated_providers()

        openrouter = next((p for p in providers if p["slug"] == "openrouter"), None)
        assert openrouter is not None
        # Should NOT call provider_model_ids for non-Copilot
        mock_provider_model_ids.assert_not_called()


if __name__ == "__main__":
    import sys

    test_class = TestCopilotLiveCatalogInPicker()
    methods = [m for m in dir(test_class) if m.startswith("test_")]
    passed = 0
    failed = 0

    for method_name in methods:
        try:
            getattr(test_class, method_name)()
            print(f"✓ {method_name}")
            passed += 1
        except Exception as e:
            print(f"✗ {method_name}: {e}")
            failed += 1

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
