from __future__ import annotations

from dataclasses import dataclass

from symphony.models import Issue
from symphony.observability import EventBuffer, build_state_snapshot
from symphony.orchestrator import OrchestratorState, RetrySchedule, RunningIssue


def issue(identifier: str, *, id: str | None = None, state: str = "Todo") -> Issue:
    return Issue(
        id=id or identifier.lower(),
        identifier=identifier,
        title=f"Issue {identifier}",
        url=f"https://tracker.example/{identifier}",
        state=state,
        labels=[],
        priority=None,
        blocked_by_ids=[],
        created_at="2026-05-01T00:00:00Z",
    )


@dataclass(frozen=True)
class Workspace:
    path: str
    evidence_dir: str


@dataclass(frozen=True)
class RunnerHandle:
    session_id: str


def test_event_buffer_is_bounded_and_drops_oldest_with_sequence_numbers():
    events = EventBuffer(capacity=2, clock_ms=lambda: 123)

    events.record("info", "first")
    events.record("info", "second")
    events.record("info", "third")

    assert events.snapshot() == [
        {"seq": 2, "ts_ms": 123, "level": "info", "message": "second"},
        {"seq": 3, "ts_ms": 123, "level": "info", "message": "third"},
    ]


def test_event_buffer_includes_context_truncates_messages_and_redacts_obvious_secrets():
    events = EventBuffer(capacity=10, max_message_chars=12, clock_ms=lambda: 9)

    events.record(
        "error",
        "prefix api_key=SECRET123456789 suffix",
        issue_id="issue-1",
        issue_identifier="ISS-1",
        session_id="session-1",
        extra={"token": "very-secret", "safe": "ok"},
    )

    assert events.snapshot() == [
        {
            "seq": 1,
            "ts_ms": 9,
            "level": "error",
            "message": "prefix api_…",
            "issue_id": "issue-1",
            "issue_identifier": "ISS-1",
            "session_id": "session-1",
            "extra": {"token": "[REDACTED]", "safe": "ok"},
        }
    ]


def test_build_state_snapshot_returns_counts_rows_totals_latest_errors_and_evidence_dirs():
    running_issue = issue("RUN", id="run", state="In Progress")
    retry_issue = issue("RETRY", id="retry")
    state = OrchestratorState(
        running={
            running_issue.id: RunningIssue(
                issue=running_issue,
                runner=RunnerHandle(session_id="session-1"),
                workspace=Workspace(path="/tmp/ws", evidence_dir="/tmp/ws/evidence"),
            )
        },
        retries={retry_issue.id: RetrySchedule(attempt=2, retry_after_ms=5000)},
        now_ms=lambda: 1000,
    )
    events = EventBuffer(capacity=5, clock_ms=lambda: 2000)
    events.record("info", "started", issue_id="run", session_id="session-1")
    events.record("error", "boom", issue_id="run", issue_identifier="RUN")

    snapshot = build_state_snapshot(state, events=events.snapshot())

    assert snapshot == {
        "counts": {"running": 1, "retrying": 1, "events": 2, "latest_errors": 1},
        "running": [
            {
                "issue_id": "run",
                "issue_identifier": "RUN",
                "title": "Issue RUN",
                "state": "In Progress",
                "session_id": "session-1",
                "workspace": "/tmp/ws",
                "evidence_dir": "/tmp/ws/evidence",
            }
        ],
        "retrying": [
            {"issue_id": "retry", "attempt": 2, "retry_after_ms": 5000, "retry_in_ms": 4000}
        ],
        "totals": {"running": 1, "retrying": 1},
        "latest_errors": [
            {
                "seq": 2,
                "ts_ms": 2000,
                "level": "error",
                "message": "boom",
                "issue_id": "run",
                "issue_identifier": "RUN",
            }
        ],
        "events": events.snapshot(),
        "evidence_dirs": {"run": "/tmp/ws/evidence"},
    }


def test_event_buffer_redacts_secret_like_extra_keys():
    events = EventBuffer(capacity=10, clock_ms=lambda: 1)

    events.record(
        "info",
        "ok",
        extra={
            "linear_api_key": "lin-secret",
            "github_token": "gh-secret",
            "OPENAI_API_KEY": "openai-secret",
            "nested": {"servicePassword": "pw-secret", "safe": "value"},
        },
    )

    extra = events.snapshot()[0]["extra"]
    assert extra["linear_api_key"] == "[REDACTED]"
    assert extra["github_token"] == "[REDACTED]"
    assert extra["OPENAI_API_KEY"] == "[REDACTED]"
    assert extra["nested"]["servicePassword"] == "[REDACTED]"
    assert extra["nested"]["safe"] == "value"
