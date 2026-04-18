import agent.continuation_enforcer as continuation_enforcer
from agent.continuation_enforcer import (
    claim_retry_requested_continuation,
    get_continuation_record,
    get_pending_continuations,
    reconcile_session_continuation,
    request_continuation_retry,
    should_block_delegation,
)
from agent.orchestration_state import (
    record_agent_start,
    record_delegation_end,
    record_delegation_start,
)


class TestContinuationEnforcer:
    def test_reconcile_creates_pending_continuation_for_open_todos(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))

        record = reconcile_session_continuation(
            "session-1",
            outcome_status="interrupted",
            todos=[
                {"id": "t1", "content": "Inspect failing logs", "status": "in_progress"},
                {"id": "t2", "content": "Write final summary", "status": "completed"},
            ],
            response_preview="Interrupted while collecting the remaining evidence.",
        )

        assert record is not None
        assert record["sessionId"] == "session-1"
        assert record["status"] == "pending"
        assert record["reason"] == "interrupted"
        assert [item["id"] for item in record["openTodos"]] == ["t1"]
        assert record["attemptCount"] == 1

        queue = get_pending_continuations()
        assert len(queue) == 1
        assert queue[0]["sessionId"] == "session-1"

    def test_reconcile_resolves_existing_continuation_after_completion(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))

        reconcile_session_continuation(
            "session-2",
            outcome_status="failed",
            todos=[{"id": "t1", "content": "Recover partial output", "status": "pending"}],
            response_preview="Provider call failed before the wrap-up.",
        )

        resolved = reconcile_session_continuation(
            "session-2",
            outcome_status="completed",
            todos=[{"id": "t1", "content": "Recover partial output", "status": "completed"}],
            response_preview="Recovered and completed successfully.",
        )

        assert resolved is None
        assert get_pending_continuations() == []

    def test_retry_requested_claim_sets_running_lease_and_blocks_second_claim(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))

        reconcile_session_continuation(
            "session-retry",
            outcome_status="interrupted",
            todos=[{"id": "t1", "content": "Inspect failing logs", "status": "pending"}],
            response_preview="Need another pass.",
        )

        requested = request_continuation_retry("session-retry", requested_by="pan")
        assert requested is not None
        assert requested["status"] == "retry_requested"
        assert requested["requestedBy"] == "pan"

        claimed = claim_retry_requested_continuation("gateway-worker-1", lease_seconds=90)
        assert claimed is not None
        assert claimed["sessionId"] == "session-retry"
        assert claimed["status"] == "running"
        assert claimed["leaseOwner"] == "gateway-worker-1"
        assert claimed["resumeCount"] == 1

        assert claim_retry_requested_continuation("gateway-worker-2", lease_seconds=90) is None

        persisted = get_continuation_record("session-retry")
        assert persisted is not None
        assert persisted["status"] == "running"
        assert persisted["leaseOwner"] == "gateway-worker-1"
        assert [event["type"] for event in persisted["events"]][-2:] == ["retry_requested", "auto_resume_claimed"]

    def test_retry_requested_claim_blocks_stale_request(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        monkeypatch.setattr(continuation_enforcer, "_now_iso", lambda: "2026-04-16T20:00:00Z")

        reconcile_session_continuation(
            "session-stale",
            outcome_status="failed",
            todos=[{"id": "t1", "content": "Recover partial output", "status": "pending"}],
            response_preview="Worker crashed mid-flight.",
        )
        request_continuation_retry("session-stale", requested_by="pan")

        monkeypatch.setattr(continuation_enforcer, "_now_iso", lambda: "2026-04-16T20:05:00Z")

        claimed = claim_retry_requested_continuation(
            "gateway-worker-1",
            max_retry_age_seconds=60,
        )

        assert claimed is None
        blocked = get_continuation_record("session-stale")
        assert blocked is not None
        assert blocked["status"] == "blocked"
        assert blocked["resolution"] == "retry_request_expired"

    def test_delegation_guard_blocks_after_three_recent_failures_for_same_goal(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        record_agent_start("session-guard", message="Parent task")

        for status in ("failed", "error", "interrupted"):
            delegation_id = record_delegation_start("session-guard", goal="Inspect auth middleware", task_index=0)
            record_delegation_end(
                "session-guard",
                delegation_id,
                status=status,
                summary=f"Attempt ended with {status}.",
                api_calls=2,
                duration_seconds=1.5,
                model="gpt-5.4",
            )

        guard_reason = should_block_delegation("session-guard", "Inspect auth middleware")
        assert guard_reason is not None
        assert "Inspect auth middleware" in guard_reason

        assert should_block_delegation("session-guard", "Different task") is None
