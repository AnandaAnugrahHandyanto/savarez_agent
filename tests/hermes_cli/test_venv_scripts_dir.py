"""Tests for _venv_scripts_dir() — verifying it discovers both 'venv' and '.venv'."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

import hermes_cli.main as cli_main


class TestVenvScriptsDir:
    """_venv_scripts_dir must find venv scripts regardless of directory name."""

    @staticmethod
    def _run(tmp_path: Path, venv_name: str, *, is_windows: bool = False):
        """Create a fake venv layout and run _venv_scripts_dir."""
        venv_dir = tmp_path / venv_name
        subdir = "Scripts" if is_windows else "bin"
        scripts = venv_dir / subdir
        scripts.mkdir(parents=True, exist_ok=True)

        with patch.object(cli_main, "PROJECT_ROOT", tmp_path), \
             patch.object(cli_main, "_is_windows", return_value=is_windows):
            return cli_main._venv_scripts_dir()

    def test_finds_venv(self, tmp_path: Path):
        result = self._run(tmp_path, "venv")
        assert result == tmp_path / "venv" / "bin"

    def test_finds_dotvenv(self, tmp_path: Path):
        result = self._run(tmp_path, ".venv")
        assert result == tmp_path / ".venv" / "bin"

    def test_venv_takes_precedence_over_dotvenv(self, tmp_path: Path):
        """When both exist, 'venv' should be preferred (backwards compat)."""
        self._run(tmp_path, "venv")
        self._run(tmp_path, ".venv")
        result = self._run(tmp_path, "venv")  # both exist now
        assert result == tmp_path / "venv" / "bin"

    def test_returns_none_when_neither_exists(self, tmp_path: Path):
        with patch.object(cli_main, "PROJECT_ROOT", tmp_path), \
             patch.object(cli_main, "_is_windows", return_value=False):
            assert cli_main._venv_scripts_dir() is None

    def test_windows_scripts_dir(self, tmp_path: Path):
        result = self._run(tmp_path, ".venv", is_windows=True)
        assert result == tmp_path / ".venv" / "Scripts"

    def test_venv_without_bin_scripts_returns_none(self, tmp_path: Path):
        """venv dir exists but no bin/Scripts subdir → try .venv, then None."""
        venv_dir = tmp_path / "venv"
        venv_dir.mkdir()
        # No bin/ subdir

        with patch.object(cli_main, "PROJECT_ROOT", tmp_path), \
             patch.object(cli_main, "_is_windows", return_value=False):
            assert cli_main._venv_scripts_dir() is None

    def test_dotvenv_without_bin_scripts_returns_none(self, tmp_path: Path):
        """Only .venv exists but no bin/ subdir → None."""
        venv_dir = tmp_path / ".venv"
        venv_dir.mkdir()
        # No bin/ subdir

        with patch.object(cli_main, "PROJECT_ROOT", tmp_path), \
             patch.object(cli_main, "_is_windows", return_value=False):
            assert cli_main._venv_scripts_dir() is None

    def test_venv_no_scripts_dotvenv_has_scripts(self, tmp_path: Path):
        """venv exists but has no bin/; .venv has bin/ → returns .venv/bin."""
        # venv without bin
        (tmp_path / "venv").mkdir()
        # .venv with bin
        (tmp_path / ".venv" / "bin").mkdir(parents=True)

        with patch.object(cli_main, "PROJECT_ROOT", tmp_path), \
             patch.object(cli_main, "_is_windows", return_value=False):
            result = cli_main._venv_scripts_dir()
        assert result == tmp_path / ".venv" / "bin"
