import sys
from argparse import Namespace

import pytest


@pytest.fixture()
def project_env(tmp_path, monkeypatch):
    hermes_home = tmp_path / '.hermes'
    hermes_home.mkdir()
    monkeypatch.setenv('HERMES_HOME', str(hermes_home))
    return hermes_home


def test_project_list_empty(project_env, capsys):
    from hermes_cli.projects import project_command

    rc = project_command(Namespace(project_action='list', project_id=None, name=None, summary=None, repo_path=None))
    out = capsys.readouterr().out

    assert rc == 0
    assert 'No projects found' in out


def test_project_init_creates_project_cell(project_env):
    from hermes_cli.projects import project_command

    rc = project_command(
        Namespace(
            project_action='init',
            project_id='alpha',
            name='Alpha',
            summary='Alpha project summary',
            repo_path=None,
        )
    )

    assert rc == 0
    project_dir = project_env / 'project-os-v1' / 'projects' / 'alpha'
    assert (project_dir / 'project.yaml').exists()
    assert (project_dir / 'brief.md').exists()
    assert (project_dir / 'reports' / '00-executive-summary.md').exists()
    assert (project_dir / 'tasks' / 'next-actions.md').exists()
    assert (project_dir / 'approvals.jsonl').exists()
    assert (project_dir / 'pairing' / 'status.json').exists()
    assert (project_env / 'project-os-v1' / 'projects' / 'registry.json').exists()
    project_yaml = (project_dir / 'project.yaml').read_text()
    assert 'workspace_contracts:' in project_yaml
    assert 'approvals_file: approvals.jsonl' in project_yaml
    assert 'sync_dir: sync' in project_yaml
    assert 'pairing_dir: pairing' in project_yaml
    assert str(project_env / 'project-os-v1' / 'config' / 'path-policies.yaml') in project_yaml
    assert str(project_env / 'project-os-v1' / 'config' / 'modules.yaml') in project_yaml
    assert str(project_env / 'project-os-v1' / 'config' / 'modules.lock.yaml') in project_yaml


def test_project_show_displays_metadata(project_env, capsys):
    from hermes_cli.projects import project_command

    project_command(
        Namespace(
            project_action='init',
            project_id='alpha',
            name='Alpha',
            summary='Alpha project summary',
            repo_path=None,
        )
    )
    capsys.readouterr()

    rc = project_command(
        Namespace(
            project_action='show',
            project_id='alpha',
            name=None,
            summary=None,
            repo_path=None,
        )
    )
    out = capsys.readouterr().out

    assert rc == 0
    assert 'Project: alpha' in out
    assert 'Name:          Alpha' in out
    assert 'Summary:       Alpha project summary' in out
    assert 'Status digest:' in out
    assert 'not generated yet' in out
    assert str(project_env / 'project-os-v1' / 'projects' / 'alpha') in out


def test_project_digest_generates_digest(project_env, capsys):
    from hermes_cli.projects import project_command

    project_command(
        Namespace(
            project_action='init',
            project_id='alpha',
            name='Alpha',
            summary='Alpha project summary',
            repo_path=None,
        )
    )
    capsys.readouterr()

    rc = project_command(
        Namespace(
            project_action='digest',
            project_id='alpha',
            name=None,
            summary=None,
            repo_path=None,
        )
    )
    out = capsys.readouterr().out

    assert rc == 0
    digest_path = project_env / 'project-os-v1' / 'projects' / 'alpha' / 'reports' / '01-status-digest.md'
    assert digest_path.exists()
    assert 'Recommended next actions' in digest_path.read_text()
    assert f'Updated status digest: {digest_path}' in out


def test_project_status_alias_generates_digest(project_env, capsys):
    from hermes_cli.projects import project_command

    project_command(
        Namespace(
            project_action='init',
            project_id='alpha',
            name='Alpha',
            summary='Alpha project summary',
            repo_path=None,
        )
    )
    capsys.readouterr()

    rc = project_command(
        Namespace(
            project_action='status',
            project_id='alpha',
            name=None,
            summary=None,
            repo_path=None,
        )
    )

    assert rc == 0


def test_project_main_parser_dispatches_list(monkeypatch):
    import hermes_cli.main as main_mod

    captured = {}

    def fake_cmd_project(args):
        captured['action'] = args.project_action
        captured['command'] = args.command

    monkeypatch.setattr(main_mod, 'cmd_project', fake_cmd_project, raising=False)
    monkeypatch.setattr(sys, 'argv', ['hermes', 'project', 'list'])

    main_mod.main()

    assert captured == {'action': 'list', 'command': 'project'}


@pytest.mark.parametrize(
    ('argv', 'expected'),
    [
        (['hermes', 'project', 'show', 'alpha'], {'action': 'show', 'command': 'project', 'project_id': 'alpha'}),
        (['hermes', 'project', 'digest', 'alpha'], {'action': 'digest', 'command': 'project', 'project_id': 'alpha'}),
        (['hermes', 'project', 'status', 'alpha'], {'action': 'status', 'command': 'project', 'project_id': 'alpha'}),
    ],
)
def test_project_main_parser_dispatches_project_actions(monkeypatch, argv, expected):
    import hermes_cli.main as main_mod

    captured = {}

    def fake_cmd_project(args):
        captured['action'] = args.project_action
        captured['command'] = args.command
        captured['project_id'] = getattr(args, 'project_id', None)

    monkeypatch.setattr(main_mod, 'cmd_project', fake_cmd_project, raising=False)
    monkeypatch.setattr(sys, 'argv', argv)

    main_mod.main()

    assert captured == expected
