"""Tests for kanban task workspace terminal launch."""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from hermes_cli import kanban_db as kb


def _load_plugin_router():
    repo_root = Path(__file__).resolve().parents[2]
    plugin_file = repo_root / "plugins" / "kanban" / "dashboard" / "plugin_api.py"
    spec = importlib.util.spec_from_file_location(
        "hermes_dashboard_plugin_kanban_open_terminal_test", plugin_file,
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod.router


class KanbanOpenTerminalTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.home = Path(self._tmpdir.name) / ".hermes"
        self.home.mkdir()
        self._env_patch = patch.dict(
            os.environ,
            {"HERMES_HOME": str(self.home)},
            clear=False,
        )
        self._env_patch.start()
        self.addCleanup(self._env_patch.stop)
        self._home_patch = patch.object(Path, "home", lambda: Path(self._tmpdir.name))
        self._home_patch.start()
        self.addCleanup(self._home_patch.stop)
        kb.init_db()
        app = FastAPI()
        app.include_router(_load_plugin_router(), prefix="/api/plugins/kanban")
        self.client = TestClient(app)

    def test_open_terminal_launches_in_task_workspace(self) -> None:
        workspace = Path(self._tmpdir.name) / "ws"
        workspace.mkdir()
        conn = kb.connect()
        try:
            tid = kb.create_task(
                conn,
                title="terminal test",
                workspace_kind="dir",
                workspace_path=str(workspace),
            )
        finally:
            conn.close()

        launched: dict[str, str] = {}

        def _fake_open(path: str, *, window_title: str = "Hermes"):
            launched["path"] = path
            launched["window_title"] = window_title
            return {"path": path, "window_title": window_title, "command": "cd"}

        with patch(
            "hermes_cli.web_server.open_terminal_at_directory",
            side_effect=_fake_open,
        ):
            resp = self.client.post(f"/api/plugins/kanban/tasks/{tid}/open-terminal")

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json().get("ok"))
        self.assertEqual(launched.get("path"), str(workspace.resolve()))
        self.assertIn(tid, launched.get("window_title", ""))


if __name__ == "__main__":
    unittest.main()
