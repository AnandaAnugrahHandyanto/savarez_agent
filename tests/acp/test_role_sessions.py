"""Tests for ACP role-session transport parity and persistence."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import acp_adapter.session as acp_session
from acp_adapter.server import HermesACPAgent
from acp_adapter.session import SessionManager
from hermes_state import SessionDB


@pytest.fixture()
def db(tmp_path):
    session_db = SessionDB(db_path=tmp_path / "state.db")
    yield session_db
    session_db.close()


@pytest.fixture(autouse=True)
def disable_task_cwd_hooks(monkeypatch):
    monkeypatch.setattr(acp_session, "_register_task_cwd", lambda *args, **kwargs: None)
    monkeypatch.setattr(acp_session, "_clear_task_cwd", lambda *args, **kwargs: None)


@pytest.fixture()
def fake_agent_factory():
    def factory():
        return SimpleNamespace(
            model="acp-model",
            provider="openai",
            base_url="https://example.com",
            api_mode="responses",
        )

    return factory


class TestACPSessionRoleMetadata:
    def test_create_session_persists_parent_and_role_metadata(self, db, fake_agent_factory):
        db.create_session(session_id="lead-001", source="cli")
        manager = SessionManager(agent_factory=fake_agent_factory, db=db)
        role_metadata = {
            "role_title": "Planner",
            "execution_mode": "persistent_role_instance",
            "worktree_strategy": "shared",
        }

        state = manager.create_session(
            cwd="/workspace",
            session_id="role-role-team-runtime-planner-abc123",
            parent_session_id="lead-001",
            role_metadata=role_metadata,
        )

        assert state.session_id == "role-role-team-runtime-planner-abc123"
        assert state.parent_session_id == "lead-001"
        assert state.role_metadata == role_metadata

        row = db.get_session(state.session_id)
        assert row is not None
        assert row["parent_session_id"] == "lead-001"
        meta = json.loads(row["model_config"])
        assert meta["cwd"] == "/workspace"
        assert meta["role_metadata"] == role_metadata

        restored = SessionManager(agent_factory=fake_agent_factory, db=db).get_session(state.session_id)
        assert restored is not None
        assert restored.session_id == state.session_id
        assert restored.parent_session_id == "lead-001"
        assert restored.role_metadata == role_metadata

    @pytest.mark.asyncio
    async def test_resume_session_reuses_requested_session_id_when_missing(
        self,
        db,
        fake_agent_factory,
        monkeypatch,
    ):
        db.create_session(session_id="lead-002", source="cli")
        manager = SessionManager(agent_factory=fake_agent_factory, db=db)
        agent = HermesACPAgent(session_manager=manager)
        monkeypatch.setattr(agent, "_register_session_mcp_servers", AsyncMock(return_value=None))
        monkeypatch.setattr(agent, "_schedule_available_commands_update", MagicMock())

        role_metadata = {
            "role_title": "Developer",
            "execution_mode": "persistent_role_instance",
        }
        response = await agent.resume_session(
            cwd="/workspace",
            session_id="role-role-team-runtime-developer-xyz789",
            parent_session_id="lead-002",
            role_metadata=role_metadata,
        )

        assert response is not None
        session = db.get_session("role-role-team-runtime-developer-xyz789")
        assert session is not None
        assert session["parent_session_id"] == "lead-002"
        meta = json.loads(session["model_config"])
        assert meta["role_metadata"] == role_metadata
        assert manager.get_session("role-role-team-runtime-developer-xyz789") is not None

    def test_fork_session_records_parent_session_id(self, db, fake_agent_factory):
        manager = SessionManager(agent_factory=fake_agent_factory, db=db)
        original = manager.create_session(
            cwd="/workspace",
            session_id="role-role-team-runtime-planner-abc123",
            role_metadata={
                "role_title": "Planner",
                "execution_mode": "persistent_role_instance",
            },
        )
        forked = manager.fork_session(original.session_id, cwd="/workspace/fork")

        assert forked is not None
        assert forked.parent_session_id == original.session_id
        assert forked.session_id != original.session_id
        row = db.get_session(forked.session_id)
        assert row is not None
        assert row["parent_session_id"] == original.session_id
