from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
import sqlite3
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import yaml


DEFAULT_TIMEZONE = 'America/New_York'
DEFAULT_MORNING_DIGEST_LOCAL_TIME = '08:00'
DEFAULT_NOTIFICATION_ATTACHMENT_LIMIT = 10


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _coerce_datetime(value: str | datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _table_exists(con: sqlite3.Connection, table_name: str) -> bool:
    row = con.execute(
        "select 1 from sqlite_master where type = 'table' and name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _table_columns(con: sqlite3.Connection, table_name: str) -> set[str]:
    rows = con.execute(f'pragma table_info({table_name})').fetchall()
    names: set[str] = set()
    for row in rows:
        if isinstance(row, sqlite3.Row):
            names.add(row['name'])
        else:
            names.add(row[1])
    return names


def _ensure_columns(con: sqlite3.Connection, table_name: str, columns: dict[str, str]) -> None:
    existing = _table_columns(con, table_name)
    for name, definition in columns.items():
        if name not in existing:
            con.execute(f'alter table {table_name} add column {name} {definition}')


def _parse_morning_time(value: str | None) -> time:
    raw = (value or DEFAULT_MORNING_DIGEST_LOCAL_TIME).strip()
    hour_text, minute_text = (raw.split(':', 1) + ['00'])[:2]
    return time(hour=int(hour_text), minute=int(minute_text))


def _load_yaml_dict(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
    if not isinstance(payload, dict):
        raise ValueError(f'Expected mapping in {path}')
    return payload


def _load_operator_updates_config(config_path: str | Path | None) -> dict[str, Any]:
    if config_path is None:
        return {}
    return _load_yaml_dict(Path(config_path))


def _load_telegram_accounts(config_path: str | Path) -> list[dict[str, Any]]:
    payload = _load_yaml_dict(Path(config_path))
    accounts = payload.get('accounts') or []
    if not isinstance(accounts, list):
        raise ValueError('telegram-sources.yaml must contain an accounts list')
    return [account for account in accounts if isinstance(account, dict)]


class TelegramBotAPI:
    def send_message(self, token: str, chat_id: str, text: str) -> dict[str, Any]:
        params = {'chat_id': str(chat_id), 'text': text}
        url = f'https://api.telegram.org/bot{token}/sendMessage?{urlencode(params)}'
        with urlopen(url, timeout=30) as response:  # pragma: no cover - exercised through live usage
            payload = json.load(response)
        return payload['result']

    def send_document(
        self,
        token: str,
        chat_id: str,
        file_path: str | Path,
        caption: str | None = None,
    ) -> dict[str, Any]:
        path = Path(file_path)
        content_type = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
        boundary = f'HermesBoundary{hashlib.sha1(f"{path}:{chat_id}".encode("utf-8")).hexdigest()}'
        body = _multipart_form_data(
            boundary=boundary,
            fields={
                'chat_id': str(chat_id),
                **({'caption': caption} if caption else {}),
            },
            files={
                'document': (path.name, path.read_bytes(), content_type),
            },
        )
        request = Request(
            f'https://api.telegram.org/bot{token}/sendDocument',
            data=body,
            headers={'Content-Type': f'multipart/form-data; boundary={boundary}'},
            method='POST',
        )
        with urlopen(request, timeout=60) as response:  # pragma: no cover - exercised through live usage
            payload = json.load(response)
        return payload['result']


def _multipart_form_data(
    *,
    boundary: str,
    fields: dict[str, str],
    files: dict[str, tuple[str, bytes, str]],
) -> bytes:
    body = bytearray()
    boundary_bytes = boundary.encode('utf-8')

    for name, value in fields.items():
        body.extend(b'--' + boundary_bytes + b'\r\n')
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode('utf-8'))
        body.extend(str(value).encode('utf-8'))
        body.extend(b'\r\n')

    for name, (filename, content, content_type) in files.items():
        body.extend(b'--' + boundary_bytes + b'\r\n')
        body.extend(
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode('utf-8')
        )
        body.extend(f'Content-Type: {content_type}\r\n\r\n'.encode('utf-8'))
        body.extend(content)
        body.extend(b'\r\n')

    body.extend(b'--' + boundary_bytes + b'--\r\n')
    return bytes(body)


def _relative_label(path: str | Path, businessos_root: str | Path) -> str:
    raw_path = Path(path)
    root = Path(businessos_root)
    try:
        return str(raw_path.resolve().relative_to(root.resolve()))
    except Exception:
        return raw_path.name


def _normalize_attachment_paths(
    attachment_paths: list[str | Path] | None,
    *,
    limit: int = DEFAULT_NOTIFICATION_ATTACHMENT_LIMIT,
) -> list[Path]:
    normalized: list[Path] = []
    seen: set[str] = set()
    for value in attachment_paths or []:
        if value in (None, ''):
            continue
        path = Path(value)
        if not path.exists() or not path.is_file():
            continue
        key = str(path.resolve())
        if key in seen:
            continue
        normalized.append(path)
        seen.add(key)
        if len(normalized) >= limit:
            break
    return normalized


def ensure_operator_update_tables(con: sqlite3.Connection) -> None:
    cur = con.cursor()
    cur.executescript(
        '''
        create table if not exists pipeline_runs (
            id text primary key,
            started_at text not null,
            completed_at text,
            status text not null,
            summary_json text,
            created_at text not null,
            updated_at text not null
        );
        create table if not exists operator_notifications (
            id text primary key,
            notification_type text not null,
            source_account text,
            related_run_id text,
            report_date text,
            body text not null,
            status text not null,
            external_message_id text,
            sent_at text,
            created_at text not null
        );
        create table if not exists daily_summary_reports (
            report_date text primary key,
            timezone_name text not null,
            window_start text not null,
            window_end text not null,
            generated_at text not null,
            report_path text not null,
            metrics_json text not null,
            summary_markdown text not null,
            telegram_source_account text,
            telegram_sent_at text
        );
        '''
    )
    _ensure_columns(
        con,
        'pipeline_runs',
        {
            'completed_at': 'text',
            'status': "text not null default 'running'",
            'summary_json': 'text',
            'created_at': 'text',
            'updated_at': 'text',
            'trigger_source': 'text',
            'notification_summary_json': 'text',
            'daily_summary_status': 'text',
            'daily_summary_report_date': 'text',
        },
    )
    _ensure_columns(
        con,
        'operator_notifications',
        {
            'source_account': 'text',
            'related_run_id': 'text',
            'report_date': 'text',
            'external_message_id': 'text',
            'sent_at': 'text',
        },
    )
    _ensure_columns(
        con,
        'daily_summary_reports',
        {
            'telegram_source_account': 'text',
            'telegram_sent_at': 'text',
        },
    )
    con.commit()


def _db_connect(db_path: str | Path) -> sqlite3.Connection:
    con = sqlite3.connect(Path(db_path))
    con.row_factory = sqlite3.Row
    ensure_operator_update_tables(con)
    return con


def record_pipeline_run_start(db_path: str | Path, run_id: str, started_at: str) -> None:
    con = _db_connect(db_path)
    try:
        con.execute(
            '''
            insert into pipeline_runs (
                id,
                started_at,
                status,
                summary_json,
                trigger_source,
                created_at,
                updated_at
            )
            values (?, ?, 'running', ?, ?, ?, ?)
            on conflict(id) do update set
                started_at = excluded.started_at,
                status = excluded.status,
                summary_json = excluded.summary_json,
                trigger_source = excluded.trigger_source,
                updated_at = excluded.updated_at
            ''',
            (run_id, started_at, '{}', 'run_support_pipeline', started_at, started_at),
        )
        con.commit()
    finally:
        con.close()


def record_pipeline_run_completion(
    db_path: str | Path,
    run_id: str,
    completed_at: str,
    status: str,
    summary: dict[str, Any],
) -> None:
    con = _db_connect(db_path)
    try:
        daily_summary = summary.get('daily_summary') if isinstance(summary, dict) else None
        operator_notifications = summary.get('operator_notifications') if isinstance(summary, dict) else None
        con.execute(
            '''
            update pipeline_runs
            set completed_at = ?,
                status = ?,
                summary_json = ?,
                notification_summary_json = ?,
                daily_summary_status = ?,
                daily_summary_report_date = ?,
                updated_at = ?
            where id = ?
            ''',
            (
                completed_at,
                status,
                json.dumps(summary, sort_keys=True),
                json.dumps(operator_notifications, sort_keys=True) if operator_notifications is not None else None,
                (daily_summary or {}).get('status') if isinstance(daily_summary, dict) else None,
                (daily_summary or {}).get('report_date') if isinstance(daily_summary, dict) else None,
                completed_at,
                run_id,
            ),
        )
        con.commit()
    finally:
        con.close()


def _resolve_chat_id_from_db(db_path: str | Path, source_account: str) -> str | None:
    con = _db_connect(db_path)
    try:
        if _table_exists(con, 'source_accounts'):
            row = con.execute(
                'select external_ref from source_accounts where id = ? and coalesce(external_ref, "") != ""',
                (source_account,),
            ).fetchone()
            if row and row['external_ref']:
                return str(row['external_ref'])
        if _table_exists(con, 'communication_threads') and _table_exists(con, 'communication_messages'):
            row = con.execute(
                '''
                select m.source_message_id
                from communication_messages m
                join communication_threads t on t.id = m.thread_id
                where t.source_account = ? and coalesce(m.source_message_id, '') != ''
                order by coalesce(m.sent_at, m.created_at, t.updated_at) desc
                limit 1
                ''',
                (source_account,),
            ).fetchone()
            if row and row['source_message_id']:
                source_message_id = str(row['source_message_id'])
                if '-' in source_message_id:
                    return source_message_id.rsplit('-', 1)[0]
    finally:
        con.close()
    return None


def _resolve_notification_account(
    *,
    db_path: str | Path,
    telegram_config_path: str | Path,
    configured_source_account: str,
) -> dict[str, Any] | None:
    for account in _load_telegram_accounts(telegram_config_path):
        if account.get('id') == configured_source_account:
            resolved = dict(account)
            if not str(resolved.get('chat_id') or '').strip():
                resolved['chat_id'] = _resolve_chat_id_from_db(db_path, configured_source_account) or ''
            return resolved
    return None


def send_operator_update(
    *,
    businessos_root: str | Path,
    db_path: str | Path,
    text: str,
    notification_type: str,
    config_path: str | Path | None,
    telegram_config_path: str | Path,
    source_account: str | None = None,
    related_run_id: str | None = None,
    report_date: str | None = None,
    current_time: str | datetime | None = None,
    telegram_api: Any | None = None,
    attachment_paths: list[str | Path] | None = None,
) -> dict[str, Any]:
    now_iso = _coerce_datetime(current_time).astimezone(timezone.utc).replace(microsecond=0).isoformat()
    config = _load_operator_updates_config(config_path)
    if not config:
        return {'status': 'missing-config', 'sent': False}
    if not config.get('enabled', False):
        return {'status': 'disabled', 'sent': False}

    configured_source_account = source_account or config.get('telegram_source_account')
    if not configured_source_account:
        return {'status': 'missing-source-account', 'sent': False}

    account = _resolve_notification_account(
        db_path=db_path,
        telegram_config_path=telegram_config_path,
        configured_source_account=configured_source_account,
    )
    if account is None:
        return {'status': 'missing-account', 'sent': False, 'source_account': configured_source_account}

    token_env = str(account.get('bot_token_env') or '').strip()
    token = os.environ.get(token_env) if token_env else None
    if not token:
        result = {'status': 'missing-env', 'sent': False, 'source_account': configured_source_account}
        _record_notification(
            db_path=db_path,
            notification_type=notification_type,
            source_account=configured_source_account,
            related_run_id=related_run_id,
            report_date=report_date,
            body=text,
            status=result['status'],
            external_message_id=None,
            sent_at=None,
            created_at=now_iso,
        )
        return result

    chat_id = str(account.get('chat_id') or '').strip()
    if not chat_id:
        result = {'status': 'missing-chat-id', 'sent': False, 'source_account': configured_source_account}
        _record_notification(
            db_path=db_path,
            notification_type=notification_type,
            source_account=configured_source_account,
            related_run_id=related_run_id,
            report_date=report_date,
            body=text,
            status=result['status'],
            external_message_id=None,
            sent_at=None,
            created_at=now_iso,
        )
        return result

    telegram_api = telegram_api or TelegramBotAPI()
    payload = telegram_api.send_message(token=token, chat_id=chat_id, text=text)
    message_id = str(payload.get('message_id') or '') or None
    attachment_message_ids: list[str] = []
    attachment_errors: list[dict[str, str]] = []
    for attachment_path in _normalize_attachment_paths(attachment_paths):
        try:
            attachment_payload = telegram_api.send_document(
                token=token,
                chat_id=chat_id,
                file_path=attachment_path,
                caption=f'BusinessOS document: {_relative_label(attachment_path, businessos_root)}',
            )
            attachment_message_id = str(attachment_payload.get('message_id') or '').strip()
            if attachment_message_id:
                attachment_message_ids.append(attachment_message_id)
        except Exception as exc:
            attachment_errors.append({'path': str(attachment_path), 'error': str(exc)})
    sent_at = now_iso
    _record_notification(
        db_path=db_path,
        notification_type=notification_type,
        source_account=configured_source_account,
        related_run_id=related_run_id,
        report_date=report_date,
        body=text,
        status='sent',
        external_message_id=message_id,
        sent_at=sent_at,
        created_at=now_iso,
    )
    return {
        'status': 'sent',
        'sent': True,
        'source_account': configured_source_account,
        'chat_id': chat_id,
        'message_id': message_id,
        'attachment_count': len(attachment_message_ids),
        'attachment_message_ids': attachment_message_ids,
        'attachment_errors': attachment_errors,
    }


def _record_notification(
    *,
    db_path: str | Path,
    notification_type: str,
    source_account: str | None,
    related_run_id: str | None,
    report_date: str | None,
    body: str,
    status: str,
    external_message_id: str | None,
    sent_at: str | None,
    created_at: str,
) -> None:
    body_hash = hashlib.sha1(body.encode('utf-8')).hexdigest()[:8]
    notification_id = f"{notification_type}-{slugify(source_account or 'operator')}-{created_at.replace(':', '').replace('+', '').replace('-', '')}-{body_hash}"
    con = _db_connect(db_path)
    try:
        con.execute(
            '''
            insert into operator_notifications (
                id, notification_type, source_account, related_run_id, report_date,
                body, status, external_message_id, sent_at, created_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                notification_id,
                notification_type,
                source_account,
                related_run_id,
                report_date,
                body,
                status,
                external_message_id,
                sent_at,
                created_at,
            ),
        )
        con.commit()
    finally:
        con.close()


def slugify(value: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', (value or '').lower()).strip('-') or 'item'


def _summary_window(current_time: str | datetime | None, timezone_name: str) -> tuple[date, datetime, datetime, datetime]:
    now_utc = _coerce_datetime(current_time).astimezone(timezone.utc)
    local_now = now_utc.astimezone(ZoneInfo(timezone_name))
    report_date = local_now.date() - timedelta(days=1)
    start_local = datetime.combine(report_date, time(0, 0), tzinfo=ZoneInfo(timezone_name))
    end_local = start_local + timedelta(days=1)
    return report_date, start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc), local_now


def _metric_window_sql() -> str:
    return "datetime(coalesce(sent_at, created_at)) >= datetime(?) and datetime(coalesce(sent_at, created_at)) < datetime(?)"


def _document_window_sql() -> str:
    return "datetime(coalesce(created_at, document_date)) >= datetime(?) and datetime(coalesce(created_at, document_date)) < datetime(?)"


def build_previous_day_summary(
    *,
    businessos_root: str | Path,
    db_path: str | Path,
    current_time: str | datetime | None = None,
    timezone_name: str = DEFAULT_TIMEZONE,
) -> dict[str, Any]:
    businessos_root = Path(businessos_root)
    db_path = Path(db_path)
    report_date, start_utc, end_utc, _local_now = _summary_window(current_time, timezone_name)
    report_dir = businessos_root / '05_REPORTS' / 'daily'
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f'{report_date.isoformat()}-daily-summary.md'

    metrics: dict[str, Any] = {
        'pipeline_runs': 0,
        'pipeline_runs_completed': 0,
        'pipeline_runs_failed': 0,
        'email_imports': 0,
        'telegram_imports': 0,
        'document_inbox_processed': 0,
        'communication_messages': 0,
        'new_documents': 0,
        'expense_documents': 0,
        'expense_total': 0.0,
        'deductible_expense_total': 0.0,
        'new_tasks': 0,
        'completed_tasks': 0,
        'open_tasks': 0,
        'today_priorities': 0,
        'suggested_tasks': 0,
    }
    highlights: list[str] = []
    remaining_open_tasks: list[dict[str, Any]] = []
    todays_priorities: list[dict[str, Any]] = []
    suggested_follow_ups: list[dict[str, Any]] = []

    con = _db_connect(db_path)
    try:
        if _table_exists(con, 'pipeline_runs'):
            rows = con.execute(
                '''
                select id, status, summary_json
                from pipeline_runs
                where datetime(coalesce(started_at, created_at)) >= datetime(?)
                  and datetime(coalesce(started_at, created_at)) < datetime(?)
                order by datetime(coalesce(started_at, created_at)) asc
                ''',
                (start_utc.isoformat(), end_utc.isoformat()),
            ).fetchall()
            metrics['pipeline_runs'] = len(rows)
            for row in rows:
                status = str(row['status'] or '')
                if status == 'completed':
                    metrics['pipeline_runs_completed'] += 1
                elif status:
                    metrics['pipeline_runs_failed'] += 1
                summary = json.loads(row['summary_json'] or '{}') if row['summary_json'] else {}
                metrics['email_imports'] += int(summary.get('email', {}).get('imported_count', 0) or 0)
                metrics['telegram_imports'] += int(summary.get('telegram', {}).get('imported_count', 0) or 0)
                metrics['document_inbox_processed'] += int(summary.get('document_intake', {}).get('processed_count', 0) or 0)

        if _table_exists(con, 'communication_messages'):
            row = con.execute(
                f'select count(*) as count from communication_messages where {_metric_window_sql()}',
                (start_utc.isoformat(), end_utc.isoformat()),
            ).fetchone()
            metrics['communication_messages'] = int(row['count'] or 0) if row else 0

        if _table_exists(con, 'documents'):
            row = con.execute(
                f'select count(*) as count from documents where {_document_window_sql()}',
                (start_utc.isoformat(), end_utc.isoformat()),
            ).fetchone()
            metrics['new_documents'] = int(row['count'] or 0) if row else 0

            row = con.execute(
                f'''
                select count(*) as count, coalesce(sum(amount), 0) as total
                from documents
                where {_document_window_sql()} and coalesce(finance_direction, '') = 'expense'
                ''',
                (start_utc.isoformat(), end_utc.isoformat()),
            ).fetchone()
            metrics['expense_documents'] = int(row['count'] or 0) if row else 0
            metrics['expense_total'] = float(row['total'] or 0.0) if row else 0.0

        if _table_exists(con, 'documents') and _table_exists(con, 'expense_tax_treatment'):
            row = con.execute(
                f'''
                select coalesce(sum(d.amount), 0) as total
                from documents d
                join expense_tax_treatment e on e.document_id = d.id
                where {_document_window_sql().replace('coalesce(created_at, document_date)', 'coalesce(d.created_at, d.document_date)')}
                  and coalesce(d.finance_direction, '') = 'expense'
                  and coalesce(e.tax_relevance, '') = 'deductible'
                ''',
                (start_utc.isoformat(), end_utc.isoformat()),
            ).fetchone()
            metrics['deductible_expense_total'] = float(row['total'] or 0.0) if row else 0.0

        if _table_exists(con, 'task_items'):
            row = con.execute(
                'select count(*) as count from task_items where datetime(created_at) >= datetime(?) and datetime(created_at) < datetime(?)',
                (start_utc.isoformat(), end_utc.isoformat()),
            ).fetchone()
            metrics['new_tasks'] = int(row['count'] or 0) if row else 0

        if _table_exists(con, 'task_events'):
            row = con.execute(
                '''
                select count(*) as count
                from task_events
                where datetime(created_at) >= datetime(?) and datetime(created_at) < datetime(?)
                  and event_type = 'completed'
                ''',
                (start_utc.isoformat(), end_utc.isoformat()),
            ).fetchone()
            metrics['completed_tasks'] = int(row['count'] or 0) if row else 0

        if _table_exists(con, 'task_items'):
            remaining_open_tasks = [
                dict(row)
                for row in con.execute(
                    '''
                    select id, title, status, priority, reminder_at, due_at
                    from task_items
                    where status not in ('completed', 'cancelled')
                    order by
                        case when status = 'in_progress' then 0 else 1 end,
                        case priority when 'critical' then 0 when 'high' then 1 when 'medium' then 2 else 3 end,
                        coalesce(reminder_at, due_at, updated_at, created_at) asc
                    limit 8
                    '''
                ).fetchall()
            ]
            metrics['open_tasks'] = len(remaining_open_tasks)

        if _table_exists(con, 'daily_priorities'):
            todays_priorities = [
                dict(row)
                for row in con.execute(
                    '''
                    select focus_date, task_id, title, notes, status
                    from daily_priorities
                    where focus_date = ? and status = 'active'
                    order by created_at asc, id asc
                    limit 8
                    ''',
                    (_local_now.date().isoformat(),),
                ).fetchall()
            ]
            metrics['today_priorities'] = len(todays_priorities)

        if _table_exists(con, 'task_suggestions'):
            suggested_follow_ups = [
                dict(row)
                for row in con.execute(
                    '''
                    select title, rationale, category, assigned_queue, status
                    from task_suggestions
                    where status = 'suggested'
                    order by created_at desc, id desc
                    limit 8
                    '''
                ).fetchall()
            ]
            metrics['suggested_tasks'] = len(suggested_follow_ups)

        if _table_exists(con, 'documents'):
            for row in con.execute(
                f'''
                select document_type, vendor_name, amount
                from documents
                where {_document_window_sql()} and coalesce(finance_direction, '') = 'expense'
                order by datetime(coalesce(created_at, document_date)) desc
                limit 3
                ''',
                (start_utc.isoformat(), end_utc.isoformat()),
            ).fetchall():
                vendor = row['vendor_name'] or 'unknown vendor'
                amount = float(row['amount'] or 0.0)
                highlights.append(f'Expense recorded: {vendor} ${amount:,.2f} ({row["document_type"] or "document"})')

        if _table_exists(con, 'task_events'):
            for row in con.execute(
                '''
                select summary, event_type
                from task_events
                where datetime(created_at) >= datetime(?) and datetime(created_at) < datetime(?)
                order by datetime(created_at) desc
                limit 3
                ''',
                (start_utc.isoformat(), end_utc.isoformat()),
            ).fetchall():
                summary = str(row['summary'] or row['event_type'] or 'Task event').strip()
                highlights.append(f'Task event: {summary}')

        if _table_exists(con, 'communication_messages'):
            for row in con.execute(
                f'''
                select substr(coalesce(summary, text), 1, 120) as snippet
                from communication_messages
                where {_metric_window_sql()}
                order by datetime(coalesce(sent_at, created_at)) desc
                limit 3
                ''',
                (start_utc.isoformat(), end_utc.isoformat()),
            ).fetchall():
                snippet = str(row['snippet'] or '').strip()
                if snippet:
                    highlights.append(f'Communication captured: {snippet}')
    finally:
        con.close()

    lines = [
        f'# BusinessOS Daily Summary — {report_date.isoformat()}',
        '',
        f'Generated: {_coerce_datetime(current_time).astimezone(timezone.utc).replace(microsecond=0).isoformat()}',
        f'Timezone: {timezone_name}',
        f'Window: {start_utc.isoformat()} to {end_utc.isoformat()} (UTC)',
        '',
        '## Pipeline activity',
        '',
        f'- Pipeline runs: {metrics["pipeline_runs"]}',
        f'- Successful runs: {metrics["pipeline_runs_completed"]}',
        f'- Failed runs: {metrics["pipeline_runs_failed"]}',
        f'- Email imports: {metrics["email_imports"]}',
        f'- Telegram imports: {metrics["telegram_imports"]}',
        f'- Document inbox items processed: {metrics["document_inbox_processed"]}',
        '',
        '## Business activity captured',
        '',
        f'- New communication messages: {metrics["communication_messages"]}',
        f'- New documents: {metrics["new_documents"]}',
        f'- Expense documents: {metrics["expense_documents"]} totaling ${metrics["expense_total"]:,.2f}',
        f'- Deductible expense total: ${metrics["deductible_expense_total"]:,.2f}',
        f'- New tasks: {metrics["new_tasks"]}',
        f'- Completed tasks: {metrics["completed_tasks"]}',
        f'- Remaining open tasks: {metrics["open_tasks"]}',
        f'- Today priorities: {metrics["today_priorities"]}',
        f'- Suggested follow-up items: {metrics["suggested_tasks"]}',
        '',
        '## Highlights',
        '',
    ]
    if highlights:
        for item in highlights[:8]:
            lines.append(f'- {item}')
    else:
        lines.append('- No notable captured activity for the previous local day.')

    lines.extend(['', '## Remaining open work', ''])
    if remaining_open_tasks:
        for row in remaining_open_tasks:
            details = [str(row.get('id') or ''), str(row.get('status') or ''), str(row.get('priority') or '')]
            if row.get('title'):
                details.append(str(row['title']))
            if row.get('due_at'):
                details.append(f"due {row['due_at']}")
            elif row.get('reminder_at'):
                details.append(f"reminder {row['reminder_at']}")
            lines.append('- ' + ' | '.join(part for part in details if part))
    else:
        lines.append('- No remaining open tasks.')

    lines.extend(['', "## Today\'s priorities", ''])
    if todays_priorities:
        for row in todays_priorities:
            details = [str(row.get('task_id') or ''), str(row.get('title') or '')]
            if row.get('notes'):
                details.append(str(row['notes']))
            lines.append('- ' + ' | '.join(part for part in details if part))
    else:
        lines.append('- No priorities recorded for today yet.')

    lines.extend(['', '## Suggested follow-up items', ''])
    if suggested_follow_ups:
        for row in suggested_follow_ups:
            details = [str(row.get('category') or ''), str(row.get('assigned_queue') or ''), str(row.get('title') or '')]
            if row.get('rationale'):
                details.append(str(row['rationale']))
            lines.append('- ' + ' | '.join(part for part in details if part))
    else:
        lines.append('- No suggested follow-up items currently pending.')

    summary_markdown = '\n'.join(lines) + '\n'
    report_path.write_text(summary_markdown, encoding='utf-8')

    con = _db_connect(db_path)
    try:
        con.execute(
            '''
            insert into daily_summary_reports (
                report_date, timezone_name, window_start, window_end, generated_at,
                report_path, metrics_json, summary_markdown, telegram_source_account, telegram_sent_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, coalesce((select telegram_source_account from daily_summary_reports where report_date = ?), null), coalesce((select telegram_sent_at from daily_summary_reports where report_date = ?), null))
            on conflict(report_date) do update set
                timezone_name = excluded.timezone_name,
                window_start = excluded.window_start,
                window_end = excluded.window_end,
                generated_at = excluded.generated_at,
                report_path = excluded.report_path,
                metrics_json = excluded.metrics_json,
                summary_markdown = excluded.summary_markdown
            ''',
            (
                report_date.isoformat(),
                timezone_name,
                start_utc.isoformat(),
                end_utc.isoformat(),
                _coerce_datetime(current_time).astimezone(timezone.utc).replace(microsecond=0).isoformat(),
                str(report_path),
                json.dumps(metrics, sort_keys=True),
                summary_markdown,
                report_date.isoformat(),
                report_date.isoformat(),
            ),
        )
        con.commit()
    finally:
        con.close()

    return {
        'status': 'generated',
        'report_date': report_date.isoformat(),
        'report_path': str(report_path),
        'metrics': metrics,
        'summary_markdown': summary_markdown,
    }


def maybe_send_previous_day_summary(
    *,
    businessos_root: str | Path,
    db_path: str | Path,
    config_path: str | Path | None,
    telegram_config_path: str | Path,
    current_time: str | datetime | None = None,
    telegram_api: Any | None = None,
    send_update_fn: Any | None = None,
) -> dict[str, Any]:
    config = _load_operator_updates_config(config_path)
    if not config:
        return {'status': 'missing-config', 'sent': False, 'report_path': None}
    if not config.get('enabled', False):
        return {'status': 'disabled', 'sent': False, 'report_path': None}
    if not config.get('send_daily_summary', True):
        return {'status': 'disabled-daily-summary', 'sent': False, 'report_path': None}

    timezone_name = str(config.get('timezone') or DEFAULT_TIMEZONE)
    digest_time = _parse_morning_time(config.get('morning_digest_local_time'))
    report_date, _start_utc, _end_utc, local_now = _summary_window(current_time, timezone_name)
    if local_now.timetz().replace(tzinfo=None) < digest_time:
        return {'status': 'not-due', 'sent': False, 'report_date': report_date.isoformat(), 'report_path': None}

    con = _db_connect(db_path)
    try:
        row = con.execute(
            'select report_path, telegram_sent_at from daily_summary_reports where report_date = ?',
            (report_date.isoformat(),),
        ).fetchone()
    finally:
        con.close()
    if row and row['telegram_sent_at']:
        return {
            'status': 'already-sent',
            'sent': False,
            'report_date': report_date.isoformat(),
            'report_path': row['report_path'],
        }

    summary = build_previous_day_summary(
        businessos_root=businessos_root,
        db_path=db_path,
        current_time=current_time,
        timezone_name=timezone_name,
    )

    send_update_fn = send_update_fn or send_operator_update
    notification_result = send_update_fn(
        businessos_root=businessos_root,
        db_path=db_path,
        text=summary['summary_markdown'],
        notification_type='daily-summary',
        config_path=config_path,
        telegram_config_path=telegram_config_path,
        source_account=config.get('telegram_source_account'),
        related_run_id=None,
        report_date=summary['report_date'],
        current_time=current_time,
        telegram_api=telegram_api,
    )

    if notification_result.get('status') == 'sent':
        con = _db_connect(db_path)
        try:
            con.execute(
                '''
                update daily_summary_reports
                set telegram_source_account = ?, telegram_sent_at = ?
                where report_date = ?
                ''',
                (
                    config.get('telegram_source_account'),
                    _coerce_datetime(current_time).astimezone(timezone.utc).replace(microsecond=0).isoformat(),
                    summary['report_date'],
                ),
            )
            con.commit()
        finally:
            con.close()
        return {
            'status': 'sent',
            'sent': True,
            'report_date': summary['report_date'],
            'report_path': summary['report_path'],
            'notification_result': notification_result,
        }

    return {
        'status': 'generated',
        'sent': False,
        'report_date': summary['report_date'],
        'report_path': summary['report_path'],
        'notification_result': notification_result,
    }
