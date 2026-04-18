from agent.orchestration_state import (
    get_session_state,
    record_agent_end,
    record_agent_start,
    record_delegation_end,
    record_delegation_start,
    record_session_lifecycle,
)


class TestOrchestrationState:
    def test_agent_start_creates_running_state(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))

        state = record_agent_start(
            "session-1",
            platform="telegram",
            user_id="user-123",
            message="Investigate why the task stalled and summarize the fix.",
        )

        assert state["sessionId"] == "session-1"
        assert state["status"] == "running"
        assert state["platform"] == "telegram"
        assert state["userId"] == "user-123"
        assert state["messagePreview"].startswith("Investigate why the task stalled")
        assert state["startedAt"] is not None
        assert state["updatedAt"] is not None

    def test_delegation_start_and_end_update_same_session_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        record_agent_start("session-2", message="Parent task")

        delegation_id = record_delegation_start(
            "session-2",
            goal="Search the repo for all auth middleware implementations.",
            task_index=1,
            toolsets=["terminal", "file"],
        )
        state = get_session_state("session-2")
        assert state is not None
        assert len(state["delegations"]) == 1
        assert state["delegations"][0]["id"] == delegation_id
        assert state["delegations"][0]["status"] == "running"
        assert state["delegations"][0]["taskIndex"] == 1
        assert state["delegations"][0]["toolsets"] == ["terminal", "file"]

        record_delegation_end(
            "session-2",
            delegation_id,
            status="completed",
            summary="Found three auth middleware entrypoints and one shared helper.",
            api_calls=4,
            duration_seconds=12.5,
            model="gpt-5.4",
        )
        updated = get_session_state("session-2")
        assert updated is not None
        assert updated["delegations"][0]["status"] == "completed"
        assert updated["delegations"][0]["summary"].startswith("Found three auth middleware")
        assert updated["delegations"][0]["apiCalls"] == 4
        assert updated["delegations"][0]["durationSeconds"] == 12.5
        assert updated["delegations"][0]["model"] == "gpt-5.4"

    def test_agent_end_and_session_lifecycle_mark_completion(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        record_agent_start("session-3", message="Parent task")
        record_agent_end("session-3", status="completed", response="Implemented the requested fix and verified it.")
        record_session_lifecycle("session-3", "ended")

        state = get_session_state("session-3")
        assert state is not None
        assert state["status"] == "completed"
        assert state["responsePreview"] == "Implemented the requested fix and verified it."
        assert state["sessionLifecycle"] == "ended"
        assert state["endedAt"] is not None
