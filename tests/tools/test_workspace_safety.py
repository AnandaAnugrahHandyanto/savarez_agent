from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from gateway.session_context import clear_session_vars, get_session_env, set_session_vars
from tools.file_tools import patch_tool, write_file_tool
from tools.terminal_tool import terminal_tool
from tools.workspace_safety import check_terminal_side_effect_allowed


@pytest.fixture(autouse=True)
def clean_session_context(monkeypatch):
    for key in (
        "HERMES_SESSION_PLATFORM",
        "HERMES_SESSION_CHAT_ID",
        "HERMES_WORKSPACE_SLUG",
        "HERMES_WORKSPACE_REPO_PATH",
    ):
        monkeypatch.delenv(key, raising=False)
    tokens = set_session_vars()
    clear_session_vars(tokens)
    yield
    clear_session_vars(tokens)


def _git_repo(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / ".git").mkdir()
    return path


def _gateway_session(bound_repo: Path | None = None):
    return set_session_vars(
        platform="matrix",
        chat_id="!room:example.org",
        workspace_slug="example" if bound_repo else "",
        workspace_repo_path=str(bound_repo) if bound_repo else "",
    )


def test_write_blocked_in_wrong_repo(tmp_path):
    bound_repo = _git_repo(tmp_path / "bound")
    other_repo = _git_repo(tmp_path / "other")
    tokens = _gateway_session(bound_repo)
    try:
        result = json.loads(write_file_tool(str(other_repo / "file.txt"), "data"))
    finally:
        clear_session_vars(tokens)

    assert "Blocked repo side effect outside authoritative workspace binding" in result["error"]
    assert not (other_repo / "file.txt").exists()


def test_write_allowed_in_bound_repo(tmp_path):
    bound_repo = _git_repo(tmp_path / "bound")
    target = bound_repo / "file.txt"
    tokens = _gateway_session(bound_repo)
    try:
        result = json.loads(write_file_tool(str(target), "data"))
    finally:
        clear_session_vars(tokens)

    assert result.get("error") in (None, "")
    assert target.read_text() == "data"


def test_unbound_gateway_repo_write_blocked(tmp_path):
    repo = _git_repo(tmp_path / "repo")
    tokens = _gateway_session(None)
    try:
        result = json.loads(write_file_tool(str(repo / "file.txt"), "data"))
    finally:
        clear_session_vars(tokens)

    assert "no authoritative workspace binding" in result["error"]
    assert not (repo / "file.txt").exists()


def test_read_only_and_non_repo_behavior_unchanged(tmp_path):
    non_repo = tmp_path / "scratch" / "file.txt"
    tokens = _gateway_session(None)
    try:
        write_result = json.loads(write_file_tool(str(non_repo), "data"))
        readonly_error = check_terminal_side_effect_allowed("git status", tmp_path)
    finally:
        clear_session_vars(tokens)

    assert write_result.get("error") in (None, "")
    assert non_repo.read_text() == "data"
    assert readonly_error is None


def test_channel_identity_and_workspace_contextvars_coexist(tmp_path):
    bound_repo = _git_repo(tmp_path / "bound")
    tokens = set_session_vars(
        platform="matrix",
        chat_id="!room:example.org",
        channel_identity='{"platform":"matrix","channel_id":"!room:example.org"}',
        workspace_slug="example",
        workspace_repo_path=str(bound_repo),
    )
    try:
        assert get_session_env("HERMES_SESSION_CHANNEL_IDENTITY")
        assert get_session_env("HERMES_WORKSPACE_SLUG") == "example"
        assert get_session_env("HERMES_WORKSPACE_REPO_PATH") == str(bound_repo)
    finally:
        clear_session_vars(tokens)


def test_patch_blocked_in_wrong_repo(tmp_path):
    bound_repo = _git_repo(tmp_path / "bound")
    other_repo = _git_repo(tmp_path / "other")
    target = other_repo / "file.txt"
    target.write_text("old")
    tokens = _gateway_session(bound_repo)
    try:
        result = json.loads(patch_tool(path=str(target), old_string="old", new_string="new"))
    finally:
        clear_session_vars(tokens)

    assert "Blocked repo side effect outside authoritative workspace binding" in result["error"]
    assert target.read_text() == "old"


def test_mutating_git_command_blocked_outside_bound_repo(tmp_path):
    bound_repo = _git_repo(tmp_path / "bound")
    other_repo = _git_repo(tmp_path / "other")
    tokens = _gateway_session(bound_repo)
    try:
        error = check_terminal_side_effect_allowed("git commit -m update", other_repo)
    finally:
        clear_session_vars(tokens)

    assert error is not None
    assert "Blocked repo side effect outside authoritative workspace binding" in error


def test_terminal_tool_blocks_mutating_git_outside_bound_repo(tmp_path, monkeypatch):
    bound_repo = _git_repo(tmp_path / "bound")
    other_repo = _git_repo(tmp_path / "other")
    monkeypatch.setenv("TERMINAL_ENV", "local")
    monkeypatch.setenv("TERMINAL_CWD", str(other_repo))
    tokens = _gateway_session(bound_repo)
    try:
        result = json.loads(terminal_tool("git add file.txt", timeout=5))
    finally:
        clear_session_vars(tokens)

    assert result["status"] == "blocked"
    assert "Blocked repo side effect outside authoritative workspace binding" in result["error"]


def test_read_only_git_command_allowed(tmp_path):
    bound_repo = _git_repo(tmp_path / "bound")
    other_repo = _git_repo(tmp_path / "other")
    tokens = _gateway_session(bound_repo)
    try:
        error = check_terminal_side_effect_allowed("git status --short", other_repo)
    finally:
        clear_session_vars(tokens)

    assert error is None


def test_git_dash_c_wrong_repo_commit_is_blocked(tmp_path):
    bound_repo = _git_repo(tmp_path / "bound")
    other_repo = _git_repo(tmp_path / "other")
    tokens = _gateway_session(bound_repo)
    try:
        error = check_terminal_side_effect_allowed(
            f"git -C {other_repo} commit -m update",
            bound_repo,
        )
    finally:
        clear_session_vars(tokens)

    assert error is not None
    assert "Blocked repo side effect outside authoritative workspace binding" in error


def test_cd_wrong_repo_then_git_commit_is_blocked(tmp_path):
    bound_repo = _git_repo(tmp_path / "bound")
    other_repo = _git_repo(tmp_path / "other")
    tokens = _gateway_session(bound_repo)
    try:
        error = check_terminal_side_effect_allowed(
            f"cd {other_repo} && git commit -m update",
            bound_repo,
        )
    finally:
        clear_session_vars(tokens)

    assert error is not None
    assert "Blocked repo side effect outside authoritative workspace binding" in error


def test_git_fetch_is_guarded_as_repo_side_effect(tmp_path):
    bound_repo = _git_repo(tmp_path / "bound")
    other_repo = _git_repo(tmp_path / "other")
    tokens = _gateway_session(bound_repo)
    try:
        error = check_terminal_side_effect_allowed("git fetch origin", other_repo)
    finally:
        clear_session_vars(tokens)

    assert error is not None
    assert "Blocked repo side effect outside authoritative workspace binding" in error


def test_git_remote_add_is_guarded(tmp_path):
    bound_repo = _git_repo(tmp_path / "bound")
    other_repo = _git_repo(tmp_path / "other")
    tokens = _gateway_session(bound_repo)
    try:
        error = check_terminal_side_effect_allowed(
            "git remote add origin https://example.invalid/repo.git",
            other_repo,
        )
    finally:
        clear_session_vars(tokens)

    assert error is not None
    assert "Blocked repo side effect outside authoritative workspace binding" in error


def test_git_remote_get_url_is_allowed_read_only(tmp_path):
    bound_repo = _git_repo(tmp_path / "bound")
    other_repo = _git_repo(tmp_path / "other")
    tokens = _gateway_session(bound_repo)
    try:
        error = check_terminal_side_effect_allowed("git remote get-url origin", other_repo)
    finally:
        clear_session_vars(tokens)

    assert error is None


def test_git_branch_set_upstream_is_guarded(tmp_path):
    bound_repo = _git_repo(tmp_path / "bound")
    other_repo = _git_repo(tmp_path / "other")
    tokens = _gateway_session(bound_repo)
    try:
        error = check_terminal_side_effect_allowed(
            "git branch --set-upstream-to origin/main",
            other_repo,
        )
    finally:
        clear_session_vars(tokens)

    assert error is not None
    assert "Blocked repo side effect outside authoritative workspace binding" in error


def test_git_explicit_git_dir_fails_closed_even_from_bound_repo(tmp_path):
    bound_repo = _git_repo(tmp_path / "bound")
    other_repo = _git_repo(tmp_path / "other")
    tokens = _gateway_session(bound_repo)
    try:
        error = check_terminal_side_effect_allowed(
            f"git --git-dir={other_repo / '.git'} commit -m update",
            bound_repo,
        )
    finally:
        clear_session_vars(tokens)

    assert error is not None
    assert "cannot verify the target repository" in error


def test_complex_cd_before_git_fails_closed(tmp_path):
    bound_repo = _git_repo(tmp_path / "bound")
    other_repo = _git_repo(tmp_path / "other")
    tokens = _gateway_session(bound_repo)
    try:
        error = check_terminal_side_effect_allowed(
            f"cd {other_repo} extra && git commit -m update",
            bound_repo,
        )
    finally:
        clear_session_vars(tokens)

    assert error is not None
    assert "cannot verify the target repository" in error


def test_absolute_git_binary_wrong_repo_commit_is_blocked(tmp_path):
    bound_repo = _git_repo(tmp_path / "bound")
    other_repo = _git_repo(tmp_path / "other")
    tokens = _gateway_session(bound_repo)
    try:
        error = check_terminal_side_effect_allowed(
            "/usr/bin/git commit -m update",
            other_repo,
        )
    finally:
        clear_session_vars(tokens)

    assert error is not None
    assert "Blocked repo side effect outside authoritative workspace binding" in error


def test_git_config_core_worktree_fails_closed(tmp_path):
    bound_repo = _git_repo(tmp_path / "bound")
    other_repo = _git_repo(tmp_path / "other")
    tokens = _gateway_session(bound_repo)
    try:
        error = check_terminal_side_effect_allowed(
            f"git -c core.worktree={other_repo} commit -m update",
            bound_repo,
        )
    finally:
        clear_session_vars(tokens)

    assert error is not None
    assert "cannot verify the target repository" in error


def test_git_inline_config_core_worktree_fails_closed(tmp_path):
    bound_repo = _git_repo(tmp_path / "bound")
    other_repo = _git_repo(tmp_path / "other")
    tokens = _gateway_session(bound_repo)
    try:
        error = check_terminal_side_effect_allowed(
            f"git -ccore.worktree={other_repo} commit -m update",
            bound_repo,
        )
    finally:
        clear_session_vars(tokens)

    assert error is not None
    assert "cannot verify the target repository" in error


def test_git_config_env_core_worktree_fails_closed(tmp_path):
    bound_repo = _git_repo(tmp_path / "bound")
    other_repo = _git_repo(tmp_path / "other")
    tokens = _gateway_session(bound_repo)
    try:
        error = check_terminal_side_effect_allowed(
            "GIT_CONFIG_COUNT=1 "
            "GIT_CONFIG_KEY_0=core.worktree "
            f"GIT_CONFIG_VALUE_0={other_repo} "
            "git commit -m update",
            bound_repo,
        )
    finally:
        clear_session_vars(tokens)

    assert error is not None
    assert "cannot verify the target repository" in error


def test_git_config_env_option_core_worktree_fails_closed(tmp_path):
    bound_repo = _git_repo(tmp_path / "bound")
    tokens = _gateway_session(bound_repo)
    try:
        error = check_terminal_side_effect_allowed(
            "git --config-env core.worktree=WORKTREE_FROM_ENV commit -m update",
            bound_repo,
        )
    finally:
        clear_session_vars(tokens)

    assert error is not None
    assert "cannot verify the target repository" in error


def test_git_config_include_path_fails_closed(tmp_path):
    bound_repo = _git_repo(tmp_path / "bound")
    config_file = tmp_path / "unsafe.gitconfig"
    config_file.write_text("[core]\nworktree = /tmp/other\n", encoding="utf-8")
    tokens = _gateway_session(bound_repo)
    try:
        error = check_terminal_side_effect_allowed(
            f"git -c include.path={config_file} commit -m update",
            bound_repo,
        )
    finally:
        clear_session_vars(tokens)

    assert error is not None
    assert "cannot verify the target repository" in error


def test_git_config_include_if_path_fails_closed(tmp_path):
    bound_repo = _git_repo(tmp_path / "bound")
    config_file = tmp_path / "unsafe.gitconfig"
    config_file.write_text("[core]\nworktree = /tmp/other\n", encoding="utf-8")
    tokens = _gateway_session(bound_repo)
    try:
        error = check_terminal_side_effect_allowed(
            f"git -c includeIf.gitdir:{bound_repo}/.path={config_file} commit -m update",
            bound_repo,
        )
    finally:
        clear_session_vars(tokens)

    assert error is not None
    assert "cannot verify the target repository" in error


def test_git_dir_env_assignment_fails_closed(tmp_path):
    bound_repo = _git_repo(tmp_path / "bound")
    other_repo = _git_repo(tmp_path / "other")
    tokens = _gateway_session(bound_repo)
    try:
        error = check_terminal_side_effect_allowed(
            f"GIT_DIR={other_repo / '.git'} GIT_WORK_TREE={other_repo} git commit -m update",
            bound_repo,
        )
    finally:
        clear_session_vars(tokens)

    assert error is not None
    assert "cannot verify the target repository" in error


def test_env_git_dir_assignment_fails_closed(tmp_path):
    bound_repo = _git_repo(tmp_path / "bound")
    other_repo = _git_repo(tmp_path / "other")
    tokens = _gateway_session(bound_repo)
    try:
        error = check_terminal_side_effect_allowed(
            f"env GIT_DIR={other_repo / '.git'} GIT_WORK_TREE={other_repo} git commit -m update",
            bound_repo,
        )
    finally:
        clear_session_vars(tokens)

    assert error is not None
    assert "cannot verify the target repository" in error


def test_git_dash_c_with_shell_var_fails_closed(tmp_path):
    bound_repo = _git_repo(tmp_path / "bound")
    tokens = _gateway_session(bound_repo)
    try:
        error = check_terminal_side_effect_allowed(
            'git -C "$HOME/wrong-repo" commit -m update',
            bound_repo,
        )
    finally:
        clear_session_vars(tokens)

    assert error is not None
    assert "cannot verify the target repository" in error


def test_cd_with_tilde_before_git_mutation_fails_closed(tmp_path):
    bound_repo = _git_repo(tmp_path / "bound")
    tokens = _gateway_session(bound_repo)
    try:
        error = check_terminal_side_effect_allowed(
            "cd ~/wrong-repo && git commit -m update",
            bound_repo,
        )
    finally:
        clear_session_vars(tokens)

    assert error is not None
    assert "cannot verify the target repository" in error


def test_second_git_invocation_wrong_repo_is_blocked(tmp_path):
    bound_repo = _git_repo(tmp_path / "bound")
    other_repo = _git_repo(tmp_path / "other")

    tokens = _gateway_session(bound_repo)
    try:
        error = check_terminal_side_effect_allowed(
            f"git add README.md; git -C {other_repo} commit -m oops",
            bound_repo,
        )
    finally:
        clear_session_vars(tokens)

    assert error is not None
    assert "outside authoritative workspace binding" in error


def test_allowed_first_git_then_cd_wrong_repo_git_is_blocked(tmp_path):
    bound_repo = _git_repo(tmp_path / "bound")
    other_repo = _git_repo(tmp_path / "other")

    tokens = _gateway_session(bound_repo)
    try:
        error = check_terminal_side_effect_allowed(
            f"git status; cd {other_repo} && git commit -m oops",
            bound_repo,
        )
    finally:
        clear_session_vars(tokens)

    assert error is not None
    assert "outside authoritative workspace binding" in error


def test_non_repo_git_mutation_does_not_short_circuit_later_wrong_repo(tmp_path):
    bound_repo = _git_repo(tmp_path / "bound")
    other_repo = _git_repo(tmp_path / "other")
    scratch = tmp_path / "scratch"
    scratch.mkdir()

    tokens = _gateway_session(bound_repo)
    try:
        error = check_terminal_side_effect_allowed(
            f"cd {scratch} && git add README.md; git -C {other_repo} commit -m oops",
            bound_repo,
        )
    finally:
        clear_session_vars(tokens)

    assert error is not None
    assert "outside authoritative workspace binding" in error


def test_git_config_alias_shell_fails_closed(tmp_path):
    bound_repo = _git_repo(tmp_path / "bound")
    other_repo = _git_repo(tmp_path / "other")

    tokens = _gateway_session(bound_repo)
    try:
        error = check_terminal_side_effect_allowed(
            f"git -c alias.ci='!git -C {other_repo} commit -m oops' ci",
            bound_repo,
        )
    finally:
        clear_session_vars(tokens)

    assert error is not None
    assert "cannot verify the target repository" in error


def test_unknown_git_subcommand_alias_fails_closed_from_bound_repo(tmp_path):
    bound_repo = _git_repo(tmp_path / "bound")

    tokens = _gateway_session(bound_repo)
    try:
        error = check_terminal_side_effect_allowed("git ci", bound_repo)
    finally:
        clear_session_vars(tokens)

    assert error is not None
    assert "cannot verify the target repository" in error


def test_conventional_commit_message_with_parentheses_allowed_in_bound_repo(tmp_path):
    bound_repo = _git_repo(tmp_path / "bound")
    tokens = _gateway_session(bound_repo)
    try:
        error = check_terminal_side_effect_allowed(
            'git commit -m "fix(matrix): preserve named room identity"',
            bound_repo,
        )
    finally:
        clear_session_vars(tokens)

    assert error is None


def test_subshell_cd_wrong_repo_fails_closed(tmp_path):
    bound_repo = _git_repo(tmp_path / "bound")
    other_repo = _git_repo(tmp_path / "other")
    tokens = _gateway_session(bound_repo)
    try:
        error = check_terminal_side_effect_allowed(
            f"(cd {other_repo} && git commit -m update)",
            bound_repo,
        )
    finally:
        clear_session_vars(tokens)

    assert error is not None
    assert "cannot verify the target repository" in error
