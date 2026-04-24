"""Tests for SessionDB-backed persistent role sessions."""

from __future__ import annotations

import json
from pathlib import Path

from agent.role_runtime import resolve_role
from hermes_state import SessionDB
from tools.role_invocation_tool import _run_persistent_role_agent, invoke_role

REGISTRY_PATH = (
    Path(__file__).resolve().parents[2]
    / "web"
    / "src"
    / "data"
    / "hermesOrgChart.registry.yaml"
)


def _fake_role_runner(
    *,
    packet_content: str,
    role_session_id: str,
    role_system_prompt: str,
    session_db: object,
    parent_session_id: str | None,
    role_agent_config: dict | None = None,
) -> str:
    return (
        f"actual role response from {role_session_id}\n"
        f"prompt includes Developer: {'Developer' in role_system_prompt}\n"
        f"packet includes task: {'Implement persistence' in packet_content}\n"
        f"parent session: {parent_session_id}\n"
        f"db provided: {session_db is not None}\n"
        f"config provided: {role_agent_config is not None}"
    )


def test_get_or_create_role_session_resumes_same_role_session(tmp_path):
    from agent.role_runtime import get_or_create_role_session

    db = SessionDB(db_path=tmp_path / "state.db")
    try:
        db.create_session(session_id="lead-001", source="cli")
        developer = resolve_role("Developer", path=REGISTRY_PATH)

        first = get_or_create_role_session(
            session_db=db,
            plan_id="Role Team Runtime",
            role=developer,
            parent_session_id="lead-001",
            execution_mode="persistent_role_instance",
            policy_default_execution_mode="persistent_role_instance",
            task_packet_path="_plans/role-team-runtime/roles/developer/packets/one.md",
            artifact_paths={"packet": "one.md"},
        )
        second = get_or_create_role_session(
            session_db=db,
            plan_id="Role Team Runtime",
            role=developer,
            parent_session_id="lead-001",
            execution_mode="persistent_role_instance",
            policy_default_execution_mode="persistent_role_instance",
            task_packet_path="_plans/role-team-runtime/roles/developer/packets/two.md",
            artifact_paths={"packet": "two.md"},
        )

        assert first.session_id == second.session_id
        row = db.get_session(first.session_id)
        assert row is not None
        assert row["parent_session_id"] == "lead-001"
        meta = json.loads(row["model_config"])
        assert meta["role_metadata"]["plan_id"] == "role-team-runtime"
        assert meta["role_metadata"]["canonical_role"] == "Developer"
        assert meta["role_metadata"]["persistent_session_id"] == first.session_id
        assert meta["role_metadata"]["task_packet_path"].endswith("two.md")
    finally:
        db.close()


def test_get_or_create_role_session_isolates_different_roles(tmp_path):
    from agent.role_runtime import get_or_create_role_session

    db = SessionDB(db_path=tmp_path / "state.db")
    try:
        db.create_session(session_id="lead-001", source="cli")
        developer = resolve_role("Developer", path=REGISTRY_PATH)
        validator = resolve_role("Technical Validator", path=REGISTRY_PATH)

        dev_session = get_or_create_role_session(
            session_db=db,
            plan_id="Role Team Runtime",
            role=developer,
            parent_session_id="lead-001",
            execution_mode="persistent_role_instance",
            policy_default_execution_mode="persistent_role_instance",
        )
        validator_session = get_or_create_role_session(
            session_db=db,
            plan_id="Role Team Runtime",
            role=validator,
            parent_session_id="lead-001",
            execution_mode="persistent_role_instance",
            policy_default_execution_mode="persistent_role_instance",
        )

        assert dev_session.session_id != validator_session.session_id
        assert db.get_session(dev_session.session_id)["parent_session_id"] == "lead-001"
        assert db.get_session(validator_session.session_id)["parent_session_id"] == "lead-001"
    finally:
        db.close()


def test_retire_role_session_marks_session_inactive_without_deleting_history(tmp_path):
    from agent.role_runtime import get_or_create_role_session, retire_role_session

    db = SessionDB(db_path=tmp_path / "state.db")
    try:
        db.create_session(session_id="lead-001", source="cli")
        developer = resolve_role("Developer", path=REGISTRY_PATH)
        role_session = get_or_create_role_session(
            session_db=db,
            plan_id="Role Team Runtime",
            role=developer,
            parent_session_id="lead-001",
            execution_mode="persistent_role_instance",
            policy_default_execution_mode="persistent_role_instance",
        )

        retired = retire_role_session(
            session_db=db,
            plan_id="Role Team Runtime",
            role=developer,
            status="paused",
            reason="role_retired",
        )

        assert retired.session_id == role_session.session_id
        row = db.get_session(role_session.session_id)
        assert row is not None
        assert row["ended_at"] is not None
        assert row["end_reason"] == "role_retired"
        meta = json.loads(row["model_config"])
        assert meta["role_metadata"]["status"] == "paused"
        assert meta["role_metadata"]["retired_at"]
        assert meta["role_metadata"]["persistent_session_id"] == role_session.session_id
    finally:
        db.close()


def test_get_or_create_role_session_reopens_retired_role_session(tmp_path):
    from agent.role_runtime import get_or_create_role_session, retire_role_session

    db = SessionDB(db_path=tmp_path / "state.db")
    try:
        db.create_session(session_id="lead-001", source="cli")
        developer = resolve_role("Developer", path=REGISTRY_PATH)
        original = get_or_create_role_session(
            session_db=db,
            plan_id="Role Team Runtime",
            role=developer,
            parent_session_id="lead-001",
            execution_mode="persistent_role_instance",
            policy_default_execution_mode="persistent_role_instance",
        )
        retire_role_session(
            session_db=db,
            plan_id="Role Team Runtime",
            role=developer,
            status="paused",
            reason="role_retired",
        )

        resumed = get_or_create_role_session(
            session_db=db,
            plan_id="Role Team Runtime",
            role=developer,
            parent_session_id="lead-001",
            execution_mode="persistent_role_instance",
            policy_default_execution_mode="persistent_role_instance",
            task_packet_path="_plans/role-team-runtime/roles/developer/packets/resume.md",
        )

        assert resumed.session_id == original.session_id
        row = db.get_session(resumed.session_id)
        assert row["ended_at"] is None
        assert row["end_reason"] is None
        meta = json.loads(row["model_config"])
        assert meta["role_metadata"]["status"] == "active"
        assert "retired_at" not in meta["role_metadata"]
        assert meta["role_metadata"]["task_packet_path"].endswith("resume.md")
    finally:
        db.close()


def test_invoke_role_persistent_mode_runs_role_and_records_actual_output(tmp_path):
    db = SessionDB(db_path=tmp_path / "state.db")
    try:
        db.create_session(session_id="lead-001", source="cli")
        result = json.loads(
            invoke_role(
                role="Developer",
                plan_id="Role Team Runtime",
                summary="Lead summary fallback must not become the role output",
                workspace_root=tmp_path,
                registry_path=REGISTRY_PATH,
                session_id="lead-001",
                session_db=db,
                packet_content="Implement persistence for role sessions",
                role_runner=_fake_role_runner,
            )
        )

        assert result["success"] is True
        assert result["execution_mode"] == "persistent_role_instance"
        role_sid = result["persistent_session_id"]
        assert role_sid == result["role_session_id"]

        row = db.get_session(role_sid)
        assert row is not None
        assert row["parent_session_id"] == "lead-001"
        meta = json.loads(row["model_config"])
        assert meta["role_metadata"]["canonical_role"] == "Developer"

        output_path = Path(result["artifact_paths"]["output"])
        output_text = output_path.read_text(encoding="utf-8")
        assert "actual role response from" in output_text
        assert "Lead summary fallback" not in output_text

        utilization = json.loads(
            (tmp_path / "_plans" / "role-team-runtime" / "04-role-utilization-report.json").read_text(
                encoding="utf-8"
            )
        )
        role_record = utilization["roles"][0]
        assert role_record["persistent_session_id"] == role_sid
        assert role_record["parent_session_id"] == "lead-001"
        assert role_record["artifact_paths"]["output"] == result["artifact_paths"]["output_relative"]
    finally:
        db.close()


def test_run_persistent_role_agent_replays_role_session_history(monkeypatch):
    captured = {}
    history = [{"role": "assistant", "content": "prior role context"}]

    class FakeSessionDB:
        def get_messages_as_conversation(self, session_id: str):
            captured["loaded_session_id"] = session_id
            return history

    class FakeAgent:
        def __init__(self, **kwargs):
            captured["agent_kwargs"] = kwargs

        def run_conversation(self, packet_content: str, conversation_history=None):
            captured["packet_content"] = packet_content
            captured["conversation_history"] = conversation_history
            return {"final_response": "role response with history"}

    import run_agent

    monkeypatch.setattr(run_agent, "AIAgent", FakeAgent)

    response = _run_persistent_role_agent(
        packet_content="new packet",
        role_session_id="role-plan-developer-abc123",
        role_system_prompt="Developer role prompt",
        session_db=FakeSessionDB(),
        parent_session_id="lead-001",
        role_agent_config={"model": "gpt-test", "ignored": "value"},
    )

    assert response == "role response with history"
    assert captured["loaded_session_id"] == "role-plan-developer-abc123"
    assert captured["conversation_history"] == history
    assert captured["agent_kwargs"]["session_id"] == "role-plan-developer-abc123"
    assert captured["agent_kwargs"]["parent_session_id"] == "lead-001"
    assert captured["agent_kwargs"]["session_db"] is not None
    assert captured["agent_kwargs"]["ephemeral_system_prompt"] == "Developer role prompt"
