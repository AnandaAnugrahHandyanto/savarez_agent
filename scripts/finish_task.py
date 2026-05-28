#!/usr/bin/env python3
"""Validate and optionally commit one completed Agent Project Workspace task."""

from __future__ import annotations

import argparse
import posixpath
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

TASK_ID_RE = re.compile(r"^[A-Z0-9]+-T\d{3}$")
TASK_LINE_RE = re.compile(r"^-\s+\[(?P<state>[ xX])\]\s+(?P<body>.+)$")
TASKS_PATH = Path(".hermes/tasks.yaml")
SCHEMA_PATH = Path(".hermes/task-schema.yaml")
PROJECT_PATH = Path(".hermes/project.md")
TASKS_MD_PATH = Path("tasks.md")


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
        output = result.stdout.strip()
        raise RuntimeError(f"{' '.join(args)} failed" + (f":\n{output}" if output else ""))
    return result


def git_root() -> Path:
    result = run(["git", "rev-parse", "--show-toplevel"], Path.cwd())
    return Path(result.stdout.strip()).resolve()


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        import yaml  # type: ignore[import-not-found]
    except ModuleNotFoundError as exc:
        raise RuntimeError(f"PyYAML is required to read {path}") from exc
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def task_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


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
    return {canonical_scope_path(value) for value in task_list(values) if str(value).strip()}


def paths_overlap(a: str, b: str) -> bool:
    a = canonical_scope_path(a)
    b = canonical_scope_path(b)
    if a == "" or b == "":
        return True
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


def path_in_scope(path: str, scope_paths: set[str]) -> bool:
    candidate = canonical_scope_path(path)
    return any(paths_overlap(candidate, scope) and (scope == "" or candidate == scope or candidate.startswith(scope + "/")) for scope in scope_paths)


def task_done_line(root: Path, task_id: str) -> tuple[str, str] | None:
    tasks_path = root / TASKS_MD_PATH
    if not tasks_path.exists():
        return None
    for line in tasks_path.read_text(encoding="utf-8").splitlines():
        match = TASK_LINE_RE.match(line)
        if not match or task_id not in match.group("body"):
            continue
        if match.group("state").lower() != "x":
            raise RuntimeError(f"{task_id} exists in tasks.md but is not checked")
        if "status: done" not in line:
            raise RuntimeError(f"{task_id} is checked in tasks.md but missing status: done")
        if " done: " not in line and "| done:" not in line:
            raise RuntimeError(f"{task_id} is missing done: YYYY-MM-DD in tasks.md")
        if " evidence: " not in line and "| evidence:" not in line:
            raise RuntimeError(f"{task_id} is missing evidence in tasks.md")
        body = match.group("body")
        description = body.split("|", 1)[0].strip()
        return line, description
    raise RuntimeError(f"{task_id} not found as a completed task in tasks.md")


def validate_workspace(root: Path, task_id: str | None = None) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    for required in (PROJECT_PATH, SCHEMA_PATH, TASKS_PATH):
        if not (root / required).exists():
            errors.append(f"missing required file: {required}")

    schema = load_yaml(root / SCHEMA_PATH)
    queue = load_yaml(root / TASKS_PATH)
    project_id = queue.get("project")
    if schema.get("project") != project_id:
        errors.append(f"schema project {schema.get('project')!r} does not match queue project {project_id!r}")

    statuses = set(task_list(schema.get("status_values")))
    types = set(task_list(schema.get("type_values")))
    priorities = set(task_list(schema.get("priority_values")))
    required_fields = set(task_list(schema.get("required_task_fields")))
    guarded = set(task_list((schema.get("concurrency") or {}).get("guarded_statuses"))) or {"claimed", "active", "review"}

    tasks = [task for task in task_list(queue.get("tasks")) if isinstance(task, dict)]
    ids: list[str] = []
    by_id: dict[str, dict[str, Any]] = {}
    for task in tasks:
        task_id_value = str(task.get("id", ""))
        ids.append(task_id_value)
        by_id[task_id_value] = task

        if not TASK_ID_RE.match(task_id_value):
            errors.append(f"invalid task id: {task_id_value}")
        missing = sorted(field for field in required_fields if field not in task)
        if missing:
            errors.append(f"{task_id_value}: missing required fields: {', '.join(missing)}")
        if statuses and task.get("status") not in statuses:
            errors.append(f"{task_id_value}: invalid status {task.get('status')!r}")
        if types and task.get("type") not in types:
            errors.append(f"{task_id_value}: invalid type {task.get('type')!r}")
        if priorities and task.get("priority") not in priorities:
            errors.append(f"{task_id_value}: invalid priority {task.get('priority')!r}")

        scope = task.get("scope")
        if not isinstance(scope, dict):
            errors.append(f"{task_id_value}: scope must be a mapping")
        else:
            for key in ("read", "modify", "do_not_touch"):
                if not isinstance(scope.get(key), list):
                    errors.append(f"{task_id_value}: scope.{key} must be a list")
        if not isinstance(task.get("acceptance"), list) or not task.get("acceptance"):
            errors.append(f"{task_id_value}: acceptance must be a non-empty list")
        verification = task.get("verification")
        if not isinstance(verification, dict) or not isinstance(verification.get("commands"), list):
            errors.append(f"{task_id_value}: verification.commands must be a list")
        docs = task.get("docs")
        if not isinstance(docs, dict):
            errors.append(f"{task_id_value}: docs must be a mapping")
        else:
            for key in ("check", "update"):
                if not isinstance(docs.get(key), list):
                    errors.append(f"{task_id_value}: docs.{key} must be a list")
        commit = task.get("commit")
        if not isinstance(commit, dict) or commit.get("mode") not in {"task", "none", "pr"}:
            errors.append(f"{task_id_value}: commit.mode must be task, none, or pr")

        if task.get("status") == "done":
            evidence = task.get("evidence")
            if not isinstance(evidence, dict) or not any(evidence.get(key) for key in ("paths", "commands", "commit")):
                errors.append(f"{task_id_value}: done task missing evidence.paths, evidence.commands, or evidence.commit")

    if len(ids) != len(set(ids)):
        duplicate_ids = sorted(task_id for task_id in set(ids) if ids.count(task_id) > 1)
        errors.append(f"duplicate task ids: {', '.join(duplicate_ids)}")

    for task in tasks:
        for dep in task_list(task.get("depends_on")):
            if str(dep) not in by_id:
                errors.append(f"{task.get('id')}: missing dependency task {dep}")

    guarded_tasks = [task for task in tasks if task.get("status") in guarded]
    for index, left in enumerate(guarded_tasks):
        left_id = str(left.get("id"))
        left_paths = normalize_paths((left.get("scope") or {}).get("modify"))
        left_deps = {str(dep) for dep in task_list(left.get("depends_on"))}
        for right in guarded_tasks[index + 1 :]:
            right_id = str(right.get("id"))
            right_deps = {str(dep) for dep in task_list(right.get("depends_on"))}
            if right_id in left_deps or left_id in right_deps:
                continue
            right_paths = normalize_paths((right.get("scope") or {}).get("modify"))
            if any(paths_overlap(a, b) for a in left_paths for b in right_paths):
                errors.append(f"guarded tasks overlap without dependency: {left_id}/{right_id}")

    selected_task = by_id.get(task_id) if task_id else None
    if task_id and not selected_task:
        errors.append(f"task not found in .hermes/tasks.yaml: {task_id}")
    if selected_task:
        if selected_task.get("status") != "done":
            errors.append(f"{task_id}: task status must be done before finish")
        if task_id and (root / TASKS_MD_PATH).exists():
            task_done_line(root, task_id)
        else:
            warnings.append("tasks.md not found; validated machine queue only")

    if errors:
        raise RuntimeError("workspace validation failed:\n- " + "\n- ".join(errors))
    return {"ok": True, "tasks": len(tasks), "warnings": warnings}


def install_hooks(root: Path) -> None:
    hooks_dir = root / ".githooks"
    if hooks_dir.is_dir():
        run(["git", "config", "core.hooksPath", ".githooks"], root)


def has_staged_changes(root: Path) -> bool:
    result = run(["git", "diff", "--cached", "--quiet"], root, check=False)
    return result.returncode == 1


def selected_task(root: Path, task_id: str) -> dict[str, Any]:
    queue = load_yaml(root / TASKS_PATH)
    for task in task_list(queue.get("tasks")):
        if isinstance(task, dict) and str(task.get("id")) == task_id:
            return task
    raise RuntimeError(f"task not found in .hermes/tasks.yaml: {task_id}")


def changed_paths(root: Path) -> list[str]:
    result = run(["git", "status", "--porcelain"], root)
    paths: list[str] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        raw = line[3:]
        path = raw.split(" -> ")[-1]
        paths.append(canonical_scope_path(path))
    return paths


def enforce_scope(root: Path, task: dict[str, Any]) -> None:
    raw_scope = task.get("scope")
    scope = raw_scope if isinstance(raw_scope, dict) else {}
    modify_paths = normalize_paths(scope.get("modify"))
    do_not_touch = normalize_paths(scope.get("do_not_touch"))
    if not modify_paths:
        raise RuntimeError(f"{task.get('id')}: scope.modify must not be empty before commit")
    changed = changed_paths(root)
    out_of_scope = [path for path in changed if not path_in_scope(path, modify_paths)]
    forbidden = [path for path in changed if any(paths_overlap(path, blocked) for blocked in do_not_touch)]
    if out_of_scope:
        raise RuntimeError("changed paths outside task scope.modify:\n- " + "\n- ".join(out_of_scope))
    if forbidden:
        raise RuntimeError("changed paths overlap task scope.do_not_touch:\n- " + "\n- ".join(forbidden))


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and commit one completed repo task.")
    parser.add_argument("task_id", nargs="?", help="Task id, e.g. HERMES-T001")
    parser.add_argument("message", nargs="*", help="Commit message tail. Defaults to the task description.")
    parser.add_argument("--all", action="store_true", dest="stage_all", help="Stage all workspace changes before committing.")
    parser.add_argument("--no-hooks", action="store_true", help="Do not install repo-local git hooks before committing.")
    parser.add_argument("--validate-only", action="store_true", help="Validate the queue and optional task without staging or committing.")
    args = parser.parse_args()

    task_id = args.task_id.strip().upper() if args.task_id else None
    if task_id and not TASK_ID_RE.match(task_id):
        print(f"Invalid task id: {args.task_id}", file=sys.stderr)
        return 2
    if not task_id and not args.validate_only:
        print("task_id is required unless --validate-only is used", file=sys.stderr)
        return 2

    try:
        root = git_root()
        result = validate_workspace(root, task_id)
        if args.validate_only:
            print("workspace validation ok" + (f" ({result['tasks']} tasks)" if result.get("tasks") is not None else ""))
            for warning in result.get("warnings", []):
                print(f"warning: {warning}")
            return 0

        assert task_id is not None
        done_line = task_done_line(root, task_id)
        description = done_line[1] if done_line else task_id
        task = selected_task(root, task_id)
        enforce_scope(root, task)
        if not args.no_hooks:
            install_hooks(root)
        if args.stage_all:
            run(["git", "add", "-A"], root)
        if not has_staged_changes(root):
            raise RuntimeError("no staged changes; stage files first or rerun with --all")
        tail = " ".join(args.message).strip() or description
        commit_message = tail if task_id in tail else f"{task_id}: {tail}"
        run(["git", "commit", "-m", commit_message], root)
        commit_hash = run(["git", "rev-parse", "--short", "HEAD"], root).stdout.strip()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"Committed {task_id}: {commit_hash}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
