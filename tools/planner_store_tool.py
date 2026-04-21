import json
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from hermes_constants import get_hermes_home
from tools.registry import registry


PLANNER_STORE_SCHEMA = {
    "name": "planner_store",
    "description": (
        "Planner storage for capturing and managing personal inbox items: tasks, notes, reminders, and events. "
        "Use this for planner workflows instead of ad-hoc text memory. Supports capture, showing today's plan, inbox, "
        "marking items done, rescheduling, and daily review."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["capture", "today", "inbox", "done", "reschedule", "review", "get"],
                "description": "Planner action to perform."
            },
            "item_type": {
                "type": "string",
                "enum": ["task", "note", "reminder", "event"],
                "description": "Type for capture. If omitted, the tool will infer a best-effort type."
            },
            "id": {
                "type": "string",
                "description": "Item ID for get/done/reschedule."
            },
            "text": {
                "type": "string",
                "description": "Main user content for capture: task text, reminder text, note body, or event title."
            },
            "priority": {
                "type": "string",
                "enum": ["low", "normal", "high"],
                "description": "Priority for tasks."
            },
            "due_date": {
                "type": "string",
                "description": "Due date in ISO format YYYY-MM-DD for tasks."
            },
            "due_time": {
                "type": "string",
                "description": "Optional due time HH:MM for tasks."
            },
            "remind_at": {
                "type": "string",
                "description": "Reminder datetime in ISO format, e.g. 2026-04-21T10:00:00+03:00."
            },
            "repeat": {
                "type": "string",
                "enum": ["none", "daily", "weekly", "monthly"],
                "description": "Repeat mode for reminders."
            },
            "start_at": {
                "type": "string",
                "description": "Event start datetime in ISO format."
            },
            "end_at": {
                "type": "string",
                "description": "Event end datetime in ISO format."
            },
            "location": {
                "type": "string",
                "description": "Optional event location."
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional tags."
            },
            "notes": {
                "type": "string",
                "description": "Optional notes/context."
            }
        },
        "required": ["action"]
    }
}


def _planner_store_path() -> Path:
    root = get_hermes_home() / "data"
    root.mkdir(parents=True, exist_ok=True)
    return root / "planner_store.json"


def _now_local() -> datetime:
    return datetime.now().astimezone()


def _now_iso() -> str:
    return _now_local().isoformat(timespec="seconds")


def _today_date() -> str:
    return _now_local().date().isoformat()


def _load_store() -> Dict[str, List[Dict[str, Any]]]:
    path = _planner_store_path()
    if not path.exists():
        return {"tasks": [], "notes": [], "reminders": [], "events": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"tasks": [], "notes": [], "reminders": [], "events": []}
    if not isinstance(data, dict):
        return {"tasks": [], "notes": [], "reminders": [], "events": []}
    for key in ("tasks", "notes", "reminders", "events"):
        data.setdefault(key, [])
        if not isinstance(data[key], list):
            data[key] = []
    return data


def _save_store(store: Dict[str, List[Dict[str, Any]]]) -> None:
    path = _planner_store_path()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _make_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _infer_type(text: str, args: Dict[str, Any]) -> str:
    txt = (text or "").strip().lower()
    if args.get("remind_at") or txt.startswith("напомни") or txt.startswith("пни"):
        return "reminder"
    if args.get("start_at") or args.get("end_at") or args.get("location"):
        return "event"
    event_words = ("встреч", "созвон", "стоматолог", "прием", "приём", "ужин", "поезд", "самолет", "самолёт")
    if any(word in txt for word in event_words) and any(ch.isdigit() for ch in txt):
        return "event"
    task_words = ("сделать", "купить", "проверить", "написать", "созвониться", "доделать", "задача")
    if args.get("due_date") or args.get("due_time") or any(txt.startswith(w) for w in task_words):
        return "task"
    return "note"


def _all_items(store: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for key in ("tasks", "notes", "reminders", "events"):
        items.extend(store.get(key, []))
    return items


def _find_item(store: Dict[str, List[Dict[str, Any]]], item_id: str) -> tuple[Optional[str], Optional[Dict[str, Any]]]:
    for bucket in ("tasks", "notes", "reminders", "events"):
        for item in store.get(bucket, []):
            if item.get("id") == item_id:
                return bucket, item
    return None, None


def _capture(args: Dict[str, Any]) -> Dict[str, Any]:
    text = (args.get("text") or "").strip()
    if not text:
        return {"success": False, "error": "text is required for capture"}

    store = _load_store()
    item_type = args.get("item_type") or _infer_type(text, args)
    now = _now_iso()
    tags = [str(t).strip() for t in (args.get("tags") or []) if str(t).strip()]
    notes = (args.get("notes") or "").strip() or None

    if item_type == "task":
        item = {
            "id": _make_id("task"),
            "type": "task",
            "text": text,
            "status": "todo",
            "priority": args.get("priority") or "normal",
            "due_date": args.get("due_date") or None,
            "due_time": args.get("due_time") or None,
            "tags": tags,
            "source": "telegram",
            "created_at": now,
            "updated_at": now,
            "notes": notes,
        }
        store["tasks"].append(item)
    elif item_type == "reminder":
        item = {
            "id": _make_id("rem"),
            "type": "reminder",
            "text": text,
            "remind_at": args.get("remind_at") or None,
            "repeat": args.get("repeat") or "none",
            "status": "active",
            "created_at": now,
            "updated_at": now,
            "notes": notes,
        }
        store["reminders"].append(item)
    elif item_type == "event":
        item = {
            "id": _make_id("evt"),
            "type": "event",
            "title": text,
            "start_at": args.get("start_at") or None,
            "end_at": args.get("end_at") or None,
            "location": args.get("location") or None,
            "status": "planned",
            "created_at": now,
            "updated_at": now,
            "notes": notes,
            "tags": tags,
        }
        store["events"].append(item)
    else:
        item = {
            "id": _make_id("note"),
            "type": "note",
            "text": text,
            "tags": tags,
            "source": "telegram",
            "created_at": now,
            "updated_at": now,
        }
        if notes:
            item["notes"] = notes
        store["notes"].append(item)

    _save_store(store)
    return {
        "success": True,
        "action": "capture",
        "item": item,
        "store_path": str(_planner_store_path()),
    }


def _task_sort_key(item: Dict[str, Any]):
    return (
        item.get("due_date") or "9999-12-31",
        item.get("due_time") or "23:59",
        item.get("created_at") or "",
    )


def _today(args: Dict[str, Any]) -> Dict[str, Any]:
    store = _load_store()
    today = _today_date()
    now_iso = _now_iso()

    tasks_due_today = []
    overdue_tasks = []
    for task in store["tasks"]:
        if task.get("status") in {"done", "cancelled"}:
            continue
        due_date = task.get("due_date")
        if due_date == today:
            tasks_due_today.append(task)
        elif due_date and due_date < today:
            overdue_tasks.append(task)

    reminders_today = []
    for rem in store["reminders"]:
        if rem.get("status") != "active":
            continue
        remind_at = rem.get("remind_at") or ""
        if remind_at.startswith(today):
            reminders_today.append(rem)

    events_today = []
    for evt in store["events"]:
        if evt.get("status") == "cancelled":
            continue
        start_at = evt.get("start_at") or ""
        if start_at.startswith(today):
            events_today.append(evt)

    tasks_due_today.sort(key=_task_sort_key)
    overdue_tasks.sort(key=_task_sort_key)
    reminders_today.sort(key=lambda x: x.get("remind_at") or "")
    events_today.sort(key=lambda x: x.get("start_at") or "")

    return {
        "success": True,
        "action": "today",
        "date": today,
        "events": events_today,
        "reminders": reminders_today,
        "tasks_due_today": tasks_due_today,
        "overdue_tasks": overdue_tasks,
        "counts": {
            "events": len(events_today),
            "reminders": len(reminders_today),
            "tasks_due_today": len(tasks_due_today),
            "overdue_tasks": len(overdue_tasks),
        },
        "generated_at": now_iso,
    }


def _inbox(args: Dict[str, Any]) -> Dict[str, Any]:
    store = _load_store()
    tasks = [t for t in store["tasks"] if t.get("status") in {"inbox", "todo", "doing"}]
    notes = list(store["notes"][-10:])
    tasks.sort(key=_task_sort_key)
    return {
        "success": True,
        "action": "inbox",
        "tasks": tasks[:50],
        "recent_notes": notes,
        "counts": {"tasks": len(tasks), "recent_notes": len(notes)},
    }


def _done(args: Dict[str, Any]) -> Dict[str, Any]:
    item_id = (args.get("id") or "").strip()
    if not item_id:
        return {"success": False, "error": "id is required"}
    store = _load_store()
    bucket, item = _find_item(store, item_id)
    if not item:
        return {"success": False, "error": f"item not found: {item_id}"}
    if bucket == "tasks":
        item["status"] = "done"
    elif bucket == "reminders":
        item["status"] = "done"
    elif bucket == "events":
        item["status"] = "done"
    else:
        item["status"] = "done"
    item["updated_at"] = _now_iso()
    _save_store(store)
    return {"success": True, "action": "done", "item": item}


def _reschedule(args: Dict[str, Any]) -> Dict[str, Any]:
    item_id = (args.get("id") or "").strip()
    if not item_id:
        return {"success": False, "error": "id is required"}
    store = _load_store()
    bucket, item = _find_item(store, item_id)
    if not item:
        return {"success": False, "error": f"item not found: {item_id}"}

    if bucket == "tasks":
        if "due_date" in args:
            item["due_date"] = args.get("due_date") or None
        if "due_time" in args:
            item["due_time"] = args.get("due_time") or None
    elif bucket == "reminders":
        if "remind_at" in args:
            item["remind_at"] = args.get("remind_at") or None
    elif bucket == "events":
        if "start_at" in args:
            item["start_at"] = args.get("start_at") or None
        if "end_at" in args:
            item["end_at"] = args.get("end_at") or None
        if "location" in args:
            item["location"] = args.get("location") or None
    item["updated_at"] = _now_iso()
    _save_store(store)
    return {"success": True, "action": "reschedule", "item": item}


def _review(args: Dict[str, Any]) -> Dict[str, Any]:
    store = _load_store()
    today = _today_date()
    completed_today = []
    carryover = []
    for task in store["tasks"]:
        updated = task.get("updated_at") or ""
        if task.get("status") == "done" and updated.startswith(today):
            completed_today.append(task)
        elif task.get("status") in {"todo", "doing", "inbox"} and task.get("due_date") and task.get("due_date") <= today:
            carryover.append(task)
    return {
        "success": True,
        "action": "review",
        "date": today,
        "completed_today": completed_today,
        "carryover": carryover,
        "counts": {
            "completed_today": len(completed_today),
            "carryover": len(carryover),
        },
    }


def _get(args: Dict[str, Any]) -> Dict[str, Any]:
    store = _load_store()
    item_id = (args.get("id") or "").strip()
    if item_id:
        bucket, item = _find_item(store, item_id)
        if not item:
            return {"success": False, "error": f"item not found: {item_id}"}
        return {"success": True, "action": "get", "item": item, "bucket": bucket}
    return {
        "success": True,
        "action": "get",
        "counts": {k: len(v) for k, v in store.items()},
        "store_path": str(_planner_store_path()),
    }


def planner_store_tool(args, **_kw):
    action = (args.get("action") or "").strip().lower()
    if action == "capture":
        result = _capture(args)
    elif action == "today":
        result = _today(args)
    elif action == "inbox":
        result = _inbox(args)
    elif action == "done":
        result = _done(args)
    elif action == "reschedule":
        result = _reschedule(args)
    elif action == "review":
        result = _review(args)
    elif action == "get":
        result = _get(args)
    else:
        result = {"success": False, "error": f"unknown action: {action}"}
    return json.dumps(result, ensure_ascii=False)


registry.register(
    name="planner_store",
    toolset="planner",
    schema=PLANNER_STORE_SCHEMA,
    handler=planner_store_tool,
    emoji="🗓️",
    max_result_size_chars=100_000,
)
