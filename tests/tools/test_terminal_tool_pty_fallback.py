import json
from types import SimpleNamespace

import tools.terminal_tool as terminal_tool_module
from tools import process_registry as process_registry_module


def _base_config(tmp_path):
    return {
        "env_type": "local",
        "docker_image": "",
        "singularity_image": "",
        "modal_image": "",
        "daytona_image": "",
        "cwd": str(tmp_path),
        "timeout": 30,
    }


def test_command_requires_pipe_stdin_detects_gh_with_token():
    assert terminal_tool_module._command_requires_pipe_stdin(
        "gh auth login --hostname github.com --git-protocol https --with-token"
    ) is True
    assert terminal_tool_module._command_requires_pipe_stdin(
        "gh auth login --web"
    ) is False


def test_terminal_background_disables_pty_for_gh_with_token(monkeypatch, tmp_path):
    config = _base_config(tmp_path)
    dummy_env = SimpleNamespace(env={})
    captured = {}

    def fake_spawn_local(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(id="proc_test", pid=1234, notify_on_complete=False)

    monkeypatch.setattr(terminal_tool_module, "_get_env_config", lambda: config)
    monkeypatch.setattr(terminal_tool_module, "_start_cleanup_thread", lambda: None)
    monkeypatch.setattr(terminal_tool_module, "_check_all_guards", lambda *_args, **_kwargs: {"approved": True})
    monkeypatch.setattr(process_registry_module.process_registry, "spawn_local", fake_spawn_local)
    monkeypatch.setitem(terminal_tool_module._active_environments, "default", dummy_env)
    monkeypatch.setitem(terminal_tool_module._last_activity, "default", 0.0)

    try:
        result = json.loads(
            terminal_tool_module.terminal_tool(
                command="gh auth login --hostname github.com --git-protocol https --with-token",
                background=True,
                pty=True,
            )
        )
    finally:
        terminal_tool_module._active_environments.pop("default", None)
        terminal_tool_module._last_activity.pop("default", None)

    assert captured["use_pty"] is False
    assert result["session_id"] == "proc_test"
    assert "PTY disabled" in result["pty_note"]


def test_terminal_background_keeps_pty_for_regular_interactive_commands(monkeypatch, tmp_path):
    config = _base_config(tmp_path)
    dummy_env = SimpleNamespace(env={})
    captured = {}

    def fake_spawn_local(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(id="proc_test", pid=1234, notify_on_complete=False)

    monkeypatch.setattr(terminal_tool_module, "_get_env_config", lambda: config)
    monkeypatch.setattr(terminal_tool_module, "_start_cleanup_thread", lambda: None)
    monkeypatch.setattr(terminal_tool_module, "_check_all_guards", lambda *_args, **_kwargs: {"approved": True})
    monkeypatch.setattr(process_registry_module.process_registry, "spawn_local", fake_spawn_local)
    monkeypatch.setitem(terminal_tool_module._active_environments, "default", dummy_env)
    monkeypatch.setitem(terminal_tool_module._last_activity, "default", 0.0)

    try:
        result = json.loads(
            terminal_tool_module.terminal_tool(
                command="python3 -c \"print(input())\"",
                background=True,
                pty=True,
            )
        )
    finally:
        terminal_tool_module._active_environments.pop("default", None)
        terminal_tool_module._last_activity.pop("default", None)

    assert captured["use_pty"] is True
    assert "pty_note" not in result


def test_should_preserve_on_restart_matches_top_level_codex_and_claude():
    assert terminal_tool_module._should_preserve_on_restart(
        "codex --version", background=True, pty=True, env_type="local"
    ) is True
    assert terminal_tool_module._should_preserve_on_restart(
        "cd /tmp && claude", background=True, pty=True, env_type="local"
    ) is True
    assert terminal_tool_module._should_preserve_on_restart(
        "export https_proxy=http://127.0.0.1:8080 && codex exec", background=True, pty=True, env_type="local"
    ) is True
    assert terminal_tool_module._should_preserve_on_restart(
        "env FOO=bar BAR=baz codex exec", background=True, pty=True, env_type="local"
    ) is True


def test_should_preserve_on_restart_ignores_wrappers_and_echo():
    assert terminal_tool_module._should_preserve_on_restart(
        "echo codex", background=True, pty=True, env_type="local"
    ) is False
    assert terminal_tool_module._should_preserve_on_restart(
        "bash -lc 'codex --help'", background=True, pty=True, env_type="local"
    ) is False


def test_terminal_background_marks_codex_session_preserved(monkeypatch, tmp_path):
    config = _base_config(tmp_path)
    dummy_env = SimpleNamespace(env={})
    session = SimpleNamespace(
        id="proc_test",
        pid=1234,
        notify_on_complete=False,
        output_path="/tmp/process-output/proc_test.log",
    )

    def fake_spawn_local(**_kwargs):
        return session

    monkeypatch.setattr(terminal_tool_module, "_get_env_config", lambda: config)
    monkeypatch.setattr(terminal_tool_module, "_start_cleanup_thread", lambda: None)
    monkeypatch.setattr(terminal_tool_module, "_check_all_guards", lambda *_args, **_kwargs: {"approved": True})
    monkeypatch.setattr(process_registry_module.process_registry, "spawn_local", fake_spawn_local)
    monkeypatch.setitem(terminal_tool_module._active_environments, "default", dummy_env)
    monkeypatch.setitem(terminal_tool_module._last_activity, "default", 0.0)

    try:
        result = json.loads(
            terminal_tool_module.terminal_tool(
                command="cd /tmp && codex",
                background=True,
                pty=True,
            )
        )
    finally:
        terminal_tool_module._active_environments.pop("default", None)
        terminal_tool_module._last_activity.pop("default", None)

    assert result["preserve_on_restart"] is True
    assert result["log_path"] == "/tmp/process-output/proc_test.log"
    assert session.preserve_on_restart is True
