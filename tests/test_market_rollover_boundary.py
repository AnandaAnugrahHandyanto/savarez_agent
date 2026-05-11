import json
import subprocess
import sys
from pathlib import Path

from run_agent import (
    AIAgent,
    _resolve_initial_market_thread_id,
    default_market_thread_id_for_session,
)


class FakeDB:
    def __init__(self, thread="lane-alpha"):
        self.thread = thread
        self.thread_sets = []
        self.contract_sets = []

    def get_market_thread_id(self, session_id):
        return self.thread

    def set_market_thread_id(self, session_id, thread):
        self.thread_sets.append((session_id, thread))
        return True

    def set_market_resume_contract(self, session_id, contract):
        self.contract_sets.append((session_id, contract))
        return True


def make_agent(tmp_path, db=None):
    agent = AIAgent.__new__(AIAgent)
    agent._market_rollover_enabled = True
    agent._market_rollover_cli = str(tmp_path / "market" / "cli.py")
    Path(agent._market_rollover_cli).parent.mkdir(parents=True)
    Path(agent._market_rollover_cli).write_text("# cli", encoding="utf-8")
    agent._market_rollover_project = "home-li"
    agent._session_db = db or FakeDB()
    agent.session_id = "old-session"
    agent.session_log_file = tmp_path / "session_old-session.json"
    agent.session_log_file.write_text('{"session_id":"old-session","messages":[]}', encoding="utf-8")
    return agent


def test_prepare_market_rollover_contract_persists_successor_metadata(monkeypatch, tmp_path):
    db = FakeDB("lane-alpha")
    agent = make_agent(tmp_path, db)
    contract = {
        "boundary_mode": "market_rollover",
        "market_thread_id": "lane-alpha",
        "head_uri": "market://hermes/home-li/lane-alpha/head",
        "predecessor_session_id": "old-session",
        "successor_session_id": "new-session",
        "next_atomic_action": "continue",
    }

    def fake_run(cmd, **kwargs):
        assert cmd[:3] == [sys.executable, agent._market_rollover_cli, "market-rollover-prepare"]
        assert "--thread" in cmd and cmd[cmd.index("--thread") + 1] == "lane-alpha"
        assert "--successor-session-id" in cmd and cmd[cmd.index("--successor-session-id") + 1] == "new-session"
        assert "--source-path" in cmd and cmd[cmd.index("--source-path") + 1].endswith("session_old-session.json")
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps({"handoff_contract": contract}), stderr="")

    monkeypatch.setattr("run_agent.subprocess.run", fake_run)

    out = agent._prepare_market_rollover_contract(
        old_session_id="old-session",
        new_session_id="new-session",
        reason="context_threshold",
    )

    assert out == contract
    assert db.thread_sets == [("new-session", "lane-alpha")]
    assert db.contract_sets == [("new-session", contract)]


def test_prepare_market_rollover_contract_falls_back_on_cli_failure(monkeypatch, tmp_path):
    db = FakeDB("lane-alpha")
    agent = make_agent(tmp_path, db)

    def fail_run(*args, **kwargs):
        raise subprocess.CalledProcessError(1, args[0], stderr="boom")

    monkeypatch.setattr("run_agent.subprocess.run", fail_run)

    assert agent._prepare_market_rollover_contract(
        old_session_id="old-session",
        new_session_id="new-session",
        reason="context_threshold",
    ) is None
    assert db.thread_sets == []
    assert db.contract_sets == []


def test_market_rollover_messages_contain_only_contract_not_legacy_transcript(tmp_path):
    agent = make_agent(tmp_path)
    contract = {
        "boundary_mode": "market_rollover",
        "market_thread_id": "lane-alpha",
        "head_uri": "market://hermes/home-li/lane-alpha/head",
        "predecessor_session_id": "old-session",
        "successor_session_id": "new-session",
        "next_atomic_action": "continue",
    }

    messages = agent._market_rollover_messages(contract)

    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    assert "lane-alpha" in messages[0]["content"]
    assert "Trust market_thread_id/head_uri over session-id inference" in messages[0]["content"]
    assert "legacy transcript" not in messages[0]["content"].lower()


def test_default_market_thread_id_is_assigned_from_session_when_no_handoff(monkeypatch):
    monkeypatch.delenv("HERMES_MARKET_THREAD_ID", raising=False)
    monkeypatch.delenv("HERMES_MARKET_RESUME_CONTRACT", raising=False)

    assert default_market_thread_id_for_session("20260510_ABC def") == "hermes-20260510_abc-def"
    assert _resolve_initial_market_thread_id("session-1") == "hermes-session-1"


def test_initial_market_thread_prefers_resume_contract(monkeypatch):
    monkeypatch.delenv("HERMES_MARKET_THREAD_ID", raising=False)

    assert _resolve_initial_market_thread_id(
        "session-1",
        {"market_thread_id": "contract-lane"},
    ) == "contract-lane"


def test_ensure_db_session_persists_assigned_market_thread(monkeypatch):
    class DB:
        def __init__(self):
            self.created = None

        def create_session(self, **kwargs):
            self.created = kwargs

    monkeypatch.delenv("HERMES_MARKET_THREAD_ID", raising=False)
    monkeypatch.delenv("HERMES_MARKET_RESUME_CONTRACT", raising=False)
    db = DB()
    agent = AIAgent.__new__(AIAgent)
    agent._session_db_created = False
    agent._session_db = db
    agent.session_id = "session-1"
    agent.platform = "cli"
    agent.model = "test-model"
    agent._session_init_model_config = {}
    agent._cached_system_prompt = ""
    agent._parent_session_id = None

    agent._ensure_db_session()

    assert db.created["market_thread_id"] == "hermes-session-1"
    assert agent._market_thread_id == "hermes-session-1"
    assert agent._session_db_created is True
