from __future__ import annotations

import json
from pathlib import Path

import pytest

from hermes_cli import kanban_db as kb
from hermes_cli.production_order_db import (
    WORKFLOW_SPEC_SOURCE,
    run_architect_spec_bridge,
    run_full_bridge,
    run_orchestrator_triage_bridge,
)
from hermes_cli.production_order_dispatch import (
    DispatchManifestError,
    apply_accepted_result_action,
    build_dispatch_manifest,
    build_manual_fallback_handoff,
    build_profile_task_envelope,
    execute_profile_dispatch,
    ingest_profile_result_packet,
)
from hermes_cli.production_order_autonomous import (
    collect_profile_result_packet,
    invoke_profile_task,
)


@pytest.fixture
def kanban_home(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    kb.init_db()
    yield


@pytest.fixture
def conn(kanban_home):
    conn = kb.connect()
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def sample_brief() -> dict:
    return {
        "title": "Test authentication feature",
        "objective": "Add JWT authentication to the Relay demo",
        "target repo or workspace": "relay-go-app",
        "scope": "Implement /login and /register endpoints",
        "out of scope": "OAuth, password reset",
        "acceptance criteria": "All tests pass, protected routes reject unauthenticated requests",
        "stop conditions": "Secret management requires external service",
        "approval boundaries": "No spending, no publishing",
        "constraints": "Use existing Go module",
        "expected output": "Working auth endpoints with tests",
    }


def architect_spec_packet(production_order_id: str) -> dict:
    return {
        "production_order_id": production_order_id,
        "packet_type": "architect_spec_packet",
        "stage": "architect_spec",
        "owner_profile": "architect_os",
        "source_state": "ARCHITECT_SPEC",
        "objective": "Specify the bounded production-order handoff.",
        "source_truth": [WORKFLOW_SPEC_SOURCE],
        "scope": ["Attach a DevOS handoff packet and advance the production order state."],
        "out_of_scope": ["DevOS implementation execution"],
        "acceptance_criteria": [
            "Production order transitions to ARCHITECT_READY_FOR_DEV.",
            "Current owner becomes dev_os.",
        ],
        "devos_task": "Prepare for implementation from the approved spec.",
        "files_or_areas_allowed": [
            "hermes_cli/production_order_db.py",
            "hermes_cli/production_order_dispatch.py",
            "tests/hermes_cli/test_production_order_autonomous_engine.py",
        ],
        "stop_conditions": [
            "Production order is not in ARCHITECT_SPEC.",
            "Current owner is not architect_os.",
        ],
        "approval_boundaries": ["Do not trigger unapproved execution."],
        "artifact_references": ["architect-spec.json"],
        "next_state": "ARCHITECT_READY_FOR_DEV",
    }


def devos_build_packet(production_order_id: str) -> dict:
    return {
        "production_order_id": production_order_id,
        "packet_type": "devos_build_packet",
        "owner_profile": "dev_os",
        "source_state": "ARCHITECT_READY_FOR_DEV",
        "result_type": "build_complete",
        "summary": "Implemented the approved bridge and preserved graph semantics.",
        "files_changed": [
            "hermes_cli/production_order_db.py",
            "hermes_cli/production_order_dispatch.py",
            "tests/hermes_cli/test_production_order_autonomous_engine.py",
        ],
        "tests_run": [
            "pytest tests/hermes_cli/test_production_order_autonomous_engine.py -q",
        ],
        "test_status": "green",
        "limitations_or_notes": ["AuditOS should verify smoke evidence against the existing board."],
        "next_handoff_target": "audit_os",
    }


def create_architect_spec_order(conn, sample_brief):
    po = run_full_bridge(
        conn,
        title=sample_brief["title"],
        source_brief=json.dumps(sample_brief),
        priority_lane="Relay",
        repo_or_workspace=sample_brief["target repo or workspace"],
    )
    return run_orchestrator_triage_bridge(conn, production_order_id=po.production_order_id)


def create_ready_for_dev_order(conn, sample_brief):
    po = create_architect_spec_order(conn, sample_brief)
    return run_architect_spec_bridge(
        conn,
        production_order_id=po.production_order_id,
        architect_packet=architect_spec_packet(po.production_order_id),
    )


def test_execute_profile_dispatch_explicitly_reports_manual_fallback_until_safe_invoker_exists(conn, sample_brief):
    po = create_ready_for_dev_order(conn, sample_brief)

    result = execute_profile_dispatch(conn, po.production_order_id)

    assert result["executed"] is False
    assert result["fallback_required"] is True
    assert result["target_profile"] == "dev_os"
    assert result["result_packet"] is None
    assert result["manual_fallback"]["target_profile"] == "dev_os"
    assert result["manual_fallback"]["bridge_function"] == "run_devos_complete_bridge"
    assert "No safe synchronous profile invocation mechanism is available" in result["error"]
    assert result["next_action"] == "manual_fallback_required"


def test_manual_fallback_contract_remains_available_for_orchestrator_direct_bridge_routes(conn, sample_brief):
    po = run_full_bridge(
        conn,
        title=sample_brief["title"],
        source_brief=json.dumps(sample_brief),
        priority_lane="Relay",
        repo_or_workspace=sample_brief["target repo or workspace"],
    )

    manifest = build_dispatch_manifest(conn, po.production_order_id)
    envelope = build_profile_task_envelope(conn, po.production_order_id)
    handoff = build_manual_fallback_handoff(conn, po.production_order_id)

    assert manifest.target_profile == "orchestrator_os"
    assert manifest.bridge_function == "run_orchestrator_triage_bridge"
    assert envelope.expected_output_packet["bridge_function"] == "run_orchestrator_triage_bridge"
    assert handoff.target_profile == "orchestrator_os"
    assert handoff.bridge_function == "run_orchestrator_triage_bridge"
    assert "Call run_orchestrator_triage_bridge(" in handoff.result_return_action


def test_downstream_result_action_requires_ingestion_before_application(conn, sample_brief):
    po = create_ready_for_dev_order(conn, sample_brief)
    packet = devos_build_packet(po.production_order_id)

    with pytest.raises(DispatchManifestError, match="accepted"):
        apply_accepted_result_action(conn, po.production_order_id, result_packet=packet)

    ingestion = ingest_profile_result_packet(conn, po.production_order_id, packet)
    applied = apply_accepted_result_action(conn, po.production_order_id, result_packet=packet)

    assert ingestion["accepted"] is True
    assert ingestion["runtime_action"].startswith("run_devos_complete_bridge(")
    assert applied["applied"] is True
    assert applied["bridge_function"] == "run_devos_complete_bridge"
    assert applied["to_state"] == "DEV_COMPLETE"


def test_invoke_profile_task_accepts_fake_runner_and_collects_single_packet(conn, sample_brief):
    po = create_ready_for_dev_order(conn, sample_brief)
    envelope = build_profile_task_envelope(conn, po.production_order_id)

    def fake_runner(payload: dict) -> dict:
        assert payload["production_order_id"] == po.production_order_id
        assert payload["target_profile"] == "dev_os"
        return {
            "stdout": "",
            "stderr": "",
            "exit_code": 0,
            "duration_ms": 17,
            "result_channel": devos_build_packet(po.production_order_id),
        }

    invocation = invoke_profile_task(envelope, runner=fake_runner, timeout_seconds=30)
    packet = collect_profile_result_packet(invocation, envelope)

    assert invocation.exit_code == 0
    assert invocation.duration_ms == 17
    assert invocation.log_ref.startswith("profile-invocation:")
    assert packet["production_order_id"] == po.production_order_id
    assert packet["owner_profile"] == "dev_os"
    assert packet["source_state"] == envelope.source_state


@pytest.mark.parametrize(
    ("runner_payload", "error_match"),
    [
        ({"stdout": "done", "stderr": "", "exit_code": 0, "duration_ms": 5}, "free-text-only output"),
        ({"stdout": "{not-json}", "stderr": "", "exit_code": 0, "duration_ms": 5}, "malformed JSON"),
        (
            {
                "stdout": "",
                "stderr": "",
                "exit_code": 0,
                "duration_ms": 5,
                "result_channel": [
                    {"packet_type": "devos_build_packet"},
                    {"packet_type": "devos_build_packet"},
                ],
            },
            "multiple competing packets",
        ),
    ],
)
def test_collect_profile_result_packet_rejects_ambiguous_or_non_structured_output(
    conn,
    sample_brief,
    runner_payload,
    error_match,
):
    po = create_ready_for_dev_order(conn, sample_brief)
    envelope = build_profile_task_envelope(conn, po.production_order_id)

    invocation = invoke_profile_task(
        envelope,
        runner=lambda payload: runner_payload,
        timeout_seconds=30,
    )

    with pytest.raises(ValueError, match=error_match):
        collect_profile_result_packet(invocation, envelope)


@pytest.mark.parametrize(
    ("mutator", "error_match"),
    [
        (lambda packet: packet.__setitem__("production_order_id", "PO-wrong"), "production_order_id"),
        (lambda packet: packet.__setitem__("owner_profile", "architect_os"), "owner_profile"),
        (lambda packet: packet.__setitem__("source_state", "ARCHITECT_SPEC"), "source_state"),
        (lambda packet: packet.__setitem__("current_owner_profile", "audit_os"), "mutate workflow state directly"),
    ],
)
def test_collect_profile_result_packet_rejects_invalid_packet_contract_fields(
    conn,
    sample_brief,
    mutator,
    error_match,
):
    po = create_ready_for_dev_order(conn, sample_brief)
    envelope = build_profile_task_envelope(conn, po.production_order_id)
    packet = devos_build_packet(po.production_order_id)
    mutator(packet)

    invocation = invoke_profile_task(
        envelope,
        runner=lambda payload: {
            "stdout": "",
            "stderr": "",
            "exit_code": 0,
            "duration_ms": 9,
            "result_channel": packet,
        },
        timeout_seconds=30,
    )

    with pytest.raises(ValueError, match=error_match):
        collect_profile_result_packet(invocation, envelope)
