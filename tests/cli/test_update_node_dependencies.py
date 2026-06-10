"""Tests for _update_node_dependencies workspace root inclusion.

Regression test for https://github.com/NousResearch/hermes-agent/issues/43564:
`hermes update` workspace refresh could prune repo-root-only dependencies
(like agent-browser) because `--include-workspace-root` was missing from the
workspace-scoped npm install command.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


def _make_completed(returncode: int = 0) -> MagicMock:
    """Build a mock CompletedProcess with the given return code."""
    result = MagicMock()
    result.returncode = returncode
    result.stderr = ""
    return result


class TestUpdateNodeDependencies:
    """Verify _update_node_dependencies passes correct args to npm."""

    @pytest.fixture(autouse=True)
    def _mock_prerequisites(self, tmp_path):
        """Set up a fake PROJECT_ROOT with package.json and package-lock.json."""
        self.root = tmp_path
        (self.root / "package.json").write_text("{}")
        (self.root / "package-lock.json").write_text("{}")
        self._calls: list[list[str]] = []

        def _capture_npm(npm, cwd, *, extra_args=(), capture_output=True, env=None):
            cmd = [npm, "ci", *extra_args]
            self._calls.append(cmd)
            return _make_completed(0)

        with (
            patch("hermes_cli.main.PROJECT_ROOT", self.root),
            patch("shutil.which", return_value="/usr/bin/npm"),
            patch(
                "hermes_cli.main._run_npm_install_deterministic",
                side_effect=_capture_npm,
            ),
            patch("hermes_cli.main._nixos_build_env", return_value=None),
        ):
            yield

    def test_workspace_args_include_root(self):
        """The workspace-scoped install must include --include-workspace-root."""
        from hermes_cli.main import _update_node_dependencies

        _update_node_dependencies()

        assert len(self._calls) == 2, f"Expected 2 npm calls, got {len(self._calls)}"

        # First call: root-only install
        root_call = self._calls[0]
        assert "--workspaces=false" in root_call

        # Second call: workspace install must include root
        ws_call = self._calls[1]
        assert "--include-workspace-root" in ws_call, (
            f"Missing --include-workspace-root in workspace args: {ws_call}"
        )
        assert "--workspace" in ws_call
        assert "ui-tui" in ws_call
        assert "web" in ws_call

    def test_workspace_args_ordering(self):
        """--include-workspace-root comes after workspace selections."""
        from hermes_cli.main import _update_node_dependencies

        _update_node_dependencies()

        ws_call = self._calls[1]
        root_idx = ws_call.index("--include-workspace-root")
        # It should be the last flag
        assert root_idx == len(ws_call) - 1
