from pathlib import Path

import pytest

from symphony.errors import SymphonyError
from symphony.workspace import prepare_workspace, run_hook, sanitize_issue_identifier, workspace_path


def test_sanitize_issue_identifier_replaces_disallowed_chars_deterministically():
    assert sanitize_issue_identifier("ABC/123: x") == "ABC_123__x"
    assert sanitize_issue_identifier("ok.A_B-9") == "ok.A_B-9"
    assert sanitize_issue_identifier("日本語💡") == "____"


def test_workspace_path_returns_sanitized_path_under_root(tmp_path):
    root = tmp_path / "workspaces"

    path = workspace_path(root, "ABC/123: x")

    assert path == root / "ABC_123__x"
    assert path.resolve(strict=False).is_relative_to(root.resolve(strict=False))


@pytest.mark.parametrize("issue_identifier", ["../outside", "../../etc/passwd", "/tmp/evil"])
def test_workspace_path_traversal_identifiers_cannot_escape_root(tmp_path, issue_identifier):
    root = tmp_path / "workspaces"

    path = workspace_path(root, issue_identifier)

    assert path.resolve(strict=False).is_relative_to(root.resolve(strict=False))
    assert ".." not in path.relative_to(root).parts


def test_workspace_path_raises_stable_error_for_dotdot_identifier(tmp_path):
    root = tmp_path / "workspaces"

    with pytest.raises(SymphonyError) as exc_info:
        workspace_path(root, "..")

    assert exc_info.value.code == "invalid_workspace_cwd"


def test_workspace_path_raises_stable_error_if_containment_is_violated(tmp_path):
    root = tmp_path / "root"

    with pytest.raises(SymphonyError) as exc_info:
        workspace_path(root, "issue", sanitizer=lambda _value: "../escaped")

    assert exc_info.value.code == "invalid_workspace_cwd"


def test_prepare_workspace_creates_workspace_and_evidence_dir(tmp_path):
    prepared = prepare_workspace(tmp_path / "workspaces", "ABC/123: x")

    assert prepared.path == tmp_path / "workspaces" / "ABC_123__x"
    assert prepared.path.is_dir()
    assert prepared.evidence_dir == prepared.path / ".symphony" / "evidence"
    assert prepared.evidence_dir.is_dir()


def test_run_hook_invokes_runner_with_command_and_cwd(tmp_path):
    calls = []

    def fake_runner(command, cwd):
        calls.append((command, cwd))
        return 0

    result = run_hook("after_create", "setup.sh", tmp_path, runner=fake_runner)

    assert result == 0
    assert calls == [("setup.sh", tmp_path)]


@pytest.mark.parametrize("hook_name", ["after_create", "before_run"])
def test_fatal_hook_failure_raises_symphony_error(tmp_path, hook_name):
    def failing_runner(command, cwd):
        return 7

    with pytest.raises(SymphonyError) as exc_info:
        run_hook(hook_name, "false", tmp_path, fatal=True, runner=failing_runner)

    assert exc_info.value.code == "hook_failed"
    assert hook_name in exc_info.value.message


@pytest.mark.parametrize("hook_name", ["after_run", "before_remove"])
def test_nonfatal_hook_failure_is_logged_and_ignored(tmp_path, caplog, hook_name):
    def failing_runner(command, cwd):
        return 3

    result = run_hook(hook_name, "false", tmp_path, fatal=False, runner=failing_runner)

    assert result == 3
    assert "failed" in caplog.text
    assert hook_name in caplog.text


@pytest.mark.parametrize("hook_name", ["after_run", "before_remove"])
def test_nonfatal_lifecycle_hooks_are_nonfatal_by_default(tmp_path, caplog, hook_name):
    def failing_runner(command, cwd):
        return 3

    result = run_hook(hook_name, "false", tmp_path, runner=failing_runner)

    assert result == 3
    assert hook_name in caplog.text


def test_fatal_hook_runner_exception_raises_symphony_error(tmp_path):
    def exploding_runner(command, cwd):
        raise RuntimeError("boom")

    with pytest.raises(SymphonyError) as exc_info:
        run_hook("before_run", "explode", tmp_path, fatal=True, runner=exploding_runner)

    assert exc_info.value.code == "hook_failed"
    assert "boom" in exc_info.value.message


def test_nonfatal_hook_runner_exception_is_logged_and_ignored(tmp_path, caplog):
    def exploding_runner(command, cwd):
        raise RuntimeError("boom")

    result = run_hook("after_run", "explode", tmp_path, fatal=False, runner=exploding_runner)

    assert result is None
    assert "boom" in caplog.text
