"""Tests for _web_ui_build_needed — staleness check for the web UI dist."""

import os
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from hermes_cli.main import _web_ui_build_needed, _build_web_ui


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _touch(path: Path, offset: float = 0.0) -> None:
    """Create a file and optionally shift its mtime by offset seconds."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    if offset:
        t = time.time() + offset
        os.utime(path, (t, t))


# ---------------------------------------------------------------------------
# _web_ui_build_needed
# ---------------------------------------------------------------------------

class TestWebUIBuildNeeded:

    def test_returns_true_when_dist_missing(self, tmp_path):
        (tmp_path / "package.json").touch()
        assert _web_ui_build_needed(tmp_path) is True

    def test_returns_false_when_vite_manifest_exists_and_sources_older(self, tmp_path):
        # Write source files first, then the manifest (newer)
        src = tmp_path / "src" / "App.tsx"
        _touch(src, offset=-10)
        manifest = tmp_path / "dist" / ".vite" / "manifest.json"
        _touch(manifest)

        assert _web_ui_build_needed(tmp_path) is False

    def test_returns_true_when_source_newer_than_manifest(self, tmp_path):
        manifest = tmp_path / "dist" / ".vite" / "manifest.json"
        _touch(manifest, offset=-10)
        src = tmp_path / "src" / "App.tsx"
        _touch(src)  # newer than manifest

        assert _web_ui_build_needed(tmp_path) is True

    def test_falls_back_to_index_html_when_manifest_missing(self, tmp_path):
        _touch(tmp_path / "src" / "main.ts", offset=-10)
        _touch(tmp_path / "dist" / "index.html")  # no .vite/manifest.json

        assert _web_ui_build_needed(tmp_path) is False

    def test_returns_true_when_package_lock_newer_than_dist(self, tmp_path):
        _touch(tmp_path / "dist" / ".vite" / "manifest.json", offset=-10)
        _touch(tmp_path / "package-lock.json")  # newer → rebuild

        assert _web_ui_build_needed(tmp_path) is True

    def test_returns_true_when_vite_config_newer_than_dist(self, tmp_path):
        _touch(tmp_path / "dist" / ".vite" / "manifest.json", offset=-10)
        _touch(tmp_path / "vite.config.ts")  # newer → rebuild

        assert _web_ui_build_needed(tmp_path) is True

    def test_ignores_files_in_node_modules_and_dist(self, tmp_path):
        manifest = tmp_path / "dist" / ".vite" / "manifest.json"
        _touch(manifest, offset=-10)
        # Files inside node_modules and dist should not trigger rebuild
        _touch(tmp_path / "node_modules" / "react" / "index.js")
        _touch(tmp_path / "dist" / "assets" / "index.js")

        assert _web_ui_build_needed(tmp_path) is False


# ---------------------------------------------------------------------------
# _build_web_ui — skip when fresh
# ---------------------------------------------------------------------------

class TestBuildWebUISkipsWhenFresh:

    def test_skips_npm_when_dist_is_fresh(self, tmp_path):
        (tmp_path / "package.json").touch()
        _touch(tmp_path / "dist" / ".vite" / "manifest.json")

        with patch("hermes_cli.main.shutil.which", return_value="/usr/bin/npm"), \
             patch("hermes_cli.main.subprocess.run") as mock_run:
            result = _build_web_ui(tmp_path)

        assert result is True
        mock_run.assert_not_called()

    def test_runs_npm_when_dist_is_missing(self, tmp_path):
        (tmp_path / "package.json").touch()
        # No dist/ — build needed

        mock_cp = __import__("subprocess").CompletedProcess([], 0, stdout=b"", stderr=b"")
        with patch("hermes_cli.main.shutil.which", return_value="/usr/bin/npm"), \
             patch("hermes_cli.main.subprocess.run", return_value=mock_cp) as mock_run:
            result = _build_web_ui(tmp_path)

        assert result is True
        assert mock_run.call_count == 2  # npm install + npm run build
