"""Regression test for the kanban dashboard ``update_task`` review-status routing.

``review`` is a member of ``kanban_db.VALID_STATUSES`` and the dashboard renders a
Review column, but ``update_task``'s status routing omitted it, so moving a task
to ``review`` fell through to ``raise HTTPException(400, "unknown status: review")``.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from hermes_cli import kanban_db as kb

# plugins/ is loaded dynamically at runtime rather than imported as a normal
# package, so load the module under test directly by path.
_PLUGIN_API_PATH = (
    Path(__file__).resolve().parents[3]
    / "plugins" / "kanban" / "dashboard" / "plugin_api.py"
)
_spec = importlib.util.spec_from_file_location("kanban_plugin_api", _PLUGIN_API_PATH)
plugin_api = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
sys.modules["kanban_plugin_api"] = plugin_api  # let pydantic resolve forward refs
_spec.loader.exec_module(plugin_api)
plugin_api.UpdateTaskBody.model_rebuild()


@pytest.fixture
def kanban_home(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    kb.init_db()
    return home


def _create_task(title: str) -> str:
    with kb.connect() as conn:
        return kb.create_task(conn, title=title)


def test_update_task_accepts_review_status(kanban_home):
    """review is a board column; moving a task there must succeed (was HTTP 400)."""
    task_id = _create_task("review me")
    plugin_api.update_task(task_id, plugin_api.UpdateTaskBody(status="review"), board=None)
    with kb.connect() as conn:
        refreshed = kb.get_task(conn, task_id)
    assert refreshed.status == "review"


def test_update_task_still_rejects_unknown_status(kanban_home):
    """Genuinely invalid statuses must still raise HTTP 400."""
    from fastapi import HTTPException

    task_id = _create_task("bogus")
    with pytest.raises(HTTPException) as exc_info:
        plugin_api.update_task(task_id, plugin_api.UpdateTaskBody(status="not-a-real-status"), board=None)
    assert exc_info.value.status_code == 400
    assert "unknown status" in str(exc_info.value.detail)
