from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest


def _valid_request(**overrides):
    data = {
        "title": "Restart dashboard proxy",
        "project": "Hermes Ops",
        "profile": "default",
        "risk_label": "Live-service",
        "proposed_action": "Restart dashboard proxy only, not the messaging gateway",
        "target": "hermes-dashboard.service",
        "preview": "systemctl --user restart hermes-dashboard.service",
        "reason": "Dashboard proxy is down while gateway is healthy",
        "rollback_or_verification": "Verify /api/status returns 200 after restart",
        "created_by": "test",
    }
    data.update(overrides)
    return data


def test_approval_store_creates_request_and_appends_audit(_isolate_hermes_home):
    from hermes_cli.ops_approvals import ApprovalStore

    store = ApprovalStore()
    approval = store.create(_valid_request())

    assert approval["id"].startswith("appr_")
    assert approval["status"] == "pending"
    assert approval["execution_allowed"] is False
    assert approval["blocked_until_approved"] is True
    assert approval["risk_label"] == "Live-service"
    assert approval["generated_command"] is None

    current = store.list()
    assert [item["id"] for item in current] == [approval["id"]]

    audit_path = store.audit_path
    lines = audit_path.read_text().splitlines()
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["event"] == "created"
    assert event["approval_id"] == approval["id"]


def test_approval_decision_records_approve_without_execution(_isolate_hermes_home):
    from hermes_cli.ops_approvals import ApprovalStore

    store = ApprovalStore()
    approval = store.create(_valid_request())
    decided = store.decide(approval["id"], "approved", decided_by="Travis", decision_note="Approved for dashboard only")

    assert decided["status"] == "approved"
    assert decided["decided_by"] == "Travis"
    assert decided["execution_allowed"] is False
    assert "approved:" in decided["generated_command"].lower()
    assert "Restart dashboard proxy" in decided["generated_command"]

    events = [json.loads(line) for line in store.audit_path.read_text().splitlines()]
    assert [event["event"] for event in events] == ["created", "approved"]


def test_approval_store_rejects_invalid_transition(_isolate_hermes_home):
    from hermes_cli.ops_approvals import ApprovalStore, ApprovalError

    store = ApprovalStore()
    approval = store.create(_valid_request())
    store.decide(approval["id"], "rejected", decided_by="Travis")

    with pytest.raises(ApprovalError):
        store.decide(approval["id"], "approved", decided_by="Travis")


def test_approval_store_marks_expired_items(_isolate_hermes_home):
    from hermes_cli.ops_approvals import ApprovalStore

    store = ApprovalStore()
    approval = store.create(_valid_request(expires_at="2000-01-01T00:00:00+00:00"))

    listed = store.list(now=datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert listed[0]["id"] == approval["id"]
    assert listed[0]["status"] == "expired"


def test_approval_api_records_decision_but_has_no_execute_route(_isolate_hermes_home):
    try:
        from starlette.testclient import TestClient
    except ImportError:
        pytest.skip("fastapi/starlette not installed")

    from hermes_cli.web_server import app, _SESSION_HEADER_NAME, _SESSION_TOKEN

    client = TestClient(app)
    client.headers[_SESSION_HEADER_NAME] = _SESSION_TOKEN

    create_resp = client.post("/api/ops/approvals", json=_valid_request())
    assert create_resp.status_code == 200
    approval = create_resp.json()
    assert approval["status"] == "pending"
    assert approval["execution_allowed"] is False

    approve_resp = client.post(
        f"/api/ops/approvals/{approval['id']}/approve",
        json={"decided_by": "Travis", "decision_note": "Approved for dashboard proxy only"},
    )
    assert approve_resp.status_code == 200
    decided = approve_resp.json()
    assert decided["status"] == "approved"
    assert decided["execution_allowed"] is False
    assert decided["generated_command"]

    route_paths = {getattr(route, "path", "") for route in app.routes}
    assert f"/api/ops/approvals/{{approval_id}}/execute" not in route_paths
    execute_resp = client.post(f"/api/ops/approvals/{approval['id']}/execute")
    assert execute_resp.status_code in {404, 405}
