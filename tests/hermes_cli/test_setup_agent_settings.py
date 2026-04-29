"""Tests for agent-settings copy in the interactive setup wizard."""

from hermes_cli.setup import setup_agent_settings


def test_setup_agent_settings_prefers_config_max_turns_over_stale_env(tmp_path, monkeypatch, capsys):
    """The wizard should not surface stale HERMES_MAX_ITERATIONS when config has max_turns."""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    config = {
        "agent": {"max_turns": 90},
        "display": {"tool_progress": "all"},
        "compression": {"threshold": 0.50},
        "session_reset": {"mode": "both", "idle_minutes": 1440, "at_hour": 4},
    }

    prompt_answers = iter(["90", "all", "0.5"])
    removed_env = []

    monkeypatch.setattr("hermes_cli.setup.get_env_value", lambda key: "60" if key == "HERMES_MAX_ITERATIONS" else "")
    monkeypatch.setattr("hermes_cli.setup.prompt", lambda *args, **kwargs: next(prompt_answers))
    monkeypatch.setattr("hermes_cli.setup.prompt_choice", lambda *args, **kwargs: 4)
    monkeypatch.setattr("hermes_cli.setup.save_env_value", lambda *args, **kwargs: None)
    monkeypatch.setattr("hermes_cli.setup.remove_env_value", lambda key: removed_env.append(key))
    monkeypatch.setattr("hermes_cli.setup.save_config", lambda *args, **kwargs: None)

    setup_agent_settings(config)

    out = capsys.readouterr().out
    assert "Press Enter to keep 90." in out
    assert "Press Enter to keep 60." not in out
    assert removed_env == ["HERMES_MAX_ITERATIONS"]


def test_setup_agent_settings_uses_legacy_env_when_config_missing(tmp_path, monkeypatch, capsys):
    """Legacy env-only installs still get their current max-iteration value as the default."""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    config = {
        "display": {"tool_progress": "all"},
        "compression": {"threshold": 0.50},
        "session_reset": {"mode": "both", "idle_minutes": 1440, "at_hour": 4},
    }

    prompt_answers = iter(["60", "all", "0.5"])
    removed_env = []

    monkeypatch.setattr("hermes_cli.setup.get_env_value", lambda key: "60" if key == "HERMES_MAX_ITERATIONS" else "")
    monkeypatch.setattr("hermes_cli.setup.prompt", lambda *args, **kwargs: next(prompt_answers))
    monkeypatch.setattr("hermes_cli.setup.prompt_choice", lambda *args, **kwargs: 4)
    monkeypatch.setattr("hermes_cli.setup.save_env_value", lambda *args, **kwargs: None)
    monkeypatch.setattr("hermes_cli.setup.remove_env_value", lambda key: removed_env.append(key))
    monkeypatch.setattr("hermes_cli.setup.save_config", lambda *args, **kwargs: None)

    setup_agent_settings(config)

    out = capsys.readouterr().out
    assert "Press Enter to keep 60." in out
    assert config["agent"]["max_turns"] == 60
    assert removed_env == ["HERMES_MAX_ITERATIONS"]
