"""Tests for resolve_explicit_api_key_for_fallback() — the shared helper
that lets the CLI's one-shot path and the gateway's long-lived path agree
on which env var backs an env-driven fallback entry, and read it from
``~/.hermes/.env`` consistently.

Regression coverage for #33540 (``hermes chat -q`` losing provider auth
context for ``fallback_providers`` that point at env-backed providers
like ``azure-foundry`` and ``openrouter``).
"""

from __future__ import annotations

import pytest

from hermes_cli.fallback_config import (
    get_fallback_chain,
    resolve_explicit_api_key_for_fallback,
)


class TestInlineApiKeyTakesPrecedence:
    def test_raw_api_key_is_returned_verbatim(self):
        entry = {
            "provider": "openrouter",
            "model": "openrouter/owl-alpha",
            "api_key": "sk-or-xxxxxxxx",
        }
        assert resolve_explicit_api_key_for_fallback(entry) == "sk-or-xxxxxxxx"

    def test_inline_key_strips_surrounding_whitespace(self):
        entry = {"api_key": "  sk-or-trimmed  "}
        assert resolve_explicit_api_key_for_fallback(entry) == "sk-or-trimmed"

    def test_inline_key_beats_api_key_env(self, monkeypatch):
        monkeypatch.setenv("MY_FALLBACK_KEY", "from-env-should-be-ignored")
        entry = {
            "api_key": "from-inline",
            "api_key_env": "MY_FALLBACK_KEY",
        }
        assert (
            resolve_explicit_api_key_for_fallback(entry) == "from-inline"
        )


class TestApiKeyEnvLookup:
    def test_api_key_env_is_resolved_via_get_env_value(self, monkeypatch):
        monkeypatch.setenv("AZURE_FOUNDRY_KEY", "azure-secret")
        entry = {
            "provider": "azure-foundry",
            "model": "Kimi-K2.6",
            "base_url": "https://aoai.example/openai/v1",
            "api_key_env": "AZURE_FOUNDRY_KEY",
        }
        assert (
            resolve_explicit_api_key_for_fallback(entry) == "azure-secret"
        )

    def test_key_env_alias_is_honored(self, monkeypatch):
        # ``key_env`` is the canonical field name on ``custom_providers``;
        # we accept it so an operator can copy/paste a custom_providers
        # block straight into ``fallback_providers``.
        monkeypatch.setenv("CUSTOM_PROVIDER_KEY", "custom-secret")
        entry = {"key_env": "CUSTOM_PROVIDER_KEY"}
        assert (
            resolve_explicit_api_key_for_fallback(entry) == "custom-secret"
        )

    def test_api_key_env_wins_over_key_env(self, monkeypatch):
        monkeypatch.setenv("PRIMARY_KEY", "primary")
        monkeypatch.setenv("LEGACY_KEY", "legacy")
        entry = {"api_key_env": "PRIMARY_KEY", "key_env": "LEGACY_KEY"}
        assert resolve_explicit_api_key_for_fallback(entry) == "primary"

    def test_unset_env_var_returns_none(self, monkeypatch):
        monkeypatch.delenv("UNSET_KEY_NAME", raising=False)
        entry = {"api_key_env": "UNSET_KEY_NAME"}
        assert resolve_explicit_api_key_for_fallback(entry) is None

    def test_empty_env_value_returns_none(self, monkeypatch):
        monkeypatch.setenv("BLANK_KEY", "   ")
        entry = {"api_key_env": "BLANK_KEY"}
        assert resolve_explicit_api_key_for_fallback(entry) is None


class TestDotEnvFallback:
    """``get_env_value`` reads ~/.hermes/.env in addition to live env.
    The fallback helper must use that lookup so secrets persisted in the
    per-profile dotenv (which one-shot CLI runs inherit) are honored —
    not just secrets exported by the parent shell. Failure mode reported
    in #33540: one-shot CLI sees only os.environ and reports
    ``Provider resolver returned an empty API key`` for openrouter even
    though ``hermes auth list`` showed the credential.
    """

    def test_reads_value_from_dot_env_file(self, monkeypatch):
        monkeypatch.delenv("PROFILE_ONLY_KEY", raising=False)

        def _fake_get_env_value(key):
            return "from-dot-env" if key == "PROFILE_ONLY_KEY" else None

        monkeypatch.setattr(
            "hermes_cli.config.get_env_value",
            _fake_get_env_value,
        )
        entry = {"api_key_env": "PROFILE_ONLY_KEY"}
        assert (
            resolve_explicit_api_key_for_fallback(entry) == "from-dot-env"
        )

    def test_falls_back_to_os_getenv_when_config_import_fails(
        self, monkeypatch
    ):
        # Simulate hermes_cli.config import explosion (rare but possible
        # during early bootstrap when CLI_CONFIG isn't loaded yet).
        import builtins

        original_import = builtins.__import__

        def _selective_import(name, *args, **kwargs):
            if name == "hermes_cli.config":
                raise ImportError("simulated bootstrap failure")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", _selective_import)
        monkeypatch.setenv("OS_ENV_FALLBACK_KEY", "os-env-secret")
        entry = {"api_key_env": "OS_ENV_FALLBACK_KEY"}
        assert (
            resolve_explicit_api_key_for_fallback(entry) == "os-env-secret"
        )


class TestNothingConfigured:
    def test_entry_without_any_key_source_returns_none(self):
        entry = {"provider": "openrouter", "model": "openrouter/owl-alpha"}
        assert resolve_explicit_api_key_for_fallback(entry) is None

    def test_non_dict_input_returns_none(self):
        assert resolve_explicit_api_key_for_fallback(None) is None
        assert resolve_explicit_api_key_for_fallback("not-a-dict") is None
        assert resolve_explicit_api_key_for_fallback(42) is None

    def test_empty_string_inline_key_is_ignored(self, monkeypatch):
        # An empty/whitespace api_key on the entry must NOT short-circuit
        # the env-var lookup chain — otherwise an operator who set
        # ``api_key: ""`` (placeholder) would lose env-var resolution.
        monkeypatch.setenv("FALLBACK_KEY", "from-env")
        entry = {"api_key": "   ", "api_key_env": "FALLBACK_KEY"}
        assert (
            resolve_explicit_api_key_for_fallback(entry) == "from-env"
        )


class TestGetFallbackChainStillWorks:
    """Smoke test to confirm the older helper still composes a chain
    with the new entries the user might write. The Issue config:

      fallback_providers:
        - provider: azure-foundry
          model: Kimi-K2.6
          base_url: https://<azure-foundry>/openai/v1
        - provider: openrouter
          model: openrouter/owl-alpha
    """

    def test_two_entry_chain_preserves_order_and_base_url(self):
        cfg = {
            "fallback_providers": [
                {
                    "provider": "azure-foundry",
                    "model": "Kimi-K2.6",
                    "base_url": "https://aoai.example/openai/v1",
                },
                {
                    "provider": "openrouter",
                    "model": "openrouter/owl-alpha",
                },
            ],
        }
        chain = get_fallback_chain(cfg)
        assert [e["provider"] for e in chain] == [
            "azure-foundry", "openrouter",
        ]
        assert chain[0]["base_url"] == "https://aoai.example/openai/v1"
        # Second entry omits base_url and stays without one — the resolver
        # is expected to consult env / config for openrouter's endpoint.
        assert "base_url" not in chain[1]
