#!/usr/bin/env python3
"""Inspect and claim repo-local Agent Project Workspace tasks."""

from __future__ import annotations

import argparse
import json
import os
import posixpath
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

TASKS_PATH = Path(".hermes/tasks.yaml")
HANDOFF_DIR = Path(".hermes/runs")
LOCK_DIR = Path(".hermes/state/tasks.lock")
GUARDED_STATUSES = {"claimed", "active", "review"}
READY_STATUSES = {"ready", "todo"}
TERMINAL_STATUSES = {"done", "cancelled"}


def run(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if check and result.returncode != 0:
        raise RuntimeError(result.stdout.strip() or f"{' '.join(args)} failed")
    return result


def git_root() -> Path:
    result = run(["git", "rev-parse", "--show-toplevel"], Path.cwd())
    return Path(result.stdout.strip()).resolve()


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore[import-not-found]
    except ModuleNotFoundError as exc:
        raise RuntimeError("PyYAML is required for .hermes/tasks.yaml") from exc
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def dump_yaml(path: Path, data: dict[str, Any]) -> None:
    try:
        import yaml  # type: ignore[import-not-found]
    except ModuleNotFoundError as exc:
        raise RuntimeError("PyYAML is required for .hermes/tasks.yaml") from exc
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


@contextmanager
def repo_lock(root: Path, timeout_seconds: float = 30.0, stale_seconds: float = 15 * 60) -> Iterator[None]:
    """Cross-platform coarse lock using atomic directory creation."""
    lock_dir = root / LOCK_DIR
    lock_dir.parent.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    while True:
        try:
            lock_dir.mkdir()
            (lock_dir / "owner.txt").write_text(f"pid={os.getpid()} at={datetime.now(timezone.utc).isoformat()}\n", encoding="utf-8")
            break
        except FileExistsError:
            try:
                age = time.time() - lock_dir.stat().st_mtime
            except OSError:
                age = 0
            if age > stale_seconds:
                shutil.rmtree(lock_dir, ignore_errors=True)
                continue
            if time.monotonic() - start > timeout_seconds:
                raise RuntimeError(
                    f"timed out waiting for task lock: {LOCK_DIR}. "
                    f"If no task command is running, remove stale lock with: rm -rf {LOCK_DIR}"
                )
            time.sleep(0.1)
    try:
        yield
    finally:
        shutil.rmtree(lock_dir, ignore_errors=True)


def parse_dt(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def task_by_id(tasks: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(task.get("id")): task for task in tasks if isinstance(task, dict) and task.get("id")}


def dependencies_done(task: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> bool:
    for dep in task.get("depends_on") or []:
        if by_id.get(str(dep), {}).get("status") != "done":
            return False
    return True


def claim_expired(task: dict[str, Any], now: datetime) -> bool:
    claim = task.get("claim") if isinstance(task.get("claim"), dict) else {}
    lease_until = parse_dt(claim.get("lease_until"))
    return bool(lease_until and lease_until < now)


def canonical_scope_path(value: Any) -> str:
    raw = str(value).strip().replace("\\", "/")
    if not raw:
        return ""
    normalized = posixpath.normpath(raw)
    if normalized == ".":
        return ""
    normalized = normalized.lstrip("/")
    if normalized == ".." or normalized.startswith("../"):
        raise RuntimeError(f"scope path escapes repo: {value}")
    return normalized.rstrip("/")


def normalize_paths(values: Any) -> set[str]:
    if not isinstance(values, list):
        return set()
    return {canonical_scope_path(value) for value in values if str(value).strip()}


def paths_overlap(a: str, b: str) -> bool:
    a = canonical_scope_path(a)
    b = canonical_scope_path(b)
    if a == "" or b == "":
        return True
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


def blocked_by_concurrency(candidate: dict[str, Any], tasks: list[dict[str, Any]]) -> list[str]:
    candidate_paths = normalize_paths((candidate.get("scope") or {}).get("modify"))
    if not candidate_paths:
        return []
    blockers: list[str] = []
    candidate_id = str(candidate.get("id"))
    candidate_deps = {str(dep) for dep in task_list(candidate.get("depends_on"))}
    for other in tasks:
        other_id = str(other.get("id"))
        if other_id == candidate_id or other.get("status") not in GUARDED_STATUSES:
            continue
        if other_id in candidate_deps:
            continue
        other_paths = normalize_paths((other.get("scope") or {}).get("modify"))
        for path in candidate_paths:
            if any(paths_overlap(path, other_path) for other_path in other_paths):
                blockers.append(other_id)
                break
    return blockers


def guarded_conflicts(tasks: list[dict[str, Any]]) -> list[tuple[str, str]]:
    conflicts: list[tuple[str, str]] = []
    guarded = [task for task in tasks if task.get("status") in GUARDED_STATUSES]
    for index, left in enumerate(guarded):
        left_id = str(left.get("id"))
        left_paths = normalize_paths((left.get("scope") or {}).get("modify"))
        left_deps = {str(dep) for dep in task_list(left.get("depends_on"))}
        for right in guarded[index + 1 :]:
            right_id = str(right.get("id"))
            right_deps = {str(dep) for dep in task_list(right.get("depends_on"))}
            if right_id in left_deps or left_id in right_deps:
                continue
            right_paths = normalize_paths((right.get("scope") or {}).get("modify"))
            if any(paths_overlap(a, b) for a in left_paths for b in right_paths):
                conflicts.append((left_id, right_id))
    return conflicts


def task_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def runnable_tasks(data: dict[str, Any], now: datetime) -> list[dict[str, Any]]:
    tasks = [task for task in data.get("tasks", []) if isinstance(task, dict)]
    by_id = task_by_id(tasks)
    result = []
    for task in tasks:
        status = task.get("status")
        if status in TERMINAL_STATUSES or status in {"waiting", "review"}:
            continue
        if status == "claimed" and not claim_expired(task, now):
            continue
        if status not in READY_STATUSES and not (status == "claimed" and claim_expired(task, now)):
            continue
        if not dependencies_done(task, by_id):
            continue
        if blocked_by_concurrency(task, tasks):
            continue
        result.append(task)
    priority_order = {"high": 0, "medium": 1, "low": 2}
    return sorted(result, key=lambda item: (priority_order.get(str(item.get("priority", "medium")), 1), str(item.get("id"))))


def generate_handoff(root: Path, task: dict[str, Any]) -> Path:
    now = datetime.now().astimezone()
    task_id = str(task.get("id"))
    path = root / HANDOFF_DIR / f"{now.strftime('%Y-%m-%d-%H%M')}-{task_id.lower()}-handoff.md"
    scope = task.get("scope") or {}
    verification = task.get("verification") or {}
    docs = task.get("docs") or {}
    lines = [
        f"# Task Handoff: {task_id}",
        "",
        f"- Generated: {now.isoformat(timespec='seconds')}",
        f"- Goal: {task.get('goal')}",
        f"- Title: {task.get('title')}",
        f"- Status: {task.get('status')}",
        f"- Priority: {task.get('priority')}",
        "",
        "## Dependencies",
        "",
        *(f"- {dep}" for dep in task_list(task.get("depends_on")) or ["none"]),
        "",
        "## Scope: read first",
        "",
        *(f"- `{item}`" for item in task_list(scope.get("read")) or ["none"]),
        "",
        "## Scope: modify only",
        "",
        *(f"- `{item}`" for item in task_list(scope.get("modify")) or ["none"]),
        "",
        "## Do not touch",
        "",
        *(f"- `{item}`" for item in task_list(scope.get("do_not_touch")) or ["none"]),
        "",
        "## Acceptance criteria",
        "",
        *(f"- [ ] {item}" for item in task_list(task.get("acceptance")) or ["No explicit criteria"]),
        "",
        "## Verification commands",
        "",
        *(f"- `{cmd}`" for cmd in task_list(verification.get("commands") if isinstance(verification, dict) else None) or ["No command specified"]),
        "",
        "## Documentation",
        "",
        "Check:",
        *(f"- `{item}`" for item in task_list(docs.get("check"))),
        "",
        "Update:",
        *(f"- `{item}`" for item in task_list(docs.get("update"))),
        "",
        "## Commit",
        "",
        f"- Mode: {(task.get('commit') or {}).get('mode')}",
        f"- Message: `{(task.get('commit') or {}).get('message')}`",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def task_to_text(task: dict[str, Any]) -> str:
    return json.dumps(task, indent=2, ensure_ascii=False)


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect or claim the next repo task.")
    parser.add_argument("--claim", action="store_true", help="Claim the next runnable task and write a handoff file.")
    parser.add_argument("--agent", default=os.environ.get("HERMES_PROFILE", "hermes-agent"), help="Agent/profile name for claims.")
    parser.add_argument("--session", default=os.environ.get("HERMES_SESSION_ID", ""), help="Optional session id to record in the claim.")
    parser.add_argument("--task", help="Show one task by id.")
    parser.add_argument("--list", action="store_true", help="List tasks and runnable status.")
    parser.add_argument("--json", action="store_true", help="Emit JSON only.")
    args = parser.parse_args()

    try:
        root = git_root()
        path = root / TASKS_PATH
        if not path.exists():
            raise RuntimeError(f"missing task queue: {TASKS_PATH}")
        with repo_lock(root):
            data = load_yaml(path)
            tasks = [task for task in data.get("tasks", []) if isinstance(task, dict)]
            conflicts = guarded_conflicts(tasks)
            if conflicts:
                formatted = ", ".join(f"{left}/{right}" for left, right in conflicts)
                raise RuntimeError(f"conflicting guarded tasks with overlapping modify paths: {formatted}")
            by_id = task_by_id(tasks)
            now = datetime.now(timezone.utc)

            if args.task:
                task = by_id.get(args.task)
                if not task:
                    raise RuntimeError(f"task not found: {args.task}")
                print(task_to_text(task))
                return 0

            runnable = runnable_tasks(data, now)
            if args.list or not args.claim:
                rows = []
                for task in tasks:
                    rows.append(
                        {
                            "id": task.get("id"),
                            "status": task.get("status"),
                            "priority": task.get("priority"),
                            "runnable": task in runnable,
                            "title": task.get("title"),
                        }
                    )
                if args.json:
                    print(json.dumps(rows, indent=2, ensure_ascii=False))
                else:
                    print("\n".join(f"{row['id']} [{row['status']}] runnable={row['runnable']} — {row['title']}" for row in rows))
                return 0

            if not runnable:
                print(json.dumps({"claimed": None, "reason": "no runnable tasks"}) if args.json else "No runnable tasks.")
                return 0

            task = runnable[0]
            lease_minutes = int((data.get("queue_policy") or {}).get("lease_minutes") or 60)
            task["status"] = "claimed"
            task["claim"] = {
                "by": args.agent,
                "at": now.isoformat(timespec="seconds"),
                "lease_until": (now + timedelta(minutes=lease_minutes)).isoformat(timespec="seconds"),
            }
            if args.session:
                task["claim"]["session"] = args.session
            handoff = generate_handoff(root, task)
            dump_yaml(path, data)
            payload = {"claimed": task.get("id"), "title": task.get("title"), "handoff": str(handoff.relative_to(root))}
            print(json.dumps(payload, indent=2, ensure_ascii=False) if args.json else f"Claimed {payload['claimed']}: {payload['handoff']}")
            return 0
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
