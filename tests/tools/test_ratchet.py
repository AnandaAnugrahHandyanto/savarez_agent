"""Tests for session-scoped ratchet refs in tools/checkpoint_manager.py."""

from pathlib import Path

import pytest

from tools.checkpoint_manager import CheckpointManager, _ratchet_repo_path


@pytest.fixture()
def work_dir(tmp_path):
    d = tmp_path / "project"
    d.mkdir()
    (d / "main.py").write_text("v1\n")
    return d


@pytest.fixture()
def fake_hermes_home(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setattr("tools.checkpoint_manager.get_hermes_home", lambda: home)
    return home


def test_ratchet_pin_and_list_round_trip(work_dir, fake_hermes_home):
    mgr = CheckpointManager(enabled=True, max_snapshots=5)

    first = mgr.ratchet_pin("sess-1", str(work_dir), message_id="msg-1", reason="first state")
    assert first["success"] is True

    (work_dir / "main.py").write_text("v2\n")
    second = mgr.ratchet_pin("sess-1", str(work_dir), message_id="msg-2", reason="second state")
    assert second["success"] is True
    assert second["created_commit"] is True

    refs = mgr.ratchet_list("sess-1")
    assert [ref["ref_tag"] for ref in refs] == ["msg-2", "msg-1"]
    assert refs[0]["reason"] == "second state"
    assert refs[0]["working_dir"] == str(work_dir.resolve())


def test_ratchet_restore_rewinds_worktree(work_dir, fake_hermes_home):
    mgr = CheckpointManager(enabled=True, max_snapshots=5)

    first = mgr.ratchet_pin("sess-restore", str(work_dir), message_id="msg-1", reason="v1")
    assert first["success"] is True

    (work_dir / "main.py").write_text("v2\n")
    second = mgr.ratchet_pin("sess-restore", str(work_dir), message_id="msg-2", reason="v2")
    assert second["success"] is True

    (work_dir / "main.py").write_text("dirty\n")
    restored = mgr.ratchet_restore("sess-restore", "msg-1")
    assert restored["success"] is True
    assert restored["restored_to"] == "msg-1"
    assert (work_dir / "main.py").read_text() == "v1\n"


def test_ratchet_pin_reuses_head_when_no_file_changes(work_dir, fake_hermes_home):
    mgr = CheckpointManager(enabled=True, max_snapshots=5)

    first = mgr.ratchet_pin("sess-stable", str(work_dir), message_id="msg-1", reason="first")
    assert first["success"] is True

    second = mgr.ratchet_pin("sess-stable", str(work_dir), message_id="msg-2", reason="same tree")
    assert second["success"] is True
    assert second["created_commit"] is False
    assert second["commit"] == first["commit"]


def test_ratchet_restore_returns_session_snapshot_metadata(work_dir, fake_hermes_home):
    mgr = CheckpointManager(enabled=True, max_snapshots=5)
    snapshot = {"session_id": "sess-meta", "messages": [{"role": "user", "content": "hi"}]}

    pinned = mgr.ratchet_pin(
        "sess-meta",
        str(work_dir),
        message_id="msg-meta",
        reason="with session payload",
        session_snapshot=snapshot,
    )
    assert pinned["success"] is True

    restored = mgr.ratchet_restore("sess-meta", "msg-meta")
    assert restored["success"] is True
    assert restored["session_snapshot"] == snapshot


def test_ratchet_repo_path_lives_under_sessions(fake_hermes_home):
    path = _ratchet_repo_path("abc123")
    assert path == fake_hermes_home / "sessions" / "abc123" / ".ratchet.git"


def test_ratchet_prunes_old_refs(work_dir, fake_hermes_home):
    mgr = CheckpointManager(enabled=True, max_snapshots=2)

    for idx in range(1, 4):
        (work_dir / "main.py").write_text(f"v{idx}\n")
        result = mgr.ratchet_pin("sess-prune", str(work_dir), message_id=f"msg-{idx}", reason=f"v{idx}")
        assert result["success"] is True

    refs = mgr.ratchet_list("sess-prune")
    assert [ref["ref_tag"] for ref in refs] == ["msg-3", "msg-2"]
