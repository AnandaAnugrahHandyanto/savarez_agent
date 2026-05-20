"""Read-only parked-state triage helper for GitHub-backed Kanban tasks.

The public CLI entrypoint is intentionally neutral and no-side-effect:

    kanban-parked-triage diagnose --issue 156 --task-id t_...

It reads GitHub/Kanban evidence, classifies the current parked state with
rule-based signals, and renders either JSON or Markdown.  It does not mutate
GitHub labels, Kanban rows, Telegram traces, profile runtime, or services.
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


RESULT_SCHEMA = {
    "$id": "kanban-parked-triage-result:v1",
    "schema": "kanban-parked-triage-result-schema:v1",
    "required_fields": [
        "schema",
        "generated_at",
        "issue",
        "task_id",
        "board",
        "current_status",
        "is_current_block",
        "parked_type",
        "confidence",
        "evidence",
        "recommendation",
        "warnings",
        "side_effects",
    ],
    "parked_type_values": [
        "review-required-with-child",
        "review-required-no-child",
        "returned-awaiting-rework",
        "needs-evidence",
        "needs-human-decision",
        "budget-exhausted-with-artifact",
        "infra-missing",
        "stale-or-contradictory-trace-intent",
        "historical-only-not-current-block",
    ],
    "evidence_source_values": [
        "kanban.task",
        "kanban.child",
        "kanban.run",
        "kanban.comment",
        "kanban.event",
        "github.issue",
        "github.pr",
        "github.comment",
    ],
}

RUNBOOK: dict[str, dict[str, Any]] = {
    "review-required-with-child": {
        "summary": "父任务停在 review-required，但 review/audit child 已存在。",
        "next_action": "恢复/完成父执行任务，让已存在的 review child 通过依赖晋级接手。",
        "automation_level": "可自动推进",
        "owner": "orchestrator/dispatcher",
        "allowed_actions": [
            "核对 child task 与父任务 handoff 是否匹配",
            "若实现证据齐全，complete 父任务并促发 review child",
            "在 Kanban/GitHub 留一条恢复理由",
        ],
        "forbidden_actions": ["重跑执行者", "让执行者继续自审", "新建重复 review child"],
    },
    "review-required-no-child": {
        "summary": "执行证据显示需要审计，但没有可接手的 review child。",
        "next_action": "创建/派发 review child；父任务可保持 handoff block 或由编排方完成交棒。",
        "automation_level": "需窄续跑",
        "owner": "orchestrator",
        "allowed_actions": [
            "基于现有 PR/commit/tests 创建 review task",
            "把验收标准、非目标、head SHA、测试证据写入 review task",
        ],
        "forbidden_actions": ["让执行者兼任审计", "重新实现全任务"],
    },
    "returned-awaiting-rework": {
        "summary": "审计已退回并给出 blocking findings，当前等待返工链路。",
        "next_action": "创建或推进 rework + re-review 链，返工只处理 blocking findings delta。",
        "automation_level": "可自动推进",
        "owner": "orchestrator/executor",
        "allowed_actions": [
            "提取 return packet / blocking findings",
            "派发 rework task 给原执行者或正确 specialist",
            "预建 re-review task，parent 指向 rework task",
        ],
        "forbidden_actions": ["长期停在 reviewer blocked", "复审全量重做", "忽略退回项直接关闭"],
    },
    "needs-evidence": {
        "summary": "artifact/PR/commit/test/trace/label 等证据缺失或存在待补占位。",
        "next_action": "建窄补证任务或 unblock 一次窄续跑，只补缺失证据。",
        "automation_level": "需窄续跑",
        "owner": "original executor or evidence owner",
        "allowed_actions": [
            "列出缺失证据项",
            "只补 PR URL、head SHA、测试输出、trace receipt、label readback 等缺口",
        ],
        "forbidden_actions": ["重新实现全任务", "声称完成但不提供可回读证据"],
    },
    "needs-human-decision": {
        "summary": "缺产品、权限、风险或范围决策，不能由 worker 推断。",
        "next_action": "block 到唯一明确问题，等待人类拍板。",
        "automation_level": "需人类决策",
        "owner": "human/orchestrator",
        "allowed_actions": ["把缺口压成一句具体问题", "提供可选路径和风险差异"],
        "forbidden_actions": ["猜测决策", "绕过权限/风险边界", "用假完整方案硬推进"],
    },
    "budget-exhausted-with-artifact": {
        "summary": "预算耗尽但 PR/commit/tests 等 artifact 已存在。",
        "next_action": "窄续跑只做收尾账：GitHub comment、label、trace、kanban_complete。",
        "automation_level": "需窄续跑",
        "owner": "original executor/orchestrator",
        "allowed_actions": [
            "复用已有 artifact/head SHA/tests",
            "补齐交付评论、label readback、trace receipt、Kanban metadata",
        ],
        "forbidden_actions": ["原样重拉实现", "扩大自审范围", "在业务卡里修基础设施"],
    },
    "infra-missing": {
        "summary": "helper/profile/gateway/watcher/credential 等基础设施能力缺口。",
        "next_action": "保留业务证据并精确 block；另立基础设施 issue/task。",
        "automation_level": "需另立基础设施 issue",
        "owner": "ops/infrastructure owner",
        "allowed_actions": [
            "记录失败命令、idempotency key、receipt 路径和错误摘要",
            "业务任务不现场调试基础设施",
        ],
        "forbidden_actions": ["在业务卡内修 Hermes core/profile/gateway/watcher", "触碰凭据/OAuth 材料"],
    },
    "stale-or-contradictory-trace-intent": {
        "summary": "trace intent 与源任务/PR/审计证据矛盾或已过期。",
        "next_action": "阻止发送该 trace，留下审计说明并等待编排方修正 intent。",
        "automation_level": "需人类决策",
        "owner": "trace intent owner/orchestrator",
        "allowed_actions": [
            "核对 source task、event、intent_key 与当前 GitHub/Kanban 证据",
            "在 trace-intent 卡写明矛盾证据",
        ],
        "forbidden_actions": ["发送虚假生命周期 trace", "用旧 intent 覆盖当前已批准/已关闭状态"],
    },
    "historical-only-not-current-block": {
        "summary": "blocked/parked 只是历史样本；当前任务或 issue 已不处于阻塞态。",
        "next_action": "不要重拉执行；仅把历史停车作为耗时样本或复盘输入。",
        "automation_level": "无需推进",
        "owner": "none",
        "allowed_actions": ["引用历史证据做复盘", "确认当前 terminal 状态可回读"],
        "forbidden_actions": ["把历史 blocked 当成当前 blocker", "重复创建返工/审计任务"],
    },
}

_SECRET_REDACTIONS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bgh[opsu]_[A-Za-z0-9_]{8,}\b"), "<redacted-github-token>"),
    (re.compile(r"(?i)\b(token|api[_-]?key|secret|password)\s*[:=]\s*[^\s,;]+"), r"\1=<redacted>"),
    (re.compile(r"\btelegram:-?\d+(?::\d+)?\b"), "telegram:<redacted-raw-locator>"),
)

_TRACE_INTENT_RE = re.compile(r"\[(?:kanban-)?trace-intent:v1\]|kanban-trace-intent:v1", re.I)
_PR_URL_RE = re.compile(r"https://github\.com/[^\s)]+/[^\s)]+/pull/(\d+)", re.I)
_PR_REF_RE = re.compile(r"\b(?:PR|pull request)\s*#?(\d+)\b", re.I)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _redact(value: Any) -> str:
    text = "" if value is None else str(value)
    for pattern, repl in _SECRET_REDACTIONS:
        text = pattern.sub(repl, text)
    return text


def _compact(text: Any, limit: int = 220) -> str:
    redacted = " ".join(_redact(text).split())
    if len(redacted) <= limit:
        return redacted
    return redacted[: limit - 1].rstrip() + "…"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, str):
        return _redact(value)
    return value


def _row_to_dict(row: sqlite3.Row | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(row, sqlite3.Row):
        return {key: row[key] for key in row.keys()}
    return dict(row)


def _maybe_json(value: Any) -> Any:
    if not isinstance(value, str) or not value.strip():
        return value
    try:
        return json.loads(value)
    except Exception:
        return value


def _lower_text(snapshot: Mapping[str, Any]) -> str:
    chunks: list[str] = []

    def walk(value: Any) -> None:
        if value is None:
            return
        if isinstance(value, str):
            chunks.append(value)
        elif isinstance(value, Mapping):
            for item in value.values():
                walk(item)
        elif isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray)):
            for item in value:
                walk(item)
        else:
            chunks.append(str(value))

    walk(snapshot)
    return "\n".join(chunks).lower()


def _task(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    return _as_dict(snapshot.get("task"))


def _issue(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    return _as_dict(snapshot.get("issue"))


def _current_status(snapshot: Mapping[str, Any]) -> str:
    task_status = str(_task(snapshot).get("status") or "").strip()
    if task_status:
        return task_status
    issue_state = str(_issue(snapshot).get("state") or "").strip()
    return issue_state or "unknown"


def _is_terminal(snapshot: Mapping[str, Any]) -> bool:
    task_status = str(_task(snapshot).get("status") or "").lower()
    issue_state = str(_issue(snapshot).get("state") or "").lower()
    labels = {str(label).lower() for label in _as_list(_issue(snapshot).get("labels"))}
    return task_status in {"done", "archived"} or issue_state == "closed" or "已关闭" in labels


def _has_current_block(snapshot: Mapping[str, Any]) -> bool:
    if _is_terminal(snapshot):
        return False
    task_status = str(_task(snapshot).get("status") or "").lower()
    labels = {str(label).lower() for label in _as_list(_issue(snapshot).get("labels"))}
    text = _lower_text(snapshot)
    if task_status == "blocked":
        return True
    if task_status in {"running", "ready", "todo", "pending", "claimed", "in_progress", "in-progress"}:
        return False
    if labels & {"已退回", "待补证", "已阻塞", "阻塞", "blocked"}:
        return True
    return any(marker in text for marker in ("review-required", "needs-evidence", "needs-human-decision", "infra-missing"))


def _has_historical_block(snapshot: Mapping[str, Any]) -> bool:
    text = _lower_text(snapshot)
    if "blocked" in text or "阻塞" in text or "停车" in text:
        return True
    return any(str(event.get("kind", "")).lower() == "blocked" for event in _as_list(snapshot.get("events")) if isinstance(event, Mapping))


def _has_review_child(snapshot: Mapping[str, Any]) -> bool:
    for child in _as_list(snapshot.get("children")):
        if not isinstance(child, Mapping):
            continue
        fields = " ".join(
            str(child.get(key) or "") for key in ("id", "title", "body", "assignee", "current_step_key")
        ).lower()
        if any(marker in fields for marker in ("review", "audit", "审计", "审核", "复审", "yushidafu")):
            return True
    return False


def _has_artifact(snapshot: Mapping[str, Any]) -> bool:
    text = _lower_text(snapshot)
    if _as_list(snapshot.get("prs")):
        return True
    artifact_markers = (
        "pull/",
        "pr ",
        "pr#",
        "pr #",
        "head_sha",
        "head sha",
        "commit",
        "changed_files",
        "tests_run",
        "tests pass",
        "pytest",
        "artifact_url",
    )
    return any(marker in text for marker in artifact_markers)


def _has_placeholder_or_missing_evidence(snapshot: Mapping[str, Any]) -> bool:
    text = _lower_text(snapshot)
    placeholders = (
        "待补",
        "tbd",
        "待 pr",
        "pr url: 待补",
        "missing evidence",
        "needs-evidence",
        "tests: todo",
        "trace receipt: todo",
        "todo；",
        "todo;",
    )
    if any(marker in text for marker in placeholders):
        return True
    task_status = str(_task(snapshot).get("status") or "").lower()
    if task_status == "blocked" and not _has_artifact(snapshot):
        return True
    return False


def _contains_any(snapshot: Mapping[str, Any], markers: Sequence[str]) -> bool:
    text = _lower_text(snapshot)
    return any(marker.lower() in text for marker in markers)


def _is_stale_or_contradictory_trace_intent(snapshot: Mapping[str, Any]) -> bool:
    text = _lower_text(snapshot)
    has_intent = bool(_TRACE_INTENT_RE.search(text)) or "trace intent" in text
    if not has_intent:
        return False
    contradictory_markers = (
        "contradict",
        "矛盾",
        "approved",
        "审核通过",
        "merged",
        "已合并",
        "closed",
        "已关闭",
        "source task conclusion is approved",
    )
    return any(marker in text for marker in contradictory_markers)


def _classification(snapshot: Mapping[str, Any]) -> tuple[str, str]:
    """Return ``(parked_type, confidence)`` using deterministic rule order."""
    if _is_stale_or_contradictory_trace_intent(snapshot):
        return "stale-or-contradictory-trace-intent", "high"
    if not _has_current_block(snapshot):
        if _has_historical_block(snapshot):
            return "historical-only-not-current-block", "high"
        return "historical-only-not-current-block", "medium"
    if _contains_any(snapshot, ("infra-missing", "trace-missing", "github-permission-missing", "helper missing", "helper 缺", "platform 'telegram' is not configured", "spawn_failed")):
        return "infra-missing", "high"
    if _contains_any(snapshot, ("needs-human-decision", "human decision", "人类决策", "拍板", "缺产品", "权限决策", "风险决策")):
        return "needs-human-decision", "high"
    if _contains_any(snapshot, ("returned-awaiting-rework", "blocking_findings", "blocking findings", "审核退回", "已退回", "退回", "returned")):
        return "returned-awaiting-rework", "high"
    if _has_placeholder_or_missing_evidence(snapshot):
        return "needs-evidence", "high"
    if _contains_any(snapshot, ("budget-exhausted-with-artifact", "iteration budget exhausted", "budget exhausted", "预算耗尽")) and _has_artifact(snapshot):
        return "budget-exhausted-with-artifact", "high"
    if _contains_any(snapshot, ("review-required", "review required", "需审计", "需要审计")):
        if _has_review_child(snapshot):
            return "review-required-with-child", "high"
        return "review-required-no-child", "medium" if _has_artifact(snapshot) else "low"
    if _is_terminal(snapshot):
        return "historical-only-not-current-block", "medium"
    return "needs-human-decision", "low"


def _source_items(snapshot: Mapping[str, Any]) -> list[tuple[str, Any]]:
    items: list[tuple[str, Any]] = []
    task = _task(snapshot)
    issue = _issue(snapshot)
    if task:
        items.append(("kanban.task", task))
    if issue:
        items.append(("github.issue", issue))
    for pr in _as_list(snapshot.get("prs")):
        items.append(("github.pr", pr))
    for child in _as_list(snapshot.get("children")):
        items.append(("kanban.child", child))
    for run in _as_list(snapshot.get("runs")):
        items.append(("kanban.run", run))
    for comment in _as_list(snapshot.get("comments")):
        items.append(("kanban.comment", comment))
    for comment in _as_list(issue.get("comments")):
        items.append(("github.comment", comment))
    for event in _as_list(snapshot.get("events")):
        items.append(("kanban.event", event))
    return items


def _build_evidence(snapshot: Mapping[str, Any], parked_type: str) -> list[dict[str, str]]:
    markers_by_type = {
        "review-required-with-child": ("review", "审计", "审核", "child", "review-required"),
        "review-required-no-child": ("review-required", "pr", "head_sha", "tests"),
        "returned-awaiting-rework": ("退回", "returned", "blocking"),
        "needs-evidence": ("待补", "todo", "tbd", "missing", "needs-evidence"),
        "needs-human-decision": ("needs-human", "人类", "拍板", "决策"),
        "budget-exhausted-with-artifact": ("budget", "预算", "pr", "head_sha", "tests"),
        "infra-missing": ("infra", "trace-missing", "helper", "gateway", "telegram", "spawn_failed"),
        "stale-or-contradictory-trace-intent": ("trace", "intent", "矛盾", "approved", "merged"),
        "historical-only-not-current-block": ("done", "closed", "blocked", "历史", "已关闭"),
    }
    markers = markers_by_type.get(parked_type, ())
    evidence: list[dict[str, str]] = []
    for source, item in _source_items(snapshot):
        text = json.dumps(_json_safe(item), ensure_ascii=False, sort_keys=True)
        lowered = text.lower()
        if any(marker.lower() in lowered for marker in markers):
            evidence.append({"source": source, "summary": _compact(text)})
        if len(evidence) >= 8:
            break
    if evidence:
        return evidence
    for source, item in _source_items(snapshot)[:4]:
        evidence.append({"source": source, "summary": _compact(json.dumps(_json_safe(item), ensure_ascii=False, sort_keys=True))})
    return evidence


def diagnose_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Classify a supplied GitHub/Kanban evidence snapshot.

    This pure function is the testable core.  It reads no files, runs no
    commands, and has no side effects.
    """
    parked_type, confidence = _classification(snapshot)
    runbook = RUNBOOK[parked_type]
    issue = _issue(snapshot)
    task = _task(snapshot)
    result = {
        "schema": "kanban-parked-triage-result:v1",
        "generated_at": _now_iso(),
        "issue": {
            "number": issue.get("number"),
            "url": _redact(issue.get("url")),
            "state": issue.get("state"),
            "labels": _json_safe(issue.get("labels", [])),
            "title": _redact(issue.get("title")),
        },
        "task_id": task.get("id"),
        "board": snapshot.get("board"),
        "current_status": _current_status(snapshot),
        "is_current_block": _has_current_block(snapshot),
        "parked_type": parked_type,
        "confidence": confidence,
        "evidence": _build_evidence(snapshot, parked_type),
        "recommendation": {
            "summary": runbook["summary"],
            "next_action": runbook["next_action"],
            "automation_level": runbook["automation_level"],
            "owner": runbook["owner"],
            "allowed_actions": list(runbook["allowed_actions"]),
            "forbidden_actions": list(runbook["forbidden_actions"]),
        },
        "warnings": _json_safe(snapshot.get("warnings", [])),
        "side_effects": [],
    }
    return _json_safe(result)


def render_json(result: Mapping[str, Any]) -> str:
    return json.dumps(_json_safe(result), ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def render_markdown(result: Mapping[str, Any]) -> str:
    issue = _as_dict(result.get("issue"))
    rec = _as_dict(result.get("recommendation"))
    lines = [
        "# kanban-parked-triage diagnose",
        "",
        f"- issue: {_compact(issue.get('url') or issue.get('number') or '')}",
        f"- task_id: {_compact(result.get('task_id') or '')}",
        f"- board: {_compact(result.get('board') or '')}",
        f"- current_status: {_compact(result.get('current_status') or '')}",
        f"- is_current_block: {str(bool(result.get('is_current_block'))).lower()}",
        f"- parked_type: {_compact(result.get('parked_type') or '')}",
        f"- confidence: {_compact(result.get('confidence') or '')}",
        "",
        "## Evidence",
    ]
    for item in _as_list(result.get("evidence")):
        if isinstance(item, Mapping):
            lines.append(f"- [{_compact(item.get('source') or '')}] {_compact(item.get('summary') or '')}")
    if not _as_list(result.get("evidence")):
        lines.append("- none")
    lines.extend([
        "",
        "## Recommendation",
        f"- summary: {_compact(rec.get('summary') or '')}",
        f"- next_action: {_compact(rec.get('next_action') or '')}",
        f"- automation_level: {_compact(rec.get('automation_level') or '')}",
        f"- owner: {_compact(rec.get('owner') or '')}",
        "- allowed_actions:",
    ])
    for action in _as_list(rec.get("allowed_actions")):
        lines.append(f"  - {_compact(action)}")
    lines.append("- forbidden_actions:")
    for action in _as_list(rec.get("forbidden_actions")):
        lines.append(f"  - {_compact(action)}")
    warnings = _as_list(result.get("warnings"))
    if warnings:
        lines.extend(["", "## Warnings"])
        for warning in warnings:
            lines.append(f"- {_compact(warning)}")
    lines.append("")
    return "\n".join(lines)


def _run_json(command: Sequence[str], *, timeout: int = 30) -> tuple[Any | None, str | None]:
    try:
        proc = subprocess.run(
            list(command),
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        return None, f"command not found: {command[0]}"
    except subprocess.TimeoutExpired:
        return None, f"command timed out: {' '.join(command[:2])}"
    if proc.returncode != 0:
        return None, _compact(proc.stderr or proc.stdout or f"exit {proc.returncode}")
    try:
        return json.loads(proc.stdout), None
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON from {command[0]}: {exc}"


def _parse_pr_numbers(*texts: Any) -> list[int]:
    found: set[int] = set()
    for text in texts:
        s = str(text or "")
        found.update(int(match.group(1)) for match in _PR_URL_RE.finditer(s))
        found.update(int(match.group(1)) for match in _PR_REF_RE.finditer(s))
    return sorted(found)


def load_github_snapshot(issue: str, repo: str, gh_command: str = "gh") -> tuple[dict[str, Any], list[str]]:
    """Read GitHub issue and linked PR evidence through gh CLI."""
    warnings: list[str] = []
    gh = shlex.split(gh_command) or ["gh"]
    issue_fields = "number,title,state,labels,body,url,comments"
    data, err = _run_json([*gh, "issue", "view", str(issue), "--repo", repo, "--json", issue_fields])
    if err:
        warnings.append(f"github issue read failed: {err}")
        fallback_number: int | str = int(issue) if str(issue).isdigit() else issue
        return {
            "issue": {
                "number": fallback_number,
                "url": f"https://github.com/{repo}/issues/{issue}",
                "state": None,
                "labels": [],
                "comments": [],
            },
            "prs": [],
        }, warnings
    issue_obj = _as_dict(data)
    issue_obj["labels"] = [label.get("name") if isinstance(label, Mapping) else label for label in _as_list(issue_obj.get("labels"))]
    text_sources = [issue_obj.get("body"), issue_obj.get("title")]
    text_sources.extend(comment.get("body") for comment in _as_list(issue_obj.get("comments")) if isinstance(comment, Mapping))
    pr_numbers = _parse_pr_numbers(*text_sources)[:5]
    prs: list[dict[str, Any]] = []
    pr_fields = "number,title,state,url,headRefOid,baseRefName,isDraft,mergedAt,statusCheckRollup"
    for number in pr_numbers:
        pr_data, pr_err = _run_json([*gh, "pr", "view", str(number), "--repo", repo, "--json", pr_fields])
        if pr_err:
            warnings.append(f"github pr #{number} read failed: {pr_err}")
            continue
        prs.append(_as_dict(pr_data))
    return {"issue": issue_obj, "prs": prs}, warnings


def _read_rows(conn: sqlite3.Connection, query: str, params: Sequence[Any]) -> list[dict[str, Any]]:
    try:
        rows = conn.execute(query, tuple(params)).fetchall()
    except sqlite3.Error:
        return []
    out = []
    for row in rows:
        item = _row_to_dict(row)
        for key in ("payload", "metadata", "skills"):
            if key in item:
                item[key] = _maybe_json(item[key])
        out.append(item)
    return out


def load_kanban_snapshot(task_id: str | None, board: str | None = None) -> tuple[dict[str, Any], list[str]]:
    """Read a Kanban task graph through a read-only SQLite connection."""
    if not task_id:
        return {}, []
    warnings: list[str] = []
    try:
        from hermes_cli import kanban_db as kb

        db_path = kb.kanban_db_path(board=board)
    except Exception as exc:  # pragma: no cover - defensive import path
        return {}, [f"kanban path resolution failed: {exc}"]
    if not db_path.exists():
        return {}, [f"kanban db not found: {db_path}"]
    uri = f"file:{db_path}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
    except sqlite3.Error as exc:
        return {}, [f"kanban read-only open failed: {exc}"]
    try:
        conn.row_factory = sqlite3.Row
        tasks = _read_rows(conn, "SELECT * FROM tasks WHERE id = ?", [task_id])
        if not tasks:
            return {}, [f"kanban task not found: {task_id}"]
        parents = _read_rows(
            conn,
            """
            SELECT t.* FROM tasks t
            JOIN task_links l ON l.parent_id = t.id
            WHERE l.child_id = ?
            ORDER BY t.created_at ASC, t.id ASC
            """,
            [task_id],
        )
        children = _read_rows(
            conn,
            """
            SELECT t.* FROM tasks t
            JOIN task_links l ON l.child_id = t.id
            WHERE l.parent_id = ?
            ORDER BY t.created_at ASC, t.id ASC
            """,
            [task_id],
        )
        comments = _read_rows(
            conn,
            "SELECT * FROM task_comments WHERE task_id = ? ORDER BY created_at ASC, id ASC",
            [task_id],
        )
        events = _read_rows(
            conn,
            "SELECT * FROM task_events WHERE task_id = ? ORDER BY created_at ASC, id ASC",
            [task_id],
        )
        runs = _read_rows(
            conn,
            "SELECT * FROM task_runs WHERE task_id = ? ORDER BY started_at ASC, id ASC",
            [task_id],
        )
        return {
            "task": tasks[0],
            "parents": parents,
            "children": children,
            "comments": comments,
            "events": events,
            "runs": runs,
            "board": board,
        }, warnings
    finally:
        conn.close()


def load_live_snapshot(issue: str, task_id: str | None, repo: str, board: str | None, gh_command: str) -> dict[str, Any]:
    snapshot: dict[str, Any] = {"board": board, "warnings": []}
    github_part, github_warnings = load_github_snapshot(issue, repo, gh_command=gh_command)
    snapshot.update(github_part)
    snapshot["warnings"].extend(github_warnings)
    kanban_part, kanban_warnings = load_kanban_snapshot(task_id, board=board)
    snapshot.update(kanban_part)
    snapshot["warnings"].extend(kanban_warnings)
    if task_id and "task" not in snapshot:
        snapshot["task"] = {"id": task_id, "status": "unknown"}
    return snapshot


def _load_fixture(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kanban-parked-triage",
        description="Read-only parked-state classifier for GitHub-backed Hermes Kanban tasks.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_diag = sub.add_parser("diagnose", help="classify a parked issue/task")
    p_diag.add_argument("--issue", required=True, help="GitHub issue number, e.g. 156")
    p_diag.add_argument("--task-id", default=None, help="Hermes Kanban task id, e.g. t_abc12345")
    p_diag.add_argument("--repo", default="GTZhou/TianGongKaiWu", help="GitHub owner/repo")
    p_diag.add_argument("--board", default="tiangongkaiwu", help="Hermes Kanban board slug")
    p_diag.add_argument("--gh-command", default="gh", help="gh command or wrapper to use for read-only GitHub calls")
    p_diag.add_argument("--fixture", default=None, help="read a JSON evidence fixture instead of live GitHub/Kanban")
    p_diag.add_argument("--format", choices=("markdown", "json"), default="markdown", help="output format")
    p_diag.add_argument("--json", action="store_true", help="shortcut for --format json")

    sub.add_parser("schema", help="print the JSON result schema")
    p_runbook = sub.add_parser("runbook", help="print the parked-type runbook")
    p_runbook.add_argument("--format", choices=("markdown", "json"), default="markdown")
    return parser


def _render_runbook_markdown() -> str:
    lines = ["# kanban-parked-triage runbook", ""]
    for parked_type, item in RUNBOOK.items():
        lines.extend([
            f"## {parked_type}",
            f"- summary: {item['summary']}",
            f"- next_action: {item['next_action']}",
            f"- automation_level: {item['automation_level']}",
            f"- owner: {item['owner']}",
            "- allowed_actions:",
        ])
        for action in item["allowed_actions"]:
            lines.append(f"  - {action}")
        lines.append("- forbidden_actions:")
        for action in item["forbidden_actions"]:
            lines.append(f"  - {action}")
        lines.append("")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.command == "schema":
        sys.stdout.write(render_json(RESULT_SCHEMA))
        return 0
    if args.command == "runbook":
        if args.format == "json":
            sys.stdout.write(render_json({"schema": "kanban-parked-triage-runbook:v1", "runbook": RUNBOOK}))
        else:
            sys.stdout.write(_render_runbook_markdown())
        return 0
    if args.command == "diagnose":
        output_format = "json" if args.json else args.format
        snapshot = _load_fixture(args.fixture) if args.fixture else load_live_snapshot(
            issue=args.issue,
            task_id=args.task_id,
            repo=args.repo,
            board=args.board,
            gh_command=args.gh_command,
        )
        if args.board and "board" not in snapshot:
            snapshot["board"] = args.board
        if args.task_id and "task" not in snapshot:
            snapshot["task"] = {"id": args.task_id, "status": "unknown"}
        result = diagnose_snapshot(snapshot)
        sys.stdout.write(render_json(result) if output_format == "json" else render_markdown(result))
        return 0
    parser.error(f"unknown command {args.command}")
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
