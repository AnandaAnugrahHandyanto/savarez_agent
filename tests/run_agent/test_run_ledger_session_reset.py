from pathlib import Path

from hermes_state import SessionDB
from run_agent import AIAgent


def _agent(tmp_path: Path, session_db=None):
    agent = object.__new__(AIAgent)
    agent.session_id = "current"
    agent._session_db = session_db
    agent._run_ledger_config = {"enabled": True, "preview_chars": 128, "blob_threshold_chars": 256}
    agent._run_ledger = None
    return agent


def test_reset_run_ledger_retargets_new_independent_session(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes-home"))
    agent = _agent(tmp_path)

    agent._reset_run_ledger_for_session("new-session")

    assert agent._run_ledger.run_id == "new-session"
    assert agent._run_ledger.session_id == "new-session"


def test_reset_run_ledger_uses_root_compression_parent(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes-home"))
    db = SessionDB(db_path=tmp_path / "state.db")
    db.create_session("root", source="cli")
    db.end_session("root", "compression")
    db.create_session("mid", source="cli", parent_session_id="root")
    db.end_session("mid", "compression")
    db.create_session("tip", source="cli", parent_session_id="mid")
    agent = _agent(tmp_path, db)

    agent._reset_run_ledger_for_session("tip")

    assert agent._run_ledger.run_id == "root"
    assert agent._run_ledger.session_id == "tip"


def test_reset_run_ledger_does_not_use_branch_parent_as_run_root(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes-home"))
    db = SessionDB(db_path=tmp_path / "state.db")
    db.create_session("parent", source="cli")
    db.end_session("parent", "branched")
    db.create_session("branch", source="cli", parent_session_id="parent")
    agent = _agent(tmp_path, db)

    agent._reset_run_ledger_for_session("branch")

    assert agent._run_ledger.run_id == "branch"
    assert agent._run_ledger.session_id == "branch"


def test_reset_run_ledger_does_not_use_delegate_child_as_compression_child(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes-home"))
    db = SessionDB(db_path=tmp_path / "state.db")
    db.create_session("parent", source="cli")
    db.create_session("delegate-child", source="cli", parent_session_id="parent")
    db.end_session("parent", "compression")
    agent = _agent(tmp_path, db)

    agent._reset_run_ledger_for_session("delegate-child")

    assert agent._run_ledger.run_id == "delegate-child"
    assert agent._run_ledger.session_id == "delegate-child"


def test_reset_run_ledger_disabled_uses_null_ledger(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes-home"))
    agent = _agent(tmp_path)
    agent._run_ledger_config = {"enabled": False}

    agent._reset_run_ledger_for_session("new-session")

    assert not agent._run_ledger
    assert agent._run_ledger.session_id == ""
