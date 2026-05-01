from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from cron.jobs import create_job, update_job

from .registry_api import bind_mapping, load_registry

TZ = timezone(timedelta(hours=8))
USAGE = (
    "❌ 用法: task_hook.py cron_upsert <任务ID> <jobName> <cronExpr> "
    "[--message 文本 | --system-event 文本] [--channel feishu] [--to user:xxx] "
    "[--account main] [--model xxx] [--timeout-seconds N] [--session isolated] "
    "[--thinking medium] [--announce] [--best-effort-deliver] [--light-context] [--dry-run] [--json]"
)
GRAY_USAGE = "❌ 用法: task_hook.py cron_upsert_gray <任务ID> <jobName> <cronExpr> [其余参数同 cron_upsert]"


def _now_iso() -> str:
    return datetime.now(TZ).isoformat()


def _extract_flag_value(args: list[str], *flags: str) -> str | None:
    for i, arg in enumerate(args):
        if arg in flags and i + 1 < len(args):
            return args[i + 1]
    return None


def _extract_bool_flag(args: list[str], *flags: str) -> bool:
    return any(flag in args for flag in flags)


def _remove_flags(args: list[str], flags_with_values: set[str], bool_flags: set[str]) -> list[str]:
    cleaned: list[str] = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in flags_with_values:
            i += 2
            continue
        if arg in bool_flags:
            i += 1
            continue
        cleaned.append(arg)
        i += 1
    return cleaned


def _build_prompt(task_id: str, job_name: str, forwarded_args: list[str]) -> str:
    message = _extract_flag_value(forwarded_args, '--message')
    system_event = _extract_flag_value(forwarded_args, '--system-event')
    timeout_seconds = _extract_flag_value(forwarded_args, '--timeout-seconds')
    account = _extract_flag_value(forwarded_args, '--account')
    session_mode = _extract_flag_value(forwarded_args, '--session')
    model = _extract_flag_value(forwarded_args, '--model')
    thinking = _extract_flag_value(forwarded_args, '--thinking')
    channel = _extract_flag_value(forwarded_args, '--channel') or 'feishu'
    target = _extract_flag_value(forwarded_args, '--to') or 'feishu'
    best_effort = _extract_bool_flag(forwarded_args, '--best-effort-deliver')
    light_context = _extract_bool_flag(forwarded_args, '--light-context')
    announce = _extract_bool_flag(forwarded_args, '--announce')
    passthrough = _remove_flags(
        forwarded_args,
        flags_with_values={
            '--message', '--system-event', '--timeout-seconds', '--account', '--session', '--model', '--thinking', '--channel', '--to'
        },
        bool_flags={'--best-effort-deliver', '--light-context', '--announce', '--dry-run', '--json'},
    )

    instructions: list[str] = [
        f"任务定时触发：jobName={job_name}",
        f"taskId={task_id}",
        f"channel={channel}",
        f"target={target}",
    ]
    if session_mode:
        instructions.append(f"sessionMode={session_mode}")
    if account:
        instructions.append(f"account={account}")
    if timeout_seconds:
        instructions.append(f"timeoutSeconds={timeout_seconds}")
    if model:
        instructions.append(f"requestedModel={model}")
    if thinking:
        instructions.append(f"thinking={thinking}")
    if announce:
        instructions.append("announce=true")
    if best_effort:
        instructions.append("bestEffortDeliver=true")
    if light_context:
        instructions.append("lightContext=true")
    if passthrough:
        instructions.append("passthroughArgs=" + " ".join(passthrough))

    body = system_event or message or f'【TASK_CRON】 taskId={task_id} jobName={job_name}\n\n请按已绑定任务执行。'
    return (
        "你是 Hermes 的任务定时执行器。请在独立会话中按以下约束执行。\n\n"
        + "\n".join(f"- {line}" for line in instructions)
        + "\n\n执行内容：\n"
        + body.strip()
        + "\n\n要求：\n"
        + "1. 直接执行，不要要求补充当前会话上下文。\n"
        + "2. 输出中保留 taskId 与 jobName，便于回写审计。\n"
        + "3. 若信息不足，以 best effort 方式完成并说明假设。"
    )


def _resolve_deliver(forwarded_args: list[str]) -> str:
    channel = (_extract_flag_value(forwarded_args, '--channel') or 'feishu').strip().lower()
    target = (_extract_flag_value(forwarded_args, '--to') or '').strip()
    if target:
        if target.startswith(('feishu:', 'telegram:', 'discord:', 'slack:', 'whatsapp:', 'signal:', 'matrix:', 'mattermost:', 'email:', 'sms:')):
            return target
        if target.startswith('user:') or target.startswith('chat:'):
            return f'{channel}:{target}'
    return channel or 'feishu'


def _find_existing_job_id(task_id: str, job_name: str) -> str | None:
    task_link = (load_registry().get('tasks') or {}).get(task_id, {})
    job_ids = task_link.get('jobIds') or []
    if job_ids:
        return job_ids[-1]
    for candidate in job_ids:
        if candidate == job_name:
            return candidate
    return None


def upsert_task_cron(task_id: str, job_name: str, cron_expr: str, forwarded_args: list[str], *, gray: bool = False) -> dict[str, Any]:
    if gray:
        return {
            'ok': True,
            'gray': True,
            'taskId': task_id,
            'jobName': job_name,
            'schedule': cron_expr,
            'deliver': _resolve_deliver(forwarded_args),
            'promptPreview': _build_prompt(task_id, job_name, forwarded_args)[:200],
            'message': 'Hermes-native cron_upsert gray preview generated',
        }

    dry_run = _extract_bool_flag(forwarded_args, '--dry-run')
    prompt = _build_prompt(task_id, job_name, forwarded_args)
    deliver = _resolve_deliver(forwarded_args)
    model = _extract_flag_value(forwarded_args, '--model')
    existing_job_id = _find_existing_job_id(task_id, job_name)

    if dry_run:
        return {
            'ok': True,
            'dryRun': True,
            'taskId': task_id,
            'jobName': job_name,
            'schedule': cron_expr,
            'deliver': deliver,
            'model': model,
            'message': 'Hermes-native cron_upsert dry-run only',
        }

    if existing_job_id:
        job = update_job(existing_job_id, {
            'prompt': prompt,
            'schedule': {'kind': 'cron', 'expr': cron_expr, 'display': cron_expr},
            'schedule_display': cron_expr,
            'deliver': deliver,
            'model': model,
            'enabled': True,
            'state': 'scheduled',
        })
        action = 'updated'
    else:
        job = create_job(
            prompt=prompt,
            schedule=cron_expr,
            name=job_name,
            deliver=deliver,
            model=model,
        )
        action = 'created'

    if not job:
        return {'ok': False, 'error': 'cron upsert failed: no job returned'}

    registry = bind_mapping(
        task_id=task_id,
        job_id=job.get('id'),
        note=f'task_cron.{action}:{job_name}',
        source='hermes_team.task_cron',
        status='scheduled',
    )
    task_link = (registry.get('tasks') or {}).get(task_id, {})
    return {
        'ok': True,
        'action': action,
        'taskId': task_id,
        'jobId': job.get('id'),
        'jobName': job_name,
        'schedule': job.get('schedule_display', cron_expr),
        'deliver': job.get('deliver'),
        'updatedAt': _now_iso(),
        'registry': task_link,
    }
