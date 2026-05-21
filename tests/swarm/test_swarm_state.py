import json

from agent.swarm_state import EvalResult, PermissionGrant, RoutingPlan, SwarmJob


def test_swarm_job_create_sets_defaults_and_stable_shape():
    job = SwarmJob.create(
        "please check the logs",
        platform="slack",
        user_id="U1",
        chat_id="C1",
        session_id="S1",
        created_at="2026-05-21T00:00:00+00:00",
    )

    assert job.job_id.startswith("swarm_")
    assert job.status == "received"
    assert job.created_at == "2026-05-21T00:00:00+00:00"
    assert job.updated_at == job.created_at
    assert job.original_request == "please check the logs"
    assert job.tasks == []
    assert job.audit == []

    same = SwarmJob.create(
        "please check the logs",
        platform="slack",
        user_id="U1",
        chat_id="C1",
        session_id="S1",
        created_at="2026-05-21T00:00:00+00:00",
    )
    assert same.job_id == job.job_id


def test_add_task_appends_task_and_audit_event():
    job = SwarmJob.create("do work")
    task = job.add_task("Research", "look up docs", mode="swarm", toolsets=["web"])

    assert task in job.tasks
    assert task.status == "queued"
    assert job.audit[-1].event_type == "task_added"
    assert job.audit[-1].metadata["task_id"] == task.task_id


def test_transition_records_status_change_and_audit_event():
    job = SwarmJob.create("do work")
    job.transition("triaging", metadata={"reason": "shadow"})

    assert job.status == "triaging"
    assert job.audit[-1].event_type == "status_changed"
    assert job.audit[-1].metadata["from"] == "received"
    assert job.audit[-1].metadata["to"] == "triaging"
    assert job.audit[-1].metadata["reason"] == "shadow"


def test_json_round_trip_preserves_nested_data():
    job = SwarmJob.create("deploy after approval", platform="slack", user_id="U1")
    grant = PermissionGrant("perm_deploy", "Deploy production", scope={"env": "prod"})
    job.permissions.append(grant)
    job.evals.append(EvalResult("unit", True, "passed"))
    job.routing_plan = RoutingPlan(
        mode="swarm",
        reason="multi-step",
        suggested_tasks=[{"title": "Review code"}],
        permission_requests=[grant],
        verification_required=True,
    )
    job.add_task("Review code", permission_required=True)

    encoded = json.loads(json.dumps(job.to_dict()))
    restored = SwarmJob.from_dict(encoded)

    assert restored.to_dict() == job.to_dict()
