from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from build_support_health_report import build_support_health_report
from build_support_readiness_report import (
    build_support_readiness_report,
    classify_email_step,
    classify_telegram_step,
)
from business_ops_core import (
    build_finance_reports,
    build_task_dashboard_report,
    process_document_inbox,
)
from mirror_to_dropbox import run_dropbox_mirror
from operator_updates import (
    build_previous_day_summary,
    ensure_operator_update_tables,
    maybe_send_previous_day_summary,
    record_pipeline_run_completion,
    record_pipeline_run_start,
    send_operator_update,
)
from poll_support_email import _ensure_support_tables, poll_support_email
from poll_telegram_updates import poll_telegram_updates


MAX_NOTIFICATION_ATTACHMENTS = 10


def _coerce_datetime(value: str | datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _run_email_step(
    businessos_root: Path,
    db_path: Path,
    scripts_dir: Path,
    configs_dir: Path,
) -> tuple[str, dict[str, Any]]:
    email_script = scripts_dir / 'poll_support_email.py'
    email_config = configs_dir / 'support-inboxes.yaml'

    script_status = classify_email_step(email_script)
    if script_status != 'available-not-run':
        return script_status, {'imported_count': 0, 'accounts': {}, 'imported_messages': [], 'status': script_status}
    if not email_config.exists():
        return 'missing-config', {'imported_count': 0, 'accounts': {}, 'imported_messages': [], 'status': 'missing-config'}

    result = poll_support_email(
        businessos_root=businessos_root,
        db_path=db_path,
        config_path=email_config,
        source_account=None,
    )
    return result.get('status', 'completed'), result


def _run_telegram_step(
    businessos_root: Path,
    db_path: Path,
    scripts_dir: Path,
    configs_dir: Path,
) -> tuple[str, dict[str, Any]]:
    telegram_script = scripts_dir / 'poll_telegram_updates.py'
    telegram_config = configs_dir / 'telegram-sources.yaml'

    script_status = classify_telegram_step(telegram_script)
    if script_status != 'available-not-run':
        return script_status, {'imported_count': 0, 'accounts': {}, 'imported_messages': [], 'status': script_status}
    if not telegram_config.exists():
        return 'missing-config', {'imported_count': 0, 'accounts': {}, 'imported_messages': [], 'status': 'missing-config'}

    result = poll_telegram_updates(
        businessos_root=businessos_root,
        db_path=db_path,
        config_path=telegram_config,
        source_account=None,
    )
    return result.get('status', 'completed'), result


def _shorten(text: str | None, limit: int = 120) -> str:
    value = (text or '').strip()
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)].rstrip() + '…'


def _relative_path(value: str | Path | None, businessos_root: Path) -> str | None:
    if not value:
        return None
    path = Path(value)
    try:
        return str(path.resolve().relative_to(businessos_root.resolve()))
    except Exception:
        return str(value)


def _format_amount(value: Any) -> str | None:
    if value in (None, ''):
        return None
    try:
        return f'${float(value):.2f}'
    except Exception:
        return str(value)


def _limited_lines(items: list[str], limit: int = 6) -> list[str]:
    trimmed = items[:limit]
    if len(items) > limit:
        trimmed.append(f'- (+{len(items) - limit} more)')
    return trimmed


def _classification_label_for_item(item: dict[str, Any]) -> str:
    existing = str(item.get('classification_label') or '').strip()
    if existing:
        return existing
    category = str(item.get('category') or '').strip()
    assigned_queue = str(item.get('assigned_queue') or item.get('mailbox_role') or 'unassigned').strip() or 'unassigned'
    if item.get('task_operation'):
        primary = 'todo'
        semantic = 'task-capture'
    elif category == 'business-expense-record' or str(item.get('mailbox_role') or '').strip() == 'expense-intake':
        primary = 'expense'
        semantic = category or 'business-expense-record'
    elif category == 'business-identity-record':
        primary = 'business-identity'
        semantic = category
    elif category == 'billing' or assigned_queue == 'billing-support':
        primary = 'billing'
        semantic = category or 'billing'
    elif 'legal' in category or assigned_queue == 'legal-review':
        primary = 'legal'
        semantic = category or 'legal'
    elif 'privacy' in category or assigned_queue == 'privacy-review':
        primary = 'privacy'
        semantic = category or 'privacy'
    elif category in {'operator-command', 'operator-note'} or assigned_queue == 'operator-control':
        primary = 'operator'
        semantic = category or 'operator'
    elif category == 'internal-test':
        primary = 'internal-test'
        semantic = category
    else:
        primary = 'support'
        semantic = category or 'support-request'
    return f'{primary} / {semantic} / {assigned_queue}'


def _format_email_detail_lines(result: dict[str, Any], businessos_root: Path) -> list[str]:
    lines: list[str] = []
    for item in result.get('imported_messages') or []:
        parts = [_shorten(item.get('subject') or '(no subject)', 90)]
        if item.get('sender_handle'):
            parts.append(f"from {item['sender_handle']}")
        parts.append(f"Classification: {_classification_label_for_item(item)}")
        suggested_task = item.get('suggested_task') or {}
        if suggested_task.get('title'):
            parts.append(f"Suggested task: {suggested_task['title']}")
        doc_ids = item.get('linked_document_ids') or []
        if doc_ids:
            parts.append(f"docs {', '.join(doc_ids[:3])}")
        normalized_path = _relative_path(item.get('normalized_path'), businessos_root)
        if normalized_path:
            parts.append(normalized_path)
        lines.append('- ' + ' | '.join(parts))
    return _limited_lines(lines)


def _format_telegram_detail_lines(result: dict[str, Any], businessos_root: Path) -> list[str]:
    lines: list[str] = []
    for item in result.get('imported_messages') or []:
        snippet = _shorten(item.get('text') or item.get('summary') or '(no text)', 100)
        parts = [snippet]
        if item.get('sender_handle'):
            parts.append(f"from {item['sender_handle']}")
        parts.append(f"Classification: {_classification_label_for_item(item)}")
        suggested_task = item.get('suggested_task') or {}
        if suggested_task.get('title'):
            parts.append(f"Suggested task: {suggested_task['title']}")
        normalized_path = _relative_path(item.get('normalized_path'), businessos_root)
        if normalized_path:
            parts.append(normalized_path)
        lines.append('- ' + ' | '.join(parts))
    return _limited_lines(lines)


def _format_document_detail_lines(result: dict[str, Any], businessos_root: Path) -> list[str]:
    lines: list[str] = []
    for item in result.get('documents') or []:
        parts = [str(item.get('id') or 'document')]
        if item.get('document_type'):
            parts.append(str(item['document_type']))
        if item.get('vendor_name'):
            parts.append(str(item['vendor_name']))
        amount = _format_amount(item.get('amount'))
        if amount:
            parts.append(amount)
        local_path = _relative_path(item.get('local_path'), businessos_root)
        if local_path:
            parts.append(local_path)
        lines.append('- ' + ' | '.join(parts))
    return _limited_lines(lines)


def _format_path_lines(paths: list[Any], prefix: str = '- ', limit: int = 8) -> list[str]:
    lines = [prefix + str(path) for path in (paths or [])]
    return _limited_lines(lines, limit=limit)


def _existing_file_paths(paths: list[str | Path], limit: int = MAX_NOTIFICATION_ATTACHMENTS) -> list[str]:
    existing: list[str] = []
    seen: set[str] = set()
    for value in paths:
        if value in (None, ''):
            continue
        path = Path(value)
        if not path.exists() or not path.is_file():
            continue
        resolved = str(path.resolve())
        if resolved in seen:
            continue
        existing.append(resolved)
        seen.add(resolved)
        if len(existing) >= limit:
            break
    return existing


def _document_attachment_paths(result: dict[str, Any]) -> list[str]:
    return _existing_file_paths([item.get('local_path') for item in result.get('documents') or []])


def _dropbox_copied_attachment_paths(dropbox_result: dict[str, Any], businessos_root: Path) -> list[str]:
    return _existing_file_paths([businessos_root / str(path) for path in (dropbox_result.get('copied') or [])])


def _completion_attachment_paths(
    *,
    businessos_root: Path,
    dropbox_result: dict[str, Any],
    health_report_path: Path,
    readiness_report_path: Path,
    task_dashboard_path: Path,
    finance_reports: dict[str, Any],
) -> list[str]:
    return _existing_file_paths(
        [
            health_report_path,
            readiness_report_path,
            task_dashboard_path,
            finance_reports.get('finance_summary_path'),
            finance_reports.get('deductible_summary_path'),
            *[businessos_root / str(path) for path in (dropbox_result.get('copied') or [])],
        ]
    )


def _should_notify_step(step_name: str, step_status: str, result: dict[str, Any]) -> bool:
    if step_name in {'email', 'telegram', 'document_inbox', 'dropbox_mirror'}:
        return True
    return step_status != 'completed'


def _format_step_message(step_name: str, step_status: str, result: dict[str, Any], businessos_root: Path) -> str:
    lines = ['BusinessOS step update', f'Step: {step_name}', f'Status: {step_status}']
    if step_name == 'email':
        lines.append(f"New imports: {int(result.get('imported_count', 0) or 0)}")
        lines.extend(_format_email_detail_lines(result, businessos_root) or ['- no new email items'])
    elif step_name == 'telegram':
        lines.append(f"New imports: {int(result.get('imported_count', 0) or 0)}")
        lines.extend(_format_telegram_detail_lines(result, businessos_root) or ['- no new Telegram items'])
    elif step_name == 'document_inbox':
        lines.append(f"Processed documents: {int(result.get('processed_count', 0) or 0)}")
        lines.extend(_format_document_detail_lines(result, businessos_root) or ['- no new document items'])
    elif step_name == 'dropbox_mirror':
        lines.append(f"Copied: {int(result.get('copied_count', 0) or 0)}")
        lines.append(f"Deleted: {int(result.get('deleted_count', 0) or 0)}")
        copied_lines = _format_path_lines(result.get('copied') or [], limit=10)
        if copied_lines:
            lines.append('Copied paths:')
            lines.extend(copied_lines)
        deleted_lines = _format_path_lines(result.get('deleted') or [], limit=5)
        if deleted_lines:
            lines.append('Deleted paths:')
            lines.extend(deleted_lines)
    return '\n'.join(lines)


def _format_completion_message(
    run_id: str,
    email_result: dict[str, Any],
    telegram_result: dict[str, Any],
    document_result: dict[str, Any],
    dropbox_result: dict[str, Any],
    daily_summary_result: dict[str, Any],
    businessos_root: Path,
    health_report_path: Path,
    readiness_report_path: Path,
    task_dashboard_path: Path,
    finance_reports: dict[str, Any],
) -> str:
    lines = [
        'BusinessOS run completed',
        f'Run: {run_id}',
        f"Email imports: {int(email_result.get('imported_count', 0) or 0)}",
        f"Telegram imports: {int(telegram_result.get('imported_count', 0) or 0)}",
        f"Documents processed: {int(document_result.get('processed_count', 0) or 0)}",
        f"Dropbox copied: {int(dropbox_result.get('copied_count', 0) or 0)}",
    ]
    daily_status = str(daily_summary_result.get('status') or 'unknown')
    daily_date = daily_summary_result.get('report_date')
    lines.append(f"Daily summary: {daily_status}{f' ({daily_date})' if daily_date else ''}")

    email_lines = _format_email_detail_lines(email_result, businessos_root)
    if email_lines:
        lines.append('')
        lines.append('Email items:')
        lines.extend(email_lines)

    telegram_lines = _format_telegram_detail_lines(telegram_result, businessos_root)
    if telegram_lines:
        lines.append('')
        lines.append('Telegram items:')
        lines.extend(telegram_lines)

    document_lines = _format_document_detail_lines(document_result, businessos_root)
    if document_lines:
        lines.append('')
        lines.append('Documents processed:')
        lines.extend(document_lines)

    copied_lines = _format_path_lines(dropbox_result.get('copied') or [], limit=10)
    if copied_lines:
        lines.append('')
        lines.append('Dropbox copied paths:')
        lines.extend(copied_lines)

    deleted_lines = _format_path_lines(dropbox_result.get('deleted') or [], limit=5)
    if deleted_lines:
        lines.append('')
        lines.append('Dropbox deleted paths:')
        lines.extend(deleted_lines)

    lines.append('')
    lines.append('Report paths:')
    lines.append(f"- {_relative_path(health_report_path, businessos_root) or str(health_report_path)}")
    lines.append(f"- {_relative_path(readiness_report_path, businessos_root) or str(readiness_report_path)}")
    lines.append(f"- {_relative_path(task_dashboard_path, businessos_root) or str(task_dashboard_path)}")
    lines.append(
        f"- {_relative_path(finance_reports['finance_summary_path'], businessos_root) or str(finance_reports['finance_summary_path'])}"
    )
    lines.append(
        f"- {_relative_path(finance_reports['deductible_summary_path'], businessos_root) or str(finance_reports['deductible_summary_path'])}"
    )
    return '\n'.join(lines)


def _summarize_notifications(notification_results: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'attempted_count': len(notification_results),
        'sent_count': sum(1 for item in notification_results if item.get('status') == 'sent'),
        'statuses': [item.get('status', 'unknown') for item in notification_results],
    }


def run_pipeline(
    businessos_root: str | Path | None = None,
    db_path: str | Path | None = None,
    mirror_config_path: str | Path | None = None,
    skip_email: bool = False,
    skip_telegram: bool = False,
    current_time: str | datetime | None = None,
    operator_updates_config_path: str | Path | None = None,
) -> dict[str, Any]:
    businessos_root = Path(businessos_root or Path(__file__).resolve().parents[2])
    db_path = Path(db_path or businessos_root / '03_DATA' / 'db' / 'businessos.db')
    mirror_config_path = Path(
        mirror_config_path or businessos_root / '04_AUTOMATIONS' / 'configs' / 'dropbox-mirror.yaml'
    )
    support_report_dir = businessos_root / '05_REPORTS' / 'support'
    support_report_dir.mkdir(parents=True, exist_ok=True)

    current_dt = _coerce_datetime(current_time).astimezone(timezone.utc).replace(microsecond=0)
    started_at = current_dt.isoformat()
    run_id = f"pipeline-{current_dt.strftime('%Y%m%dT%H%M%SZ')}"

    steps: dict[str, str] = {}
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    _ensure_support_tables(con)
    ensure_operator_update_tables(con)
    con.commit()
    con.close()
    scripts_dir = businessos_root / '04_AUTOMATIONS' / 'scripts'
    configs_dir = businessos_root / '04_AUTOMATIONS' / 'configs'
    operator_updates_config_path = Path(
        operator_updates_config_path or configs_dir / 'operator-updates.yaml'
    )
    telegram_config_path = configs_dir / 'telegram-sources.yaml'
    notification_results: list[dict[str, Any]] = []
    daily_summary_result: dict[str, Any] = {'status': 'not-run', 'sent': False, 'report_path': None}

    record_pipeline_run_start(db_path=db_path, run_id=run_id, started_at=started_at)

    def _send_notification(
        text: str,
        notification_type: str,
        event_time: str | datetime | None = None,
        attachment_paths: list[str | Path] | None = None,
    ) -> dict[str, Any]:
        notify_time = _coerce_datetime(event_time) if event_time is not None else datetime.now(timezone.utc)
        result = send_operator_update(
            businessos_root=businessos_root,
            db_path=db_path,
            text=text,
            notification_type=notification_type,
            config_path=operator_updates_config_path,
            telegram_config_path=telegram_config_path,
            related_run_id=run_id,
            current_time=notify_time,
            attachment_paths=attachment_paths,
        )
        notification_results.append(result)
        return result

    _send_notification(
        f'BusinessOS run started\nRun: {run_id}\nStarted: {started_at}',
        'run-started',
    )

    try:
        if skip_email:
            steps['email'] = 'skipped'
            email_result: dict[str, Any] = {'imported_count': 0, 'accounts': {}, 'imported_messages': [], 'status': 'skipped'}
        else:
            steps['email'], email_result = _run_email_step(businessos_root, db_path, scripts_dir, configs_dir)
        if _should_notify_step('email', steps['email'], email_result):
            _send_notification(
                _format_step_message('email', steps['email'], email_result, businessos_root),
                'email-step',
            )

        if skip_telegram:
            steps['telegram'] = 'skipped'
            telegram_result: dict[str, Any] = {'imported_count': 0, 'accounts': {}, 'imported_messages': [], 'status': 'skipped'}
        else:
            steps['telegram'], telegram_result = _run_telegram_step(businessos_root, db_path, scripts_dir, configs_dir)
        if _should_notify_step('telegram', steps['telegram'], telegram_result):
            _send_notification(
                _format_step_message('telegram', steps['telegram'], telegram_result, businessos_root),
                'telegram-step',
            )

        document_result = process_document_inbox(businessos_root=businessos_root, db_path=db_path)
        steps['document_inbox'] = document_result.get('status', 'completed')
        if _should_notify_step('document_inbox', steps['document_inbox'], document_result):
            _send_notification(
                _format_step_message('document_inbox', steps['document_inbox'], document_result, businessos_root),
                'document-step',
                attachment_paths=_document_attachment_paths(document_result),
            )

        task_dashboard_path = build_task_dashboard_report(businessos_root=businessos_root, db_path=db_path)
        steps['task_dashboard'] = 'completed'

        finance_reports = build_finance_reports(businessos_root=businessos_root, db_path=db_path)
        steps['finance_reports'] = 'completed'

        generated_at = _coerce_datetime(current_time).astimezone(timezone.utc).replace(microsecond=0).isoformat()
        health_report_path = build_support_health_report(
            db_path,
            support_report_dir,
            run_summary={
                'generated_at': generated_at,
                'email': {
                    'status': steps['email'],
                    'imported_count': email_result.get('imported_count', 0),
                },
                'telegram': {
                    'status': steps['telegram'],
                    'imported_count': telegram_result.get('imported_count', 0),
                },
            },
        )
        steps['health_report'] = 'completed'
        readiness_report_path = build_support_readiness_report(businessos_root, db_path, support_report_dir)
        steps['readiness_report'] = 'completed'

        dropbox_result: dict[str, Any]
        if mirror_config_path.exists():
            dropbox_result = run_dropbox_mirror(mirror_config_path)
            steps['dropbox_mirror'] = 'completed'
        else:
            dropbox_result = {'copied_count': 0, 'deleted_count': 0, 'copied': [], 'deleted': []}
            steps['dropbox_mirror'] = 'missing-config'
        if _should_notify_step('dropbox_mirror', steps['dropbox_mirror'], dropbox_result):
            _send_notification(
                _format_step_message('dropbox_mirror', steps['dropbox_mirror'], dropbox_result, businessos_root),
                'dropbox-step',
                attachment_paths=_dropbox_copied_attachment_paths(dropbox_result, businessos_root),
            )

        daily_summary_result = maybe_send_previous_day_summary(
            businessos_root=businessos_root,
            db_path=db_path,
            config_path=operator_updates_config_path,
            telegram_config_path=telegram_config_path,
            current_time=current_dt,
            send_update_fn=send_operator_update,
        )
        daily_notification = daily_summary_result.get('notification_result')
        if isinstance(daily_notification, dict):
            notification_results.append(daily_notification)

        completion_message = _format_completion_message(
            run_id=run_id,
            email_result=email_result,
            telegram_result=telegram_result,
            document_result=document_result,
            dropbox_result=dropbox_result,
            daily_summary_result=daily_summary_result,
            businessos_root=businessos_root,
            health_report_path=health_report_path,
            readiness_report_path=readiness_report_path,
            task_dashboard_path=task_dashboard_path,
            finance_reports=finance_reports,
        )
        _send_notification(
            completion_message,
            'run-completed',
            attachment_paths=_completion_attachment_paths(
                businessos_root=businessos_root,
                dropbox_result=dropbox_result,
                health_report_path=health_report_path,
                readiness_report_path=readiness_report_path,
                task_dashboard_path=task_dashboard_path,
                finance_reports=finance_reports,
            ),
        )

        result = {
            'generated_at': generated_at,
            'pipeline_run_id': run_id,
            'businessos_root': str(businessos_root),
            'db_path': str(db_path),
            'email': email_result,
            'telegram': telegram_result,
            'document_intake': document_result,
            'health_report_path': str(health_report_path),
            'readiness_report_path': str(readiness_report_path),
            'task_dashboard_path': str(task_dashboard_path),
            'finance_summary_path': str(finance_reports['finance_summary_path']),
            'deductible_summary_path': str(finance_reports['deductible_summary_path']),
            'dropbox_mirror': dropbox_result,
            'steps': steps,
            'operator_notifications': _summarize_notifications(notification_results),
            'daily_summary': daily_summary_result,
        }
        record_pipeline_run_completion(
            db_path=db_path,
            run_id=run_id,
            completed_at=generated_at,
            status='completed',
            summary={
                'email': email_result,
                'telegram': telegram_result,
                'document_intake': document_result,
                'dropbox_mirror': dropbox_result,
                'steps': steps,
                'daily_summary': {
                    'status': daily_summary_result.get('status'),
                    'report_date': daily_summary_result.get('report_date'),
                },
                'operator_notifications': result['operator_notifications'],
            },
        )
        return result
    except Exception as exc:
        failed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        try:
            _send_notification(
                f'BusinessOS run failed\nRun: {run_id}\nError: {exc}',
                'run-failed',
            )
        except Exception:
            pass
        record_pipeline_run_completion(
            db_path=db_path,
            run_id=run_id,
            completed_at=failed_at,
            status='failed',
            summary={'steps': steps, 'error': str(exc)},
        )
        raise


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description='Run the BusinessOS support ingestion pipeline.')
    parser.add_argument('--skip-email', action='store_true')
    parser.add_argument('--skip-telegram', action='store_true')
    args = parser.parse_args()
    result = run_pipeline(skip_email=args.skip_email, skip_telegram=args.skip_telegram)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
