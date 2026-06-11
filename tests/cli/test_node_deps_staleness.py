"""Tests for _node_deps_install_needed() — staleness check before npm ci."""

import os
import time
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tree(root: Path, *, lockfile: bool = True, marker: bool = True,
               lockfile_mtime: float | None = None,
               marker_mtime: float | None = None) -> None:
    """Create a minimal PROJECT_ROOT with package-lock.json and node_modules marker."""
    (root / "package.json").write_text("{}")
    if lockfile:
        lf = root / "package-lock.json"
        lf.write_text("{}")
        if lockfile_mtime is not None:
            os.utime(lf, (lockfile_mtime, lockfile_mtime))
    if marker:
        nm = root / "node_modules"
        nm.mkdir(exist_ok=True)
        mk = nm / ".package-lock.json"
        mk.write_text("{}")
        if marker_mtime is not None:
            os.utime(mk, (marker_mtime, marker_mtime))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestNodeDepsInstallNeeded:
    """Test _node_deps_install_needed() staleness logic."""

    def test_returns_true_when_lockfile_newer(self, tmp_path):
        """Lockfile modified after marker → install needed."""
        _make_tree(tmp_path, lockfile_mtime=200, marker_mtime=100)
        with patch("hermes_cli.main.PROJECT_ROOT", tmp_path):
            from hermes_cli.main import _node_deps_install_needed
            assert _node_deps_install_needed() is True

    def test_returns_false_when_marker_newer(self, tmp_path):
        """Marker modified after lockfile → already installed."""
        _make_tree(tmp_path, lockfile_mtime=100, marker_mtime=200)
        with patch("hermes_cli.main.PROJECT_ROOT", tmp_path):
            from hermes_cli.main import _node_deps_install_needed
            assert _node_deps_install_needed() is False

    def test_returns_false_when_same_mtime(self, tmp_path):
        """Same mtime → already installed (lockfile NOT newer)."""
        _make_tree(tmp_path, lockfile_mtime=100, marker_mtime=100)
        with patch("hermes_cli.main.PROJECT_ROOT", tmp_path):
            from hermes_cli.main import _node_deps_install_needed
            assert _node_deps_install_needed() is False

    def test_returns_true_when_no_marker(self, tmp_path):
        """No node_modules marker → install needed."""
        _make_tree(tmp_path, marker=False)
        with patch("hermes_cli.main.PROJECT_ROOT", tmp_path):
            from hermes_cli.main import _node_deps_install_needed
            assert _node_deps_install_needed() is True

    def test_returns_true_when_no_lockfile(self, tmp_path):
        """No lockfile → install needed (let npm handle it)."""
        _make_tree(tmp_path, lockfile=False, marker=False)
        with patch("hermes_cli.main.PROJECT_ROOT", tmp_path):
            from hermes_cli.main import _node_deps_install_needed
            assert _node_deps_install_needed() is True

    def test_skip_node_deps_config_overrides(self, tmp_path):
        """Config updates.skip_node_deps=True → always skip."""
        _make_tree(tmp_path, lockfile_mtime=200, marker_mtime=100)
        mock_cfg = {"updates": {"skip_node_deps": True}}
        with patch("hermes_cli.main.PROJECT_ROOT", tmp_path), \
             patch("hermes_cli.config.load_config", return_value=mock_cfg):
            from hermes_cli.main import _node_deps_install_needed
            assert _node_deps_install_needed() is False

    def test_skip_node_deps_false_does_not_skip(self, tmp_path):
        """Config updates.skip_node_deps=False → normal staleness check."""
        _make_tree(tmp_path, lockfile_mtime=200, marker_mtime=100)
        mock_cfg = {"updates": {"skip_node_deps": False}}
        with patch("hermes_cli.main.PROJECT_ROOT", tmp_path), \
             patch("hermes_cli.config.load_config", return_value=mock_cfg):
            from hermes_cli.main import _node_deps_install_needed
            assert _node_deps_install_needed() is True

    def test_config_load_failure_does_not_crash(self, tmp_path):
        """If load_config raises, fall through to mtime check."""
        _make_tree(tmp_path, lockfile_mtime=100, marker_mtime=200)
        with patch("hermes_cli.main.PROJECT_ROOT", tmp_path), \
             patch("hermes_cli.config.load_config", side_effect=Exception("broken")):
            from hermes_cli.main import _node_deps_install_needed
            assert _node_deps_install_needed() is False


class TestUpdateNodeDepsSkipsWhenFresh:
    """Test that _update_node_dependencies() prints skip message and returns early."""

    def test_skips_npm_ci_when_deps_fresh(self, tmp_path, capsys):
        """When _node_deps_install_needed returns False, npm is never called."""
        _make_tree(tmp_path, lockfile_mtime=100, marker_mtime=200)
        with patch("hermes_cli.main.PROJECT_ROOT", tmp_path), \
             patch("hermes_cli.main._node_deps_install_needed", return_value=False), \
             patch("shutil.which", return_value="/usr/bin/npm"):
            from hermes_cli.main import _update_node_dependencies
            _update_node_dependencies()
        captured = capsys.readouterr()
        assert "skipping npm ci" in captured.out

    def test_runs_npm_ci_when_deps_stale(self, tmp_path, capsys):
        """When _node_deps_install_needed returns True, npm ci runs."""
        _make_tree(tmp_path, lockfile_mtime=200, marker_mtime=100)
        import subprocess
        mock_result = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        with patch("hermes_cli.main.PROJECT_ROOT", tmp_path), \
             patch("hermes_cli.main._node_deps_install_needed", return_value=True), \
             patch("shutil.which", return_value="/usr/bin/npm"), \
             patch("hermes_cli.main._run_npm_install_deterministic", return_value=mock_result) as mock_npm, \
             patch("hermes_cli.main._nixos_build_env", return_value=None):
            from hermes_cli.main import _update_node_dependencies
            _update_node_dependencies()
        assert mock_npm.call_count == 2  # root + workspace install


class TestDefaultConfigHasSkipNodeDeps:
    """Verify the config key exists in DEFAULT_CONFIG."""

    def test_skip_node_deps_in_default_config(self):
        from hermes_cli.config import DEFAULT_CONFIG
        updates = DEFAULT_CONFIG.get("updates", {})
        assert "skip_node_deps" in updates
        assert updates["skip_node_deps"] is False
