"""Execution receipts CLI and slash-command surface for Hermes."""

from __future__ import annotations

import io
import json
import shlex
import sys
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

from hermes_cli.colors import Colors, color
from tools.execution_receipts_tool import execution_receipts_tool


def _receipts_api(**kwargs) -> dict[str, Any]:
    return json.loads(execution_receipts_tool(**kwargs))


def _print_list(limit: int = 10, status: str | None = None, parent_session_id: str | None = None, child_session_id: str | None = None):
    result = _receipts_api(
        action="query" if any([status, parent_session_id, child_session_id]) else "list",
        limit=limit,
        status=status,
        parent_session_id=parent_session_id,
        child_session_id=child_session_id,
    )
    if result.get("error"):
        print(color(f"Failed to query receipts: {result['error']}", Colors.RED))
        return 1

    receipts = result.get("receipts", [])
    if not receipts:
        print(color("No execution receipts found.", Colors.DIM))
        return 0

    print()
    print(color("┌─────────────────────────────────────────────────────────────────────────┐", Colors.CYAN))
    print(color("│                        Execution Receipts                               │", Colors.CYAN))
    print(color("└─────────────────────────────────────────────────────────────────────────┘", Colors.CYAN))
    print()

    for row in receipts:
        status_text = row.get("status") or "unknown"
        if status_text == "completed":
            status_display = color(f"[{status_text}]", Colors.GREEN)
        elif status_text == "failed":
            status_display = color(f"[{status_text}]", Colors.RED)
        else:
            status_display = color(f"[{status_text}]", Colors.YELLOW)
        print(f"  {color(row.get('receipt_id', '?'), Colors.YELLOW)} {status_display}")
        print(f"    Goal:       {row.get('goal') or '(none)'}")
        print(f"    Created:    {row.get('created_at')}")
        print(f"    Parent:     {row.get('parent_session_id') or '-'}")
        print(f"    Child:      {row.get('child_session_id') or '-'}")
        print(f"    Model:      {row.get('model') or '-'}")
        if row.get("execution_path") and row.get("execution_path") != "subagent":
            print(f"    Exec path:  {row.get('execution_path')}")
        print(f"    API calls:  {row.get('api_calls') if row.get('api_calls') is not None else '-'}")
        print(f"    Duration:   {row.get('duration_seconds') if row.get('duration_seconds') is not None else '-'}")
        if row.get("worker_mode"):
            worker_line = f"{row.get('worker_mode')}"
            if row.get("worker_reused"):
                worker_line += f" (reuse_count={row.get('worker_reuse_count', 0)})"
            if row.get("worker_task_id"):
                worker_line += f" via {row.get('worker_task_id')}"
            if row.get("worker_runtime_reused"):
                worker_line += " [runtime-reused]"
            print(f"    Worker:     {worker_line}")
            if row.get("worker_runtime_id"):
                print(f"    Runtime:    {row.get('worker_runtime_kind') or '-'} {row.get('worker_runtime_id')}")
        print(f"    File:       {row.get('file_path') or '-'}")
        if row.get("fallback_reason"):
            print(f"    Fallback:   {row['fallback_reason']}")
        print()
    return 0


def _print_reconcile(delete_missing_rows: bool = True):
    result = _receipts_api(action="reconcile", delete_missing_rows=delete_missing_rows)
    if result.get("error"):
        print(color(f"Failed to reconcile receipts: {result['error']}", Colors.RED))
        return 1

    print(color("Reconciled execution receipt ledger.", Colors.GREEN))
    print(f"  Inserted missing rows: {result.get('inserted_count', 0)}")
    print(f"  Removed missing-file rows: {result.get('removed_missing_count', 0)}")
    parse_errors = result.get("parse_errors") or []
    if parse_errors:
        print(color(f"  Parse errors: {len(parse_errors)}", Colors.YELLOW))
        for path in parse_errors[:5]:
            print(f"    - {path}")
    return 0


def _print_prune(max_age_seconds: float, keep_failed: bool = True, limit: int = 100):
    result = _receipts_api(
        action="prune",
        max_age_seconds=max_age_seconds,
        keep_failed=keep_failed,
        limit=limit,
    )
    if result.get("error"):
        print(color(f"Failed to prune receipts: {result['error']}", Colors.RED))
        return 1

    print(color("Pruned execution receipts.", Colors.GREEN))
    print(f"  Deleted: {result.get('deleted_count', 0)}")
    print(f"  Missing files observed: {result.get('missing_files', 0)}")
    deleted_ids = result.get("deleted_receipt_ids") or []
    if deleted_ids:
        print("  Receipt IDs:")
        for receipt_id in deleted_ids:
            print(f"    - {receipt_id}")
    return 0


def _print_maintenance_status():
    result = _receipts_api(action="maintenance_status")
    if result.get("error"):
        print(color(f"Failed to inspect maintenance status: {result['error']}", Colors.RED))
        return 1

    print()
    print(color("Execution receipt maintenance", Colors.CYAN))
    print(color("-" * 32, Colors.CYAN))
    print(f"  Installed jobs: {result.get('installed_count', 0)}")
    jobs = result.get("jobs") or []
    if not jobs:
        print(color("  No maintenance job installed.", Colors.DIM))
        return 0

    for job in jobs:
        print(f"  Job ID:      {job.get('job_id')}")
        print(f"  State:       {job.get('state')}")
        print(f"  Schedule:    {job.get('schedule')}")
        print(f"  Next run:    {job.get('next_run_at')}")
        print(f"  Last run:    {job.get('last_run_at')}")
        print(f"  Last status: {job.get('last_status')}")
        config = job.get("config") or {}
        if config:
            print(f"  Retain completed for: {config.get('prune_completed_after_seconds')}s")
            print(f"  Retain failed for:    {config.get('prune_failed_after_seconds')}s")
            print(f"  Delete missing rows:  {config.get('delete_missing_rows')}")
            print(f"  Prune limit:          {config.get('prune_limit')}")
        print()
    return 0


def _print_install(schedule: str | None, prune_completed_after_seconds: float | None,
                   prune_failed_after_seconds: float | None, delete_missing_rows: bool,
                   limit: int | None, model: str | None, provider: str | None, base_url: str | None):
    result = _receipts_api(
        action="install_maintenance",
        schedule=schedule,
        prune_completed_after_seconds=prune_completed_after_seconds,
        prune_failed_after_seconds=prune_failed_after_seconds,
        delete_missing_rows=delete_missing_rows,
        limit=limit,
        model=model,
        provider=provider,
        base_url=base_url,
    )
    if result.get("error"):
        print(color(f"Failed to install maintenance: {result['error']}", Colors.RED))
        return 1

    verb = "Created" if result.get("created") else "Updated"
    job = result.get("job") or {}
    print(color(f"{verb} execution receipt maintenance job.", Colors.GREEN))
    print(f"  Job ID: {job.get('job_id')}")
    print(f"  Schedule: {job.get('schedule')}")
    print(f"  State: {job.get('state')}")
    config = job.get("config") or {}
    if config:
        print(f"  Completed retention: {config.get('prune_completed_after_seconds')}s")
        print(f"  Failed retention:    {config.get('prune_failed_after_seconds')}s")
        print(f"  Delete missing rows: {config.get('delete_missing_rows')}")
        print(f"  Prune limit:         {config.get('prune_limit')}")
    if result.get("removed_duplicate_job_ids"):
        print(f"  Removed duplicates:  {', '.join(result['removed_duplicate_job_ids'])}")
    return 0


def _print_remove():
    result = _receipts_api(action="remove_maintenance")
    if result.get("error"):
        print(color(f"Failed to remove maintenance job: {result['error']}", Colors.RED))
        return 1

    deleted = result.get("deleted_count", 0)
    if deleted == 0:
        print(color("No execution receipt maintenance job was installed.", Colors.DIM))
        return 0

    print(color("Removed execution receipt maintenance job(s).", Colors.GREEN))
    for job_id in result.get("deleted_job_ids") or []:
        print(f"  - {job_id}")
    return 0


def receipts_command(args):
    subcmd = getattr(args, "receipts_command", None)

    if subcmd is None or subcmd == "list":
        return _print_list(
            limit=getattr(args, "limit", 10),
            status=getattr(args, "status", None),
            parent_session_id=getattr(args, "parent_session_id", None),
            child_session_id=getattr(args, "child_session_id", None),
        )

    if subcmd == "reconcile":
        return _print_reconcile(delete_missing_rows=not getattr(args, "keep_missing_rows", False))

    if subcmd == "prune":
        return _print_prune(
            max_age_seconds=getattr(args, "max_age_seconds"),
            keep_failed=not getattr(args, "include_failed", False),
            limit=getattr(args, "limit", 100),
        )

    if subcmd == "status":
        return _print_maintenance_status()

    if subcmd == "install":
        return _print_install(
            schedule=getattr(args, "schedule", None),
            prune_completed_after_seconds=getattr(args, "prune_completed_after_seconds", None),
            prune_failed_after_seconds=getattr(args, "prune_failed_after_seconds", None),
            delete_missing_rows=not getattr(args, "keep_missing_rows", False),
            limit=getattr(args, "limit", None),
            model=getattr(args, "model", None),
            provider=getattr(args, "provider", None),
            base_url=getattr(args, "base_url", None),
        )

    if subcmd in {"remove", "rm", "delete"}:
        return _print_remove()

    print(f"Unknown receipts command: {subcmd}")
    print("Usage: hermes receipts [list|prune|reconcile|status|install|remove]")
    return 1


def _parse_slash_flags(tokens: list[str]) -> dict[str, Any] | None:
    opts: dict[str, Any] = {
        "limit": None,
        "status": None,
        "parent_session_id": None,
        "child_session_id": None,
        "max_age_seconds": None,
        "include_failed": False,
        "keep_missing_rows": False,
        "schedule": None,
        "prune_completed_after_seconds": None,
        "prune_failed_after_seconds": None,
        "model": None,
        "provider": None,
        "base_url": None,
        "positionals": [],
    }
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token == "--limit" and i + 1 < len(tokens):
            try:
                opts["limit"] = int(tokens[i + 1])
            except ValueError:
                print("(._.) --limit must be an integer")
                return None
            i += 2
        elif token == "--status" and i + 1 < len(tokens):
            opts["status"] = tokens[i + 1]
            i += 2
        elif token == "--parent-session-id" and i + 1 < len(tokens):
            opts["parent_session_id"] = tokens[i + 1]
            i += 2
        elif token == "--child-session-id" and i + 1 < len(tokens):
            opts["child_session_id"] = tokens[i + 1]
            i += 2
        elif token == "--schedule" and i + 1 < len(tokens):
            opts["schedule"] = tokens[i + 1]
            i += 2
        elif token == "--prune-completed-after-seconds" and i + 1 < len(tokens):
            try:
                opts["prune_completed_after_seconds"] = float(tokens[i + 1])
            except ValueError:
                print("(._.) --prune-completed-after-seconds must be a number")
                return None
            i += 2
        elif token == "--prune-failed-after-seconds" and i + 1 < len(tokens):
            try:
                opts["prune_failed_after_seconds"] = float(tokens[i + 1])
            except ValueError:
                print("(._.) --prune-failed-after-seconds must be a number")
                return None
            i += 2
        elif token == "--model" and i + 1 < len(tokens):
            opts["model"] = tokens[i + 1]
            i += 2
        elif token == "--provider" and i + 1 < len(tokens):
            opts["provider"] = tokens[i + 1]
            i += 2
        elif token == "--base-url" and i + 1 < len(tokens):
            opts["base_url"] = tokens[i + 1]
            i += 2
        elif token in {"--include-failed", "--prune-failed-now"}:
            opts["include_failed"] = True
            i += 1
        elif token == "--keep-missing-rows":
            opts["keep_missing_rows"] = True
            i += 1
        else:
            opts["positionals"].append(token)
            i += 1
    return opts


def handle_receipts_slash(cmd: str):
    tokens = shlex.split(cmd)
    if len(tokens) == 1:
        print()
        print("+" + "-" * 68 + "+")
        print("|" + " " * 19 + "(✦_✦) Execution Receipts" + " " * 22 + "|")
        print("+" + "-" * 68 + "+")
        print()
        print("  Commands:")
        print("    /receipts list [--limit 10] [--status completed|failed]")
        print("    /receipts reconcile [--keep-missing-rows]")
        print("    /receipts prune <max_age_seconds> [--limit 100] [--include-failed]")
        print("    /receipts status")
        print("    /receipts install [--schedule 'every 6h'] [--prune-completed-after-seconds 604800] [--prune-failed-after-seconds 2592000]")
        print("    /receipts remove")
        print()
        _print_list(limit=10)
        print()
        _print_maintenance_status()
        return

    subcommand = tokens[1].lower()
    opts = _parse_slash_flags(tokens[2:])
    if opts is None:
        return

    if subcommand == "list":
        _print_list(
            limit=opts["limit"] or 10,
            status=opts["status"],
            parent_session_id=opts["parent_session_id"],
            child_session_id=opts["child_session_id"],
        )
        return

    if subcommand == "reconcile":
        _print_reconcile(delete_missing_rows=not opts["keep_missing_rows"])
        return

    if subcommand == "prune":
        if not opts["positionals"]:
            print("(._.) Usage: /receipts prune <max_age_seconds> [--limit 100] [--include-failed]")
            return
        try:
            max_age_seconds = float(opts["positionals"][0])
        except ValueError:
            print("(._.) max_age_seconds must be a number")
            return
        _print_prune(max_age_seconds=max_age_seconds, keep_failed=not opts["include_failed"], limit=opts["limit"] or 100)
        return

    if subcommand == "status":
        _print_maintenance_status()
        return

    if subcommand == "install":
        _print_install(
            schedule=opts["schedule"],
            prune_completed_after_seconds=opts["prune_completed_after_seconds"],
            prune_failed_after_seconds=opts["prune_failed_after_seconds"],
            delete_missing_rows=not opts["keep_missing_rows"],
            limit=opts["limit"],
            model=opts["model"],
            provider=opts["provider"],
            base_url=opts["base_url"],
        )
        return

    if subcommand in {"remove", "rm", "delete"}:
        _print_remove()
        return

    print(f"(._.) Unknown receipts command: {subcommand}")
    print("  Available: list, reconcile, prune, status, install, remove")


def capture_receipts_slash_output(cmd: str) -> str:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        handle_receipts_slash(cmd)
    return buffer.getvalue()
