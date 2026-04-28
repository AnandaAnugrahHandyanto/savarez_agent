"""Tests for named custom provider and 'main' alias resolution in auxiliary_client."""

import os
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    """Redirect HERMES_HOME and clear module caches."""
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    # Write a minimal config so load_config doesn't fail
    (hermes_home / "config.yaml").write_text("model:\n  default: test-model\n")


def _write_config(tmp_path, config_dict):
    """Write a config.yaml to the test HERMES_HOME."""
    import yaml
    config_path = tmp_path / ".hermes" / "config.yaml"
    config_path.write_text(yaml.dump(config_dict))


class TestNormalizeVisionProvider:
    """_normalize_vision_provider should resolve 'main' to actual main provider."""

    def test_main_resolves_to_named_custom(self, tmp_path):
        _write_config(tmp_path, {
            "model": {"default": "my-model", "provider": "custom:beans"},
            "custom_providers": [{"name": "beans", "base_url": "http://localhost/v1"}],
        })
        from agent.auxiliary_client import _normalize_vision_provider
        assert _normalize_vision_provider("main") == "custom:beans"

    def test_main_resolves_to_openrouter(self, tmp_path):
        _write_config(tmp_path, {
            "model": {"default": "anthropic/claude-sonnet-4", "provider": "openrouter"},
        })
        from agent.auxiliary_client import _normalize_vision_provider
        assert _normalize_vision_provider("main") == "openrouter"

    def test_main_resolves_to_deepseek(self, tmp_path):
        _write_config(tmp_path, {
            "model": {"default": "deepseek-chat", "provider": "deepseek"},
        })
        from agent.auxiliary_client import _normalize_vision_provider
        assert _normalize_vision_provider("main") == "deepseek"

    def test_main_falls_back_to_custom_when_no_provider(self, tmp_path):
        _write_config(tmp_path, {"model": {"default": "gpt-4o"}})
        from agent.auxiliary_client import _normalize_vision_provider
        assert _normalize_vision_provider("main") == "custom"

    def test_bare_provider_name_unchanged(self):
        from agent.auxiliary_client import _normalize_vision_provider
        assert _normalize_vision_provider("beans") == "beans"
        assert _normalize_vision_provider("deepseek") == "deepseek"

    def test_custom_colon_named_provider_preserved(self):
        from agent.auxiliary_client import _normalize_vision_provider
        assert _normalize_vision_provider("custom:beans") == "beans"

    def test_codex_alias_still_works(self):
        from agent.auxiliary_client import _normalize_vision_provider
        assert _normalize_vision_provider("codex") == "openai-codex"

    def test_auto_unchanged(self):
        from agent.auxiliary_client import _normalize_vision_provider
        assert _normalize_vision_provider("auto") == "auto"
        assert _normalize_vision_provider(None) == "auto"


class TestResolveProviderClientMainAlias:
    """resolve_provider_client('main', ...) should resolve to actual main provider."""

    def test_main_resolves_to_named_custom_provider(self, tmp_path):
        _write_config(tmp_path, {
            "model": {"default": "my-model", "provider": "beans"},
            "custom_providers": [
                {"name": "beans", "base_url": "http://beans.local/v1", "api_key": "k"},
            ],
        })
        from agent.auxiliary_client import resolve_provider_client
        client, model = resolve_provider_client("main", "override-model")
        assert client is not None
        assert model == "override-model"
        assert "beans.local" in str(client.base_url)

    def test_main_with_custom_colon_prefix(self, tmp_path):
        _write_config(tmp_path, {
            "model": {"default": "my-model", "provider": "custom:beans"},
            "custom_providers": [
                {"name": "beans", "base_url": "http://beans.local/v1", "api_key": "k"},
            ],
        })
        from agent.auxiliary_client import resolve_provider_client
        client, model = resolve_provider_client("main", "test")
        assert client is not None
        assert "beans.local" in str(client.base_url)

    def test_main_resolves_github_copilot_alias(self, tmp_path):
        _write_config(tmp_path, {
            "model": {"default": "gpt-5.4", "provider": "github-copilot"},
        })
        with (
            patch("hermes_cli.auth.resolve_api_key_provider_credentials", return_value={
                "api_key": "ghu_test_token",
                "base_url": "https://api.githubcopilot.com",
            }),
            patch("agent.auxiliary_client.OpenAI") as mock_openai,
        ):
            mock_openai.return_value = MagicMock()
            from agent.auxiliary_client import resolve_provider_client

            client, model = resolve_provider_client("main", "gpt-5.4")

        assert client is not None
        assert model == "gpt-5.4"
        assert mock_openai.called


class TestResolveProviderClientNamedCustom:
    """resolve_provider_client should resolve named custom providers directly."""

    def test_named_custom_provider(self, tmp_path):
        _write_config(tmp_path, {
            "model": {"default": "test-model"},
            "custom_providers": [
                {"name": "beans", "base_url": "http://beans.local/v1", "api_key": "k"},
            ],
        })
        from agent.auxiliary_client import resolve_provider_client
        client, model = resolve_provider_client("beans", "my-model")
        assert client is not None
        assert model == "my-model"
        assert "beans.local" in str(client.base_url)

    def test_named_custom_provider_default_model(self, tmp_path):
        _write_config(tmp_path, {
            "model": {"default": "main-model"},
            "custom_providers": [
                {"name": "beans", "base_url": "http://beans.local/v1", "api_key": "k"},
            ],
        })
        from agent.auxiliary_client import resolve_provider_client
        client, model = resolve_provider_client("beans")
        assert client is not None
        # Should use _read_main_model() fallback
        assert model == "main-model"

    def test_named_custom_no_api_key_uses_fallback(self, tmp_path):
        _write_config(tmp_path, {
            "model": {"default": "test"},
            "custom_providers": [
                {"name": "local", "base_url": "http://localhost:8080/v1"},
            ],
        })
        from agent.auxiliary_client import resolve_provider_client
        client, model = resolve_provider_client("local", "test")
        assert client is not None
        # no-key-required should be used

    def test_nonexistent_named_custom_falls_through(self, tmp_path):
        _write_config(tmp_path, {
            "model": {"default": "test"},
            "custom_providers": [
                {"name": "beans", "base_url": "http://beans.local/v1"},
            ],
        })
        from agent.auxiliary_client import resolve_provider_client
        # "coffee" doesn't exist in custom_providers
        client, model = resolve_provider_client("coffee", "test")
        assert client is None


class TestResolveProviderClientModelNormalization:
    """Direct-provider auxiliary routing should normalize models like main runtime."""

    def test_matching_native_prefix_is_stripped_for_main_provider(self, tmp_path):
        _write_config(tmp_path, {
            "model": {"default": "zai/glm-5.1", "provider": "zai"},
        })
        with (
            patch("hermes_cli.auth.resolve_api_key_provider_credentials", return_value={
                "api_key": "glm-key",
                "base_url": "https://api.z.ai/api/paas/v4",
            }),
            patch("agent.auxiliary_client.OpenAI") as mock_openai,
        ):
            mock_openai.return_value = MagicMock()
            from agent.auxiliary_client import resolve_provider_client

            client, model = resolve_provider_client("main", "zai/glm-5.1")

        assert client is not None
        assert model == "glm-5.1"

    def test_non_matching_prefix_is_preserved_for_direct_provider(self, tmp_path):
        _write_config(tmp_path, {
            "model": {"default": "zai/glm-5.1", "provider": "zai"},
        })
        with (
            patch("hermes_cli.auth.resolve_api_key_provider_credentials", return_value={
                "api_key": "glm-key",
                "base_url": "https://api.z.ai/api/paas/v4",
            }),
            patch("agent.auxiliary_client.OpenAI") as mock_openai,
        ):
            mock_openai.return_value = MagicMock()
            from agent.auxiliary_client import resolve_provider_client

            client, model = resolve_provider_client("zai", "google/gemini-2.5-pro")

        assert client is not None
        assert model == "google/gemini-2.5-pro"

    def test_aggregator_vendor_slug_is_preserved(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
        with patch("agent.auxiliary_client.OpenAI") as mock_openai:
            mock_openai.return_value = MagicMock()
            from agent.auxiliary_client import resolve_provider_client

            client, model = resolve_provider_client(
                "openrouter", "anthropic/claude-sonnet-4.6"
            )

        assert client is not None
        assert model == "anthropic/claude-sonnet-4.6"


class TestExplicitBaseUrlForNamedProvider:
    """#16719: PROVIDER_REGISTRY branch must honor explicit_base_url /
    explicit_api_key forwarded by _resolve_auto, instead of always falling
    back to pconfig.inference_base_url."""

    def test_explicit_base_url_overrides_provider_default(self, tmp_path):
        _write_config(tmp_path, {
            "model": {"default": "glm-5.1", "provider": "zai"},
        })
        with (
            patch("hermes_cli.auth.resolve_api_key_provider_credentials", return_value={
                "api_key": "creds-key",
                "base_url": "https://api.z.ai/api/paas/v4",
            }),
            patch("agent.auxiliary_client.OpenAI") as mock_openai,
        ):
            mock_openai.return_value = MagicMock()
            from agent.auxiliary_client import resolve_provider_client

            client, model = resolve_provider_client(
                "zai",
                "glm-5.1",
                explicit_base_url="https://custom-zai.example.com/v1",
                explicit_api_key="explicit-key",
            )

        assert client is not None
        assert model == "glm-5.1"
        kwargs = mock_openai.call_args.kwargs
        assert kwargs["base_url"] == "https://custom-zai.example.com/v1"
        assert kwargs["api_key"] == "explicit-key"

    def test_falls_back_to_creds_when_no_explicit(self, tmp_path):
        """Regression: existing behavior preserved when explicit_* not given."""
        _write_config(tmp_path, {
            "model": {"default": "glm-5.1", "provider": "zai"},
        })
        with (
            patch("hermes_cli.auth.resolve_api_key_provider_credentials", return_value={
                "api_key": "creds-key",
                "base_url": "https://api.z.ai/api/paas/v4",
            }),
            patch("agent.auxiliary_client.OpenAI") as mock_openai,
        ):
            mock_openai.return_value = MagicMock()
            from agent.auxiliary_client import resolve_provider_client

            client, _ = resolve_provider_client("zai", "glm-5.1")

        kwargs = mock_openai.call_args.kwargs
        assert "api.z.ai" in kwargs["base_url"]
        assert kwargs["api_key"] == "creds-key"


class TestAnthropicMessagesPreservesPath:
    """#17086: when api_mode=anthropic_messages or the URL ends in /anthropic,
    the /anthropic suffix must NOT be rewritten to /v1 — the AnthropicAuxiliary
    wrapper expects to talk to the original /anthropic surface."""

    def test_custom_branch_keeps_anthropic_suffix_with_explicit_api_mode(self, tmp_path):
        from unittest.mock import patch as _patch
        with _patch("agent.anthropic_adapter.build_anthropic_client") as mock_build:
            mock_build.return_value = MagicMock(name="anthropic_sdk_client")
            from agent.auxiliary_client import resolve_provider_client

            client, _ = resolve_provider_client(
                "custom",
                "claude-3-5",
                explicit_base_url="http://localhost:6655/anthropic/",
                explicit_api_key="k",
                api_mode="anthropic_messages",
            )
        assert client is not None
        # build_anthropic_client must be called with the original /anthropic
        # path, not the rewritten /v1.
        called_base = mock_build.call_args.args[1] if mock_build.call_args.args else \
            mock_build.call_args.kwargs.get("base_url", "")
        assert called_base.endswith("/anthropic"), (
            f"Anthropic adapter must receive the /anthropic path, got: {called_base!r}"
        )

    def test_custom_branch_rewrites_when_no_anthropic_signal(self, tmp_path):
        """Regression: non-Anthropic /anthropic URLs (none in practice, but
        guard against the gate misfiring) — when api_mode is unset and
        endpoint isn't recognized as Anthropic, no rewrite should happen
        either, since the URL doesn't end in /anthropic."""
        with patch("agent.auxiliary_client.OpenAI") as mock_openai:
            mock_openai.return_value = MagicMock()
            from agent.auxiliary_client import resolve_provider_client

            client, _ = resolve_provider_client(
                "custom",
                "gpt-4o",
                explicit_base_url="https://api.example.com/v1",
                explicit_api_key="k",
            )
        assert client is not None
        assert mock_openai.call_args.kwargs["base_url"] == "https://api.example.com/v1"


class TestResolveAutoForwardsBaseUrlForNamedProvider:
    """#16719: _resolve_auto must forward main_runtime.base_url as
    explicit_base_url for ANY provider, not just 'custom' / 'custom:*'.
    Without this, configuring `provider: zai, base_url: <custom>` silently
    routes auxiliary traffic to z.ai's default endpoint."""

    def test_named_provider_with_custom_base_url_forwards(self, tmp_path):
        _write_config(tmp_path, {
            "model": {"default": "glm-5.1", "provider": "zai"},
        })
        with patch(
            "agent.auxiliary_client.resolve_provider_client",
        ) as mock_resolve:
            mock_resolve.return_value = (MagicMock(), "glm-5.1")
            from agent.auxiliary_client import _resolve_auto

            _resolve_auto(main_runtime={
                "provider": "zai",
                "model": "glm-5.1",
                "base_url": "https://custom-zai.example.com/v1",
                "api_key": "user-key",
                "api_mode": "",
            })

        assert mock_resolve.called
        kwargs = mock_resolve.call_args.kwargs
        assert kwargs["explicit_base_url"] == "https://custom-zai.example.com/v1"
        assert kwargs["explicit_api_key"] == "user-key"
        # provider stays "zai" — not rewritten to "custom".
        assert mock_resolve.call_args.args[0] == "zai"


class TestResolveVisionProviderClientModelNormalization:
    """Vision auto-routing should reuse the same provider-specific normalization."""

    def test_vision_auto_strips_matching_main_provider_prefix(self, tmp_path):
        _write_config(tmp_path, {
            "model": {"default": "zai/glm-5.1", "provider": "zai"},
        })
        with (
            patch("agent.auxiliary_client._read_nous_auth", return_value=None),
            patch("hermes_cli.auth.resolve_api_key_provider_credentials", return_value={
                "api_key": "glm-key",
                "base_url": "https://api.z.ai/api/paas/v4",
            }),
            patch("agent.auxiliary_client.OpenAI") as mock_openai,
        ):
            mock_openai.return_value = MagicMock()
            from agent.auxiliary_client import resolve_vision_provider_client

            provider, client, model = resolve_vision_provider_client()

        assert provider == "zai"
        assert client is not None
        assert model == "glm-5v-turbo"  # zai has dedicated vision model in _PROVIDER_VISION_MODELS


class TestVisionPathApiMode:
    """Vision path should propagate api_mode to _get_cached_client."""

    def test_explicit_provider_passes_api_mode(self, tmp_path):
        _write_config(tmp_path, {
            "model": {"default": "test-model"},
            "auxiliary": {"vision": {"api_mode": "chat_completions"}},
        })
        with patch("agent.auxiliary_client._get_cached_client") as mock_gcc:
            mock_gcc.return_value = (MagicMock(), "test-model")
            from agent.auxiliary_client import resolve_vision_provider_client

            provider, client, model = resolve_vision_provider_client(provider="deepseek")

        mock_gcc.assert_called_once()
        _, kwargs = mock_gcc.call_args
        assert kwargs.get("api_mode") == "chat_completions"


class TestProvidersDictApiModeAnthropicMessages:
    """Regression guard for #15033.

    Named providers declared under the ``providers:`` dict with
    ``api_mode: anthropic_messages`` must route auxiliary calls through
    the Anthropic Messages API (via AnthropicAuxiliaryClient), not
    through an OpenAI chat-completions client.

    The bug had two halves: the providers-dict branch of
    ``_get_named_custom_provider`` dropped the ``api_mode`` field, and
    ``resolve_provider_client``'s named-custom branch never read it.
    """

    def test_providers_dict_propagates_api_mode(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MYRELAY_API_KEY", "sk-test")
        _write_config(tmp_path, {
            "providers": {
                "myrelay": {
                    "name": "myrelay",
                    "base_url": "https://example-relay.test/anthropic",
                    "key_env": "MYRELAY_API_KEY",
                    "api_mode": "anthropic_messages",
                    "default_model": "claude-opus-4-7",
                },
            },
        })
        from hermes_cli.runtime_provider import _get_named_custom_provider
        entry = _get_named_custom_provider("myrelay")
        assert entry is not None
        assert entry.get("api_mode") == "anthropic_messages"
        assert entry.get("base_url") == "https://example-relay.test/anthropic"
        assert entry.get("api_key") == "sk-test"

    def test_providers_dict_invalid_api_mode_is_dropped(self, tmp_path):
        _write_config(tmp_path, {
            "providers": {
                "weird": {
                    "name": "weird",
                    "base_url": "https://example.test",
                    "api_mode": "bogus_nonsense",
                    "default_model": "x",
                },
            },
        })
        from hermes_cli.runtime_provider import _get_named_custom_provider
        entry = _get_named_custom_provider("weird")
        assert entry is not None
        assert "api_mode" not in entry

    def test_providers_dict_without_api_mode_is_unchanged(self, tmp_path):
        _write_config(tmp_path, {
            "providers": {
                "localchat": {
                    "name": "localchat",
                    "base_url": "http://127.0.0.1:1234/v1",
                    "api_key": "local-key",
                    "default_model": "llama-3",
                },
            },
        })
        from hermes_cli.runtime_provider import _get_named_custom_provider
        entry = _get_named_custom_provider("localchat")
        assert entry is not None
        assert "api_mode" not in entry

    def test_resolve_provider_client_returns_anthropic_client(self, tmp_path, monkeypatch):
        """Named custom provider with api_mode=anthropic_messages must
        route through AnthropicAuxiliaryClient."""
        monkeypatch.setenv("MYRELAY_API_KEY", "sk-test")
        _write_config(tmp_path, {
            "providers": {
                "myrelay": {
                    "name": "myrelay",
                    "base_url": "https://example-relay.test/anthropic",
                    "key_env": "MYRELAY_API_KEY",
                    "api_mode": "anthropic_messages",
                    "default_model": "claude-opus-4-7",
                },
            },
        })
        from agent.auxiliary_client import (
            resolve_provider_client,
            AnthropicAuxiliaryClient,
            AsyncAnthropicAuxiliaryClient,
        )
        sync_client, sync_model = resolve_provider_client("myrelay", async_mode=False)
        assert isinstance(sync_client, AnthropicAuxiliaryClient), (
            f"expected AnthropicAuxiliaryClient, got {type(sync_client).__name__}"
        )
        assert sync_model == "claude-opus-4-7"

        async_client, async_model = resolve_provider_client("myrelay", async_mode=True)
        assert isinstance(async_client, AsyncAnthropicAuxiliaryClient), (
            f"expected AsyncAnthropicAuxiliaryClient, got {type(async_client).__name__}"
        )
        assert async_model == "claude-opus-4-7"

    def test_aux_task_override_routes_named_provider_to_anthropic(self, tmp_path, monkeypatch):
        """The full chain: auxiliary.<task>.provider: myrelay with
        api_mode anthropic_messages must produce an Anthropic client."""
        monkeypatch.setenv("MYRELAY_API_KEY", "sk-test")
        _write_config(tmp_path, {
            "providers": {
                "myrelay": {
                    "name": "myrelay",
                    "base_url": "https://example-relay.test/anthropic",
                    "key_env": "MYRELAY_API_KEY",
                    "api_mode": "anthropic_messages",
                    "default_model": "claude-opus-4-7",
                },
            },
            "auxiliary": {
                "compression": {
                    "provider": "myrelay",
                    "model": "claude-sonnet-4.6",
                },
            },
            "model": {"provider": "openrouter", "default": "anthropic/claude-sonnet-4.6"},
        })
        from agent.auxiliary_client import (
            get_async_text_auxiliary_client,
            get_text_auxiliary_client,
            AnthropicAuxiliaryClient,
            AsyncAnthropicAuxiliaryClient,
        )
        async_client, async_model = get_async_text_auxiliary_client("compression")
        assert isinstance(async_client, AsyncAnthropicAuxiliaryClient)
        assert async_model == "claude-sonnet-4.6"

        sync_client, sync_model = get_text_auxiliary_client("compression")
        assert isinstance(sync_client, AnthropicAuxiliaryClient)
        assert sync_model == "claude-sonnet-4.6"

    def test_provider_without_api_mode_still_uses_openai(self, tmp_path):
        """Named providers that don't declare api_mode should still go
        through the plain OpenAI-wire path (no regression)."""
        _write_config(tmp_path, {
            "providers": {
                "localchat": {
                    "name": "localchat",
                    "base_url": "http://127.0.0.1:1234/v1",
                    "api_key": "local-key",
                    "default_model": "llama-3",
                },
            },
        })
        from agent.auxiliary_client import resolve_provider_client
        from openai import OpenAI, AsyncOpenAI
        sync_client, _ = resolve_provider_client("localchat", async_mode=False)
        # sync returns the raw OpenAI client
        assert isinstance(sync_client, OpenAI)
        async_client, _ = resolve_provider_client("localchat", async_mode=True)
        assert isinstance(async_client, AsyncOpenAI)
