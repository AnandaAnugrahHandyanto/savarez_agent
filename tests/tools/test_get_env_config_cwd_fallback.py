"""Tests for _get_env_config handling of missing CWD (FileNotFoundError).

Regression test for https://github.com/NousResearch/hermes-agent/issues/33367:
On systems with aggressive tmpfs cleanup (e.g. Arch Linux), os.getcwd() can raise
FileNotFoundError when the process's CWD has been removed. The cleanup thread calls
_get_env_config() every 60 seconds, so this must not crash.
"""

import os
import types
from unittest.mock import patch

import pytest


@pytest.fixture()
def _tt_mod():
    """Import the terminal_tool module once."""
    import importlib
    return importlib.import_module("tools.terminal_tool")


class TestGetEnvConfigCwdFallback:
    """_get_env_config must not raise when os.getcwd() fails."""

    def test_local_env_getcwd_file_not_found(self, _tt_mod, monkeypatch):
        """When env_type=local and os.getcwd() raises FileNotFoundError,
        _get_env_config should fall back to the user's home directory."""
        monkeypatch.setenv("TERMINAL_ENV", "local")
        monkeypatch.delenv("TERMINAL_CWD", raising=False)

        def _boom():
            raise FileNotFoundError(2, "No such file or directory")

        with patch("os.getcwd", side_effect=_boom):
            config = _tt_mod._get_env_config()

        assert config["env_type"] == "local"
        # Should have fallen back to home directory, not crashed
        assert config["cwd"] == os.path.expanduser("~")
        assert os.path.isabs(config["cwd"])

    def test_local_env_getcwd_os_error(self, _tt_mod, monkeypatch):
        """When env_type=local and os.getcwd() raises OSError (e.g. ENOENT),
        _get_env_config should fall back to the user's home directory."""
        monkeypatch.setenv("TERMINAL_ENV", "local")
        monkeypatch.delenv("TERMINAL_CWD", raising=False)

        def _boom():
            raise OSError(2, "No such file or directory")

        with patch("os.getcwd", side_effect=_boom):
            config = _tt_mod._get_env_config()

        assert config["env_type"] == "local"
        assert config["cwd"] == os.path.expanduser("~")

    def test_local_env_getcwd_normal(self, _tt_mod, monkeypatch):
        """Normal case: os.getcwd() succeeds, default_cwd should be the real CWD."""
        monkeypatch.setenv("TERMINAL_ENV", "local")
        monkeypatch.delenv("TERMINAL_CWD", raising=False)

        config = _tt_mod._get_env_config()

        assert config["env_type"] == "local"
        # Should be the actual CWD, not the fallback
        assert config["cwd"] == os.getcwd()

    def test_local_env_terminal_cwd_overrides_fallback(self, _tt_mod, monkeypatch):
        """When TERMINAL_CWD is set, it should be used even if os.getcwd() fails."""
        monkeypatch.setenv("TERMINAL_ENV", "local")
        monkeypatch.setenv("TERMINAL_CWD", "/some/explicit/path")

        def _boom():
            raise FileNotFoundError(2, "No such file or directory")

        with patch("os.getcwd", side_effect=_boom):
            config = _tt_mod._get_env_config()

        # TERMINAL_CWD should still be the effective cwd
        assert config["cwd"] == "/some/explicit/path"

    def test_docker_mount_cwd_getcwd_file_not_found(self, _tt_mod, monkeypatch):
        """When env_type=docker and mount_cwd is enabled, os.getcwd() failure
        should not crash; should fall back gracefully."""
        monkeypatch.setenv("TERMINAL_ENV", "docker")
        monkeypatch.setenv("TERMINAL_DOCKER_MOUNT_CWD_TO_WORKSPACE", "true")
        monkeypatch.delenv("TERMINAL_CWD", raising=False)

        def _boom():
            raise FileNotFoundError(2, "No such file or directory")

        with patch("os.getcwd", side_effect=_boom):
            config = _tt_mod._get_env_config()

        assert config["env_type"] == "docker"
        # Should not crash; docker_cwd_source should fall back to home
        assert config["cwd"] in ("/workspace", os.path.expanduser("~"))
