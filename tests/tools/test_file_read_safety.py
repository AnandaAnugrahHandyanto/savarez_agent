"""Tests for read blocking of sensitive local Hermes state."""

from pathlib import Path

from agent.file_safety import get_read_block_error


def test_hermes_env_is_blocked(tmp_path: Path, monkeypatch):
    hermes_home = tmp_path / "hermes"
    hermes_home.mkdir()
    target = hermes_home / ".env"
    target.write_text("TOKEN=secret\n")

    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    assert get_read_block_error(str(target)) is not None


def test_hermes_sessions_are_blocked(tmp_path: Path, monkeypatch):
    hermes_home = tmp_path / "hermes"
    target = hermes_home / "sessions" / "session.json"
    target.parent.mkdir(parents=True)
    target.write_text("{}")

    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    assert get_read_block_error(str(target)) is not None


def test_regular_workspace_file_is_allowed(tmp_path: Path, monkeypatch):
    hermes_home = tmp_path / "hermes"
    hermes_home.mkdir()
    target = tmp_path / "workspace" / "notes.txt"
    target.parent.mkdir()
    target.write_text("hello")

    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    assert get_read_block_error(str(target)) is None
