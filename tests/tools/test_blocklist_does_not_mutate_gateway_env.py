"""Regression tests for the gateway-process scope of the env blocklist (#33936).

``_HERMES_PROVIDER_ENV_BLOCKLIST`` is a *subprocess sanitization* filter.
It must never pop or otherwise mutate provider credential env vars on the
calling Hermes process (gateway, CLI, cron worker). Users in #33936
mis-diagnosed cron-job failures as "the blocklist is removing
``DEEPSEEK_API_KEY`` from the gateway process" because their only
diagnostic surface (``env | grep ...`` invoked through the agent's
terminal tool) routed through ``_sanitize_subprocess_env`` and returned
empty. Pin the actual contract here so a future refactor cannot
silently break it.
"""

from __future__ import annotations

import os
from unittest.mock import patch


class TestBlocklistImportDoesNotMutateOsEnviron:
    """Importing the local environment module must not pop blocked vars."""

    def test_provider_credentials_still_in_os_environ_after_import(self):
        """Sanity: provider creds set in os.environ remain after blocklist import.

        Mirrors the bug report in #33936: users set ``DEEPSEEK_API_KEY``
        (or any other blocked provider env var) in ``/opt/data/.env`` /
        ``~/.hermes/.env`` and expect the gateway's provider resolver
        to see it. The blocklist must not interfere with that
        in-process visibility.
        """
        provider_creds = {
            "DEEPSEEK_API_KEY": "sk-deepseek-fake",
            "ANTHROPIC_API_KEY": "sk-ant-fake",
            "OPENAI_API_KEY": "sk-openai-fake",
            "ZAI_API_KEY": "zai-fake",
            "GROQ_API_KEY": "groq-fake",
        }
        with patch.dict(os.environ, provider_creds, clear=False):
            # Force a fresh import path — the build_provider_env_blocklist
            # call inside the module imports several other modules that
            # could in principle scrub os.environ as a side effect.
            from tools.environments import local as local_mod
            from importlib import reload

            reload(local_mod)

            for var, expected in provider_creds.items():
                assert os.environ.get(var) == expected, (
                    f"{var} disappeared from os.environ after importing "
                    f"the blocklist module — the subprocess sanitization "
                    f"contract leaked into gateway-process state (#33936)."
                )

    def test_blocklist_is_a_frozenset_not_a_mutator(self):
        """The blocklist itself must be an inert frozenset of names."""
        from tools.environments.local import _HERMES_PROVIDER_ENV_BLOCKLIST

        assert isinstance(_HERMES_PROVIDER_ENV_BLOCKLIST, frozenset)
        # Cannot be coerced into modifying os.environ — it's just names.
        for name in _HERMES_PROVIDER_ENV_BLOCKLIST:
            assert isinstance(name, str)


class TestSanitizeSubprocessEnvDoesNotMutateBaseEnv:
    """Calling ``_sanitize_subprocess_env(os.environ)`` must not pop keys."""

    def test_passing_os_environ_directly_does_not_modify_it(self):
        """If a caller passes ``os.environ`` (not a copy), the function
        must still leave ``os.environ`` untouched. Mirrors the cron
        scheduler / terminal tool patterns that may pass live env
        references.
        """
        from tools.environments.local import _sanitize_subprocess_env

        with patch.dict(
            os.environ,
            {
                "DEEPSEEK_API_KEY": "sk-deepseek-fake",
                "ANTHROPIC_API_KEY": "sk-ant-fake",
            },
            clear=False,
        ):
            before = dict(os.environ)
            _ = _sanitize_subprocess_env(os.environ)
            after = dict(os.environ)

            assert before == after, (
                "_sanitize_subprocess_env mutated os.environ in place — "
                "blocked vars must only be stripped from the *returned* "
                "subprocess env dict, never from the caller's live "
                "environment (#33936)."
            )
            assert os.environ.get("DEEPSEEK_API_KEY") == "sk-deepseek-fake"
            assert os.environ.get("ANTHROPIC_API_KEY") == "sk-ant-fake"

    def test_return_value_strips_blocked_vars_only(self):
        """Spot-check: the *returned* dict drops blocked vars but
        leaves everything else (PATH, HOME, custom user vars).
        """
        from tools.environments.local import _sanitize_subprocess_env

        base = {
            "DEEPSEEK_API_KEY": "sk-deepseek-fake",
            "PATH": "/usr/bin:/bin",
            "HOME": "/home/user",
            "MY_CUSTOM_VAR": "keep-me",
        }
        result = _sanitize_subprocess_env(base)

        assert "DEEPSEEK_API_KEY" not in result
        assert result.get("PATH") == "/usr/bin:/bin"
        assert result.get("HOME") == "/home/user"
        assert result.get("MY_CUSTOM_VAR") == "keep-me"
        # The input dict is left intact — no in-place mutation.
        assert base.get("DEEPSEEK_API_KEY") == "sk-deepseek-fake"


class TestRuntimeProviderStillSeesBlockedCredentials:
    """Cross-check: the in-process runtime provider resolver reads
    the same env vars that the subprocess blocklist scrubs."""

    def test_resolve_api_key_provider_reads_blocked_var(self):
        """``DEEPSEEK_API_KEY`` is in the blocklist, but
        :func:`resolve_api_key_provider_credentials` must still
        return it for the gateway's own use. This is the property
        the cron scheduler depends on.
        """
        from hermes_cli.auth import resolve_api_key_provider_credentials

        with patch.dict(
            os.environ,
            {"DEEPSEEK_API_KEY": "sk-deepseek-fake-for-test-only-1234"},
            clear=False,
        ):
            creds = resolve_api_key_provider_credentials("deepseek")
            assert creds.get("api_key") == "sk-deepseek-fake-for-test-only-1234", (
                "Provider resolver could not see DEEPSEEK_API_KEY despite "
                "it being in os.environ — the subprocess blocklist must "
                "not affect in-process credential reads (#33936)."
            )
