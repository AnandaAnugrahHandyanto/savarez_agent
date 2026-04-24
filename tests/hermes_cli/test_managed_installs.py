from types import SimpleNamespace
from unittest.mock import patch

from hermes_cli.config import (
    format_managed_message,
    format_protected_update_message,
    get_managed_system,
    recommended_update_command,
)
from hermes_cli.main import cmd_update
from tools.skills_hub import OptionalSkillSource


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
    monkeypatch.setattr("hermes_cli.config.get_protected_update_context", lambda project_root=None: None)

    assert recommended_update_command() == "hermes update"


def test_recommended_update_command_prefers_protected_branch_controller(monkeypatch):
    monkeypatch.delenv("HERMES_MANAGED", raising=False)
    monkeypatch.setattr(
        "hermes_cli.config.get_protected_update_context",
        lambda project_root=None: {
            "repo": "/tmp/hermes-agent",
            "protected_branch": "local/dashboard-kinni-custom",
            "current_branch": "main",
            "command": "python3 /tmp/hermes_protected_auto_update.py --repo /tmp/hermes-agent --branch local/dashboard-kinni-custom",
            "helper_path": "/tmp/hermes_protected_auto_update.py",
        },
    )

    assert recommended_update_command() == (
        "python3 /tmp/hermes_protected_auto_update.py --repo /tmp/hermes-agent --branch local/dashboard-kinni-custom"
    )


def test_format_protected_update_message_mentions_protected_branch():
    message = format_protected_update_message(
        {
            "repo": "/tmp/hermes-agent",
            "protected_branch": "local/dashboard-kinni-custom",
            "current_branch": "main",
            "command": "python3 /tmp/hermes_protected_auto_update.py --repo /tmp/hermes-agent --branch local/dashboard-kinni-custom",
            "helper_path": "/tmp/hermes_protected_auto_update.py",
        },
        action="update Hermes Agent",
    )

    assert "protected branch workflow" in message
    assert "local/dashboard-kinni-custom" in message
    assert "python3 /tmp/hermes_protected_auto_update.py" in message


def test_cmd_update_blocks_managed_homebrew(monkeypatch, capsys):
    monkeypatch.setenv("HERMES_MANAGED", "homebrew")

    with patch("hermes_cli.main.subprocess.run") as mock_run:
        cmd_update(SimpleNamespace())

    assert not mock_run.called
    captured = capsys.readouterr()
    assert "managed by Homebrew" in captured.err
    assert "brew upgrade hermes-agent" in captured.err


def test_cmd_update_blocks_protected_branch_workflow(monkeypatch, capsys):
    monkeypatch.delenv("HERMES_MANAGED", raising=False)
    monkeypatch.setattr("hermes_cli.config.is_managed", lambda: False)
    monkeypatch.setattr(
        "hermes_cli.config.get_protected_update_context",
        lambda project_root=None: {
            "repo": "/tmp/hermes-agent",
            "protected_branch": "local/dashboard-kinni-custom",
            "current_branch": "main",
            "command": "python3 /tmp/hermes_protected_auto_update.py --repo /tmp/hermes-agent --branch local/dashboard-kinni-custom",
            "helper_path": "/tmp/hermes_protected_auto_update.py",
        },
    )

    with patch("hermes_cli.main.subprocess.run") as mock_run:
        cmd_update(SimpleNamespace(gateway=False))

    assert not mock_run.called
    captured = capsys.readouterr()
    assert "protected branch workflow" in captured.err
    assert "local/dashboard-kinni-custom" in captured.err
    assert "python3 /tmp/hermes_protected_auto_update.py" in captured.err


def test_optional_skill_source_honors_env_override(monkeypatch, tmp_path):
    optional_dir = tmp_path / "optional-skills"
    optional_dir.mkdir()
    monkeypatch.setenv("HERMES_OPTIONAL_SKILLS", str(optional_dir))

    source = OptionalSkillSource()

    assert source._optional_dir == optional_dir
