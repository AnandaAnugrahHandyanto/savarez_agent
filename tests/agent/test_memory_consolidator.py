"""Tests for memory consolidation."""

import json
import os
import tempfile
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

import pytest

from agent.memory_consolidator import (
    check_consolidation_gates,
    consolidate_memories,
    increment_session_count,
)
from tools.memory_engine import MemoryEngine


@pytest.fixture
def engine(tmp_path):
    eng = MemoryEngine(db_path=tmp_path / "memory.db")
    yield eng
    eng.close()


@pytest.fixture
def populated_engine(engine):
    engine.add("User prefers direct communication without fluff", target="user", type="preference")
    engine.add("Project uses Python 3.11 on WSL Ubuntu with systemd", target="memory", type="project")
    engine.add("Discord output: only final text visible per turn", target="memory", type="correction")
    engine.add("The CI pipeline runs on GitHub Actions", target="memory", type="project")
    engine.add("User timezone is CET (Central European Time)", target="user", type="preference")
    return engine


@pytest.fixture
def mock_aux():
    client = MagicMock()
    return client


# ---------------------------------------------------------------------------
# Gate checks
# ---------------------------------------------------------------------------


class TestGates:
    def test_disabled_skips(self, engine):
        reason = check_consolidation_gates(engine, {"consolidation_enabled": False})
        assert reason is not None
        assert "false" in reason

    def test_too_soon_skips(self, engine):
        engine._set_meta("last_consolidation", datetime.now(timezone.utc).isoformat())
        reason = check_consolidation_gates(engine, {
            "consolidation_enabled": True,
            "consolidation_interval_hours": 24,
            "consolidation_min_sessions": 0,
        })
        assert reason is not None
        assert "hours" in reason or "0." in reason

    def test_not_enough_sessions_skips(self, engine):
        engine._set_meta("consolidation_session_count", "2")
        reason = check_consolidation_gates(engine, {
            "consolidation_enabled": True,
            "consolidation_interval_hours": 0,
            "consolidation_min_sessions": 5,
        })
        assert reason is not None
        assert "sessions" in reason

    def test_all_gates_pass(self, engine):
        engine._set_meta("last_consolidation", (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat())
        engine._set_meta("consolidation_session_count", "6")
        reason = check_consolidation_gates(engine, {
            "consolidation_enabled": True,
            "consolidation_interval_hours": 24,
            "consolidation_min_sessions": 5,
        })
        assert reason is None

    def test_first_run_passes(self, engine):
        """No last_consolidation metadata = first run, should pass time gate."""
        engine._set_meta("consolidation_session_count", "10")
        reason = check_consolidation_gates(engine, {
            "consolidation_enabled": True,
            "consolidation_interval_hours": 24,
            "consolidation_min_sessions": 5,
        })
        assert reason is None


# ---------------------------------------------------------------------------
# Consolidation execution
# ---------------------------------------------------------------------------


class TestConsolidate:
    def test_no_aux_client_skips(self, populated_engine):
        result = consolidate_memories(
            populated_engine, auxiliary_client=None,
            config={"consolidation_enabled": True, "consolidation_interval_hours": 0, "consolidation_min_sessions": 0},
        )
        assert result["consolidated"] is False
        assert "auxiliary" in result["reason"]

    def test_none_response(self, populated_engine, mock_aux):
        mock_aux.call_llm.return_value = "NONE"
        populated_engine._set_meta("consolidation_session_count", "10")
        result = consolidate_memories(
            populated_engine, auxiliary_client=mock_aux,
            config={"consolidation_enabled": True, "consolidation_interval_hours": 0, "consolidation_min_sessions": 0},
        )
        assert result["consolidated"] is True
        assert result["actions"] == 0

    def test_merge_action(self, populated_engine, mock_aux):
        # Get the actual short IDs
        mems = populated_engine.get_active_memories("memory")
        project_mems = [m for m in mems if "project" in m.get("type", "")]
        if len(project_mems) >= 2:
            id1 = project_mems[0]["id"][:8]
            id2 = project_mems[1]["id"][:8]
            mock_aux.call_llm.return_value = json.dumps({
                "action": "merge",
                "remove_ids": [id1, id2],
                "new_content": "Project uses Python 3.11 on WSL with GitHub Actions CI",
                "target": "memory",
                "type": "project",
            })
            populated_engine._set_meta("consolidation_session_count", "10")
            result = consolidate_memories(
                populated_engine, auxiliary_client=mock_aux,
                config={"consolidation_enabled": True, "consolidation_interval_hours": 0, "consolidation_min_sessions": 0},
            )
            assert result["consolidated"] is True
            assert result["actions"] >= 1

    def test_archive_action(self, populated_engine, mock_aux):
        mems = populated_engine.get_active_memories("memory")
        if mems:
            short_id = mems[0]["id"][:8]
            mock_aux.call_llm.return_value = json.dumps({
                "action": "archive",
                "id": short_id,
                "reason": "no longer relevant",
            })
            populated_engine._set_meta("consolidation_session_count", "10")
            result = consolidate_memories(
                populated_engine, auxiliary_client=mock_aux,
                config={"consolidation_enabled": True, "consolidation_interval_hours": 0, "consolidation_min_sessions": 0},
            )
            assert result["consolidated"] is True
            assert result["actions"] == 1

    def test_updates_meta_after_run(self, populated_engine, mock_aux):
        mock_aux.call_llm.return_value = "NONE"
        populated_engine._set_meta("consolidation_session_count", "10")
        consolidate_memories(
            populated_engine, auxiliary_client=mock_aux,
            config={"consolidation_enabled": True, "consolidation_interval_hours": 0, "consolidation_min_sessions": 0},
        )
        assert populated_engine._get_meta("consolidation_session_count") == "0"
        assert populated_engine._get_meta("last_consolidation") != ""


# ---------------------------------------------------------------------------
# Session counter
# ---------------------------------------------------------------------------


class TestSessionCounter:
    def test_increment(self, engine):
        assert engine._get_meta("consolidation_session_count") == "0"
        increment_session_count(engine)
        assert engine._get_meta("consolidation_session_count") == "1"
        increment_session_count(engine)
        assert engine._get_meta("consolidation_session_count") == "2"
