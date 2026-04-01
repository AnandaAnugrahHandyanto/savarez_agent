"""Tests for remote-agent management inside `hermes setup`."""

from argparse import Namespace
import sys


def _make_setup_args(**overrides):
    return Namespace(
        non_interactive=overrides.get("non_interactive", False),
        section=overrides.get("section", None),
        reset=overrides.get("reset", False),
    )


def test_cli_setup_remote_section_is_parsed(monkeypatch):
    """`hermes setup remote` should parse and route to cmd_setup with section='remote'."""
    from hermes_cli.main import main

    captured = {}

    def fake_cmd_setup(args):
        captured["section"] = args.section
        captured["non_interactive"] = args.non_interactive

    monkeypatch.setattr("hermes_cli.main.cmd_setup", fake_cmd_setup)
    monkeypatch.setattr(sys, "argv", ["hermes", "setup", "remote", "--non-interactive"])

    main()

    assert captured["section"] == "remote"
    assert captured["non_interactive"] is True


def test_run_setup_wizard_remote_section_dispatches(monkeypatch):
    """Section-specific setup should dispatch the remote-agents section function."""
    from hermes_cli import setup as setup_mod

    called = {"remote": False, "saved": False}

    def fake_remote(config):
        called["remote"] = True
        config.setdefault("remote_agents", {})["demo"] = {"endpoint": "http://demo/v1"}

    monkeypatch.setattr(setup_mod, "ensure_hermes_home", lambda: None)
    monkeypatch.setattr(setup_mod, "load_config", lambda: {})
    monkeypatch.setattr(setup_mod, "get_hermes_home", lambda: "/tmp/.hermes")
    monkeypatch.setattr(setup_mod, "is_interactive_stdin", lambda: True)
    monkeypatch.setattr(setup_mod, "save_config", lambda cfg: called.__setitem__("saved", True))
    monkeypatch.setattr(
        setup_mod,
        "SETUP_SECTIONS",
        [("remote", "Remote Agents", fake_remote)],
    )

    args = _make_setup_args(section="remote")
    setup_mod.run_setup_wizard(args)

    assert called["remote"] is True
    assert called["saved"] is True


def test_setup_remote_agents_select_existing_then_remove(monkeypatch):
    """Selecting an existing remote agent should allow removing it."""
    from hermes_cli import setup as setup_mod

    config = {
        "remote_agents": {
            "bsha": {
                "endpoint": "http://bsha:8080/v1",
                "api_key": "${BSHA_API_KEY}",
                "model": "hermes-agent",
                "timeout": 300,
                "description": "BSHA remote Hermes",
            }
        }
    }

    # Main menu: select existing agent (0)
    # Agent submenu: remove (1)
    # Main menu again with no agents: back (1)
    choice_values = iter([0, 1, 1])

    monkeypatch.setattr(setup_mod, "prompt_choice", lambda *args, **kwargs: next(choice_values))
    monkeypatch.setattr(setup_mod, "prompt_yes_no", lambda *args, **kwargs: True)

    setup_mod.setup_remote_agents(config)

    assert config.get("remote_agents", {}) == {}


def test_setup_remote_agents_add_hides_api_key_input(monkeypatch):
    """API key prompt should use password input (hidden characters)."""
    from hermes_cli import setup as setup_mod

    config = {}
    captured_password_flags = []

    # No agents yet => menu is [Add new remote agent, Back]
    # Choose add (0), then back (2) once an agent exists
    choice_values = iter([0, 2])

    prompt_values = iter([
        "bsha",
        "http://bsha:8080/v1",
        "${BSHA_API_KEY}",
        "hermes-agent",
        "300",
        "BSHA remote Hermes",
    ])

    def fake_prompt(question, default=None, password=False):
        captured_password_flags.append((question, password))
        return next(prompt_values)

    monkeypatch.setattr(setup_mod, "prompt_choice", lambda *args, **kwargs: next(choice_values))
    monkeypatch.setattr(setup_mod, "prompt", fake_prompt)

    setup_mod.setup_remote_agents(config)

    api_key_prompt = next((flag for q, flag in captured_password_flags if "API key" in q), None)
    assert api_key_prompt is True
    assert "bsha" in config.get("remote_agents", {})
