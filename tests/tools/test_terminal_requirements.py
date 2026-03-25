import importlib
import logging
import builtins
import sys
from pathlib import Path

terminal_tool_module = importlib.import_module("tools.terminal_tool")


def _clear_terminal_env(monkeypatch):
    """Remove terminal env vars that could affect requirements checks."""
    keys = [
        "TERMINAL_ENV",
        "TERMINAL_SSH_HOST",
        "TERMINAL_SSH_USER",
        "MODAL_TOKEN_ID",
        "HOME",
        "USERPROFILE",
    ]
    for key in keys:
        monkeypatch.delenv(key, raising=False)


def test_local_terminal_requirements(monkeypatch, caplog):
    """Local backend uses Hermes' own LocalEnvironment wrapper."""
    _clear_terminal_env(monkeypatch)
    monkeypatch.setenv("TERMINAL_ENV", "local")

    with caplog.at_level(logging.ERROR):
        ok = terminal_tool_module.check_terminal_requirements()

    assert ok is True
    assert "Terminal requirements check failed" not in caplog.text


def test_unknown_terminal_env_logs_error_and_returns_false(monkeypatch, caplog):
    _clear_terminal_env(monkeypatch)
    monkeypatch.setenv("TERMINAL_ENV", "unknown-backend")

    with caplog.at_level(logging.ERROR):
        ok = terminal_tool_module.check_terminal_requirements()

    assert ok is False
    assert any(
        "Unknown TERMINAL_ENV 'unknown-backend'" in record.getMessage()
        for record in caplog.records
    )


def test_ssh_backend_without_host_or_user_logs_and_returns_false(monkeypatch, caplog):
    _clear_terminal_env(monkeypatch)
    monkeypatch.setenv("TERMINAL_ENV", "ssh")

    with caplog.at_level(logging.ERROR):
        ok = terminal_tool_module.check_terminal_requirements()

    assert ok is False
    assert any(
        "SSH backend selected but TERMINAL_SSH_HOST and TERMINAL_SSH_USER" in record.getMessage()
        for record in caplog.records
    )


def test_modal_backend_without_token_or_config_logs_specific_error(monkeypatch, caplog, tmp_path):
    _clear_terminal_env(monkeypatch)
    monkeypatch.setenv("TERMINAL_ENV", "modal")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    # Pretend swerex is installed
    monkeypatch.setattr(terminal_tool_module.importlib.util, "find_spec", lambda _name: object())

    with caplog.at_level(logging.ERROR):
        ok = terminal_tool_module.check_terminal_requirements()

    assert ok is False
    assert any(
        "Modal backend selected but no MODAL_TOKEN_ID environment variable" in record.getMessage()
        for record in caplog.records
    )


def test_terminal_tool_imports_without_minisweagent_path_helper(monkeypatch):
    terminal_tool_path = Path(__file__).resolve().parents[2] / "tools" / "terminal_tool.py"
    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "minisweagent_path":
            raise ImportError("helper missing")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    module_name = "terminal_tool_no_helper_test"
    sys.modules.pop(module_name, None)

    spec = importlib.util.spec_from_file_location(module_name, terminal_tool_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert callable(module.ensure_minisweagent_on_path)


def test_docker_backend_without_minisweagent_logs_specific_error(monkeypatch, caplog):
    _clear_terminal_env(monkeypatch)
    monkeypatch.setenv("TERMINAL_ENV", "docker")
    monkeypatch.setattr(terminal_tool_module, "ensure_minisweagent_on_path", lambda _root: None)
    monkeypatch.setattr(terminal_tool_module.importlib.util, "find_spec", lambda _name: None)

    with caplog.at_level(logging.ERROR):
        ok = terminal_tool_module.check_terminal_requirements()

    assert ok is False
    assert any(
        "mini-swe-agent is required for docker terminal backend but is not importable" in record.getMessage()
        for record in caplog.records
    )
