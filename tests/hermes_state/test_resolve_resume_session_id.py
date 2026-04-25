"""Regression guards for `/resume` after compression continuation splits.

Context compression ends the current session and forks a continuation child
(linked by ``parent_session_id``). The live user-facing session is the latest
compression tip, not merely the first descendant in the chain that happens to
contain message rows.

``SessionDB.resolve_resume_session_id()`` therefore projects through true
compression continuations and returns the newest reachable tip. Non-compression
children (subagents, branches) must not be followed.
"""
import time

import pytest

from hermes_state import SessionDB


@pytest.fixture
def db(tmp_path):
    return SessionDB(tmp_path / "state.db")


def _make_chain(db: SessionDB, ids_with_parent):
    """Create sessions in order, forcing started_at so ordering is deterministic."""
    base = int(time.time()) - 10_000
    for i, (sid, parent) in enumerate(ids_with_parent):
        db.create_session(sid, source="cli", parent_session_id=parent)
        db._conn.execute(
            "UPDATE sessions SET started_at = ? WHERE id = ?",
            (base + i * 100, sid),
        )
    db._conn.commit()


def _mark_compressed(db: SessionDB, session_id: str, ended_at: int | None = None):
    if ended_at is None:
        row = db._conn.execute(
            "SELECT started_at FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        started_at = row["started_at"] if hasattr(row, "keys") else row[0]
        ended_at = int(started_at) + 1
    db._conn.execute(
        "UPDATE sessions SET end_reason = 'compression', ended_at = ? WHERE id = ?",
        (ended_at, session_id),
    )
    db._conn.commit()


def test_redirects_from_root_to_latest_compression_tip(db):
    _make_chain(db, [
        ("head", None),
        ("mid1", "head"),
        ("mid2", "mid1"),
        ("mid3", "mid2"),
        ("bulk", "mid3"),
        ("tail", "bulk"),
    ])
    for sid in ["head", "mid1", "mid2", "mid3", "bulk"]:
        _mark_compressed(db, sid)
    for i in range(5):
        db.append_message("bulk", role="user", content=f"msg {i}")

    assert db.resolve_resume_session_id("head") == "tail"


def test_returns_latest_tip_even_when_root_has_messages(db):
    _make_chain(db, [("root", None), ("child", "root")])
    db.append_message("root", role="user", content="old root message")
    _mark_compressed(db, "root")
    db.append_message("child", role="user", content="latest child message")
    assert db.resolve_resume_session_id("root") == "child"


def test_returns_self_when_no_compression_lineage_exists(db):
    _make_chain(db, [("root", None), ("child1", "root"), ("child2", "child1")])
    assert db.resolve_resume_session_id("root") == "root"


def test_returns_self_for_isolated_session(db):
    db.create_session("isolated", source="cli")
    assert db.resolve_resume_session_id("isolated") == "isolated"


def test_returns_self_for_nonexistent_session(db):
    assert db.resolve_resume_session_id("does_not_exist") == "does_not_exist"


def test_empty_session_id_passthrough(db):
    assert db.resolve_resume_session_id("") == ""
    assert db.resolve_resume_session_id(None) is None


def test_walks_from_middle_of_compression_chain(db):
    _make_chain(db, [("a", None), ("b", "a"), ("c", "b"), ("d", "c")])
    for sid in ["a", "b", "c"]:
        _mark_compressed(db, sid)
    db.append_message("d", role="user", content="latest")
    assert db.resolve_resume_session_id("b") == "d"
    assert db.resolve_resume_session_id("c") == "d"


def test_prefers_most_recent_compression_child_when_fork_exists(db):
    # If malformed data produces two post-compression children, pick the latest one.
    _make_chain(db, [
        ("parent", None),
        ("older_fork", "parent"),
        ("newer_fork", "parent"),
    ])
    _mark_compressed(db, "parent")
    db.append_message("newer_fork", role="user", content="x")
    assert db.resolve_resume_session_id("parent") == "newer_fork"


def test_does_not_follow_non_compression_child_sessions(db):
    _make_chain(db, [("parent", None), ("subagent_child", "parent")])
    db.append_message("subagent_child", role="user", content="subagent output")
    assert db.resolve_resume_session_id("parent") == "parent"
