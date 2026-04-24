from types import SimpleNamespace
from unittest.mock import patch

from hermes_cli.config import (
    format_managed_message,
    format_protected_update_message,
    get_managed_system,
    get_protected_update_context,
    recommended_update_command,
)
from hermes_cli.main import cmd_update
from tools.skills_hub import OptionalSkillSource


_PROTECTED_UPDATE_ENVS = (
    "HERMES_ALLOW_PROTECTED_BRANCH_UPDATE",
    "HERMES_PROTECTED_UPDATE_BRANCH",
    "HERMES_PROTECTED_UPDATE_COMMAND",
    "HERMES_PROTECTED_UPDATE_HELPER",
    "HERMES_PROTECTED_UPDATE_REBASE_COMMAND",
)


def _clear_protected_update_env(monkeypatch):
    for name in _PROTECTED_UPDATE_ENVS:
        monkeypatch.delenv(name, raising=False)


def test_get_managed_system_homebrew(monkeypatch):
    monkeypatch.setenv("HERMES_MANAGED", "homebrew")

    assert get_managed_system() == "Homebrew"
    assert recommended_update_command() == "brew upgrade hermes-agent"


def test_format_managed_message_homebrew(monkeypatch):
    monkeypatch.setenv("HERMES_MANAGED", "homebrew")

    message = format_managed_message("update Hermes Agent")

    assert "managed by Homebrew" in message
    assert "brew upgrade hermes-agent" in message


def test_recommended_update_command_defaults_to_hermes_update(monkeypatch):
    monkeypatch.delenv("HERMES_MANAGED", raising=False)
    _clear_protected_update_env(monkeypatch)

    assert recommended_update_command() == "hermes update"


def test_get_protected_update_context_uses_configured_command(monkeypatch, tmp_path):
    _clear_protected_update_env(monkeypatch)
    monkeypatch.setenv("HERMES_PROTECTED_UPDATE_BRANCH", "local/custom-dashboard")
    monkeypatch.setenv(
        "HERMES_PROTECTED_UPDATE_COMMAND",
        "python3 /tmp/protected-update.py --repo /tmp/hermes-agent --branch local/custom-dashboard",
    )
    monkeypatch.setenv("HERMES_PROTECTED_UPDATE_REBASE_COMMAND", "python3 /tmp/rebase-helper.py")

    def fake_run(args, **kwargs):
        if args == ["git", "rev-parse", "--verify", "refs/heads/local/custom-dashboard"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if args == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
            return SimpleNamespace(returncode=0, stdout="local/custom-dashboard\n", stderr="")
        raise AssertionError(f"unexpected subprocess call: {args!r}")

    monkeypatch.setattr("hermes_cli.config.subprocess.run", fake_run)

    context = get_protected_update_context(tmp_path)

    assert context is not None
    assert context["repo"] == str(tmp_path.resolve())
    assert context["protected_branch"] == "local/custom-dashboard"
    assert context["current_branch"] == "local/custom-dashboard"
    assert context["command"].startswith("python3 /tmp/protected-update.py")
    assert context["helper_command"] == "python3 /tmp/rebase-helper.py"


def test_get_protected_update_context_builds_helper_command(monkeypatch, tmp_path):
    _clear_protected_update_env(monkeypatch)
    helper = tmp_path / "protected update.py"
    helper.write_text("# helper\n")
    monkeypatch.setenv("HERMES_PROTECTED_UPDATE_BRANCH", "local/custom-dashboard")
    monkeypatch.setenv("HERMES_PROTECTED_UPDATE_HELPER", str(helper))

    def fake_run(args, **kwargs):
        if args == ["git", "rev-parse", "--verify", "refs/heads/local/custom-dashboard"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if args == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
            return SimpleNamespace(returncode=0, stdout="local/custom-dashboard\n", stderr="")
        raise AssertionError(f"unexpected subprocess call: {args!r}")

    monkeypatch.setattr("hermes_cli.config.subprocess.run", fake_run)

    context = get_protected_update_context(tmp_path)

    assert context is not None
    assert context["helper_path"] == str(helper.resolve())
    assert "protected update.py" in context["command"]
    assert f"--repo {tmp_path.resolve()}" in context["command"]
    assert "--branch local/custom-dashboard" in context["command"]
    assert context["warning"] == ""


def test_get_protected_update_context_fails_closed_when_branch_missing(monkeypatch, tmp_path):
    _clear_protected_update_env(monkeypatch)
    monkeypatch.setenv("HERMES_PROTECTED_UPDATE_BRANCH", "local/custom-dashboard")
    monkeypatch.setenv("HERMES_PROTECTED_UPDATE_COMMAND", "python3 /tmp/protected-update.py")

    def fake_run(args, **kwargs):
        if args == ["git", "rev-parse", "--verify", "refs/heads/local/custom-dashboard"]:
            return SimpleNamespace(returncode=1, stdout="", stderr="missing")
        if args == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
            return SimpleNamespace(returncode=0, stdout="main\n", stderr="")
        raise AssertionError(f"unexpected subprocess call: {args!r}")

    monkeypatch.setattr("hermes_cli.config.subprocess.run", fake_run)

    context = get_protected_update_context(tmp_path)

    assert context is not None
    assert context["command"] == "python3 /tmp/protected-update.py"
    assert "Configured protected branch was not found" in context["warning"]


def test_get_protected_update_context_honors_bypass(monkeypatch, tmp_path):
    _clear_protected_update_env(monkeypatch)
    monkeypatch.setenv("HERMES_PROTECTED_UPDATE_BRANCH", "local/custom-dashboard")
    monkeypatch.setenv("HERMES_PROTECTED_UPDATE_COMMAND", "python3 /tmp/protected-update.py")
    monkeypatch.setenv("HERMES_ALLOW_PROTECTED_BRANCH_UPDATE", "1")

    with patch("hermes_cli.config.subprocess.run") as mock_run:
        assert get_protected_update_context(tmp_path) is None

    assert not mock_run.called


def test_recommended_update_command_prefers_protected_update_controller(monkeypatch):
    monkeypatch.delenv("HERMES_MANAGED", raising=False)
    monkeypatch.setattr(
        "hermes_cli.config.get_protected_update_context",
        lambda project_root=None: {
            "repo": "/tmp/hermes-agent",
            "protected_branch": "local/custom-dashboard",
            "current_branch": "main",
            "command": "python3 /tmp/protected-update.py --repo /tmp/hermes-agent --branch local/custom-dashboard",
            "helper_path": "/tmp/protected-update.py",
        },
    )

    assert recommended_update_command() == (
        "python3 /tmp/protected-update.py --repo /tmp/hermes-agent --branch local/custom-dashboard"
    )


def test_format_protected_update_message_mentions_protected_branch():
    message = format_protected_update_message(
        {
            "repo": "/tmp/hermes-agent",
            "protected_branch": "local/custom-dashboard",
            "current_branch": "main",
            "command": "python3 /tmp/protected-update.py --repo /tmp/hermes-agent --branch local/custom-dashboard",
            "helper_path": "/tmp/protected-update.py",
        },
        action="update Hermes Agent",
    )

    assert "protected local update workflow" in message
    assert "/tmp/hermes-agent" in message
    assert "local/custom-dashboard" in message
    assert "python3 /tmp/protected-update.py" in message


def test_recommended_update_command_avoids_raw_update_when_protected_context_has_no_command(monkeypatch):
    monkeypatch.delenv("HERMES_MANAGED", raising=False)
    monkeypatch.setattr(
        "hermes_cli.config.get_protected_update_context",
        lambda project_root=None: {
            "repo": "/tmp/hermes-agent",
            "protected_branch": "local/custom-dashboard",
            "current_branch": "main",
            "command": "",
        },
    )

    assert recommended_update_command() == "protected local update workflow"


def test_cmd_update_blocks_managed_homebrew(monkeypatch, capsys):
    monkeypatch.setenv("HERMES_MANAGED", "homebrew")

    with patch("hermes_cli.main.subprocess.run") as mock_run:
        cmd_update(SimpleNamespace())

    assert not mock_run.called
    captured = capsys.readouterr()
    assert "managed by Homebrew" in captured.err
    assert "brew upgrade hermes-agent" in captured.err


def test_cmd_update_blocks_protected_update_workflow(monkeypatch, capsys):
    monkeypatch.delenv("HERMES_MANAGED", raising=False)
    monkeypatch.setattr("hermes_cli.config.is_managed", lambda: False)
    monkeypatch.setattr(
        "hermes_cli.config.get_protected_update_context",
        lambda project_root=None: {
            "repo": "/tmp/hermes-agent",
            "protected_branch": "local/custom-dashboard",
            "current_branch": "main",
            "command": "python3 /tmp/protected-update.py --repo /tmp/hermes-agent --branch local/custom-dashboard",
            "helper_path": "/tmp/protected-update.py",
        },
    )

    with patch("hermes_cli.main.subprocess.run") as mock_run:
        cmd_update(SimpleNamespace(gateway=False))

    assert not mock_run.called
    captured = capsys.readouterr()
    assert "protected local update workflow" in captured.err
    assert "local/custom-dashboard" in captured.err
    assert "python3 /tmp/protected-update.py" in captured.err


def test_optional_skill_source_honors_env_override(monkeypatch, tmp_path):
    optional_dir = tmp_path / "optional-skills"
    optional_dir.mkdir()
    monkeypatch.setenv("HERMES_OPTIONAL_SKILLS", str(optional_dir))

    source = OptionalSkillSource()

    assert source._optional_dir == optional_dir
