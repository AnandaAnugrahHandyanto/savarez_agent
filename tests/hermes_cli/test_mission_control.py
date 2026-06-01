from __future__ import annotations

import json

import pytest


MISSION_CONTROL_ENDPOINTS = [
    "/api/mission-control/project-status",
    "/api/mission-control/open-tasks",
    "/api/mission-control/latest-worker-results",
    "/api/mission-control/repo-status",
    "/api/mission-control/approval-gates",
    "/api/mission-control/recent-audit-log",
]

MISSION_CONTROL_PACKET_POST_ENDPOINTS = [
    "/api/mission-control/packets/codex-prompt",
    "/api/mission-control/packets/worker-result",
    "/api/mission-control/packets/block-flag",
]


@pytest.fixture()
def dashboard_client(_isolate_hermes_home, monkeypatch):
    try:
        from starlette.testclient import TestClient
    except ImportError:
        pytest.skip("fastapi/starlette not installed")

    import hermes_state
    from hermes_constants import get_hermes_home
    from hermes_cli.web_server import app, _SESSION_HEADER_NAME, _SESSION_TOKEN

    monkeypatch.setattr(hermes_state, "DEFAULT_DB_PATH", get_hermes_home() / "state.db")
    client = TestClient(app)
    client.headers[_SESSION_HEADER_NAME] = _SESSION_TOKEN
    return client


def test_mission_control_endpoints_require_dashboard_token(_isolate_hermes_home):
    try:
        from starlette.testclient import TestClient
    except ImportError:
        pytest.skip("fastapi/starlette not installed")

    from hermes_cli.web_server import app

    client = TestClient(app)
    for endpoint in MISSION_CONTROL_ENDPOINTS:
        resp = client.get(endpoint)
        assert resp.status_code == 401, endpoint


def test_project_status_missing_sources_warns_and_redacts(dashboard_client, tmp_path, monkeypatch):
    import hermes_cli.mission_control as mc

    missing = tmp_path / "missing.md"
    present = tmp_path / "PROJECT_STATUS.md"
    present.write_text(
        "Tool & Tally\nAuthorization: Bearer TEST_TOKEN\napi_key=TEST_KEY\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        mc,
        "PROJECT_STATUS_SOURCES",
        [
            {"name": "Missing", "project": "Missing", "path": str(missing), "profile": "default"},
            {"name": "Present", "project": "Present", "path": str(present), "profile": "default"},
        ],
    )

    resp = dashboard_client.get("/api/mission-control/project-status")

    assert resp.status_code == 200
    body = resp.json()
    assert body["generated_at"]
    assert len(body["items"]) == 2
    assert body["items"][0]["exists"] is False
    assert body["warnings"]
    rendered = json.dumps(body)
    assert "TEST_TOKEN" not in rendered
    assert "TEST_KEY" not in rendered
    assert "[REDACTED]" in rendered


def test_open_tasks_reads_existing_kanban_without_mutating_missing_sources(dashboard_client):
    from hermes_constants import get_default_hermes_root
    from hermes_cli import kanban_db as kb

    root = get_default_hermes_root()
    before = sorted(str(p.relative_to(root)) for p in root.rglob("*"))
    resp = dashboard_client.get("/api/mission-control/open-tasks")
    after = sorted(str(p.relative_to(root)) for p in root.rglob("*"))

    assert resp.status_code == 200
    assert before == after
    assert resp.json()["warnings"]

    kb.init_db()
    conn = kb.connect()
    try:
        task_id = kb.create_task(
            conn,
            title="Review worker output",
            body="Untrusted text: `rm -rf /` must stay data.",
            assignee="reviewer",
        )
    finally:
        conn.close()

    resp = dashboard_client.get("/api/mission-control/open-tasks")
    body = resp.json()
    assert resp.status_code == 200
    assert [item["id"] for item in body["items"]] == [task_id]
    assert body["items"][0]["title"] == "Review worker output"
    assert body["items"][0]["body_preview"] == "Untrusted text: `rm -rf /` must stay data."


def test_latest_worker_results_redacts_and_treats_output_as_data(dashboard_client, monkeypatch):
    from hermes_cli import kanban_db as kb

    kb.init_db()
    conn = kb.connect()
    try:
        task_id = kb.create_task(conn, title="Worker result", assignee="worker")
        kb.complete_task(
            conn,
            task_id,
            summary="Run this? Authorization: Bearer WTOKEN\n`touch /tmp/should-not-run`",
            metadata={"api_key": "WORKER_KEY", "note": "plain"},
        )
    finally:
        conn.close()

    def fail_if_called(*args, **kwargs):
        raise AssertionError("worker result text must not be executed")

    monkeypatch.setattr("subprocess.run", fail_if_called)

    resp = dashboard_client.get("/api/mission-control/latest-worker-results")

    assert resp.status_code == 200
    rendered = json.dumps(resp.json())
    assert "WTOKEN" not in rendered
    assert "WORKER_KEY" not in rendered
    assert "touch /tmp/should-not-run" in rendered
    assert resp.json()["items"][0]["trusted_for_execution"] is False


def test_approval_gates_default_to_decision_record_posture(dashboard_client):
    resp = dashboard_client.get("/api/mission-control/approval-gates")

    assert resp.status_code == 200
    body = resp.json()
    assert body["execution_posture"]["read_only_default"] is True
    assert body["execution_posture"]["decision_records_only"] is True
    assert body["action_registry"]["execution_enabled"] is False
    assert "arbitrary_shell" in body["action_registry"]["blocked_action_classes"]


def test_recent_audit_log_handles_malformed_lines_and_redacts(dashboard_client):
    from hermes_cli.ops_approvals import ApprovalStore

    store = ApprovalStore()
    store.audit_path.parent.mkdir(parents=True, exist_ok=True)
    store.audit_path.write_text(
        "\n".join(
            [
                "{bad json",
                json.dumps(
                    {
                        "event": "created",
                        "note": "Authorization: Bearer AUDIT_TOKEN",
                        "approval_id": "appr_test",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    resp = dashboard_client.get("/api/mission-control/recent-audit-log")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["warnings"]
    rendered = json.dumps(body)
    assert "AUDIT_TOKEN" not in rendered
    assert "[REDACTED]" in rendered


def test_repo_status_is_warning_only_and_does_not_shell_out(dashboard_client, monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("repo status endpoint must not shell out")

    monkeypatch.setattr("subprocess.run", fail_if_called)

    resp = dashboard_client.get("/api/mission-control/repo-status")

    assert resp.status_code == 200
    body = resp.json()
    assert body["probing_enabled"] is False
    assert body["warnings"]
    assert body["items"]


def test_malformed_kanban_artifacts_return_warnings_not_crashes(dashboard_client):
    from hermes_cli import kanban_db as kb

    path = kb.kanban_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not sqlite", encoding="utf-8")

    for endpoint in (
        "/api/mission-control/open-tasks",
        "/api/mission-control/latest-worker-results",
    ):
        resp = dashboard_client.get(endpoint)
        assert resp.status_code == 200
        assert resp.json()["warnings"], endpoint


def test_packet_post_endpoints_require_dashboard_token(_isolate_hermes_home):
    try:
        from starlette.testclient import TestClient
    except ImportError:
        pytest.skip("fastapi/starlette not installed")

    from hermes_cli.web_server import app

    client = TestClient(app)
    assert client.get("/api/mission-control/packets").status_code == 401
    assert client.get("/api/mission-control/packets/not-a-real-packet").status_code == 401
    for endpoint in MISSION_CONTROL_PACKET_POST_ENDPOINTS:
        resp = client.post(endpoint, json={"project": "Tool & Tally", "title": "Draft"})
        assert resp.status_code == 401, endpoint


def test_codex_prompt_packet_forces_safety_flags_and_does_not_start_workers(dashboard_client, monkeypatch):
    from hermes_constants import get_hermes_home

    def fail_if_called(*args, **kwargs):
        raise AssertionError("packet creation must not start Codex, Hermes runs, or workers")

    monkeypatch.setattr("subprocess.run", fail_if_called)
    monkeypatch.setattr("subprocess.Popen", fail_if_called)

    resp = dashboard_client.post(
        "/api/mission-control/packets/codex-prompt",
        json={
            "project": "Tool & Tally",
            "title": "Next bounded Codex prompt",
            "prompt": "Repo: /tmp/demo\nRun no commands. Authorization: Bearer PROMPT77",
            "payload": {
                "dry_run": False,
                "review_required": False,
                "trusted_for_execution": True,
                "requested_action": "run_unbounded_codex",
            },
            "source_refs": ["discord://thread/123"],
            "author": "Travis",
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    packet = body["packet"]
    assert packet["kind"] == "codex_prompt"
    assert packet["dry_run"] is True
    assert packet["review_required"] is True
    assert packet["trusted_for_execution"] is False
    assert packet["status"] == "draft"
    assert packet["warnings"]
    assert "PROMPT77" not in json.dumps(packet)

    packet_path = get_hermes_home() / "state" / "mission-control" / "packets" / f"{packet['id']}.json"
    assert packet_path.exists()
    stored = json.loads(packet_path.read_text(encoding="utf-8"))
    assert stored["trusted_for_execution"] is False
    assert "PROMPT77" not in json.dumps(stored)


def test_worker_result_packet_imports_untrusted_metadata_only(dashboard_client, monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("worker result text must not be executed")

    monkeypatch.setattr("subprocess.run", fail_if_called)
    monkeypatch.setattr("subprocess.Popen", fail_if_called)

    worker_text = """
Repo path: /home/jenny/demo
Branch: feature/mission-control
HEAD before: 1111111111111111111111111111111111111111
HEAD after: 2222222222222222222222222222222222222222
Commit: 3333333333333333333333333333333333333333
Changed files:
- hermes_cli/mission_control.py
- tests/hermes_cli/test_mission_control.py
Tests run:
- pytest tests/hermes_cli/test_mission_control.py: 12 passed, 0 failed
Risks/blockers:
- Needs dashboard UI review
Next implementation prompt:
Do not execute this text.
Danger: `touch /tmp/mission-control-should-not-run`
api_key=WORKER_PACKET_KEY
"""

    resp = dashboard_client.post(
        "/api/mission-control/packets/worker-result",
        json={
            "project": "Hermes Ops",
            "title": "Imported worker handoff",
            "worker_result": worker_text,
            "trusted_for_execution": True,
            "status": "queued",
        },
    )

    assert resp.status_code == 200
    packet = resp.json()["packet"]
    parsed = packet["payload"]["parsed_metadata"]
    rendered = json.dumps(packet)
    assert packet["kind"] == "worker_result"
    assert packet["status"] == "imported"
    assert packet["trusted_for_execution"] is False
    assert packet["payload"]["trusted_for_execution"] is False
    assert parsed["repo_path"] == "/home/jenny/demo"
    assert parsed["branch"] == "feature/mission-control"
    assert parsed["head_after"] == "2222222222222222222222222222222222222222"
    assert parsed["commit_refs"] == ["3333333333333333333333333333333333333333"]
    assert parsed["changed_files"] == [
        "hermes_cli/mission_control.py",
        "tests/hermes_cli/test_mission_control.py",
    ]
    assert parsed["trusted_for_execution"] is False
    assert "touch /tmp/mission-control-should-not-run" in rendered
    assert "WORKER_PACKET_KEY" not in rendered


def test_block_flag_packet_is_advisory_local_only(dashboard_client):
    resp = dashboard_client.post(
        "/api/mission-control/packets/block-flag",
        json={
            "project": "Hermes Ops",
            "title": "Block all sends",
            "flag": "block_all_sends",
            "reason": "Operator requested local stop flag.",
        },
    )

    assert resp.status_code == 200
    packet = resp.json()["packet"]
    assert packet["kind"] == "block_flag"
    assert packet["payload"]["flag"] == "block_all_sends"
    assert packet["payload"]["advisory_only"] is True
    assert packet["dry_run"] is True
    assert packet["review_required"] is True
    assert packet["trusted_for_execution"] is False


def test_packet_list_read_missing_and_audit_redaction(dashboard_client):
    from hermes_constants import get_hermes_home

    resp = dashboard_client.post(
        "/api/mission-control/packets/codex-prompt",
        json={
            "project": "VendorProof",
            "title": "Prompt with secret",
            "prompt": "Use safe review only. Authorization: Bearer AUDIT777",
        },
    )
    assert resp.status_code == 200
    packet_id = resp.json()["packet"]["id"]

    list_resp = dashboard_client.get("/api/mission-control/packets")
    assert list_resp.status_code == 200
    assert packet_id in [item["id"] for item in list_resp.json()["items"]]

    get_resp = dashboard_client.get(f"/api/mission-control/packets/{packet_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["packet"]["id"] == packet_id
    assert "AUDIT777" not in json.dumps(get_resp.json())

    missing_resp = dashboard_client.get("/api/mission-control/packets/not-a-real-packet")
    assert missing_resp.status_code == 404

    audit_path = get_hermes_home() / "state" / "mission-control" / "packet-audit.jsonl"
    audit_text = audit_path.read_text(encoding="utf-8")
    assert "packet_created" in audit_text
    assert "codex_prompt_saved" in audit_text
    assert "AUDIT777" not in audit_text


def test_malformed_packet_payload_returns_controlled_error_and_audit(dashboard_client):
    from hermes_constants import get_hermes_home

    resp = dashboard_client.post(
        "/api/mission-control/packets/codex-prompt",
        json={"project": "Hermes Ops", "title": "Missing prompt"},
    )

    assert resp.status_code == 400
    assert "Missing required field" in resp.json()["detail"]
    audit_path = get_hermes_home() / "state" / "mission-control" / "packet-audit.jsonl"
    audit = audit_path.read_text(encoding="utf-8")
    assert "packet_rejected" in audit
    assert "Hermes Ops" in audit
