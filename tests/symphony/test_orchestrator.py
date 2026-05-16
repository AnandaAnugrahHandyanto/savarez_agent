from __future__ import annotations

from dataclasses import replace

from symphony.models import Issue
from symphony.orchestrator import (
    OrchestratorState,
    RunningIssue,
    RetrySchedule,
    reconcile_running_issue,
    schedule_retry,
    select_dispatchable_issues,
)
from symphony.runner import RunnerStatus


def issue(
    identifier: str,
    *,
    id: str | None = None,
    state: str = "Todo",
    title: str | None = None,
    priority: int | None = None,
    created_at: str = "2026-05-01T00:00:00Z",
    blocked_by_ids: list[str] | None = None,
) -> Issue:
    return Issue(
        id=id or identifier.lower(),
        identifier=identifier,
        title=title or f"Issue {identifier}",
        url=f"https://tracker.example/{identifier}",
        state=state,
        labels=[],
        priority=priority,
        blocked_by_ids=blocked_by_ids or [],
        created_at=created_at,
    )


def test_dispatch_sort_order_priority_created_at_identifier_and_none_priority_last():
    issues = [
        issue("D", priority=None, created_at="2026-01-01T00:00:00Z"),
        issue("C", priority=2, created_at="2026-01-01T00:00:00Z"),
        issue("B", priority=1, created_at="2026-01-02T00:00:00Z"),
        issue("A", priority=1, created_at="2026-01-01T00:00:00Z"),
        issue("AA", priority=1, created_at="2026-01-01T00:00:00Z"),
    ]

    selected = select_dispatchable_issues(issues, OrchestratorState(now_ms=lambda: 0))

    assert [candidate.identifier for candidate in selected] == ["A", "AA", "B", "C", "D"]


def test_todo_issue_with_non_terminal_blocker_is_skipped_but_terminal_blocker_allows_dispatch():
    blocked = issue("BLOCKED", id="blocked", blocked_by_ids=["open-blocker"])
    unblocked = issue("UNBLOCKED", id="unblocked", blocked_by_ids=["done-blocker", "closed-blocker"])
    open_blocker = issue("OPEN", id="open-blocker", state="In Progress")
    done_blocker = issue("DONE", id="done-blocker", state="done")
    closed_blocker = issue("CLOSED", id="closed-blocker", state="CLOSED")

    selected = select_dispatchable_issues(
        [blocked, unblocked, open_blocker, done_blocker, closed_blocker],
        OrchestratorState(now_ms=lambda: 0),
    )

    assert [candidate.identifier for candidate in selected] == ["UNBLOCKED"]


def test_running_or_claimed_issue_prevents_duplicate_dispatch_in_one_orchestrator_state():
    target = issue("RUNNING")
    also_target = replace(target, title="fresh snapshot")
    state = OrchestratorState(running={target.id: RunningIssue(issue=target, runner="runner", workspace="ws")}, now_ms=lambda: 0)

    selected = select_dispatchable_issues([also_target], state)

    assert selected == []


def test_duplicate_candidates_are_deduplicated_within_one_selection():
    first = issue("DUP", id="same-id", title="first")
    second = replace(first, title="second")

    selected = select_dispatchable_issues([first, second], OrchestratorState(now_ms=lambda: 0))

    assert selected == [first]


def test_retry_scheduling_clean_exit_uses_attempt_one_and_one_second_delay_with_injected_clock():
    state = OrchestratorState(now_ms=lambda: 123_000)

    retry = schedule_retry(state, "ISSUE-1", RunnerStatus.TURN_COMPLETED)

    assert retry == RetrySchedule(attempt=1, retry_after_ms=124_000)
    assert state.retries["ISSUE-1"] == retry


def test_retry_scheduling_abnormal_exit_uses_exponential_backoff_capped_by_max():
    state = OrchestratorState(now_ms=lambda: 1_000, max_retry_backoff_ms=25_000)

    first = schedule_retry(state, "ISSUE-1", RunnerStatus.TURN_FAILED)
    second = schedule_retry(state, "ISSUE-1", RunnerStatus.TURN_TIMEOUT)
    third = schedule_retry(state, "ISSUE-1", RunnerStatus.TURN_FAILED)

    assert first == RetrySchedule(attempt=1, retry_after_ms=11_000)
    assert second == RetrySchedule(attempt=2, retry_after_ms=21_000)
    assert third == RetrySchedule(attempt=3, retry_after_ms=26_000)


def test_retry_schedule_blocks_dispatch_until_due():
    target = issue("RETRY")
    state = OrchestratorState(
        retries={target.id: RetrySchedule(attempt=1, retry_after_ms=5_000)},
        now_ms=lambda: 4_999,
    )

    assert select_dispatchable_issues([target], state) == []

    state.now_ms = lambda: 5_000
    assert [candidate.identifier for candidate in select_dispatchable_issues([target], state)] == ["RETRY"]


class FakeRunner:
    def __init__(self):
        self.terminated: list[str] = []

    def terminate(self, handle):
        self.terminated.append(handle)


class FakeWorkspaceManager:
    def __init__(self):
        self.cleaned: list[str] = []

    def cleanup(self, workspace):
        self.cleaned.append(workspace)


def test_reconciliation_terminal_state_terminates_runner_cleans_workspace_and_removes_running():
    old = issue("DONE", id="done", state="In Progress")
    new = replace(old, state="Completed")
    state = OrchestratorState(running={old.id: RunningIssue(issue=old, runner="run-1", workspace="ws-1")})
    runner = FakeRunner()
    workspaces = FakeWorkspaceManager()

    result = reconcile_running_issue(state, new, runner=runner, workspace_manager=workspaces)

    assert result == "terminal_cleanup"
    assert runner.terminated == ["run-1"]
    assert workspaces.cleaned == ["ws-1"]
    assert old.id not in state.running


def test_reconciliation_non_active_non_terminal_terminates_without_cleanup():
    old = issue("PAUSED", id="paused", state="In Progress")
    new = replace(old, state="Backlog")
    state = OrchestratorState(running={old.id: RunningIssue(issue=old, runner="run-1", workspace="ws-1")})
    runner = FakeRunner()
    workspaces = FakeWorkspaceManager()

    result = reconcile_running_issue(state, new, runner=runner, workspace_manager=workspaces)

    assert result == "stopped_non_active"
    assert runner.terminated == ["run-1"]
    assert workspaces.cleaned == []
    assert old.id not in state.running


def test_reconciliation_active_state_updates_running_issue_snapshot():
    old = issue("ACTIVE", id="active", state="Todo", title="old")
    new = replace(old, state="In Progress", title="new")
    state = OrchestratorState(running={old.id: RunningIssue(issue=old, runner="run-1", workspace="ws-1")})
    runner = FakeRunner()
    workspaces = FakeWorkspaceManager()

    result = reconcile_running_issue(state, new, runner=runner, workspace_manager=workspaces)

    assert result == "updated_active"
    assert runner.terminated == []
    assert workspaces.cleaned == []
    assert state.running[old.id].issue == new
