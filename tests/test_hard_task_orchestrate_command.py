"""Tests for the /orchestrate CLI command."""

import queue
from types import SimpleNamespace
from unittest.mock import patch


def _import_cli():
    import hermes_cli.config as config_mod

    if not hasattr(config_mod, "save_env_value_secure"):
        config_mod.save_env_value_secure = lambda key, value: {
            "success": True,
            "stored_as": key,
            "validated": False,
        }

    import cli as cli_mod

    return cli_mod


def test_orchestrate_command_registered():
    from hermes_cli.commands import resolve_command

    cmd = resolve_command("orchestrate")
    assert cmd is not None
    assert cmd.name == "orchestrate"
    assert cmd.args_hint == "<task>"


def test_handle_orchestrate_command_requires_task():
    cli_mod = _import_cli()
    stub = SimpleNamespace(_pending_input=queue.Queue(), _agent_running=False)

    with patch.object(cli_mod, "_cprint") as mock_cprint:
        cli_mod.HermesCLI._handle_orchestrate_command(stub, "/orchestrate")

    assert stub._pending_input.empty()
    printed = " ".join(str(call) for call in mock_cprint.call_args_list)
    assert "Usage: /orchestrate <task>" in printed


def test_handle_orchestrate_command_queues_generated_prompt():
    cli_mod = _import_cli()
    stub = SimpleNamespace(_pending_input=queue.Queue(), _agent_running=False)

    with patch.object(cli_mod, "_cprint"):
        cli_mod.HermesCLI._handle_orchestrate_command(stub, "/orchestrate Ship durable cron monitoring")

    prompt = stub._pending_input.get_nowait()
    assert "Ship durable cron monitoring" in prompt
    assert ".hermes/plans/ship-durable-cron-monitoring.md" in prompt
    assert "hard-task orchestrator" in prompt.lower()
    assert stub._pending_input.empty()
