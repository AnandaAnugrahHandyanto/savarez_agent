from unittest.mock import MagicMock

import cli as cli_module


def _make_cli():
    from cli import HermesCLI

    cli = object.__new__(HermesCLI)
    cli.active_workspace = "people"
    return cli


def test_cli_people_workspace_intercepts(monkeypatch):
    cli = _make_cli()

    monkeypatch.setattr("cli.handle_people_message", lambda text, lane_id, workspace: "Profile updated")

    result = cli._maybe_handle_people_manager_input("Update Alice Chen: shipped memo")

    assert result == "Profile updated"


def test_cli_non_people_workspace_does_not_intercept(monkeypatch):
    cli = _make_cli()
    cli.active_workspace = "speech"
    fake = MagicMock(return_value="should not be used")
    monkeypatch.setattr("cli.handle_people_message", fake)

    result = cli._maybe_handle_people_manager_input("Update Alice Chen: shipped memo")

    assert result is None
    fake.assert_not_called()


def test_cli_unmatched_text_falls_through(monkeypatch):
    cli = _make_cli()
    monkeypatch.setattr("cli.handle_people_message", lambda text, lane_id, workspace: None)

    result = cli._maybe_handle_people_manager_input("Alice seems good")

    assert result is None



def test_cli_people_workspace_fastpath_intercepts_adhoc_1o1_prep(monkeypatch):
    cli = _make_cli()

    monkeypatch.setattr("cli.handle_people_message", lambda text, lane_id, workspace: "Fiona Cao 1:1\n- family summer travels")

    result = cli._maybe_handle_people_manager_input("1o1 prep Fiona")

    assert result.startswith("Fiona Cao 1:1")


def test_workspace_switch_is_session_only(monkeypatch):
    cli = _make_cli()
    cli.personalities = {}
    cli.system_prompt = "Base prompt"
    cli.agent = object()
    called = []

    monkeypatch.setattr(cli_module, "_cprint", lambda *args, **kwargs: None)
    cli.new_session = lambda: called.append("new_session")

    cli._handle_workspace_switch_command("people")

    assert cli.active_workspace == "people"
    assert cli.system_prompt == cli._default_workspace_prompt("people")
    assert cli.agent is None
    assert called == ["new_session"]


def test_personality_command_clears_active_workspace(monkeypatch):
    cli = _make_cli()
    cli.personalities = {"coach": "Coach prompt"}
    cli.system_prompt = "People prompt"
    cli.agent = object()

    monkeypatch.setattr(cli_module, "save_config_value", lambda *args, **kwargs: True)
    monkeypatch.setattr("builtins.print", lambda *args, **kwargs: None)

    cli._handle_personality_command("/personality coach")

    assert cli.active_workspace is None
    assert cli.system_prompt == "Coach prompt"
