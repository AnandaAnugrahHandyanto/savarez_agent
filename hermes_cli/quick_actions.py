"""Telegram Quick Actions local control plane.

This module intentionally keeps promotion conservative: it reviews and marks
routing candidates, but it does not directly mutate Cortex, brain-sync, or
Kanban. Downstream workers can consume ``promotions.jsonl`` after a human or
operator explicitly promotes a captured candidate.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Callable, Iterable

from hermes_constants import get_hermes_home


QA_DIRNAME = "telegram_quick_actions"
ROUTING_CANDIDATES = "routing_candidates.jsonl"
PROMOTIONS = "promotions.jsonl"
DISCARDS = "discards.jsonl"
EXECUTIONS = "executions.jsonl"
WIKI_CANDIDATES = "wiki_candidates.jsonl"
KANBAN_CANDIDATES = "kanban_candidates.jsonl"
ACTIVE_ACTIONS = "active_actions.json"


def _qa_dir(home: Path | None = None) -> Path:
    root = home or get_hermes_home()
    path = root / QA_DIRNAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def _jsonl_path(name: str, home: Path | None = None) -> Path:
    return _qa_dir(home) / name


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            item = {"_invalid": True, "_line_no": line_no, "raw": line}
        if isinstance(item, dict):
            item.setdefault("_line_no", line_no)
            rows.append(item)
    return rows


def _append_jsonl(path: Path, item: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")


def _write_jsonl_atomic(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    tmp.replace(path)


def _candidate_id(row: dict[str, Any]) -> str:
    return str(row.get("id") or row.get("token") or row.get("_line_no") or "")


def _shorten(text: Any, limit: int = 96) -> str:
    value = str(text or "").replace("\n", " ").strip()
    value = " ".join(value.split())
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)].rstrip() + "…"


def _target_alias(target: str) -> str:
    aliases = {
        "cortex_memory": "memory",
        "cortex_todo": "todo",
        "brain_sync_wiki_candidate": "wiki",
        "kanban_candidate": "kanban",
    }
    return aliases.get(target, target)


def _candidate_targets(row: dict[str, Any]) -> list[str]:
    targets = [str(t) for t in (row.get("recommended_targets") or []) if t]
    promoted_to = row.get("promoted_to")
    if promoted_to and not targets:
        targets = [str(promoted_to)]
    return [_target_alias(t) for t in targets]


def _candidate_time(row: dict[str, Any]) -> str:
    captured = str(row.get("captured_at") or row.get("promoted_at") or row.get("discarded_at") or "")
    if not captured:
        return "time unknown"
    try:
        dt = datetime.fromisoformat(captured.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%m-%d %H:%MZ")
    except Exception:
        return captured[:16]


def _primary_target(row: dict[str, Any]) -> str:
    return (_candidate_targets(row) or ["memory"])[0]


def _target_for_command(target_alias: str) -> str:
    return {
        "memory": "cortex_memory",
        "todo": "cortex_todo",
        "wiki": "brain_sync_wiki_candidate",
        "kanban": "kanban_candidate",
    }.get(target_alias, target_alias)


def format_candidate_card(row: dict[str, Any], *, index: int | None = None, verbose: bool = False) -> str:
    """Format one routing candidate for compact chat surfaces.

    Design goal: a Telegram review card should be glanceable in under two
    seconds.  Default mode is intentionally two lines per candidate; verbose
    mode is the escape hatch for terminal review.
    """
    cid = _candidate_id(row)
    status = str(row.get("status") or "candidate")
    action = str(row.get("action") or "?")
    idx = f"{index}. " if index is not None else ""
    title = _shorten(row.get("title") or row.get("content") or "(untitled)", 86)
    primary = _primary_target(row)
    captured = _candidate_time(row)
    lines = [
        f"{idx}**{action}** -> **{primary}** · `{cid}`",
        f"{title} · {captured}",
    ]
    if verbose:
        targets = ", ".join(_candidate_targets(row)) or "no target"
        lines.append(f"state: {status} · targets: {targets}")
        content = _shorten(row.get("content") or "", 240)
        if content and content != title:
            lines.append(f"content: {content}")
        if status == "candidate":
            target_for_command = _target_for_command(primary)
            lines.append(f"commands: `/qa promote {cid} --to {target_for_command}` · `/qa discard {cid}`")
        else:
            lines.append(f"details: `/qa show {cid}`")
    return "\n".join(lines)


def format_candidate_digest(
    rows: list[dict[str, Any]],
    *,
    status: str,
    limit: int,
    verbose: bool = False,
    notice: str | None = None,
) -> str:
    if not rows:
        base = f"**Quick Actions**\nQueue is clear for status `{status}`."
        return base + (f"\n\nLast action: {notice}" if notice else "")
    counts: dict[str, int] = {}
    target_counts: dict[str, int] = {}
    for row in rows:
        key = str(row.get("action") or "?")
        counts[key] = counts.get(key, 0) + 1
        target = _primary_target(row)
        target_counts[target] = target_counts.get(target, 0) + 1
    mix = ", ".join(f"{key} {value}" for key, value in sorted(counts.items()))
    target_mix = ", ".join(f"{key} {value}" for key, value in sorted(target_counts.items()))
    lines = [
        "**Quick Actions**",
        f"{len(rows)} pending · {mix} · targets: {target_mix}",
    ]
    if status == "candidate":
        lines.append("Tap a button to promote the suggested target or discard. Use `-v` for commands.")
    else:
        lines.append(f"status: `{status}` · use `/qa show <id>` for full JSON")
    if notice:
        lines.append(f"Last action: {notice}")
    lines.append("")
    for idx, row in enumerate(rows, start=1):
        if idx > 1:
            lines.append("")
        lines.append(format_candidate_card(row, index=idx, verbose=verbose))
    lines.extend([
        "",
        f"Next: `/qa list --limit {min(max(limit * 2, 5), 25)}` · Detail: `/qa show <id>`",
    ])
    return "\n".join(lines)


def _find_candidate(identifier: str, *, home: Path | None = None) -> tuple[int, dict[str, Any], list[dict[str, Any]]]:
    rows = _read_jsonl(_jsonl_path(ROUTING_CANDIDATES, home))
    ident = str(identifier)
    for idx, row in enumerate(rows):
        if _candidate_id(row) == ident or str(row.get("token") or "") == ident or str(row.get("_line_no") or "") == ident:
            return idx, row, rows
    raise SystemExit(f"No Quick Action routing candidate found for id/token/line: {identifier}")


def _format_candidate(row: dict[str, Any], *, verbose: bool = False) -> str:
    cid = _candidate_id(row)
    action = row.get("action", "?")
    status = row.get("status", "candidate")
    title = str(row.get("title") or "(untitled)").replace("\n", " ")
    targets = ",".join(str(t) for t in (row.get("recommended_targets") or [])) or "-"
    captured_at = row.get("captured_at") or "-"
    line = f"{cid}\t{status}\t{action}\t{targets}\t{captured_at}\t{title}"
    if not verbose:
        return line
    source_ref = ""
    todo = row.get("todo") if isinstance(row.get("todo"), dict) else {}
    if todo:
        source_ref = str(todo.get("source_ref") or "")
    elif row.get("chat_id") or row.get("message_id"):
        source_ref = f"telegram:{row.get('chat_id') or ''}:{row.get('thread_id') or ''}:{row.get('message_id') or ''}"
    content = str(row.get("content") or "")
    if len(content) > 500:
        content = content[:497].rstrip() + "…"
    return "\n".join([
        line,
        f"  source: {source_ref or '-'}",
        f"  content: {content}",
    ])


def list_candidates(*, status: str = "candidate", limit: int = 20, home: Path | None = None, verbose: bool = False) -> list[dict[str, Any]]:
    rows = _read_jsonl(_jsonl_path(ROUTING_CANDIDATES, home))
    if status != "all":
        rows = [r for r in rows if str(r.get("status") or "candidate") == status]
    return rows[-limit:] if limit > 0 else rows


def promote_candidate(identifier: str, *, target: str, home: Path | None = None, actor: str = "cli") -> dict[str, Any]:
    idx, row, rows = _find_candidate(identifier, home=home)
    now = datetime.now(timezone.utc).isoformat()
    updated = dict(row)
    updated["status"] = "promoted"
    updated["promoted_to"] = target
    updated["promoted_at"] = now
    updated["promoted_by"] = actor
    rows[idx] = updated
    _write_jsonl_atomic(_jsonl_path(ROUTING_CANDIDATES, home), rows)
    event = {
        "candidate_id": _candidate_id(row),
        "token": row.get("token"),
        "target": target,
        "title": row.get("title"),
        "action": row.get("action"),
        "content": row.get("content"),
        "source": row.get("source") or {},
        "promoted_at": now,
        "promoted_by": actor,
        "status": "pending_execution",
    }
    _append_jsonl(_jsonl_path(PROMOTIONS, home), event)
    return updated


def discard_candidate(identifier: str, *, reason: str = "", home: Path | None = None, actor: str = "cli") -> dict[str, Any]:
    idx, row, rows = _find_candidate(identifier, home=home)
    now = datetime.now(timezone.utc).isoformat()
    updated = dict(row)
    updated["status"] = "discarded"
    updated["discarded_at"] = now
    updated["discarded_by"] = actor
    if reason:
        updated["discard_reason"] = reason
    rows[idx] = updated
    _write_jsonl_atomic(_jsonl_path(ROUTING_CANDIDATES, home), rows)
    _append_jsonl(_jsonl_path(DISCARDS, home), {
        "candidate_id": _candidate_id(row),
        "token": row.get("token"),
        "title": row.get("title"),
        "reason": reason,
        "discarded_at": now,
        "discarded_by": actor,
    })
    return updated


def _promotion_key(row: dict[str, Any]) -> str:
    return f"{row.get('candidate_id') or row.get('token') or ''}:{row.get('target') or ''}".strip(":")


def _find_candidate_for_promotion(promotion: dict[str, Any], *, home: Path | None = None) -> dict[str, Any]:
    identifiers = [promotion.get("candidate_id"), promotion.get("token")]
    for ident in identifiers:
        if not ident:
            continue
        try:
            _, row, _ = _find_candidate(str(ident), home=home)
            return row
        except SystemExit:
            continue
    return dict(promotion)


def _cmem_memory_args(candidate: dict[str, Any], promotion: dict[str, Any]) -> list[str]:
    memory = candidate.get("memory") if isinstance(candidate.get("memory"), dict) else {}
    return [
        "cmem",
        "remember",
        "--type",
        str(memory.get("type") or "context"),
        "--title",
        str(candidate.get("title") or promotion.get("title") or "Telegram Quick Action memory"),
        "--content",
        str(candidate.get("content") or promotion.get("content") or ""),
        "--project",
        str(memory.get("project") or "hermes"),
    ]


def _cmem_todo_args(candidate: dict[str, Any], promotion: dict[str, Any]) -> list[str]:
    todo = candidate.get("todo") if isinstance(candidate.get("todo"), dict) else {}
    return [
        "cmem",
        "todo-add",
        "--title",
        str(candidate.get("title") or promotion.get("title") or "Telegram Quick Action todo"),
        "--content",
        str(candidate.get("content") or promotion.get("content") or ""),
        "--priority",
        str(todo.get("priority") or "P2"),
        "--category",
        str(todo.get("category") or "dev"),
        "--project",
        str(todo.get("project") or "hermes"),
        "--source-type",
        str(todo.get("source_type") or "manual"),
        "--source-ref",
        str(todo.get("source_ref") or f"quick-action:{promotion.get('candidate_id') or promotion.get('token') or ''}"),
    ]


def _run_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, text=True, capture_output=True, timeout=30, check=False)


def _execute_one_promotion(
    promotion: dict[str, Any],
    *,
    candidate: dict[str, Any],
    home: Path | None = None,
    dry_run: bool = False,
    runner: Callable[[list[str]], subprocess.CompletedProcess[str]] | None = None,
) -> dict[str, Any]:
    target = str(promotion.get("target") or "")
    now = datetime.now(timezone.utc).isoformat()
    base = {
        "candidate_id": promotion.get("candidate_id"),
        "token": promotion.get("token"),
        "target": target,
        "executed_at": now,
        "dry_run": dry_run,
    }

    if target in {"cortex", "cortex_memory"}:
        args = _cmem_memory_args(candidate, promotion)
        base["operation"] = "cmem_remember"
        base["command"] = args
        if dry_run:
            return {**base, "status": "dry_run"}
        proc = (runner or _run_command)(args)
        return {
            **base,
            "status": "executed" if proc.returncode == 0 else "failed",
            "returncode": proc.returncode,
            "stdout": (proc.stdout or "").strip()[-2000:],
            "stderr": (proc.stderr or "").strip()[-2000:],
        }

    if target in {"cortex_todo"}:
        args = _cmem_todo_args(candidate, promotion)
        base["operation"] = "cmem_todo_add"
        base["command"] = args
        if dry_run:
            return {**base, "status": "dry_run"}
        proc = (runner or _run_command)(args)
        return {
            **base,
            "status": "executed" if proc.returncode == 0 else "failed",
            "returncode": proc.returncode,
            "stdout": (proc.stdout or "").strip()[-2000:],
            "stderr": (proc.stderr or "").strip()[-2000:],
        }

    if target in {"wiki", "brain_sync_wiki_candidate"}:
        record = {**base, "operation": "wiki_candidate", "candidate": candidate, "promotion": promotion}
        if dry_run:
            return {**record, "status": "dry_run"}
        _append_jsonl(_jsonl_path(WIKI_CANDIDATES, home), record)
        return {**record, "status": "executed"}

    if target in {"kanban", "kanban_candidate"}:
        record = {**base, "operation": "kanban_candidate", "candidate": candidate, "promotion": promotion}
        if dry_run:
            return {**record, "status": "dry_run"}
        _append_jsonl(_jsonl_path(KANBAN_CANDIDATES, home), record)
        return {**record, "status": "executed"}

    return {**base, "status": "failed", "error": f"Unsupported target: {target}"}


def execute_promotions(
    *,
    home: Path | None = None,
    limit: int = 20,
    target: str | None = None,
    dry_run: bool = False,
    runner: Callable[[list[str]], subprocess.CompletedProcess[str]] | None = None,
) -> dict[str, Any]:
    """Execute pending promoted Quick Actions with an idempotent ledger.

    Cortex targets call ``cmem``; wiki/kanban targets stay candidate-first by
    appending local JSONL candidate ledgers.  ``executions.jsonl`` is the
    idempotency source of truth, so reruns skip successful prior executions.
    """
    promotions_path = _jsonl_path(PROMOTIONS, home)
    promotions = _read_jsonl(promotions_path)
    executions_path = _jsonl_path(EXECUTIONS, home)
    executions = _read_jsonl(executions_path)
    done_keys = {
        _promotion_key(e)
        for e in executions
        if str(e.get("status") or "") == "executed" and _promotion_key(e)
    }
    selected: list[tuple[int, dict[str, Any]]] = []
    for idx, promotion in enumerate(promotions):
        if str(promotion.get("status") or "") != "pending_execution":
            continue
        if target and str(promotion.get("target") or "") != target:
            continue
        key = _promotion_key(promotion)
        if key and key in done_keys:
            continue
        selected.append((idx, promotion))
        if limit > 0 and len(selected) >= limit:
            break

    results: list[dict[str, Any]] = []
    for idx, promotion in selected:
        candidate = _find_candidate_for_promotion(promotion, home=home)
        result = _execute_one_promotion(
            promotion,
            candidate=candidate,
            home=home,
            dry_run=dry_run,
            runner=runner,
        )
        results.append(result)
        if not dry_run:
            _append_jsonl(executions_path, result)
            if result.get("status") == "executed":
                promotions[idx] = {**promotion, "status": "executed", "executed_at": result["executed_at"]}
            else:
                # Keep transient failures retryable while still recording the
                # attempt in executions.jsonl for audit/debugging.
                promotions[idx] = {
                    **promotion,
                    "status": "pending_execution",
                    "last_execution_status": result.get("status"),
                    "last_executed_at": result["executed_at"],
                }

    if results and not dry_run:
        _write_jsonl_atomic(promotions_path, promotions)
    return {
        "selected": len(selected),
        "executed": sum(1 for r in results if r.get("status") == "executed"),
        "dry_run": sum(1 for r in results if r.get("status") == "dry_run"),
        "failed": sum(1 for r in results if r.get("status") == "failed"),
        "skipped_done": len(done_keys),
        "results": results,
    }

def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def prune_active_actions(*, older_than_days: int = 14, drop_undated: bool = False, home: Path | None = None) -> dict[str, int]:
    path = _qa_dir(home) / ACTIVE_ACTIONS
    if not path.exists():
        return {"kept": 0, "removed": 0, "total": 0}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"Failed to read {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"Expected {path} to contain a JSON object")

    cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
    kept: dict[str, Any] = {}
    removed = 0
    for token, payload in data.items():
        if not isinstance(payload, dict):
            removed += 1
            continue
        created = _parse_dt(payload.get("created_at") or payload.get("recorded_at") or payload.get("captured_at"))
        if created is None:
            if drop_undated:
                removed += 1
                continue
            kept[token] = payload
            continue
        if created < cutoff:
            removed += 1
            continue
        kept[token] = payload

    if removed:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(kept, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
    return {"kept": len(kept), "removed": removed, "total": len(data)}


def cli_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hermes qa", description="Review Telegram Quick Action routing candidates")
    sub = parser.add_subparsers(dest="action", required=True)

    p_list = sub.add_parser("list", aliases=["ls"], help="List routing candidates")
    p_list.add_argument("--status", default="candidate", choices=["candidate", "promoted", "discarded", "all"])
    p_list.add_argument("--limit", type=int, default=20)
    p_list.add_argument("--verbose", "-v", action="store_true")

    p_show = sub.add_parser("show", help="Show one candidate as JSON")
    p_show.add_argument("id")

    p_promote = sub.add_parser("promote", help="Mark a candidate promoted and append promotions.jsonl")
    p_promote.add_argument("id")
    p_promote.add_argument("--to", required=True, choices=["cortex", "wiki", "kanban", "cortex_memory", "cortex_todo", "brain_sync_wiki_candidate", "kanban_candidate"])

    p_execute = sub.add_parser("execute", help="Execute pending promotions into Cortex or local candidate ledgers")
    p_execute.add_argument("--limit", type=int, default=20)
    p_execute.add_argument("--target", choices=["cortex", "wiki", "kanban", "cortex_memory", "cortex_todo", "brain_sync_wiki_candidate", "kanban_candidate"])
    p_execute.add_argument("--dry-run", action="store_true")

    p_discard = sub.add_parser("discard", help="Discard a routing candidate")
    p_discard.add_argument("id")
    p_discard.add_argument("--reason", default="")

    p_prune = sub.add_parser("prune-active", help="Prune stale active button payloads")
    p_prune.add_argument("--older-than-days", type=int, default=14)
    p_prune.add_argument("--drop-undated", action="store_true", help="Also remove legacy active payloads without timestamps")

    args = parser.parse_args(argv)
    if args.action in {"list", "ls"}:
        rows = list_candidates(status=args.status, limit=args.limit, verbose=args.verbose)
        print(format_candidate_digest(rows, status=args.status, limit=args.limit, verbose=args.verbose))
        return 0
    if args.action == "show":
        _, row, _ = _find_candidate(args.id)
        print(json.dumps(row, ensure_ascii=False, indent=2))
        return 0
    if args.action == "promote":
        row = promote_candidate(args.id, target=args.to)
        print(f"Promoted {_candidate_id(row)} -> {args.to}")
        return 0
    if args.action == "execute":
        result = execute_promotions(limit=args.limit, target=args.target, dry_run=args.dry_run)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.action == "discard":
        row = discard_candidate(args.id, reason=args.reason)
        print(f"Discarded {_candidate_id(row)}")
        return 0
    if args.action == "prune-active":
        result = prune_active_actions(older_than_days=args.older_than_days, drop_undated=args.drop_undated)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    parser.print_help()
    return 1


def register_cli(parent: argparse.ArgumentParser) -> None:
    parent.set_defaults(func=lambda a: sys.exit(cli_main([a.qa_action] + getattr(a, "qa_args", []))))
    parent.add_argument("qa_action", nargs="?", help="list/show/promote/execute/discard/prune-active")
    parent.add_argument("qa_args", nargs=argparse.REMAINDER)


if __name__ == "__main__":
    raise SystemExit(cli_main())
