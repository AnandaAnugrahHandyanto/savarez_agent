"""Tests for terminal.env_passthrough .env fallback in local backend.

Verifies that passthrough keys listed in config or registered by skills
are sourced from ~/.hermes/.env when they are not present in os.environ.

See: https://github.com/NousResearch/hermes-agent/issues/46152
"""

import os
import threading
from unittest.mock import MagicMock, patch

from tools.environments.local import _make_run_env


class TestPassthroughDotenvFallback:
    """Passthrough keys missing from os.environ should fall back to .env."""

    def test_passthrough_key_from_dotenv_injected(self, monkeypatch):
        """A passthrough key that only exists in .env appears in run_env."""
        monkeypatch.delenv("MY_SECRET_TOKEN", raising=False)

        with patch(
            "tools.env_passthrough.get_all_passthrough",
            return_value=frozenset({"MY_SECRET_TOKEN"}),
        ), patch(
            "hermes_cli.config.load_env",
            return_value={"MY_SECRET_TOKEN": "tok123"},
        ):
            result = _make_run_env({})

        assert result.get("MY_SECRET_TOKEN") == "tok123"

    def test_passthrough_key_in_os_environ_not_overwritten(self, monkeypatch):
        """When the key is already in os.environ, .env is not consulted."""
        monkeypatch.setenv("MY_SECRET_TOKEN", "from_shell")

        with patch(
            "tools.env_passthrough.get_all_passthrough",
            return_value=frozenset({"MY_SECRET_TOKEN"}),
        ), patch(
            "hermes_cli.config.load_env",
            return_value={"MY_SECRET_TOKEN": "from_dotenv"},
        ):
            result = _make_run_env({})

        assert result.get("MY_SECRET_TOKEN") == "from_shell"

    def test_non_passthrough_key_not_loaded_from_dotenv(self, monkeypatch):
        """Keys not in the passthrough list are not loaded from .env."""
        monkeypatch.delenv("UNRELATED_VAR", raising=False)

        with patch(
            "tools.env_passthrough.get_all_passthrough",
            return_value=frozenset(set()),
        ), patch(
            "hermes_cli.config.load_env",
            return_value={"UNRELATED_VAR": "should_not_appear"},
        ):
            result = _make_run_env({})

        assert "UNRELATED_VAR" not in result

    def test_dotenv_load_failure_is_silent(self, monkeypatch):
        """If load_env() raises, the fallback is silently skipped."""
        monkeypatch.delenv("MY_TOKEN", raising=False)

        with patch(
            "tools.env_passthrough.get_all_passthrough",
            return_value=frozenset({"MY_TOKEN"}),
        ), patch(
            "hermes_cli.config.load_env",
            side_effect=Exception("no .env file"),
        ):
            result = _make_run_env({})

        assert "MY_TOKEN" not in result

    def test_passthrough_key_from_env_param(self, monkeypatch):
        """Keys passed via the env parameter are already present — no .env needed."""
        monkeypatch.delenv("MY_SECRET_TOKEN", raising=False)

        with patch(
            "tools.env_passthrough.get_all_passthrough",
            return_value=frozenset({"MY_SECRET_TOKEN"}),
        ), patch(
            "hermes_cli.config.load_env",
            return_value={"MY_SECRET_TOKEN": "from_dotenv"},
        ):
            result = _make_run_env({"MY_SECRET_TOKEN": "from_param"})

        assert result.get("MY_SECRET_TOKEN") == "from_param"
