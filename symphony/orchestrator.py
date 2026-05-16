"""Synchronous orchestration skeleton for Symphony issue dispatch/retry/reconcile."""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Iterable
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from symphony.errors import SymphonyError
from symphony.models import Issue
from symphony.prompt import build_runner_prompt
from symphony.runner import RunnerResult, RunnerStatus
from symphony.workspace import prepare_workspace

ClockMs = Callable[[], int]

TERMINAL_STATES = frozenset({"done", "canceled", "cancelled", "completed", "closed"})
ACTIVE_STATES = frozenset({"todo", "in progress", "in_progress", "started", "claimed", "running"})


def _system_now_ms() -> int:
    return int(time.time() * 1000)


@dataclass(frozen=True, slots=True)
class RetrySchedule:
    """Retry metadata for an issue."""

    attempt: int
    retry_after_ms: int


@dataclass(frozen=True, slots=True)
class RunningIssue:
    """State retained for an issue currently owned by a runner/session."""

    issue: Issue
    runner: Any
    workspace: Any


@dataclass(frozen=True, slots=True)
class FutureJob:
    issue: Issue
    workspace: Any
    claim_lock: Path
    order: int


@dataclass(slots=True)
class OrchestratorState:
    """Mutable MVP state for synchronous orchestrator decisions."""

    running: dict[str, RunningIssue] = field(default_factory=dict)
    retries: dict[str, RetrySchedule] = field(default_factory=dict)
    exhausted: set[str] = field(default_factory=set)
    futures: dict[str, Future[Any]] = field(default_factory=dict, repr=False)
    future_jobs: dict[str, FutureJob] = field(default_factory=dict, repr=False)
    executor: ThreadPoolExecutor | None = field(default=None, repr=False)
    now_ms: ClockMs = _system_now_ms
    max_retry_backoff_ms: int = 60_000


@dataclass(frozen=True, slots=True)
class RunOnceResult:
    """Summary of one synchronous Symphony poll/dispatch cycle."""

    dispatched: int
    issue_identifiers: list[str]
    snapshot: dict[str, Any]


def select_dispatchable_issues(issues: Iterable[Issue], state: OrchestratorState) -> list[Issue]:
    """Return currently dispatchable Todo issues in deterministic order."""

    issue_list = list(issues)
    issue_by_id = {issue.id: issue for issue in issue_list}
    now_ms = state.now_ms()

    dispatchable = []
    seen_ids: set[str] = set()
    for issue in issue_list:
        if issue.id in seen_ids:
            continue
        if _is_dispatchable(issue, state=state, issue_by_id=issue_by_id, now_ms=now_ms):
            dispatchable.append(issue)
            seen_ids.add(issue.id)
    return sorted(dispatchable, key=_dispatch_sort_key)


def run_once(
    *,
    config: Any,
    workflow_prompt_template: str,
    tracker: Any,
    runner: Any,
    state: OrchestratorState | None = None,
    state_observer: Callable[[dict[str, Any]], None] | None = None,
    wait_for_completion: bool = True,
) -> RunOnceResult:
    """Run one poll/dispatch cycle against the configured tracker and runner."""

    orchestration_state = state or OrchestratorState()
    completed_identifiers = _collect_completed_futures(orchestration_state, tracker, state_observer)
    issues = tracker.fetch_candidate_issues(
        project_slug=config.tracker.project_slug,
        active_states=list(config.tracker.active_states),
        first=config.tracker.first,
    )
    dispatchable = select_dispatchable_issues(issues, orchestration_state)
    max_dispatch = max(0, int(config.agent.max_concurrent_agents) - len(orchestration_state.running))
    selected = dispatchable[:max_dispatch]

    jobs: list[tuple[Issue, Any, str, Path]] = []
    for issue in selected:
        workspace = prepare_workspace(config.workspace.root, issue.identifier)
        claim_lock = _claim_lock_path(config.workspace.root, issue.id)
        if not _acquire_claim_lock(claim_lock):
            continue
        attempt = _next_attempt(orchestration_state, issue.id)
        if attempt > int(config.agent.max_turns):
            orchestration_state.exhausted.add(issue.id)
            _release_claim_lock(claim_lock)
            if hasattr(tracker, "post_comment"):
                _safe_post_comment(tracker, issue.id, _max_turns_comment(issue, int(config.agent.max_turns)))
            continue
        claim_comment = _claim_comment(issue, attempt, workspace.evidence_dir)
        try:
            if hasattr(tracker, "claim_issue") and not tracker.claim_issue(issue.id, comment=claim_comment):
                _release_claim_lock(claim_lock)
                continue
        except Exception:  # noqa: BLE001 - failed claim must not leak the cross-process lock.
            _release_claim_lock(claim_lock)
            continue

        try:
            prompt = build_runner_prompt(
                workflow_prompt_template,
                workspace_path=workspace.path,
                evidence_dir=workspace.evidence_dir,
                issue=_issue_context(issue),
                attempt=attempt,
            )
        except Exception as exc:  # noqa: BLE001 - prompt failures are retryable orchestration failures.
            _release_claim_lock(claim_lock)
            result = _runner_exception_result(exc, workspace)
            schedule_retry(orchestration_state, issue.id, result.status)
            if hasattr(tracker, "post_comment"):
                _safe_post_comment(tracker, issue.id, _completion_comment(issue, result))
            continue
        jobs.append((issue, workspace, prompt, claim_lock))
        orchestration_state.running[issue.id] = RunningIssue(issue=issue, runner=runner, workspace=workspace)

    _notify_state(state_observer, orchestration_state)

    submitted_identifiers = _submit_jobs(
        orchestration_state,
        jobs,
        runner,
        timeout_seconds=config.hermes.timeout_seconds,
    )
    if wait_for_completion:
        completed_identifiers.extend(
            _collect_completed_futures(orchestration_state, tracker, state_observer, wait=True)
        )

    identifiers = completed_identifiers if wait_for_completion else submitted_identifiers
    return RunOnceResult(
        dispatched=len(identifiers),
        issue_identifiers=identifiers,
        snapshot=_snapshot(orchestration_state),
    )


def _submit_jobs(
    state: OrchestratorState,
    jobs: list[tuple[Issue, Any, str, Path]],
    runner: Any,
    *,
    timeout_seconds: int,
) -> list[str]:
    """Submit runner jobs without blocking the polling loop."""

    if not jobs:
        return []
    if state.executor is None:
        state.executor = ThreadPoolExecutor(max_workers=max(1, len(jobs)))
    submitted: list[str] = []
    next_order = len(state.future_jobs)
    for offset, (issue, workspace, prompt, claim_lock) in enumerate(jobs):
        future = state.executor.submit(runner.run_turn, prompt, workspace, timeout_seconds=timeout_seconds)
        state.futures[issue.id] = future
        state.future_jobs[issue.id] = FutureJob(
            issue=issue,
            workspace=workspace,
            claim_lock=claim_lock,
            order=next_order + offset,
        )
        submitted.append(issue.identifier)
    return submitted


def _collect_completed_futures(
    state: OrchestratorState,
    tracker: Any,
    state_observer: Callable[[dict[str, Any]], None] | None,
    *,
    wait: bool = False,
) -> list[str]:
    """Finalize completed runner futures and return issue identifiers in submit order."""

    if not state.futures:
        return []
    future_items = list(state.futures.items())
    if wait:
        futures = [future for _issue_id, future in future_items]
        completed_futures = set(as_completed(futures))
        completed_issue_ids = [issue_id for issue_id, future in future_items if future in completed_futures]
    else:
        completed_issue_ids = [issue_id for issue_id, future in future_items if future.done()]

    finalized: list[tuple[int, str]] = []
    for issue_id in completed_issue_ids:
        future = state.futures.pop(issue_id, None)
        job = state.future_jobs.pop(issue_id, None)
        if future is None or job is None:
            continue
        try:
            result = future.result()
        except Exception as exc:  # noqa: BLE001 - runner failures are retryable turn failures.
            result = _runner_exception_result(exc, job.workspace)
        finally:
            state.running.pop(issue_id, None)
            _release_claim_lock(job.claim_lock)
        schedule_retry(state, issue_id, result.status)
        if hasattr(tracker, "post_comment"):
            _safe_post_comment(tracker, issue_id, _completion_comment(job.issue, result))
        finalized.append((job.order, job.issue.identifier))
        _notify_state(state_observer, state)
    return [identifier for _order, identifier in sorted(finalized)]


def schedule_retry(state: OrchestratorState, issue_id: str, runner_status: RunnerStatus | str) -> RetrySchedule:
    """Record and return the next retry schedule for a runner result."""

    status = RunnerStatus(runner_status)
    previous = state.retries.get(issue_id)
    previous_attempt = previous.attempt if previous is not None else 0
    attempt = previous_attempt + 1
    if status == RunnerStatus.TURN_COMPLETED:
        retry = RetrySchedule(attempt=attempt, retry_after_ms=state.now_ms() + 1_000)
    else:
        delay_ms = min(10_000 * (2 ** (attempt - 1)), state.max_retry_backoff_ms)
        retry = RetrySchedule(attempt=attempt, retry_after_ms=state.now_ms() + delay_ms)

    state.retries[issue_id] = retry
    return retry


def reconcile_running_issue(
    state: OrchestratorState,
    latest_issue: Issue,
    *,
    runner: Any,
    workspace_manager: Any,
) -> str:
    """Reconcile one running issue against its latest tracker state."""

    running = state.running.get(latest_issue.id)
    if running is None:
        return "not_running"

    if is_terminal_state(latest_issue.state):
        runner.terminate(running.runner)
        workspace_manager.cleanup(running.workspace)
        del state.running[latest_issue.id]
        return "terminal_cleanup"

    if not is_active_state(latest_issue.state):
        runner.terminate(running.runner)
        del state.running[latest_issue.id]
        return "stopped_non_active"

    state.running[latest_issue.id] = RunningIssue(
        issue=latest_issue,
        runner=running.runner,
        workspace=running.workspace,
    )
    return "updated_active"


def is_terminal_state(state: str) -> bool:
    return _normalize_state(state) in TERMINAL_STATES


def is_active_state(state: str) -> bool:
    return _normalize_state(state) in ACTIVE_STATES


def _is_dispatchable(
    issue: Issue,
    *,
    state: OrchestratorState,
    issue_by_id: dict[str, Issue],
    now_ms: int,
) -> bool:
    if _normalize_state(issue.state) != "todo":
        return False
    if issue.id in state.running:
        return False
    if issue.id in state.exhausted:
        return False
    retry = state.retries.get(issue.id)
    if retry is not None and retry.retry_after_ms > now_ms:
        return False
    return not _has_non_terminal_blocker(issue, issue_by_id)


def _has_non_terminal_blocker(issue: Issue, issue_by_id: dict[str, Issue]) -> bool:
    for blocker_id in issue.blocked_by_ids:
        blocker = issue_by_id.get(blocker_id)
        if blocker is None or not is_terminal_state(blocker.state):
            return True
    return False


def _dispatch_sort_key(issue: Issue) -> tuple[bool, int, str, str]:
    priority = issue.priority if issue.priority is not None else 0
    return (issue.priority is None, priority, issue.created_at, issue.identifier)


def _normalize_state(state: str) -> str:
    return state.strip().casefold()


def _next_attempt(state: OrchestratorState, issue_id: str) -> int:
    retry = state.retries.get(issue_id)
    return 1 if retry is None else retry.attempt + 1


def _issue_context(issue: Issue) -> dict[str, Any]:
    return asdict(issue)


def _claim_comment(issue: Issue, attempt: int, evidence_dir: Path) -> str:
    return (
        f"Symphony run claimed by Hermes for {issue.identifier}.\n\n"
        f"Attempt: {attempt}\n"
        f"Evidence directory: `{evidence_dir}`"
    )


def _completion_comment(issue: Issue, result: Any) -> str:
    files = _evidence_files(Path(result.evidence_dir))
    file_lines = "\n".join(f"- `{path}`" for path in files) if files else "- No evidence files produced"
    return (
        f"Symphony run completed for {issue.identifier}.\n\n"
        f"Status: `{result.status}`\n"
        f"Return code: `{result.returncode}`\n"
        f"Evidence directory: `{result.evidence_dir}`\n\n"
        f"Evidence files:\n{file_lines}"
    )


def _max_turns_comment(issue: Issue, max_turns: int) -> str:
    return (
        f"Symphony run stopped for {issue.identifier}.\n\n"
        f"Configured max turns ({max_turns}) has been reached; leaving the issue for human review."
    )


def _runner_exception_result(exc: Exception, workspace: Any) -> RunnerResult:
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    evidence_dir = Path(workspace.evidence_dir)
    stderr = f"{type(exc).__name__}: {exc}"
    if isinstance(exc, SymphonyError):
        stderr = f"{exc.code}: {exc.message}"
    return RunnerResult(
        status=RunnerStatus.TURN_FAILED,
        events=["turn_started", RunnerStatus.TURN_FAILED.value],
        started_at=now,
        ended_at=now,
        evidence_dir=evidence_dir,
        evidence_path=evidence_dir,
        stdout="",
        stderr=stderr,
        returncode=None,
    )


def _claim_lock_path(workspace_root: Path, issue_id: str) -> Path:
    safe_id = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in issue_id)
    return Path(workspace_root) / ".symphony" / "claims" / f"{safe_id}.lock"


def _acquire_claim_lock(path: Path) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(str(os.getpid()))
    return True


def _release_claim_lock(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def _safe_post_comment(tracker: Any, issue_id: str, body: str) -> None:
    try:
        tracker.post_comment(issue_id, body)
    except Exception:
        pass


def _notify_state(observer: Callable[[dict[str, Any]], None] | None, state: OrchestratorState) -> None:
    if observer is None:
        return
    try:
        observer(_snapshot(state))
    except Exception:
        pass


def _evidence_files(evidence_dir: Path) -> list[str]:
    if not evidence_dir.exists():
        return []
    return sorted(str(path.relative_to(evidence_dir)) for path in evidence_dir.rglob("*") if path.is_file())


def _snapshot(state: OrchestratorState) -> dict[str, Any]:
    return {
        "counts": {"running": len(state.running), "retries": len(state.retries)},
        "running": sorted(state.running),
        "exhausted": sorted(state.exhausted),
        "retries": {
            issue_id: {"attempt": retry.attempt, "retry_after_ms": retry.retry_after_ms}
            for issue_id, retry in sorted(state.retries.items())
        },
    }
