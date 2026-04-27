"""Test that named provider + custom base_url resolves credentials from the
provider's pool (#16290).

When auxiliary.vision.provider is set to a named provider (e.g. ``zai``) with
a custom ``base_url``, the credential pool for that provider should be
consulted instead of falling back to the generic OPENAI_API_KEY pool.
"""

import pytest
from unittest.mock import patch, MagicMock


class TestResolveTaskProviderModelPreservesProviderWithBaseUrl:
    """_resolve_task_provider_model must preserve the named provider when
    both provider and base_url are set in config."""

    def test_provider_preserved_with_base_url(self):
        """When cfg_provider='zai' and cfg_base_url are both set, the
        returned provider should be 'zai', not 'custom'."""
        from agent.auxiliary_client import _resolve_task_provider_model

        config = {
            "auxiliary": {
                "vision": {
                    "provider": "zai",
                    "model": "glm-4v",
                    "base_url": "https://open.bigmodel.cn/api/paas/v4",
                    "api_key": "",
                }
            }
        }
        with patch("agent.auxiliary_client._get_auxiliary_task_config",
                   return_value=config["auxiliary"]["vision"]):
            provider, model, base_url, api_key, api_mode = _resolve_task_provider_model(
                "vision", None, None, None, None
            )

        assert provider == "zai", f"Expected 'zai', got '{provider}'"
        assert base_url == "https://open.bigmodel.cn/api/paas/v4"

    def test_custom_when_base_url_without_provider(self):
        """When only cfg_base_url is set (no provider), provider should be
        'custom'."""
        from agent.auxiliary_client import _resolve_task_provider_model

        config = {
            "auxiliary": {
                "vision": {
                    "base_url": "https://my-server.local/v1",
                }
            }
        }
        with patch("agent.auxiliary_client._get_auxiliary_task_config",
                   return_value=config["auxiliary"]["vision"]):
            provider, model, base_url, api_key, api_mode = _resolve_task_provider_model(
                "vision", None, None, None, None
            )

        assert provider == "custom"
        assert base_url == "https://my-server.local/v1"

    def test_auto_provider_not_preserved_with_base_url(self):
        """When cfg_provider='auto' and cfg_base_url are set, provider should
        be 'custom' (auto is not a real provider name)."""
        from agent.auxiliary_client import _resolve_task_provider_model

        config = {
            "auxiliary": {
                "vision": {
                    "provider": "auto",
                    "base_url": "https://my-server.local/v1",
                }
            }
        }
        with patch("agent.auxiliary_client._get_auxiliary_task_config",
                   return_value=config["auxiliary"]["vision"]):
            provider, model, base_url, api_key, api_mode = _resolve_task_provider_model(
                "vision", None, None, None, None
            )

        assert provider == "custom"


class TestResolveProviderApiKey:
    """_resolve_provider_api_key should look up the right env vars for a
    named provider."""

    def test_zai_key_resolved_from_env(self):
        """ZAI_API_KEY env var should be found for provider='zai'."""
        from agent.auxiliary_client import _resolve_provider_api_key

        with patch("hermes_cli.auth.resolve_api_key_provider_credentials",
                   return_value={"api_key": "zai-test-key-123", "base_url": "https://api.z.ai/api/paas/v4", "source": "env"}), \
             patch("hermes_cli.auth.PROVIDER_REGISTRY",
                   {"zai": MagicMock(auth_type="api_key")}):
            key = _resolve_provider_api_key("zai")
        assert key == "zai-test-key-123"

    def test_unknown_provider_returns_none(self):
        """Unknown provider should return None."""
        from agent.auxiliary_client import _resolve_provider_api_key

        with patch("hermes_cli.auth.PROVIDER_REGISTRY", {}):
            key = _resolve_provider_api_key("bogus-provider")
        assert key is None

    def test_provider_with_no_key_returns_none(self):
        """Provider whose credential pool has no key should return None."""
        from agent.auxiliary_client import _resolve_provider_api_key

        with patch("hermes_cli.auth.resolve_api_key_provider_credentials",
                   return_value={"api_key": "", "base_url": "https://...", "source": "none"}), \
             patch("hermes_cli.auth.PROVIDER_REGISTRY",
                   {"zai": MagicMock(auth_type="api_key")}):
            key = _resolve_provider_api_key("zai")
        assert key is None


class TestVisionClientWithNamedProviderAndBaseUrl:
    """resolve_vision_provider_client should consult the named provider's
    credential pool when base_url is also set."""

    def test_zai_with_base_url_uses_zai_credentials(self):
        """When provider='zai' + base_url is set, ZAI_API_KEY should be
        resolved and passed to the custom endpoint client."""
        from agent.auxiliary_client import resolve_vision_provider_client

        fake_client = MagicMock()
        fake_client.base_url = "https://open.bigmodel.cn/api/paas/v4"

        with (
            patch("agent.auxiliary_client._resolve_task_provider_model",
                  return_value=("zai", "glm-4v", "https://open.bigmodel.cn/api/paas/v4", None, None)),
            patch("agent.auxiliary_client._resolve_provider_api_key",
                  return_value="zai-env-key-456"),
            patch("agent.auxiliary_client.resolve_provider_client",
                  return_value=(fake_client, "glm-4v")) as mock_rpc,
        ):
            provider, client, model = resolve_vision_provider_client()

        # resolve_provider_client should be called with the zai-resolved key
        call_kwargs = mock_rpc.call_args.kwargs
        assert call_kwargs["explicit_api_key"] == "zai-env-key-456"
        assert call_kwargs["explicit_base_url"] == "https://open.bigmodel.cn/api/paas/v4"

    def test_custom_with_base_url_no_credential_lookup(self):
        """When provider='custom' + base_url is set, no credential pool
        lookup should happen (original behavior preserved)."""
        from agent.auxiliary_client import resolve_vision_provider_client

        fake_client = MagicMock()

        with (
            patch("agent.auxiliary_client._resolve_task_provider_model",
                  return_value=("custom", "my-model", "https://my-server.local/v1", "my-key", None)),
            patch("agent.auxiliary_client._resolve_provider_api_key") as mock_key,
            patch("agent.auxiliary_client.resolve_provider_client",
                  return_value=(fake_client, "my-model")),
        ):
            resolve_vision_provider_client()

        # _resolve_provider_api_key should NOT be called for "custom"
        mock_key.assert_not_called()
