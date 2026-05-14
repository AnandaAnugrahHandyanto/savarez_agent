"""Tests for Hermes' isolated Codex runtime home resolution."""

from __future__ import annotations

from pathlib import Path

from hermes_cli.codex_runtime_home import resolve_codex_runtime_home


def test_defaults_to_hermes_isolated_codex_home(monkeypatch, tmp_path):
    hermes_home = tmp_path / "hermes-home"
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.delenv("HERMES_CODEX_HOME", raising=False)
    monkeypatch.delenv("CODEX_HOME", raising=False)

    assert resolve_codex_runtime_home() == hermes_home / "codex-runtime"


def test_hermes_codex_home_overrides_global_codex_home(monkeypatch, tmp_path):
    hermes_codex_home = tmp_path / "runtime-codex"
    global_codex_home = tmp_path / "global-codex"
    monkeypatch.setenv("HERMES_CODEX_HOME", str(hermes_codex_home))
    monkeypatch.setenv("CODEX_HOME", str(global_codex_home))

    assert resolve_codex_runtime_home() == hermes_codex_home


def test_explicit_path_wins(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_CODEX_HOME", str(tmp_path / "env-codex"))

    assert resolve_codex_runtime_home(Path("~/explicit-codex")).name == "explicit-codex"
