from __future__ import annotations

import json
import sys
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .approval_store import ApprovalStore
from .paths import ensure_team_state_dir
from .registry_api import bind_mapping, load_registry, update_mapping_status
from .source_bridge import audit_team_state_vs_legacy
from .task_cron import GRAY_USAGE as CRON_UPSERT_GRAY_USAGE
from .task_cron import USAGE as CRON_UPSERT_USAGE
from .task_cron import upsert_task_cron
from .task_store import STATE_LABELS, VALID_TRANSITIONS, TaskStore

TZ = timezone(timedelta(hours=8))
CMD_MAP = {
    "triage": ("cio_triage", "cio"),
    "intel": ("intel_gather", "cio"),
    "risk": ("risk_review", "intelligence_officer"),
    "approve": ("assigned", "risk_officer"),
    "reject": ("intel_gather", "risk_officer"),
    "assign": ("assigned", "cio"),
    "execute": ("executing", "cio"),
    "submit": ("review", "execution_officer"),
    "complete": ("done", "cio"),
    "block": ("blocked", "cio"),
    "cancel": ("cancelled", "cio"),
}

_TASK_STORE = TaskStore(ensure_team_state_dir())
_APPROVAL_STORE = ApprovalStore(ensure_team_state_dir())


def _now_iso() -> str:
    return datetime.now(TZ).isoformat()


def _save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def _next_task_id(existing_ids: set[str]) -> str:
    """[P1] Avoid duplicate task IDs when multiple tasks are created within the same second."""
    base = datetime.now(TZ).strftime('%Y%m%d-%H%M%S')
    candidate = f"TSK-{base}"
    if candidate not in existing_ids:
        return candidate

    suffix = 1
    while True:
        candidate = f"TSK-{base}-{suffix:02d}"
        if candidate not in existing_ids:
            return candidate
        suffix += 1


def list_tasks() -> list[dict[str, Any]]:
    return _TASK_STORE.list_tasks()


def list_archive() -> list[dict[str, Any]]:
    return _TASK_STORE.list_archive()


def _write_tasks(tasks: list[dict[str, Any]]) -> None:
    _save_json(_TASK_STORE.tasks_path, tasks)


def _write_archive(tasks: list[dict[str, Any]]) -> None:
    _save_json(_TASK_STORE.archive_path, tasks)


def _find_task(tasks: list[dict[str, Any]], task_id: str) -> tuple[int, dict[str, Any] | None]:
    for idx, task in enumerate(tasks):
        if task.get('id') == task_id:
            return idx, task
    return -1, None


def create_task(title: str, description: str = '', priority: str = 'normal') -> dict[str, Any]:
    tasks = list_tasks()
    existing_ids = {str(item.get('id') or '') for item in tasks if item.get('id')}
    task_id = _next_task_id(existing_ids)
    task = {
        'id': task_id,
        'title': title,
        'description': description,
        'state': 'pending',
        'assignee': 'cio',
        'priority': priority,
        'created_at': _now_iso(),
        'updated_at': _now_iso(),
        'flow': [
            {
                'from_state': None,
                'to_state': 'pending',
                'by': 'system',
                'at': _now_iso(),
                'reason': '任务创建',
            }
        ],
        'taskType': 'general',
    }
    tasks.append(task)
    _write_tasks(tasks)
    return deepcopy(task)


def transition(task_id: str, new_state: str, by: str, reason: str) -> dict[str, Any]:
    tasks = list_tasks()
    idx, task = _find_task(tasks, task_id)
    if task is None:
        archived = list_archive()
        _, archived_task = _find_task(archived, task_id)
        if archived_task is not None:
            return {'ok': False, 'error': '任务已归档，不能再流转'}
        return {'ok': False, 'error': f'任务不存在: {task_id}'}

    old_state = task.get('state', 'pending')
    allowed = VALID_TRANSITIONS.get(old_state, [])
    if new_state not in allowed:
        return {'ok': False, 'error': f'非法状态流转: {old_state} -> {new_state}'}

    updated = deepcopy(task)
    updated['state'] = new_state
    updated['updated_at'] = _now_iso()
    updated.setdefault('flow', []).append({
        'from_state': old_state,
        'to_state': new_state,
        'by': by,
        'at': _now_iso(),
        'reason': reason,
    })
    tasks[idx] = updated

    if new_state == 'done':
        archive = list_archive()
        archive.append(updated)
        _write_archive(archive)
        tasks.pop(idx)
    _write_tasks(tasks)
    return {'ok': True, 'task': deepcopy(updated)}


def _build_task_approval_status_map() -> dict[str, dict[str, str]]:
    latest_by_task = {}
    for approval in _APPROVAL_STORE.list_approvals():
        scope = approval.get('scope') or {}
        task_id = scope.get('task_id') or approval.get('task_id')
        if not task_id:
            continue
        created_at = approval.get('created_at') or approval.get('createdAt') or ''
        current = latest_by_task.get(task_id)
        current_ts = '' if current is None else (current.get('created_at') or current.get('createdAt') or '')
        if current is None or created_at > current_ts:
            latest_by_task[task_id] = approval
    return {
        task_id: {
            'status': (approval.get('status') or 'none').lower(),
            'approval_id': approval.get('approval_id') or approval.get('approvalId') or '—',
        }
        for task_id, approval in latest_by_task.items()
    }


def _build_task_registry_map() -> dict[str, Any]:
    registry = load_registry()
    return registry.get('tasks') or {}


def _format_approval_display(approval_info: dict[str, Any] | None) -> str:
    if not approval_info:
        return '—'
    status = approval_info.get('status') or 'none'
    approval_id = approval_info.get('approval_id') or '—'
    if approval_id == '—':
        return status
    return f"{status} ({approval_id})"


def _format_link_display(task_link: dict[str, Any] | None) -> str:
    if not task_link:
        return '—'
    parts = []
    for key, label in (('jobIds', 'job'), ('runIds', 'run'), ('sessionIds', 'session'), ('sessionKeys', 'sessionKey')):
        values = task_link.get(key) or []
        if values:
            parts.append(f"{label}={values[-1]}")
    return ' | '.join(parts) if parts else '—'


def _format_registry_status(task_link: dict[str, Any] | None) -> str:
    if not task_link:
        return 'unlinked'
    has_link = any(task_link.get(key) for key in ('jobIds', 'runIds', 'sessionIds', 'sessionKeys'))
    status = task_link.get('lastStatus') or 'linked'
    updated_at = task_link.get('updatedAt') or ''
    if not has_link:
        base = f"registered_only({status})"
        return f"{base} @ {updated_at}" if updated_at else base
    return f"{status} @ {updated_at}" if updated_at else status


def _task_exists(task_id: str) -> bool:
    return any(t.get('id') == task_id for t in list_tasks() + list_archive())


def _ensure_registry_placeholder(task_id: str, status: str, note: str, source: str) -> dict[str, Any]:
    return update_mapping_status(task_id, status, note=note, source=source)


def _extract_flag_value(args: list[str], *flags: str) -> str | None:
    for i, arg in enumerate(args):
        if arg in flags and i + 1 < len(args):
            return args[i + 1]
    return None


def _extract_bool_flag(args: list[str], *flags: str) -> bool:
    return any(flag in args for flag in flags)


def _normalize_cron_forward_args(task_id: str, raw_args: list[str]) -> list[str]:
    if len(raw_args) < 2:
        raise ValueError(CRON_UPSERT_USAGE)
    return [task_id, *raw_args[2:]]


def _handle_cron_upsert(args: list[str], gray: bool = False) -> None:
    if len(args) < 3:
        raise ValueError(CRON_UPSERT_GRAY_USAGE if gray else CRON_UPSERT_USAGE)
    task_id = args[0]
    job_name = args[1]
    cron_expr = args[2]
    if not _task_exists(task_id):
        print(f'❌ 任务不存在: {task_id}')
        return
    forwarded_args = _normalize_cron_forward_args(task_id, args[1:])
    result = upsert_task_cron(task_id, job_name, cron_expr, forwarded_args, gray=gray)
    if not result.get('ok'):
        print(f"❌ {result.get('error', 'cron upsert failed')}")
        return
    if result.get('gray'):
        print(
            f"🩶 {task_id} cron_upsert gray | job={result.get('jobName')} | schedule={result.get('schedule')} | "
            f"deliver={result.get('deliver')}"
        )
        preview = result.get('promptPreview') or ''
        if preview:
            print(f"   preview: {preview}")
        return
    if result.get('dryRun'):
        print(
            f"🧪 {task_id} cron_upsert dry-run | job={result.get('jobName')} | schedule={result.get('schedule')} | "
            f"deliver={result.get('deliver')}"
        )
        return
    registry_link = result.get('registry') or {}
    print(
        f"✅ {task_id} cron_upsert {result.get('action')} | job={result.get('jobId')} | "
        f"schedule={result.get('schedule')} | deliver={result.get('deliver')}"
    )
    print(f"🔗 {task_id} registry: {_format_registry_status(registry_link)} | link: {_format_link_display(registry_link)}")


def dispatch(args: list[str]) -> None:
    if not args:
        print('❌ 用法: task_hook.py <create|list|archive|summary|audit_legacy_diff|bind|backfill_registry|unblock|triage|intel|risk|approve|reject|assign|execute|submit|complete|block|cancel|cron_upsert|cron_upsert_gray> ...')
        return

    cmd = args[0]
    args = args[1:]

    if cmd == 'create':
        title = args[0] if args else '未命名任务'
        desc = args[1] if len(args) > 1 else ''
        priority = args[2] if len(args) > 2 else 'normal'
        task = create_task(title, desc, priority)
        _ensure_registry_placeholder(task['id'], task['state'], note='task created', source='task_hook.create')
        print(f"✅ 已创建任务: {task['id']} | {task['title']} | {STATE_LABELS.get(task['state'], task['state'])}")
    elif cmd == 'bind':
        if len(args) < 1:
            print('❌ 用法: task_hook.py bind <任务ID> [jobId] [sessionId] [sessionKey] [runId] [note]')
            return
        task_id = args[0]
        job_id = args[1] if len(args) > 1 and args[1] not in ('-', '—', 'none', 'null') else None
        session_id = args[2] if len(args) > 2 and args[2] not in ('-', '—', 'none', 'null') else None
        session_key = args[3] if len(args) > 3 and args[3] not in ('-', '—', 'none', 'null') else None
        run_id = args[4] if len(args) > 4 and args[4] not in ('-', '—', 'none', 'null') else None
        note = args[5] if len(args) > 5 else 'manual bind'
        registry = bind_mapping(task_id=task_id, job_id=job_id, session_id=session_id, session_key=session_key, run_id=run_id, note=note, source='task_hook.bind')
        print(f"✅ {task_id} 已绑定 | {_format_link_display((registry.get('tasks') or {}).get(task_id, {}))}")
    elif cmd == 'backfill_registry':
        tasks = list_tasks()
        registry = load_registry()
        task_registry_map = (registry.get('tasks') or {}) if isinstance(registry, dict) else {}
        touched = []
        for task in tasks:
            task_id = task.get('id')
            if task_id and task_id not in task_registry_map:
                update_mapping_status(task_id, task.get('state') or 'pending', note='historical task backfill placeholder', source='task_hook.backfill_registry')
                touched.append(task_id)
        print(f"✅ 已回填 registry: {len(touched)} 条")
        if touched:
            print(f"   └─ 回填任务: {', '.join(touched[:10])}")
    elif cmd == 'list':
        tasks = list_tasks()
        if not tasks:
            print('📋 无活跃任务')
            return
        approval_map = _build_task_approval_status_map()
        registry_map = _build_task_registry_map()
        for task in tasks:
            task_id = task['id']
            print(
                f"{task_id} | {STATE_LABELS.get(task.get('state'), task.get('state'))} | {task.get('title')} | "
                f"approval: {_format_approval_display(approval_map.get(task_id))} | "
                f"registry: {_format_registry_status(registry_map.get(task_id))} | "
                f"link: {_format_link_display(registry_map.get(task_id))}"
            )
    elif cmd == 'archive':
        archive = list_archive()
        if not archive:
            print('📦 无归档任务')
            return
        registry_map = _build_task_registry_map()
        for task in archive:
            print(f"{task['id']} | ✅ 已完成 | {task['title']} | 流转步数: {len(task.get('flow', []))} | registry: {_format_registry_status(registry_map.get(task['id']))} | link: {_format_link_display(registry_map.get(task['id']))}")
    elif cmd == 'summary':
        tasks = list_tasks()
        archive = list_archive()
        by_state: dict[str, int] = {}
        for task in tasks:
            state = task.get('state') or 'pending'
            by_state[state] = by_state.get(state, 0) + 1
        print('📊 任务摘要')
        print(f"- 活跃任务: {len(tasks)}")
        print(f"- 归档任务: {len(archive)}")
        for state, count in sorted(by_state.items()):
            print(f"- {STATE_LABELS.get(state, state)}: {count}")
    elif cmd == 'audit_legacy_diff':
        workspace_root = Path(args[0]).expanduser() if args else Path.cwd()
        report = audit_team_state_vs_legacy(workspace_root)
        print('📎 legacy vs hermes team state audit')
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif cmd == 'unblock':
        if len(args) < 2:
            print('❌ 用法: task_hook.py unblock <任务ID> <目标状态> [原因]')
            return
        result = transition(args[0], args[1], 'cio', args[2] if len(args) > 2 else '解除阻塞')
        print(f"✅ {args[0]} 解除阻塞 → {STATE_LABELS.get(args[1], args[1])}" if result['ok'] else f"❌ {result['error']}")
    elif cmd == 'cron_upsert':
        _handle_cron_upsert(args, gray=False)
    elif cmd == 'cron_upsert_gray':
        _handle_cron_upsert(args, gray=True)
    elif cmd in CMD_MAP:
        if len(args) < 1:
            print(f'❌ 用法: task_hook.py {cmd} <任务ID> [原因]')
            return
        new_state, by = CMD_MAP[cmd]
        reason = args[1] if len(args) > 1 else cmd
        result = transition(args[0], new_state, by, reason)
        if result['ok']:
            update_mapping_status(args[0], new_state, note=f'task transition via {cmd}', source='task_hook.transition')
            print(f"✅ {args[0]} -> {STATE_LABELS.get(new_state, new_state)}")
        else:
            print(f"❌ {result['error']}")
    else:
        print(f'❌ 未知命令: {cmd}')


if __name__ == '__main__':
    dispatch(sys.argv[1:])
