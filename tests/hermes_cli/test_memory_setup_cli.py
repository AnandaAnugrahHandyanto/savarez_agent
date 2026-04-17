import argparse
from unittest import mock

import hermes_cli.main as cli_main
import hermes_cli.memory_setup as memory_setup


def test_main_accepts_memory_setup_provider_arg(monkeypatch):
    captured = {}

    monkeypatch.setattr("hermes_cli.config.get_container_exec_info", lambda: None)

    def fake_memory_command(args):
        captured["memory_command"] = args.memory_command
        captured["provider_name"] = getattr(args, "provider_name", None)

    monkeypatch.setattr("hermes_cli.memory_setup.memory_command", fake_memory_command)

    with mock.patch("sys.argv", ["hermes", "memory", "setup", "rasputin"]):
        cli_main.main()

    assert captured == {
        "memory_command": "setup",
        "provider_name": "rasputin",
    }


def test_memory_command_routes_direct_provider_setup(monkeypatch):
    called = {}

    def fake_cmd_setup_provider(provider_name):
        called["provider_name"] = provider_name

    def fake_cmd_setup(args):
        called["interactive"] = True

    monkeypatch.setattr(memory_setup, "cmd_setup_provider", fake_cmd_setup_provider)
    monkeypatch.setattr(memory_setup, "cmd_setup", fake_cmd_setup)

    args = argparse.Namespace(memory_command="setup", provider_name="rasputin")
    memory_setup.memory_command(args)

    assert called == {"provider_name": "rasputin"}
