"""Hard blocks for local credential reads.

These tests cover the prompt-injection threat model where untrusted web/X content
tries to make Hermes read local credential stores through file or terminal tools.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

import agent.file_safety as file_safety
from tools.file_tools import read_file_tool, search_tool
from tools.terminal_tool import terminal_tool


@pytest.fixture()
def isolated_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    hermes_home = home / ".hermes"
    hermes_home.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.setattr(file_safety, "_hermes_home_path", lambda: hermes_home)
    return home, hermes_home


@pytest.mark.parametrize(
    "relative_path",
    [
        ".hermes/.env",
        ".hermes/auth.json",
        ".hermes/config.yaml",
        ".hermes/secrets/gcp-service-account.json",
        ".xurl",
        ".ssh/id_ed25519",
        ".aws/credentials",
        ".azure/accessTokens.json",
        ".config/gh/hosts.yml",
        ".netrc",
        ".npmrc",
        "projects/example/.env",
        "projects/example/.env.local",
        "projects/example/.env.production",
    ],
)
def test_sensitive_read_paths_are_hard_blocked(isolated_home, relative_path):
    home, _hermes_home = isolated_home
    err = file_safety.get_read_block_error(str(home / relative_path))

    assert err is not None
    assert "Access denied" in err
    assert "sensitive credential" in err.lower()


@pytest.mark.parametrize(
    "relative_path",
    [
        "projects/example/.env.example",
        "projects/example/.env.sample",
        "projects/example/.env.template",
        "projects/example/README.md",
    ],
)
def test_non_secret_example_files_are_not_hard_blocked(isolated_home, relative_path):
    home, _hermes_home = isolated_home

    assert file_safety.get_read_block_error(str(home / relative_path)) is None


def test_read_file_tool_blocks_sensitive_paths_before_io(isolated_home):
    _home, hermes_home = isolated_home

    with patch("tools.file_tools._get_file_ops") as mock_ops:
        result = json.loads(read_file_tool(str(hermes_home / ".env"), task_id="secret-read"))

    assert "error" in result
    assert "sensitive credential" in result["error"].lower()
    mock_ops.assert_not_called()


def test_search_files_tool_blocks_sensitive_roots_before_io(isolated_home):
    _home, hermes_home = isolated_home

    with patch("tools.file_tools._get_file_ops") as mock_ops:
        result = json.loads(search_tool(".*", path=str(hermes_home / ".env"), task_id="secret-search"))

    assert "error" in result
    assert "sensitive credential" in result["error"].lower()
    mock_ops.assert_not_called()


@pytest.mark.parametrize("root_selector", ["hermes_home", "home", "config"])
def test_search_files_tool_blocks_sensitive_parent_roots_before_io(isolated_home, root_selector):
    home, hermes_home = isolated_home
    root = {
        "hermes_home": hermes_home,
        "home": home,
        "config": home / ".config",
    }[root_selector]

    with patch("tools.file_tools._get_file_ops") as mock_ops:
        result = json.loads(search_tool(".*", path=str(root), task_id=f"secret-search-{root_selector}"))

    assert "error" in result
    assert "sensitive" in result["error"].lower()
    mock_ops.assert_not_called()


def test_read_file_tool_blocks_relative_sensitive_paths_against_live_cwd(isolated_home):
    home, _hermes_home = isolated_home

    with (
        patch("tools.file_tools._get_live_tracking_cwd", return_value=str(home)),
        patch("tools.file_tools._get_file_ops") as mock_ops,
    ):
        result = json.loads(read_file_tool(".ssh/id_ed25519", task_id="relative-secret-read"))

    assert "error" in result
    assert "sensitive credential" in result["error"].lower()
    mock_ops.assert_not_called()


def test_search_files_tool_blocks_relative_sensitive_paths_against_live_cwd(isolated_home):
    home, _hermes_home = isolated_home

    with (
        patch("tools.file_tools._get_live_tracking_cwd", return_value=str(home)),
        patch("tools.file_tools._get_file_ops") as mock_ops,
    ):
        result = json.loads(search_tool(".*", path=".aws/credentials", task_id="relative-secret-search"))

    assert "error" in result
    assert "sensitive credential" in result["error"].lower()
    mock_ops.assert_not_called()


def test_search_files_tool_blocks_project_roots_with_real_env_before_io(isolated_home):
    home, _hermes_home = isolated_home
    project = home / "projects" / "example"
    project.mkdir(parents=True)
    (project / ".env").write_text("FAKE_SECRET=do-not-read\n", encoding="utf-8")

    with patch("tools.file_tools._get_file_ops") as mock_ops:
        result = json.loads(search_tool("FAKE_SECRET", path=str(project), task_id="project-env-search"))

    assert "error" in result
    assert "sensitive" in result["error"].lower()
    mock_ops.assert_not_called()


def test_search_files_tool_allows_project_roots_with_env_examples(isolated_home):
    home, _hermes_home = isolated_home
    project = home / "projects" / "example-template"
    project.mkdir(parents=True)
    (project / ".env.example").write_text("EXAMPLE=value\n", encoding="utf-8")

    assert file_safety.get_search_block_error(str(project)) is None


@pytest.mark.parametrize(
    "command_template",
    [
        "cat {hermes_env}",
        "cat $HERMES_HOME/.env",
        "cat ${{HERMES_HOME}}/auth.json",
        "sed -n '1,20p' {hermes_auth}",
        "python3 -c \"print(open('{xurl}').read())\"",
        "cd ~/.hermes && cat auth.json",
        "cd ~/.ssh && cat id_ed25519",
        "cd ~/.hermes\ncat auth.json",
        "cd ~/.ssh\ncat id_ed25519",
        "cat ~/.azure/accessTokens.json",
        "grep -R token ~/.hermes",
        "rg token ~/.config",
        "bash -lc 'cat ~/.hermes/.env'",
        "sh -c 'cat ~/.ssh/id_ed25519'",
        "/usr/bin/env bash -lc 'cat ~/.hermes/.env'",
        "echo $(cat ~/.hermes/.env)",
        "echo $(python3 -c \"print(open('~/.hermes/.env').read())\")",
        "echo `cat ~/.hermes/.env`",
        "python3 <<'PY'\nprint(open('~/.hermes/.env').read())\nPY",
        "python3.11 -c \"print(open('~/.hermes/.env').read())\"",
        "nodejs -e \"require('fs').readFileSync('~/.hermes/.env','utf8')\"",
        "dd if=~/.ssh/id_ed25519 of=/tmp/out",
        "/usr/bin/env | sort",
        "/usr/bin/env -0 | tr '\\0' '\\n'",
        "printenv -0",
        "cat .env",
        "cat .env.local",
        "cat .env.production.local",
        "env | sort",
        "printenv",
    ],
)
def test_terminal_secret_read_commands_are_hard_blocked(isolated_home, command_template):
    home, hermes_home = isolated_home
    command = command_template.format(
        hermes_env=hermes_home / ".env",
        hermes_auth=hermes_home / "auth.json",
        xurl=home / ".xurl",
    )

    err = file_safety.get_terminal_read_block_error(command)

    assert err is not None
    assert "Access denied" in err
    assert "sensitive" in err.lower()


@pytest.mark.parametrize(
    "command,cwd",
    [
        ("cat .ssh/id_ed25519", "home"),
        ("cat .aws/credentials", "home"),
        ("cat auth.json", "hermes_home"),
    ],
)
def test_terminal_secret_read_commands_resolve_relative_to_cwd(isolated_home, command, cwd):
    home, hermes_home = isolated_home
    cwd_path = home if cwd == "home" else hermes_home

    err = file_safety.get_terminal_read_block_error(command, cwd=str(cwd_path))

    assert err is not None
    assert "Access denied" in err
    assert "sensitive" in err.lower()


@pytest.mark.parametrize(
    "command",
    [
        "cat .env.example",
        "python3 -m pytest tests/tools/test_file_read_guards.py",
        "env FOO=bar python3 scripts/build.py",
        "/usr/bin/env FOO=bar python3 scripts/build.py",
        "bash -lc 'python3 -m pytest tests/tools/test_file_read_guards.py'",
        "printenv PATH",
    ],
)
def test_terminal_guard_allows_common_non_secret_commands(isolated_home, command):
    assert file_safety.get_terminal_read_block_error(command) is None


def test_terminal_tool_blocks_sensitive_reads_before_execution(isolated_home):
    _home, hermes_home = isolated_home

    result = json.loads(terminal_tool(f"cat {hermes_home / '.env'}"))

    assert result["exit_code"] == -1
    assert result["status"] == "error"
    assert "sensitive" in result["error"].lower()


def test_terminal_tool_blocks_relative_sensitive_reads_with_workdir(isolated_home):
    _home, hermes_home = isolated_home

    result = json.loads(terminal_tool("cat auth.json", workdir=str(hermes_home)))

    assert result["exit_code"] == -1
    assert result["status"] == "error"
    assert "sensitive" in result["error"].lower()


def test_terminal_tool_blocks_recursive_project_env_grep_before_execution(isolated_home):
    home, _hermes_home = isolated_home
    project = home / "projects" / "grep-target"
    project.mkdir(parents=True)
    (project / ".env").write_text("FAKE_GREP_SECRET=do-not-read\n", encoding="utf-8")

    result = json.loads(terminal_tool("grep -R FAKE_GREP_SECRET .", workdir=str(project)))

    assert result["exit_code"] == -1
    assert result["status"] == "error"
    assert "sensitive" in result["error"].lower()


@pytest.mark.parametrize("command", ["grep -R FAKE_GREP_SECRET", "rg --hidden FAKE_GREP_SECRET"])
def test_terminal_guard_blocks_implicit_cwd_recursive_searches(isolated_home, command):
    home, _hermes_home = isolated_home
    project = home / "projects" / "implicit-grep-target"
    project.mkdir(parents=True)
    (project / ".env").write_text("FAKE_GREP_SECRET=do-not-read\n", encoding="utf-8")

    err = file_safety.get_terminal_read_block_error(command, cwd=str(project))

    assert err is not None
    assert "sensitive" in err.lower()
