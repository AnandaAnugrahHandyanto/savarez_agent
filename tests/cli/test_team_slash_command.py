from __future__ import annotations

import json
from unittest.mock import patch

from cli import HermesCLI
from hermes_cli.commands import COMMANDS, COMMAND_REGISTRY, resolve_command


def _make_cli():
    cli = HermesCLI.__new__(HermesCLI)
    cli._app = None
    cli._last_invalidate = 0.0
    cli._command_running = False
    cli._command_status = ""
    return cli


def test_team_slash_command_is_registered_for_cli():
    cmd = resolve_command('team')
    assert cmd is not None
    assert cmd.name == 'team'
    assert cmd.category == 'Tools & Skills'
    assert 'status' in cmd.subcommands
    assert 'run' in cmd.subcommands
    assert 'watch' in cmd.subcommands
    assert 'sandbox' in cmd.subcommands
    assert 'replans' in cmd.subcommands
    assert 'approval-audit' in cmd.subcommands
    assert '/team' in COMMANDS
    assert any(item.name == 'team' for item in COMMAND_REGISTRY)


def test_cli_team_roles_command_prints_roles(capsys):
    cli = _make_cli()
    assert cli.process_command('/team roles') is True
    output = capsys.readouterr().out
    assert 'cio' in output
    assert 'executor' in output
    assert 'reviewer' in output


def test_cli_team_status_command_uses_team_tool(capsys):
    cli = _make_cli()
    with patch('tools.hermes_team_tool.team_status_tool', return_value=json.dumps({'ok': True, 'runs': [], 'count': 0})):
        assert cli.process_command('/team status') is True
    output = capsys.readouterr().out
    assert '"ok": true' in output
    assert '"count": 0' in output


def test_cli_team_run_requires_goal_and_can_call_runner(capsys):
    cli = _make_cli()
    assert cli.process_command('/team run') is True
    assert 'Usage: /team run <goal>' in capsys.readouterr().out

    with patch('tools.hermes_team_tool.team_run_task_tool', return_value=json.dumps({'ok': True, 'result': {'run_id': 'run-cli', 'status': 'completed'}})) as mocked:
        assert cli.process_command('/team run verify cli wrapper') is True
    mocked.assert_called_once()
    args = mocked.call_args.args[0]
    assert args['goal'] == 'verify cli wrapper'
    assert args['roles'] == ['planner', 'executor', 'reviewer']
    output = capsys.readouterr().out
    assert 'run-cli' in output


def test_cli_team_p4_commands_call_underlying_tools(capsys):
    cli = _make_cli()
    with patch('tools.hermes_team_tool.team_watch_tool', return_value='run_id: run-cli\nstatus: completed') as mocked:
        assert cli.process_command('/team watch run-cli') is True
    mocked.assert_called_once()
    assert mocked.call_args.args[0]['run_id'] == 'run-cli'
    assert mocked.call_args.args[0]['format'] == 'text'
    assert 'run-cli' in capsys.readouterr().out

    with patch('tools.hermes_team_tool.team_sandbox_audit_tool', return_value=json.dumps({'ok': True, 'count': 1})) as mocked:
        assert cli.process_command('/team sandbox TSK-CLI') is True
    mocked.assert_called_once()
    assert mocked.call_args.args[0]['task_id'] == 'TSK-CLI'

    with patch('tools.hermes_team_tool.team_replans_tool', return_value=json.dumps({'ok': True, 'count': 0})) as mocked:
        assert cli.process_command('/team replans run-cli') is True
    mocked.assert_called_once()
    assert mocked.call_args.args[0]['run_id'] == 'run-cli'

    with patch('tools.hermes_team_tool.team_approval_audit_tool', return_value=json.dumps({'ok': True, 'audit': {'total': 0}})) as mocked:
        assert cli.process_command('/team approval-audit') is True
    mocked.assert_called_once()