#!/usr/bin/env python3
"""Operational tool surface for the H007 execution receipt ledger."""

from __future__ import annotations

import json
import re
from typing import Any

from cron.jobs import create_job, list_jobs, parse_schedule, remove_job, update_job
from tools.execution_receipts import (
    prune_execution_receipts,
    query_execution_receipts,
    reconcile_execution_receipts,
)
from tools.registry import registry, tool_error, tool_result


MAINTENANCE_JOB_NAME = "Execution receipt ledger maintenance"
MAINTENANCE_PROMPT_MARKER = "H007_EXECUTION_RECEIPTS_MAINTENANCE"
_DEFAULT_MAINTENANCE_SCHEDULE = "every 6h"
_DEFAULT_COMPLETED_RETENTION_SECONDS = 7 * 24 * 60 * 60
_DEFAULT_FAILED_RETENTION_SECONDS = 30 * 24 * 60 * 60
_DEFAULT_MAINTENANCE_PRUNE_LIMIT = 200


EXECUTION_RECEIPTS_SCHEMA = {
    "name": "execution_receipts",
    "description": (
        "Inspect and maintain the execution receipt ledger for delegated work. "
        "Use this to list recent delegated receipts, query by session/status, "
        "prune old receipts, reconcile the SQLite index with the receipt files, "
        "or install a cron-backed maintenance job for the ledger.\n\n"
        "ACTIONS:\n"
        "- list: recent receipts (default)\n"
        "- query: filtered receipt lookup\n"
        "- prune: delete old receipts from disk + index\n"
        "- reconcile: repair drift between receipt files and the SQLite index\n"
        "- maintenance_status: inspect the installed cron-backed ledger maintenance job\n"
        "- install_maintenance: create/update the cron-backed ledger maintenance job\n"
        "- remove_maintenance: remove the cron-backed ledger maintenance job\n\n"
        "Good for operational debugging of delegation, execution ledgers, and evidence packs."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "list",
                    "query",
                    "prune",
                    "reconcile",
                    "maintenance_status",
                    "install_maintenance",
                    "remove_maintenance",
                ],
                "description": "Which ledger action to perform. Default: list.",
            },
            "limit": {
                "type": "integer",
                "description": (
                    "Max rows to return for list/query, max rows to prune in one pass, "
                    "or max rows the maintenance job should prune per pass."
                ),
            },
            "status": {
                "type": "string",
                "description": "Optional status filter for query/list (e.g. completed, failed).",
            },
            "parent_session_id": {
                "type": "string",
                "description": "Optional parent session filter for query/list.",
            },
            "child_session_id": {
                "type": "string",
                "description": "Optional child session filter for query/list.",
            },
            "max_age_seconds": {
                "type": "number",
                "description": "Age threshold for prune; receipts older than this may be removed.",
            },
            "keep_failed": {
                "type": "boolean",
                "description": "For prune: keep failed receipts by default.",
                "default": True,
            },
            "delete_missing_rows": {
                "type": "boolean",
                "description": "For reconcile and maintenance: remove index rows whose files are missing.",
                "default": True,
            },
            "schedule": {
                "type": "string",
                "description": "For install_maintenance: cron schedule string. Default: every 6h.",
            },
            "prune_completed_after_seconds": {
                "type": "number",
                "description": "For install_maintenance: prune completed/non-failed receipts older than this.",
            },
            "prune_failed_after_seconds": {
                "type": "number",
                "description": "For install_maintenance: prune failed receipts older than this.",
            },
            "model": {
                "type": "string",
                "description": "Optional per-job model override for the maintenance cron job.",
            },
            "provider": {
                "type": "string",
                "description": "Optional per-job provider override for the maintenance cron job.",
            },
            "base_url": {
                "type": "string",
                "description": "Optional per-job base URL override for the maintenance cron job.",
            },
        },
        "required": [],
    },
}


def check_execution_receipts_requirements() -> bool:
    return True


def _normalize_optional_text(value: str | None, *, strip_trailing_slash: bool = False) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if strip_trailing_slash:
        text = text.rstrip("/")
    return text or None


def _normalize_maintenance_config(
    *,
    schedule: str | None,
    prune_completed_after_seconds: float | None,
    prune_failed_after_seconds: float | None,
    delete_missing_rows: bool,
    limit: int | None,
    model: str | None,
    provider: str | None,
    base_url: str | None,
) -> dict[str, Any]:
    normalized_schedule = _normalize_optional_text(schedule) or _DEFAULT_MAINTENANCE_SCHEDULE
    normalized_completed = float(
        prune_completed_after_seconds
        if prune_completed_after_seconds is not None
        else _DEFAULT_COMPLETED_RETENTION_SECONDS
    )
    normalized_failed = float(
        prune_failed_after_seconds
        if prune_failed_after_seconds is not None
        else _DEFAULT_FAILED_RETENTION_SECONDS
    )
    normalized_limit = max(1, int(limit if limit is not None else _DEFAULT_MAINTENANCE_PRUNE_LIMIT))

    if normalized_completed <= 0:
        raise ValueError("prune_completed_after_seconds must be > 0")
    if normalized_failed <= 0:
        raise ValueError("prune_failed_after_seconds must be > 0")

    return {
        "schedule": normalized_schedule,
        "prune_completed_after_seconds": normalized_completed,
        "prune_failed_after_seconds": normalized_failed,
        "delete_missing_rows": bool(delete_missing_rows),
        "prune_limit": normalized_limit,
        "model": _normalize_optional_text(model),
        "provider": _normalize_optional_text(provider),
        "base_url": _normalize_optional_text(base_url, strip_trailing_slash=True),
    }


def _build_maintenance_prompt(config: dict[str, Any]) -> str:
    config_json = json.dumps(config, ensure_ascii=False, sort_keys=True)
    return (
        f"[{MAINTENANCE_PROMPT_MARKER}]\n"
        f"{config_json}\n"
        f"[/{MAINTENANCE_PROMPT_MARKER}]\n\n"
        "You are the scheduled maintenance controller for the Hermes delegated execution receipt ledger.\n"
        "Use only the execution_receipts tool for this task.\n\n"
        "Required sequence:\n"
        f"1. Call execution_receipts with action='reconcile' and delete_missing_rows={str(config['delete_missing_rows']).lower()}.\n"
        f"2. Call execution_receipts with action='prune', max_age_seconds={config['prune_completed_after_seconds']}, "
        f"keep_failed=true, and limit={config['prune_limit']}.\n"
        f"3. Call execution_receipts with action='prune', max_age_seconds={config['prune_failed_after_seconds']}, "
        f"keep_failed=false, and limit={config['prune_limit']}.\n\n"
        "Final response rules:\n"
        "- If reconcile inserted_count=0, reconcile removed_missing_count=0, and both prune deleted_count values are 0, "
        "respond with exactly [SILENT].\n"
        "- Otherwise return a compact JSON object with keys: reconcile, completed_prune, failed_prune, changed.\n"
        "Do not ask clarifying questions. Do not use send_message."
    )


def _extract_maintenance_config(prompt: str | None) -> dict[str, Any] | None:
    text = str(prompt or "")
    pattern = rf"\[{MAINTENANCE_PROMPT_MARKER}\]\s*(\{{.*?\}})\s*\[/{MAINTENANCE_PROMPT_MARKER}\]"
    match = re.search(pattern, text, flags=re.DOTALL)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(1))
    except Exception:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def _matching_maintenance_jobs() -> list[tuple[dict[str, Any], dict[str, Any] | None]]:
    matches: list[tuple[dict[str, Any], dict[str, Any] | None]] = []
    for job in list_jobs(include_disabled=True):
        config = _extract_maintenance_config(job.get("prompt"))
        if config is not None:
            matches.append((job, config))
    matches.sort(key=lambda item: item[0].get("created_at") or "")
    return matches


def _format_maintenance_job(job: dict[str, Any], config: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "job_id": job.get("id"),
        "name": job.get("name"),
        "schedule": job.get("schedule_display"),
        "next_run_at": job.get("next_run_at"),
        "last_run_at": job.get("last_run_at"),
        "last_status": job.get("last_status"),
        "last_delivery_error": job.get("last_delivery_error"),
        "enabled": job.get("enabled", True),
        "state": job.get("state", "scheduled" if job.get("enabled", True) else "paused"),
        "deliver": job.get("deliver", "local"),
        "model": job.get("model"),
        "provider": job.get("provider"),
        "base_url": job.get("base_url"),
        "config": config,
    }


def _maintenance_status_payload() -> dict[str, Any]:
    matches = _matching_maintenance_jobs()
    jobs = [_format_maintenance_job(job, config) for job, config in matches]
    return {
        "installed": bool(jobs),
        "installed_count": len(jobs),
        "jobs": jobs,
    }


def _upsert_maintenance_job(config: dict[str, Any]) -> dict[str, Any]:
    parsed_schedule = parse_schedule(config["schedule"])
    prompt = _build_maintenance_prompt(config)
    matches = _matching_maintenance_jobs()

    removed_duplicate_job_ids: list[str] = []
    primary = matches[0][0] if matches else None
    duplicates = matches[1:] if len(matches) > 1 else []
    for duplicate, _ in duplicates:
        duplicate_id = duplicate.get("id")
        if duplicate_id and remove_job(str(duplicate_id)):
            removed_duplicate_job_ids.append(str(duplicate_id))

    if primary is None:
        job = create_job(
            prompt=prompt,
            schedule=config["schedule"],
            name=MAINTENANCE_JOB_NAME,
            deliver="local",
            model=config["model"],
            provider=config["provider"],
            base_url=config["base_url"],
        )
        created = True
    else:
        job = update_job(
            str(primary["id"]),
            {
                "name": MAINTENANCE_JOB_NAME,
                "prompt": prompt,
                "schedule": parsed_schedule,
                "schedule_display": parsed_schedule.get("display", config["schedule"]),
                "deliver": "local",
                "model": config["model"],
                "provider": config["provider"],
                "base_url": config["base_url"],
                "enabled": True,
                "state": "scheduled",
                "paused_at": None,
                "paused_reason": None,
            },
        )
        created = False

    if not job:
        raise RuntimeError("Failed to create or update the maintenance cron job")

    return {
        "installed": True,
        "created": created,
        "updated": not created,
        "removed_duplicate_job_ids": removed_duplicate_job_ids,
        "job": _format_maintenance_job(job, config),
    }


def _remove_maintenance_jobs() -> dict[str, Any]:
    deleted_job_ids: list[str] = []
    for job, _config in _matching_maintenance_jobs():
        job_id = str(job.get("id"))
        if job_id and remove_job(job_id):
            deleted_job_ids.append(job_id)
    return {
        "deleted_count": len(deleted_job_ids),
        "deleted_job_ids": deleted_job_ids,
    }


def execution_receipts_tool(
    *,
    action: str | None = None,
    limit: int | None = None,
    status: str | None = None,
    parent_session_id: str | None = None,
    child_session_id: str | None = None,
    max_age_seconds: float | None = None,
    keep_failed: bool = True,
    delete_missing_rows: bool = True,
    schedule: str | None = None,
    prune_completed_after_seconds: float | None = None,
    prune_failed_after_seconds: float | None = None,
    model: str | None = None,
    provider: str | None = None,
    base_url: str | None = None,
) -> str:
    action = (action or "list").strip().lower()

    if action in {"list", "query"}:
        effective_limit = max(1, int(limit if limit is not None else 10))
        receipts = query_execution_receipts(
            limit=effective_limit,
            status=status,
            parent_session_id=parent_session_id,
            child_session_id=child_session_id,
        )
        return tool_result({
            "action": action,
            "count": len(receipts),
            "receipts": receipts,
        })

    if action == "prune":
        if max_age_seconds is None:
            return tool_error("prune requires max_age_seconds")
        try:
            max_age = float(max_age_seconds)
        except (TypeError, ValueError):
            return tool_error("prune max_age_seconds must be a number")
        if max_age <= 0:
            return tool_error("prune max_age_seconds must be > 0")
        effective_limit = max(1, int(limit if limit is not None else 10))
        result = prune_execution_receipts(
            max_age_seconds=max_age,
            keep_failed=bool(keep_failed),
            limit=effective_limit,
        )
        return tool_result({"action": action, **result})

    if action == "reconcile":
        result = reconcile_execution_receipts(delete_missing_rows=bool(delete_missing_rows))
        return tool_result({"action": action, **result})

    if action == "maintenance_status":
        return tool_result({"action": action, **_maintenance_status_payload()})

    if action == "install_maintenance":
        try:
            config = _normalize_maintenance_config(
                schedule=schedule,
                prune_completed_after_seconds=prune_completed_after_seconds,
                prune_failed_after_seconds=prune_failed_after_seconds,
                delete_missing_rows=delete_missing_rows,
                limit=limit,
                model=model,
                provider=provider,
                base_url=base_url,
            )
            result = _upsert_maintenance_job(config)
        except Exception as exc:
            return tool_error(f"install_maintenance failed: {exc}")
        return tool_result({"action": action, **result})

    if action == "remove_maintenance":
        return tool_result({"action": action, **_remove_maintenance_jobs()})

    return tool_error(f"Unknown action: {action}")


registry.register(
    name="execution_receipts",
    toolset="execution_receipts",
    schema=EXECUTION_RECEIPTS_SCHEMA,
    handler=lambda args, **kw: execution_receipts_tool(
        action=args.get("action"),
        limit=args.get("limit"),
        status=args.get("status"),
        parent_session_id=args.get("parent_session_id"),
        child_session_id=args.get("child_session_id"),
        max_age_seconds=args.get("max_age_seconds"),
        keep_failed=args.get("keep_failed", True),
        delete_missing_rows=args.get("delete_missing_rows", True),
        schedule=args.get("schedule"),
        prune_completed_after_seconds=args.get("prune_completed_after_seconds"),
        prune_failed_after_seconds=args.get("prune_failed_after_seconds"),
        model=args.get("model"),
        provider=args.get("provider"),
        base_url=args.get("base_url"),
    ),
    check_fn=check_execution_receipts_requirements,
    emoji="🧾",
)
