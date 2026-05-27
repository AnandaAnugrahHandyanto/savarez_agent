"""Regression test for #33367: _get_env_config should not raise when CWD is deleted."""

import os
from unittest.mock import patch


def test_get_env_config_handles_deleted_cwd(monkeypatch):
    """When os.getcwd() raises FileNotFoundError (e.g. tmpfs cleanup on Arch
    Linux), _get_env_config should fall back to the home directory instead of
    propagating the error.  See #33367."""
    from tools import terminal_tool as tt

    def _raise_fnf(*a, **kw):
        raise FileNotFoundError("No such file or directory")

    monkeypatch.setattr(os, "getcwd", _raise_fnf)
    monkeypatch.setenv("TERMINAL_ENV", "local")

    config = tt._get_env_config()

    assert config["env_type"] == "local"
    assert config["cwd"] == os.path.expanduser("~")


def test_get_env_config_handles_oserror_on_cwd(monkeypatch):
    """os.getcwd() can also raise OSError (errno 10: no current directory)."""
    from tools import terminal_tool as tt

    def _raise_os(*a, **kw):
        raise OSError(10, "No current process")

    monkeypatch.setattr(os, "getcwd", _raise_os)
    monkeypatch.setenv("TERMINAL_ENV", "local")

    config = tt._get_env_config()

    assert config["env_type"] == "local"
    assert config["cwd"] == os.path.expanduser("~")
