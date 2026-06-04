"""Unit tests for the runtime credentials sanity check (#33936).

The api-key providers in ``PROVIDER_REGISTRY`` (DeepSeek, Z.AI, Kimi,
Mistral, NVIDIA NIM, …) silently return ``api_key=""`` when their env
var is unset rather than raising. Cron, gateway, and CLI all wrap the
resolver in ``try/except AuthError`` to trigger their ``fallback_providers``
chain — but the missing-key case never raised, so the agent was built
with empty credentials and crashed later at the API call with a 401
instead of falling back to the configured next provider.

These tests pin the new ``ensure_runtime_credentials_or_raise()`` /
``runtime_credentials_are_usable()`` helpers that promote the empty-key
case to ``AuthError`` so the existing fallback wiring activates.
"""

from __future__ import annotations

import pytest

from hermes_cli.auth import AuthError
from hermes_cli.runtime_provider import (
    ensure_runtime_credentials_or_raise,
    runtime_credentials_are_usable,
)


class TestRuntimeCredentialsAreUsable:
    def test_non_dict_runtime_is_unusable(self):
        assert runtime_credentials_are_usable(None) is False
        assert runtime_credentials_are_usable("not-a-dict") is False
        assert runtime_credentials_are_usable(42) is False

    def test_empty_string_api_key_for_registry_api_key_provider_is_unusable(self):
        # deepseek is a registry api-key provider; empty key must fail.
        runtime = {"provider": "deepseek", "api_key": ""}
        assert runtime_credentials_are_usable(runtime) is False

    def test_whitespace_only_api_key_for_registry_provider_is_unusable(self):
        runtime = {"provider": "deepseek", "api_key": "   \n\t"}
        assert runtime_credentials_are_usable(runtime) is False

    def test_real_api_key_is_usable(self):
        runtime = {
            "provider": "deepseek",
            "api_key": "sk-deepseek-realistic-test-key-12345",
        }
        assert runtime_credentials_are_usable(runtime) is True

    def test_callable_api_key_is_usable(self):
        """Entra ID / dynamic token resolvers expose api_key as a callable;
        the actual token is fetched at API call time, so we cannot
        inspect it now. Trust the callable."""
        runtime = {"provider": "azure-foundry", "api_key": lambda: "token"}
        assert runtime_credentials_are_usable(runtime) is True

    def test_no_key_required_placeholder_for_custom_provider_is_usable(self):
        """Localhost / custom-provider runtime sets api_key='no-key-required'.
        ``custom`` isn't a registry api-key provider so the scoped check
        lets it pass without inspecting the api_key further."""
        runtime = {"provider": "custom", "api_key": "no-key-required"}
        assert runtime_credentials_are_usable(runtime) is True

    def test_lmstudio_dummy_key_is_usable(self):
        # lmstudio is a registry api-key provider but uses a documented
        # no-auth placeholder; the placeholder allowlist must cover it.
        runtime = {"provider": "lmstudio", "api_key": "dummy-lm-api-key"}
        assert runtime_credentials_are_usable(runtime) is True

    def test_off_registry_providers_pass_through(self):
        """Non-api-key providers (openrouter, nous, bedrock, openai-codex,
        custom) are not subject to the empty-key check — they carry auth
        in other fields and have their own per-provider validation."""
        for provider, key in [
            ("openrouter", ""),
            ("openrouter", "***"),
            ("nous", ""),
            ("bedrock", "aws-sdk"),
            ("openai-codex", ""),
            ("custom", ""),
        ]:
            runtime = {"provider": provider, "api_key": key}
            assert runtime_credentials_are_usable(runtime) is True, (
                f"{provider!r} runtime should not be subject to the "
                f"registry api-key empty-check, got rejected with "
                f"api_key={key!r}"
            )

    def test_placeholder_string_for_registry_provider_is_unusable(self):
        """``has_usable_secret`` rejects obvious placeholders for api-key
        providers (``***``, ``changeme``, …) so empty-config test fakes
        also flip into the fallback path."""
        for placeholder in ("***", "changeme", "your_api_key", "placeholder", "example"):
            runtime = {"provider": "deepseek", "api_key": placeholder}
            assert runtime_credentials_are_usable(runtime) is False, placeholder


class TestEnsureRuntimeCredentialsOrRaise:
    def test_returns_silently_on_usable_runtime(self):
        runtime = {
            "provider": "deepseek",
            "api_key": "sk-deepseek-realistic-test-key-12345",
        }
        # No exception expected.
        ensure_runtime_credentials_or_raise(runtime)

    def test_raises_auth_error_on_empty_key(self):
        runtime = {"provider": "deepseek", "api_key": ""}
        with pytest.raises(AuthError) as excinfo:
            ensure_runtime_credentials_or_raise(runtime)
        assert "deepseek" in str(excinfo.value).lower()
        assert getattr(excinfo.value, "code", None) == "missing_api_key"

    def test_auth_error_names_expected_env_var(self):
        """For api-key providers in ``PROVIDER_REGISTRY``, the AuthError
        message must list the env var the resolver tried to read so
        operators can fix ``~/.hermes/.env`` without reading source code."""
        runtime = {"provider": "deepseek", "api_key": ""}
        with pytest.raises(AuthError) as excinfo:
            ensure_runtime_credentials_or_raise(runtime)
        msg = str(excinfo.value)
        assert "DEEPSEEK_API_KEY" in msg, (
            f"AuthError message should hint at the expected env var "
            f"to make the fix obvious; got: {msg!r}"
        )

    def test_off_registry_runtime_passes_through(self):
        """Openrouter / nous / codex / custom runtimes don't trip the
        check even with empty api_key — their per-provider resolvers
        are the source of truth for their respective auth shapes."""
        for provider in ("openrouter", "nous", "openai-codex", "custom"):
            runtime = {"provider": provider, "api_key": ""}
            # No exception expected.
            ensure_runtime_credentials_or_raise(runtime)

    def test_none_runtime_raises(self):
        with pytest.raises(AuthError):
            ensure_runtime_credentials_or_raise(None, requested_provider="deepseek")
