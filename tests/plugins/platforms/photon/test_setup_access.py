"""Tests for `hermes photon setup`'s access auto-configuration.

`_autoconfigure_access` allowlists the operator and points the cron home
channel at their DM, writing to the per-test ~/.hermes/.env (the hermetic
HERMES_HOME fixture isolates this). It must fill only unset keys so a re-run
never clobbers a hand-tuned allowlist.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from hermes_cli.config import get_env_value, save_env_value
from plugins.platforms.photon.adapter import _env_enablement
from plugins.platforms.photon import cli


def test_autoconfigure_access_fills_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PHOTON_ALLOWED_USERS", raising=False)
    monkeypatch.delenv("PHOTON_HOME_CHANNEL", raising=False)

    cli._autoconfigure_access("+155****4567")

    assert get_env_value("PHOTON_ALLOWED_USERS") == "+155****4567"
    assert get_env_value("PHOTON_HOME_CHANNEL") == "+155****4567"


def test_autoconfigure_access_preserves_existing_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PHOTON_ALLOWED_USERS", raising=False)
    monkeypatch.delenv("PHOTON_HOME_CHANNEL", raising=False)
    # A hand-tuned allowlist already in place must survive a setup re-run.
    save_env_value("PHOTON_ALLOWED_USERS", "+199****7777,+155****2222")

    cli._autoconfigure_access("+155****4567")

    assert get_env_value("PHOTON_ALLOWED_USERS") == "+199****7777,+155****2222"
    # The still-unset home channel is filled.
    assert get_env_value("PHOTON_HOME_CHANNEL") == "+155****4567"


def test_env_enablement_seeds_home_channel(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PHOTON_PROJECT_ID", "project_123")
    monkeypatch.setenv("PHOTON_PROJECT_SECRET", "secret_123")
    monkeypatch.setenv("PHOTON_HOME_CHANNEL", "+155****4567")
    monkeypatch.setenv("PHOTON_HOME_CHANNEL_NAME", "Primary DM")

    seed = _env_enablement()

    assert seed is not None
    assert seed["home_channel"] == {
        "chat_id": "+155****4567",
        "name": "Primary DM",
    }


def test_env_enablement_home_channel_defaults_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PHOTON_PROJECT_ID", "project_123")
    monkeypatch.setenv("PHOTON_PROJECT_SECRET", "secret_123")
    monkeypatch.setenv("PHOTON_HOME_CHANNEL", "+155****4567")
    monkeypatch.delenv("PHOTON_HOME_CHANNEL_NAME", raising=False)

    seed = _env_enablement()

    assert seed is not None
    assert seed["home_channel"] == {
        "chat_id": "+155****4567",
        "name": "Home",
    }


def test_install_sidecar_respects_committed_lockfile(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    sidecar_dir = tmp_path / "sidecar"
    sidecar_dir.mkdir()
    (sidecar_dir / "package-lock.json").write_text("{}")
    calls: list[tuple[list[str], str]] = []

    class _Result:
        returncode = 0

    def fake_run(command: list[str], *, cwd: str, check: bool) -> _Result:
        calls.append((command, cwd))
        assert check is False
        return _Result()

    monkeypatch.setattr(cli, "_SIDECAR_DIR", sidecar_dir)
    monkeypatch.setattr(cli.shutil, "which", lambda name: "/usr/bin/npm")
    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    assert cli._install_sidecar() == 0
    assert calls == [(["/usr/bin/npm", "ci"], str(sidecar_dir))]


def test_install_sidecar_falls_back_to_npm_install_without_lockfile(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    sidecar_dir = tmp_path / "sidecar"
    sidecar_dir.mkdir()
    calls: list[list[str]] = []

    class _Result:
        returncode = 0

    def fake_run(command: list[str], *, cwd: str, check: bool) -> _Result:
        calls.append(command)
        assert cwd == str(sidecar_dir)
        assert check is False
        return _Result()

    monkeypatch.setattr(cli, "_SIDECAR_DIR", sidecar_dir)
    monkeypatch.setattr(cli.shutil, "which", lambda name: "/usr/bin/npm")
    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    assert cli._install_sidecar() == 0
    assert calls == [["/usr/bin/npm", "install"]]
