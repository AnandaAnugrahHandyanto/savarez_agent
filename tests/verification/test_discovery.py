from pathlib import Path

from hermes_cli.verification.discovery import discover_commands


def test_discover_commands_prefers_explicit_commands(tmp_path):
    commands = discover_commands(repo=tmp_path, explicit_commands=["pytest -q"], family_map_path=None)

    assert [command.command for command in commands] == ["pytest -q"]
    assert commands[0].name == "command 1"
    assert commands[0].source == "explicit"


def test_discover_commands_uses_repo_family_fast_verify(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    family_map = tmp_path / "families.yaml"
    family_map.write_text(
        f"""
families:
  test-family:
    reference_repo: {repo}
    command_surface:
      fast_verify:
        - make test
        - make lint
""".strip()
    )

    commands = discover_commands(repo=repo, explicit_commands=[], family_map_path=family_map)

    assert [command.command for command in commands] == ["make test", "make lint"]
    assert commands[0].source == "repo-family:test-family"


def test_discover_commands_returns_empty_when_no_source(tmp_path):
    commands = discover_commands(repo=tmp_path, explicit_commands=[], family_map_path=None)

    assert commands == []
