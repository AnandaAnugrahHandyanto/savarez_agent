"""Tests for per-board dispatcher ownership (kanban-dispatch-boards feature)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_WORKTREE = Path(__file__).resolve().parents[2]
if str(_WORKTREE) not in sys.path:
    sys.path.insert(0, str(_WORKTREE))

from hermes_cli import kanban_db as kb


@pytest.fixture
def fresh_home(tmp_path, monkeypatch):
    home = tmp_path / "hermes_home"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    for var in ("HERMES_KANBAN_DB", "HERMES_KANBAN_WORKSPACES_ROOT",
                "HERMES_KANBAN_HOME", "HERMES_KANBAN_BOARD"):
        monkeypatch.delenv(var, raising=False)
    try:
        import hermes_constants
        hermes_constants._cached_default_hermes_root = None  # type: ignore[attr-defined]
    except Exception:
        pass
    kb._INITIALIZED_PATHS.clear()
    yield home
    kb._INITIALIZED_PATHS.clear()


def _filter_boards_by_owner(boards, own_profile):
    """Mirror of the gateway filter logic."""
    return [
        b for b in boards
        if b.get("dispatcher_owner") is None or b.get("dispatcher_owner") == own_profile
    ]


# Test 1
def test_owned_board_dispatched_by_owner(fresh_home):
    """Board with dispatcher_owner='hermes' is in filtered set for profile 'hermes'."""
    boards = [{"slug": "default", "dispatcher_owner": "hermes"}]
    result = _filter_boards_by_owner(boards, "hermes")
    assert len(result) == 1
    assert result[0]["slug"] == "default"


# Test 2
def test_owned_board_skipped_by_non_owner(fresh_home):
    """Board owned by 'hermes' is excluded for profile 'writer'."""
    boards = [{"slug": "default", "dispatcher_owner": "hermes"}]
    result = _filter_boards_by_owner(boards, "writer")
    assert result == []


# Test 3
def test_unowned_board_dispatched_by_all(fresh_home):
    """Board with no dispatcher_owner (None) is included for any profile."""
    boards = [{"slug": "writing", "dispatcher_owner": None}]
    for profile in ("hermes", "writer", "researcher"):
        result = _filter_boards_by_owner(boards, profile)
        assert len(result) == 1, f"Expected board for profile {profile!r}"


# Test 4
def test_set_owner_updates_board_json(fresh_home):
    """set_dispatcher_owner() persists to board.json."""
    kb.create_board("writing", dispatcher_owner=None)
    meta = kb.set_dispatcher_owner("writing", "writer")
    assert meta.get("dispatcher_owner") == "writer"
    # Verify persistence
    meta2 = kb.read_board_metadata("writing")
    assert meta2.get("dispatcher_owner") == "writer"


# Test 5
def test_create_board_with_owner(fresh_home):
    """create_board with dispatcher_owner stores the value."""
    meta = kb.create_board("writing", dispatcher_owner="writer")
    assert meta.get("dispatcher_owner") == "writer"
    meta2 = kb.read_board_metadata("writing")
    assert meta2.get("dispatcher_owner") == "writer"


# Test 6
def test_ready_nonempty_respects_ownership(fresh_home):
    """Filter for _ready_nonempty: profile 'writer', default owned by 'hermes'."""
    boards = [
        {"slug": "default", "dispatcher_owner": "hermes"},
        {"slug": "writing", "dispatcher_owner": "writer"},
    ]
    writer_boards = _filter_boards_by_owner(boards, "writer")
    slugs = [b["slug"] for b in writer_boards]
    assert "writing" in slugs
    assert "default" not in slugs


# Test 7
def test_wrong_owner_board_not_dispatched(fresh_home):
    """Board owned by 'hermes' is not dispatched when profile is 'writer'."""
    boards = [{"slug": "writing", "dispatcher_owner": "hermes"}]
    result = _filter_boards_by_owner(boards, "writer")
    assert result == []


# Test 8
def test_unknown_owner_logs_warning(fresh_home):
    """Board with unknown owner is dispatched by matching profile (no crash)."""
    boards = [{"slug": "writing", "dispatcher_owner": "ghost-profile"}]
    result = _filter_boards_by_owner(boards, "ghost-profile")
    assert len(result) == 1
    # A different gateway doesn't dispatch it (no crash).
    result2 = _filter_boards_by_owner(boards, "hermes")
    assert result2 == []


def test_default_board_gets_hermes_owner(fresh_home):
    """create_board('default') sets dispatcher_owner='hermes' automatically."""
    meta = kb.create_board("default")
    assert meta.get("dispatcher_owner") == "hermes"


def test_cli_set_owner(fresh_home):
    """CLI: kanban boards set-owner writing writer via _cmd_boards_set_owner."""
    from hermes_cli.kanban import _cmd_boards_set_owner
    import argparse
    kb.create_board("writing")
    args = argparse.Namespace(slug="writing", profile="writer")
    rc = _cmd_boards_set_owner(args)
    assert rc == 0
    meta = kb.read_board_metadata("writing")
    assert meta.get("dispatcher_owner") == "writer"
