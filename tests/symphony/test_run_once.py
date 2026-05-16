from __future__ import annotations

import threading
from pathlib import Path
from symphony.config import load_config
from symphony.models import Issue
from symphony.orchestrator import OrchestratorState, RetrySchedule, run_once
from symphony.runner import RunnerResult, RunnerStatus


def issue(identifier: str = "KATO-123", *, id: str = "issue-id-1", state: str = "Todo") -> Issue:
    return Issue(
        id=id,
        identifier=identifier,
        title="Implement feature",
        url=f"https://linear.app/acme/issue/{identifier}",
        state=state,
        labels=["symphony"],
        priority=1,
        blocked_by_ids=[],
        created_at="2026-05-14T00:00:00Z",
    )


class FakeTracker:
    def __init__(self, issues: list[Issue]):
        self.issues = issues
        self.comments: list[tuple[str, str]] = []
        self.claimed: list[str] = []

    def fetch_candidate_issues(self, *, project_slug, active_states, first):
        assert project_slug == "KATO"
        assert active_states == ["Todo", "In Progress"]
        assert first == 50
        return self.issues

    def claim_issue(self, issue_id, *, comment):
        self.claimed.append(issue_id)
        self.comments.append((issue_id, comment))
        return True

    def post_comment(self, issue_id, body):
        self.comments.append((issue_id, body))


class FakeRunner:
    def __init__(self):
        self.prompts: list[str] = []
        self.workspaces: list[Path] = []

    def run_turn(self, prompt, workspace, *, timeout_seconds=None):
        self.prompts.append(prompt)
        self.workspaces.append(Path(workspace.path))
        screenshot = Path(workspace.evidence_dir) / "screenshot.png"
        screenshot.write_text("fake image", encoding="utf-8")
        return RunnerResult(
            status=RunnerStatus.TURN_COMPLETED,
            events=["turn_started", "turn_completed"],
            started_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            ended_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            evidence_dir=Path(workspace.evidence_dir),
            evidence_path=Path(workspace.evidence_dir),
            stdout="done",
            stderr="",
            returncode=0,
        )


def test_run_once_fetches_claims_runs_and_posts_evidence_summary(tmp_path):
    config = load_config(
        {"workspace": {"root": str(tmp_path / "workspaces")}, "tracker": {"project_slug": "KATO"}},
        workflow_dir=tmp_path,
        env={},
    )
    tracker = FakeTracker([issue()])
    runner = FakeRunner()

    result = run_once(
        config=config,
        workflow_prompt_template="Work on {{ issue.identifier }} attempt {{ attempt }}.",
        tracker=tracker,
        runner=runner,
    )

    assert result.dispatched == 1
    assert result.issue_identifiers == ["KATO-123"]
    assert tracker.claimed == ["issue-id-1"]
    assert "Issue identifier: KATO-123" in runner.prompts[0]
    assert "Work on KATO-123 attempt 1." in runner.prompts[0]
    assert runner.workspaces == [tmp_path / "workspaces" / "KATO-123"]
    final_comment = tracker.comments[-1][1]
    assert "Symphony run completed" in final_comment
    assert "turn_completed" in final_comment
    assert "screenshot.png" in final_comment


def test_run_once_returns_noop_when_no_dispatchable_candidates(tmp_path):
    config = load_config({"workspace": {"root": str(tmp_path / "workspaces")}}, workflow_dir=tmp_path, env={})
    tracker = FakeTracker([issue(state="Backlog")])
    runner = FakeRunner()

    result = run_once(
        config=config,
        workflow_prompt_template="Work on {{ issue.identifier }}.",
        tracker=tracker,
        runner=runner,
    )

    assert result.dispatched == 0
    assert result.issue_identifiers == []
    assert tracker.claimed == []
    assert runner.prompts == []


class BarrierRunner(FakeRunner):
    def __init__(self, parties: int):
        super().__init__()
        self.barrier = threading.Barrier(parties)

    def run_turn(self, prompt, workspace, *, timeout_seconds=None):
        self.barrier.wait(timeout=1)
        return super().run_turn(prompt, workspace, timeout_seconds=timeout_seconds)


def test_run_once_dispatches_selected_issues_concurrently(tmp_path):
    config = load_config(
        {
            "agent": {"max_concurrent_agents": 2},
            "workspace": {"root": str(tmp_path / "workspaces")},
        },
        workflow_dir=tmp_path,
        env={},
    )
    tracker = FakeTracker([issue("KATO-1", id="one"), issue("KATO-2", id="two")])
    runner = BarrierRunner(parties=2)

    result = run_once(
        config=config,
        workflow_prompt_template="Work on {{ issue.identifier }}.",
        tracker=tracker,
        runner=runner,
    )

    assert result.dispatched == 2
    assert result.issue_identifiers == ["KATO-1", "KATO-2"]


def test_run_once_stops_before_runner_when_max_turns_reached(tmp_path):
    config = load_config(
        {
            "agent": {"max_turns": 1},
            "workspace": {"root": str(tmp_path / "workspaces")},
        },
        workflow_dir=tmp_path,
        env={},
    )
    target = issue("KATO-999", id="maxed")
    tracker = FakeTracker([target])
    runner = FakeRunner()
    state = OrchestratorState(retries={target.id: RetrySchedule(attempt=1, retry_after_ms=0)}, now_ms=lambda: 0)

    result = run_once(
        config=config,
        workflow_prompt_template="Work on {{ issue.identifier }}.",
        tracker=tracker,
        runner=runner,
        state=state,
    )

    assert result.dispatched == 0
    assert tracker.claimed == []
    assert runner.prompts == []
    assert "max turns" in tracker.comments[-1][1]


class RaisingRunner(FakeRunner):
    def run_turn(self, prompt, workspace, *, timeout_seconds=None):
        raise RuntimeError("boom")


def test_run_once_maps_runner_exception_to_failed_turn_and_releases_running(tmp_path):
    config = load_config(
        {"workspace": {"root": str(tmp_path / "workspaces")}},
        workflow_dir=tmp_path,
        env={},
    )
    tracker = FakeTracker([issue("KATO-500", id="raises")])
    state = OrchestratorState(now_ms=lambda: 0)

    result = run_once(
        config=config,
        workflow_prompt_template="Work on {{ issue.identifier }}.",
        tracker=tracker,
        runner=RaisingRunner(),
        state=state,
    )

    assert result.dispatched == 1
    assert state.running == {}
    assert state.retries["raises"].attempt == 1
    final_comment = tracker.comments[-1][1]
    assert "turn_failed" in final_comment


def test_existing_claim_lock_prevents_competing_dispatch(tmp_path):
    config = load_config(
        {"workspace": {"root": str(tmp_path / "workspaces")}},
        workflow_dir=tmp_path,
        env={},
    )
    target = issue("KATO-LOCKED", id="locked")
    lock = tmp_path / "workspaces" / ".symphony" / "claims" / "locked.lock"
    lock.parent.mkdir(parents=True)
    lock.write_text("other-process", encoding="utf-8")
    tracker = FakeTracker([target])
    runner = FakeRunner()

    result = run_once(
        config=config,
        workflow_prompt_template="Work on {{ issue.identifier }}.",
        tracker=tracker,
        runner=runner,
    )

    assert result.dispatched == 0
    assert tracker.claimed == []
    assert runner.prompts == []
    assert lock.exists()


class ClaimRaisesTracker(FakeTracker):
    def claim_issue(self, issue_id, *, comment):
        raise RuntimeError("claim down")


class PostRaisesTracker(FakeTracker):
    def post_comment(self, issue_id, body):
        raise RuntimeError("comment down")


def test_claim_exception_releases_cross_process_lock(tmp_path):
    config = load_config(
        {"workspace": {"root": str(tmp_path / "workspaces")}},
        workflow_dir=tmp_path,
        env={},
    )
    target = issue("KATO-CLAIM", id="claim-raises")

    result = run_once(
        config=config,
        workflow_prompt_template="Work on {{ issue.identifier }}.",
        tracker=ClaimRaisesTracker([target]),
        runner=FakeRunner(),
    )

    assert result.dispatched == 0
    assert not (tmp_path / "workspaces" / ".symphony" / "claims" / "claim-raises.lock").exists()


def test_post_comment_exception_does_not_crash_loop(tmp_path):
    config = load_config(
        {"workspace": {"root": str(tmp_path / "workspaces")}},
        workflow_dir=tmp_path,
        env={},
    )

    result = run_once(
        config=config,
        workflow_prompt_template="Work on {{ issue.identifier }}.",
        tracker=PostRaisesTracker([issue("KATO-COMMENT", id="comment-raises")]),
        runner=FakeRunner(),
    )

    assert result.dispatched == 1


def test_state_observer_sees_running_issue_before_runner_finishes(tmp_path):
    config = load_config(
        {"workspace": {"root": str(tmp_path / "workspaces")}},
        workflow_dir=tmp_path,
        env={},
    )
    snapshots = []

    result = run_once(
        config=config,
        workflow_prompt_template="Work on {{ issue.identifier }}.",
        tracker=FakeTracker([issue("KATO-STATE", id="state-visible")]),
        runner=FakeRunner(),
        state_observer=snapshots.append,
    )

    assert result.dispatched == 1
    assert any(snapshot["counts"]["running"] == 1 for snapshot in snapshots)
    assert snapshots[-1]["counts"]["running"] == 0


def test_prompt_render_error_releases_lock_after_claim(tmp_path):
    config = load_config(
        {"workspace": {"root": str(tmp_path / "workspaces")}},
        workflow_dir=tmp_path,
        env={},
    )
    target = issue("KATO-BAD-PROMPT", id="bad-prompt")
    tracker = FakeTracker([target])

    result = run_once(
        config=config,
        workflow_prompt_template="Work on {{ missing.value }}.",
        tracker=tracker,
        runner=FakeRunner(),
    )

    assert result.dispatched == 0
    assert tracker.claimed == ["bad-prompt"]
    assert not (tmp_path / "workspaces" / ".symphony" / "claims" / "bad-prompt.lock").exists()


def test_max_turns_comment_is_not_repeated_for_exhausted_issue(tmp_path):
    config = load_config(
        {"agent": {"max_turns": 1}, "workspace": {"root": str(tmp_path / "workspaces")}},
        workflow_dir=tmp_path,
        env={},
    )
    target = issue("KATO-MAX", id="max-repeat")
    tracker = FakeTracker([target])
    state = OrchestratorState(retries={target.id: RetrySchedule(attempt=1, retry_after_ms=0)}, now_ms=lambda: 0)

    first = run_once(
        config=config,
        workflow_prompt_template="Work on {{ issue.identifier }}.",
        tracker=tracker,
        runner=FakeRunner(),
        state=state,
    )
    second = run_once(
        config=config,
        workflow_prompt_template="Work on {{ issue.identifier }}.",
        tracker=tracker,
        runner=FakeRunner(),
        state=state,
    )

    assert first.dispatched == 0
    assert second.dispatched == 0
    assert sum(1 for _issue_id, body in tracker.comments if "max turns" in body) == 1
