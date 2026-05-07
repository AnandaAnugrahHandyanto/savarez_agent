from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

_DIRECTIVE_PREFIXES = ("done", "doing", "add", "block", "move")
_STATUS_BY_ACTION = {
    "done": "done",
    "doing": "doing",
    "add": "todo",
    "block": "blocked",
    "move": "todo",
}


@dataclass(frozen=True)
class TodoDirective:
    action: str
    title: str


@dataclass(frozen=True)
class TodoReplyResult:
    directives: list[TodoDirective]
    changes: list[str]
    open_tasks: list[dict]

    def render_message(self) -> str:
        lines = ["Updated to-do list"]
        for change in self.changes:
            lines.append(f"- {change}")
        if self.open_tasks:
            lines.append("")
            lines.append("Open tasks")
            for task in self.open_tasks[:8]:
                lines.append(f"- [{task['status']}] {task['title']}")
        else:
            lines.append("")
            lines.append("Open tasks")
            lines.append("- none")
        return "\n".join(lines)


def looks_like_structured_todo_reply(text: str, reply_to_text: str | None = None) -> bool:
    directives = parse_structured_todo_reply(text)
    if not directives:
        return False
    if not reply_to_text:
        return False
    lowered = reply_to_text.lower()
    return "reply format" in lowered and any(f"{prefix}:" in lowered for prefix in _DIRECTIVE_PREFIXES)


def parse_structured_todo_reply(text: str) -> list[TodoDirective]:
    directives: list[TodoDirective] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if ":" not in line:
            continue
        action, remainder = line.split(":", 1)
        action = action.strip().lower()
        if action not in _DIRECTIVE_PREFIXES:
            continue
        chunks = [chunk.strip(" -•\t") for chunk in remainder.split(";")]
        for chunk in chunks:
            if chunk:
                directives.append(TodoDirective(action=action, title=chunk))
    return directives


def apply_structured_todo_reply(tasks_path: str | Path, directives: Iterable[TodoDirective]) -> TodoReplyResult:
    tasks_file = Path(tasks_path).expanduser()
    tasks_file.parent.mkdir(parents=True, exist_ok=True)

    data = _load_tasks(tasks_file)
    tasks = [_normalize_task(task) for task in data.get("tasks", [])]
    tasks = [task for task in tasks if task is not None]

    changes: list[str] = []
    applied_directives = list(directives)
    for directive in applied_directives:
        status = _STATUS_BY_ACTION[directive.action]
        task = _find_task(tasks, directive.title)
        if task is None:
            task = {"title": directive.title, "status": status, "notes": ""}
            tasks.append(task)
            if directive.action == "add":
                changes.append(f"added: {directive.title}")
            else:
                changes.append(f"created {status}: {directive.title}")
            continue

        previous_status = task.get("status", "todo")
        task["status"] = status
        if directive.action == "add":
            if previous_status == "done":
                changes.append(f"reopened: {directive.title}")
            else:
                changes.append(f"kept: {directive.title}")
        elif previous_status == status:
            changes.append(f"unchanged {status}: {directive.title}")
        else:
            changes.append(f"{previous_status} -> {status}: {directive.title}")

    today = datetime.now().date().isoformat()
    data["version"] = data.get("version", 1)
    data["created"] = data.get("created") or today
    data["updated"] = today
    data["tasks"] = tasks
    tasks_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    open_tasks = [task for task in tasks if task.get("status") != "done"]
    open_tasks.sort(key=lambda task: (_status_sort_key(task.get("status", "todo")), task.get("title", "").lower()))
    return TodoReplyResult(directives=applied_directives, changes=changes, open_tasks=open_tasks)


def _load_tasks(tasks_file: Path) -> dict:
    if not tasks_file.exists():
        return {"version": 1, "created": datetime.now().date().isoformat(), "tasks": []}
    loaded = json.loads(tasks_file.read_text(encoding="utf-8"))
    if isinstance(loaded, dict):
        return loaded
    return {"version": 1, "created": datetime.now().date().isoformat(), "tasks": []}


def _normalize_task(task) -> dict | None:
    if isinstance(task, str):
        title = task.strip()
        return {"title": title, "status": "todo", "notes": ""} if title else None
    if not isinstance(task, dict):
        return None
    title = str(task.get("title") or "").strip()
    if not title:
        return None
    status = str(task.get("status") or "todo").strip().lower()
    if status not in {"todo", "doing", "blocked", "done"}:
        status = "todo"
    return {
        "title": title,
        "status": status,
        "notes": str(task.get("notes") or "").strip(),
    }


def _find_task(tasks: list[dict], query: str) -> dict | None:
    needle = query.strip().lower()
    if not needle:
        return None

    exact_matches = [task for task in tasks if task.get("title", "").strip().lower() == needle]
    if exact_matches:
        return exact_matches[0]

    fuzzy_matches = [
        task for task in tasks
        if needle in task.get("title", "").strip().lower() or task.get("title", "").strip().lower() in needle
    ]
    if len(fuzzy_matches) == 1:
        return fuzzy_matches[0]
    return None


def _status_sort_key(status: str) -> int:
    order = {"doing": 0, "todo": 1, "blocked": 2, "done": 3}
    return order.get(status, 99)
