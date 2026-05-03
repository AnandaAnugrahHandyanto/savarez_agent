from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

import yaml

from business_ops_core import apply_task_command, ensure_business_ops_tables, parse_task_command, record_task_suggestion


class TelegramAPI:
    def get_me(self, token: str) -> dict[str, Any]:
        url = f'https://api.telegram.org/bot{token}/getMe'
        with urlopen(url, timeout=30) as response:  # pragma: no cover - exercised through integration usage
            payload = json.load(response)
        return payload['result']

    def get_updates(
        self,
        token: str,
        offset: int | None = None,
        allowed_updates: list[str] | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {'timeout': 0}
        if offset is not None:
            params['offset'] = offset
        if allowed_updates is not None:
            params['allowed_updates'] = json.dumps(allowed_updates)
        url = f'https://api.telegram.org/bot{token}/getUpdates?{urlencode(params)}'
        with urlopen(url, timeout=30) as response:  # pragma: no cover - exercised through integration usage
            return json.load(response)


def get_me(token: str) -> dict[str, Any]:
    return TelegramAPI().get_me(token)


def warn_if_group_privacy_blocks_messages(account: dict[str, Any], token: str, telegram_api: Any | None = None) -> None:
    chat_id = str(account.get('chat_id') or '')
    if not chat_id.startswith('-'):
        return

    telegram_api = telegram_api or TelegramAPI()
    me = telegram_api.get_me(token)
    if me.get('can_read_all_group_messages'):
        return

    print(
        (
            f"Telegram privacy mode may block ordinary group messages for {account.get('id')} "
            f"(chat_id={chat_id}). Disable BotFather privacy mode or grant broader group access."
        ),
        file=sys.stderr,
    )


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _ensure_support_tables(con: sqlite3.Connection) -> None:
    cur = con.cursor()
    cur.executescript(
        '''
        create table if not exists source_accounts (
            id text primary key,
            source_type text not null,
            external_ref text,
            app_id text,
            config_json text,
            active integer default 1,
            created_at text default current_timestamp,
            updated_at text default current_timestamp
        );
        create table if not exists ingestion_checkpoints (
            source_type text not null,
            source_account text not null,
            checkpoint_value text,
            updated_at text default current_timestamp,
            primary key (source_type, source_account)
        );
        create table if not exists communication_threads (
            id text primary key,
            source_channel text not null,
            app_id text,
            customer_handle text,
            subject text,
            status text default 'open',
            priority text,
            sentiment text,
            latest_summary text,
            suggested_response text,
            escalation_flag integer default 0,
            created_at text default current_timestamp,
            updated_at text default current_timestamp,
            source_account text,
            first_seen_at text,
            last_seen_at text,
            last_customer_message_at text,
            unread_count integer default 0,
            needs_human_reply integer default 0,
            assigned_queue text
        );
        create table if not exists communication_messages (
            id text primary key,
            thread_id text not null,
            source_message_id text,
            sender_handle text,
            sender_role text default 'customer',
            sent_at text,
            text text not null,
            summary text,
            category text,
            priority text,
            sentiment text,
            app_id text,
            platform text,
            suggested_response text,
            response_status text default 'draft',
            created_at text default current_timestamp,
            raw_path text,
            normalized_path text,
            attachment_count integer default 0,
            in_reply_to text,
            references_header text,
            normalized_hash text,
            dedupe_key text
        );
        create table if not exists feedback_items (
            id text primary key,
            source_channel text not null,
            source_item_id text,
            app_id text,
            thread_id text,
            message_id text,
            platform text,
            app_version text,
            rating integer,
            title text,
            body text not null,
            summary text,
            category text,
            priority text,
            sentiment text,
            duplicate_group_id text,
            bug_candidate_id text,
            feature_candidate_id text,
            launch_blocker_flag integer default 0,
            planning_status text default 'new',
            created_at text default current_timestamp,
            source_account text,
            theme text,
            fingerprint text,
            first_seen_at text,
            last_seen_at text,
            customer_impact_score integer default 0
        );
        '''
    )
    con.commit()


def _load_accounts(config_path: Path) -> list[dict[str, Any]]:
    payload = yaml.safe_load(config_path.read_text(encoding='utf-8')) or {}
    accounts = payload.get('accounts') or []
    if not isinstance(accounts, list):
        raise ValueError('telegram-sources.yaml must contain an accounts list')
    return accounts


def _get_checkpoint(con: sqlite3.Connection, source_type: str, source_account: str) -> str | None:
    row = con.execute(
        'select checkpoint_value from ingestion_checkpoints where source_type = ? and source_account = ?',
        (source_type, source_account),
    ).fetchone()
    return row[0] if row else None


def _set_checkpoint(con: sqlite3.Connection, source_type: str, source_account: str, checkpoint_value: str) -> None:
    con.execute(
        '''
        insert into ingestion_checkpoints (source_type, source_account, checkpoint_value, updated_at)
        values (?, ?, ?, ?)
        on conflict(source_type, source_account)
        do update set checkpoint_value = excluded.checkpoint_value, updated_at = excluded.updated_at
        ''',
        (source_type, source_account, checkpoint_value, _utc_now_iso()),
    )


def _upsert_source_account(con: sqlite3.Connection, account: dict[str, Any]) -> None:
    config_json = json.dumps(
        {
            'chat_id': account.get('chat_id'),
            'import_type': 'telegram-live-poller',
            'lane': account.get('lane'),
            'live_poll': account.get('live_poll', True),
            'export_path': account.get('export_path'),
        },
        sort_keys=True,
    )
    con.execute(
        '''
        insert into source_accounts (id, source_type, external_ref, app_id, config_json, active, updated_at)
        values (?, 'telegram', ?, ?, ?, 1, ?)
        on conflict(id) do update set
            external_ref = excluded.external_ref,
            app_id = excluded.app_id,
            config_json = excluded.config_json,
            active = 1,
            updated_at = excluded.updated_at
        ''',
        (
            account['id'],
            str(account.get('chat_id') or ''),
            account.get('app_id'),
            config_json,
            _utc_now_iso(),
        ),
    )


def _message_exists(con: sqlite3.Connection, message_id: str) -> bool:
    row = con.execute('select 1 from communication_messages where id = ?', (message_id,)).fetchone()
    return row is not None


def _sent_at_from_unix(timestamp: int | float | None) -> str:
    if timestamp is None:
        return _utc_now_iso()
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).replace(microsecond=0).isoformat()


def _classification_label(category: str | None, assigned_queue: str | None, mailbox_role: str | None = None, task_operation: Any | None = None) -> str:
    category_value = str(category or '').strip()
    queue_value = str(assigned_queue or mailbox_role or 'unassigned').strip() or 'unassigned'
    if task_operation:
        primary = 'todo'
        semantic = 'task-capture'
    elif category_value == 'business-expense-record':
        primary = 'expense'
        semantic = category_value
    elif category_value == 'business-identity-record':
        primary = 'business-identity'
        semantic = category_value
    elif category_value == 'billing' or queue_value == 'billing-support':
        primary = 'billing'
        semantic = category_value or 'billing'
    elif 'legal' in category_value or queue_value == 'legal-review':
        primary = 'legal'
        semantic = category_value or 'legal'
    elif 'privacy' in category_value or queue_value == 'privacy-review':
        primary = 'privacy'
        semantic = category_value or 'privacy'
    elif category_value in {'operator-command', 'operator-note'} or queue_value == 'operator-control':
        primary = 'operator'
        semantic = category_value or 'operator'
    elif category_value == 'internal-test':
        primary = 'internal-test'
        semantic = category_value
    else:
        primary = 'support'
        semantic = category_value or 'support-request'
    return f'{primary} / {semantic} / {queue_value}'


def _sender_handle(message: dict[str, Any]) -> str:
    sender = message.get('from') or {}
    username = sender.get('username')
    if username:
        return f'@{username}'
    first_name = str(sender.get('first_name') or '').strip()
    last_name = str(sender.get('last_name') or '').strip()
    full_name = ' '.join(part for part in [first_name, last_name] if part).strip()
    if full_name:
        return full_name
    return f"user{sender.get('id', 'unknown')}"


def _attachment_manifest(message: dict[str, Any]) -> list[dict[str, Any]]:
    photo_sizes = message.get('photo') or []
    if not photo_sizes:
        return []
    best = photo_sizes[-1]
    return [
        {
            'filename': f"photo-{best.get('file_unique_id', 'unknown')}.jpg",
            'content_type': 'image/jpeg',
            'size_bytes': best.get('file_size'),
            'file_id': best.get('file_id'),
            'file_unique_id': best.get('file_unique_id'),
            'kind': 'photo',
        }
    ]


def _is_operator_message(account: dict[str, Any], message: dict[str, Any]) -> bool:
    sender = message.get('from') or {}
    username = str(sender.get('username') or '').lower()
    sender_id = sender.get('id')
    operator_user_ids = {int(value) for value in account.get('operator_user_ids', []) or []}
    operator_usernames = {str(value).lower() for value in account.get('operator_usernames', []) or []}
    return (sender_id in operator_user_ids) or (username in operator_usernames)


def _classify_telegram_message(account: dict[str, Any], message: dict[str, Any], sender_handle: str, text: str) -> dict[str, Any]:
    combined = f"{message.get('chat', {}).get('title', '')} {text}".strip().lower()
    is_operator = _is_operator_message(account, message)
    is_test = 'test' in combined
    lane = str(account.get('lane') or '').lower()
    task_command = parse_task_command(text=text)

    if lane == 'operator-control':
        command_like = bool(task_command) or text.strip().startswith('/')
        return {
            'category': 'internal-test' if is_test else ('operator-command' if command_like else 'operator-note'),
            'priority': 'low' if is_test else ('medium' if command_like else 'low'),
            'sentiment': 'neutral',
            'assigned_queue': 'operator-control',
            'needs_human_reply': 0,
            'theme': 'operator-control',
            'suggested_response': 'Operator-control message captured for BusinessOS. This lane is not customer support and does not require a customer reply.',
            'thread_suffix': '-operator-control',
        }
    if is_operator and is_test:
        return {
            'category': 'internal-test',
            'priority': 'low',
            'sentiment': 'neutral',
            'assigned_queue': 'admin',
            'needs_human_reply': 0,
            'theme': 'internal-test',
            'suggested_response': 'Administrative/vendor notification captured for BusinessOS review. No customer reply is needed by default.',
            'thread_suffix': '-internal-test',
        }
    if task_command:
        return {
            'category': 'task-capture',
            'priority': 'medium',
            'sentiment': 'neutral',
            'assigned_queue': 'operator-review',
            'needs_human_reply': 0,
            'theme': 'task-capture',
            'suggested_response': 'Task command captured for BusinessOS operator review and task creation. No customer reply is needed by default.',
            'thread_suffix': '',
        }
    if any(keyword in combined for keyword in ('refund', 'charged', 'billing')):
        return {
            'category': 'billing',
            'priority': 'high',
            'sentiment': 'negative',
            'assigned_queue': 'billing-support',
            'needs_human_reply': 1,
            'theme': 'subscriptions',
            'suggested_response': f'Hi {sender_handle}, thanks for contacting our billing team. We\'re reviewing the charge and refund details now and will follow up with the next steps shortly.',
            'thread_suffix': '',
        }
    if any(keyword in combined for keyword in ('crash', 'hang', 'freeze', 'bug')):
        return {
            'category': 'support-request',
            'priority': 'high',
            'sentiment': 'negative',
            'assigned_queue': 'urgent',
            'needs_human_reply': 1,
            'theme': 'support-request',
            'suggested_response': f'Hi {sender_handle}, thanks for contacting our support team. We\'ve logged this issue and would like to confirm your app version and device so we can investigate quickly.',
            'thread_suffix': '',
        }
    return {
        'category': 'support-request',
        'priority': 'medium',
        'sentiment': 'neutral' if text else 'neutral',
        'assigned_queue': 'general',
        'needs_human_reply': 1,
        'theme': 'support-request',
        'suggested_response': f'Hi {sender_handle}, thanks for reaching out. We\'ve received your message and will follow up with the next steps shortly.',
        'thread_suffix': '',
    }


def poll_telegram_updates(
    businessos_root: str | Path | None = None,
    db_path: str | Path | None = None,
    config_path: str | Path | None = None,
    source_account: str | None = None,
    telegram_api: Any | None = None,
) -> dict[str, Any]:
    businessos_root = Path(businessos_root or Path(__file__).resolve().parents[2])
    db_path = Path(db_path or businessos_root / '03_DATA' / 'db' / 'businessos.db')
    config_path = Path(config_path or businessos_root / '04_AUTOMATIONS' / 'configs' / 'telegram-sources.yaml')
    telegram_api = telegram_api or TelegramAPI()

    if not config_path.exists():
        return {'imported_count': 0, 'accounts': {}, 'status': 'missing-config'}

    accounts = _load_accounts(config_path)
    if source_account:
        accounts = [account for account in accounts if account.get('id') == source_account]
    else:
        accounts = [account for account in accounts if account.get('live_poll', False)]

    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    _ensure_support_tables(con)
    ensure_business_ops_tables(con)
    con.row_factory = sqlite3.Row
    result: dict[str, Any] = {'imported_count': 0, 'accounts': {}, 'imported_messages': [], 'status': 'completed'}

    try:
        for account in accounts:
            account_id = account['id']
            token_env = account.get('bot_token_env')
            token = os.environ.get(token_env or '') if token_env else None
            if not token:
                result['accounts'][account_id] = {'imported_count': 0, 'status': 'missing-env'}
                continue

            _upsert_source_account(con, account)
            con.commit()
            warn_if_group_privacy_blocks_messages(account, token, telegram_api=telegram_api)

            last_checkpoint = _get_checkpoint(con, 'telegram', account_id)
            offset = int(last_checkpoint) + 1 if last_checkpoint and str(last_checkpoint).isdigit() else None
            payload = telegram_api.get_updates(token, offset=offset, allowed_updates=['message'])
            updates = payload.get('result') or []
            configured_chat_id = str(account.get('chat_id') or '')
            imported_for_account = 0
            account_imported_messages: list[dict[str, Any]] = []
            max_update_id = last_checkpoint

            for update in updates:
                update_id = update.get('update_id')
                message = update.get('message') or {}
                chat = message.get('chat') or {}
                if configured_chat_id and str(chat.get('id')) != configured_chat_id:
                    continue
                if not message:
                    continue

                sender = message.get('from') or {}
                sender_id = sender.get('id', 'unknown')
                chat_id = int(chat.get('id'))
                raw_chat_id = str(chat.get('id'))
                chat_id_abs = str(abs(chat_id))
                sender_handle = _sender_handle(message)
                text = str(message.get('text') or message.get('caption') or '')
                subject = str(chat.get('title') or '')
                classification = _classify_telegram_message(account, message, sender_handle, text)
                sender_role = 'operator' if str(account.get('lane') or '').lower() == 'operator-control' else 'customer'
                thread_id = f'telegram-{chat_id_abs}-{sender_id}{classification["thread_suffix"]}'
                message_id = f'{chat_id_abs}-{message.get("message_id")}'
                source_message_id = f'{raw_chat_id}-{message.get("message_id")}'
                sent_at = _sent_at_from_unix(message.get('date'))
                last_customer_message_at = sent_at if sender_role == 'customer' else None
                unread_increment = 1 if sender_role == 'customer' else 0

                if _message_exists(con, message_id):
                    max_update_id = str(update_id)
                    continue

                try:
                    sent_dt = datetime.fromisoformat(sent_at)
                except Exception:
                    sent_dt = datetime.now(timezone.utc)
                year = sent_dt.strftime('%Y')
                month = sent_dt.strftime('%m')

                raw_dir = businessos_root / '00_INBOX' / 'communications' / 'telegram' / 'raw' / year / month
                raw_dir.mkdir(parents=True, exist_ok=True)
                raw_path = raw_dir / f'{message_id}.json'
                raw_path.write_text(json.dumps(update, indent=2) + '\n', encoding='utf-8')

                attachments_dir = businessos_root / '00_INBOX' / 'communications' / 'telegram' / 'media' / year / month / f'telegram-{chat_id_abs}-{sender_id}'
                attachments_dir.mkdir(parents=True, exist_ok=True)
                attachment_manifest = _attachment_manifest(message)

                normalized_dir = businessos_root / '03_DATA' / 'normalized' / 'support' / year / month / 'telegram'
                normalized_dir.mkdir(parents=True, exist_ok=True)
                normalized_path = normalized_dir / f'{message_id}.json'

                summary = ' '.join(part for part in [subject, text] if part).strip()
                task_command = parse_task_command(subject=subject, text=text)
                task_result = None
                if task_command:
                    task_result = apply_task_command(
                        db_path=db_path,
                        command=task_command,
                        source_channel='telegram',
                        source_account=account_id,
                        source_message_id=source_message_id,
                        source_thread_id=thread_id,
                        author_handle=sender_handle,
                        app_id=account.get('app_id'),
                    )
                suggested_task = record_task_suggestion(
                    db_path=db_path,
                    source_channel='telegram',
                    source_account=account_id,
                    source_message_id=source_message_id,
                    source_thread_id=thread_id,
                    message_id=message_id,
                    subject=subject,
                    summary=summary,
                    category=classification['category'],
                    assigned_queue=classification['assigned_queue'],
                    task_operation=task_result,
                )

                normalized_payload = {
                    'thread_id': thread_id,
                    'message_id': message_id,
                    'source_item_id': source_message_id,
                    'source_channel': 'telegram',
                    'source_account': account_id,
                    'sender_handle': sender_handle,
                    'sent_at': sent_at,
                    'subject': subject,
                    'text': text,
                    'summary': summary,
                    'app_id': account.get('app_id'),
                    'platform': 'telegram-bot',
                    'sender_role': sender_role,
                    'rating': None,
                    'mailbox_role': None,
                    'routing_queue': classification['assigned_queue'],
                    'routed_address': None,
                    'mailbox_entity_id': None,
                    'raw_path': str(raw_path),
                    'normalized_path': str(normalized_path),
                    'attachments_dir': str(attachments_dir),
                    'attachment_manifest': attachment_manifest,
                    'task_operation': task_result,
                    'suggested_task': suggested_task,
                    'category': classification['category'],
                    'priority': classification['priority'],
                    'sentiment': classification['sentiment'],
                    'launch_blocker': False,
                    'theme': classification['theme'],
                }
                normalized_path.write_text(json.dumps(normalized_payload, indent=2) + '\n', encoding='utf-8')
                normalized_hash = hashlib.sha256(normalized_path.read_bytes()).hexdigest()

                con.execute(
                    '''
                    insert into communication_threads (
                        id, source_channel, app_id, customer_handle, subject, priority, sentiment,
                        latest_summary, suggested_response, escalation_flag, source_account,
                        first_seen_at, last_seen_at, last_customer_message_at, unread_count,
                        needs_human_reply, assigned_queue, created_at, updated_at
                    ) values (?, 'telegram', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, current_timestamp, current_timestamp)
                    on conflict(id) do update set
                        app_id = excluded.app_id,
                        customer_handle = excluded.customer_handle,
                        subject = excluded.subject,
                        priority = excluded.priority,
                        sentiment = excluded.sentiment,
                        latest_summary = excluded.latest_summary,
                        suggested_response = excluded.suggested_response,
                        escalation_flag = excluded.escalation_flag,
                        source_account = excluded.source_account,
                        last_seen_at = excluded.last_seen_at,
                        last_customer_message_at = coalesce(excluded.last_customer_message_at, communication_threads.last_customer_message_at),
                        unread_count = communication_threads.unread_count + excluded.unread_count,
                        needs_human_reply = excluded.needs_human_reply,
                        assigned_queue = excluded.assigned_queue,
                        updated_at = current_timestamp
                    ''',
                    (
                        thread_id,
                        account.get('app_id'),
                        sender_handle,
                        subject,
                        classification['priority'],
                        classification['sentiment'],
                        summary,
                        classification['suggested_response'],
                        1 if classification['priority'] in {'high', 'critical'} else 0,
                        account_id,
                        sent_at,
                        sent_at,
                        last_customer_message_at,
                        unread_increment,
                        classification['needs_human_reply'],
                        classification['assigned_queue'],
                    ),
                )

                con.execute(
                    '''
                    insert into communication_messages (
                        id, thread_id, source_message_id, sender_handle, sender_role, sent_at, text,
                        summary, category, priority, sentiment, app_id, platform, suggested_response,
                        raw_path, normalized_path, attachment_count, in_reply_to, references_header,
                        normalized_hash, dedupe_key
                    ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''',
                    (
                        message_id,
                        thread_id,
                        source_message_id,
                        sender_handle,
                        sender_role,
                        sent_at,
                        text,
                        summary,
                        classification['category'],
                        classification['priority'],
                        classification['sentiment'],
                        account.get('app_id'),
                        'telegram-bot',
                        classification['suggested_response'],
                        str(raw_path),
                        str(normalized_path),
                        len(attachment_manifest),
                        None,
                        None,
                        normalized_hash,
                        classification['theme'],
                    ),
                )

                if str(account.get('lane') or '').lower() != 'operator-control':
                    con.execute(
                        '''
                        insert into feedback_items (
                            id, source_channel, source_item_id, app_id, thread_id, message_id, platform,
                            title, body, summary, category, priority, sentiment, duplicate_group_id,
                            launch_blocker_flag, planning_status, source_account, theme, fingerprint,
                            first_seen_at, last_seen_at, customer_impact_score
                        ) values (?, 'telegram', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 'new', ?, ?, ?, ?, ?, ?)
                        ''',
                        (
                            f'fb-{message_id}',
                            source_message_id,
                            account.get('app_id'),
                            thread_id,
                            message_id,
                            'telegram-bot',
                            subject,
                            text,
                            summary,
                            classification['category'],
                            classification['priority'],
                            classification['sentiment'],
                            classification['theme'],
                            account_id,
                            classification['theme'],
                            classification['theme'],
                            sent_at,
                            sent_at,
                            7 if classification['priority'] == 'high' else 4,
                        ),
                    )
                con.commit()
                imported_detail = {
                    'message_id': message_id,
                    'source_message_id': source_message_id,
                    'thread_id': thread_id,
                    'source_account': account_id,
                    'sender_handle': sender_handle,
                    'sent_at': sent_at,
                    'subject': subject,
                    'text': text,
                    'summary': summary,
                    'category': classification['category'],
                    'priority': classification['priority'],
                    'assigned_queue': classification['assigned_queue'],
                    'mailbox_role': None,
                    'task_operation': task_result,
                    'suggested_task': suggested_task,
                    'classification_label': _classification_label(
                        classification['category'],
                        classification['assigned_queue'],
                        None,
                        task_result,
                    ),
                    'normalized_path': str(normalized_path),
                    'raw_path': str(raw_path),
                    'attachment_count': len(attachment_manifest),
                }
                result['imported_messages'].append(imported_detail)
                account_imported_messages.append(imported_detail)
                imported_for_account += 1
                result['imported_count'] += 1
                max_update_id = str(update_id)

            if max_update_id:
                _set_checkpoint(con, 'telegram', account_id, str(max_update_id))
                con.commit()
            result['accounts'][account_id] = {
                'imported_count': imported_for_account,
                'imported_messages': account_imported_messages,
                'status': 'completed',
            }
    finally:
        con.close()

    return result


def main() -> None:
    import argparse

    default_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description='Poll configured BusinessOS Telegram support lanes via getUpdates.')
    parser.add_argument('--businessos-root', default=str(default_root))
    parser.add_argument('--db-path', default=None)
    parser.add_argument('--config-path', default=None)
    parser.add_argument('--source-account', default=None)
    args = parser.parse_args()

    businessos_root = Path(args.businessos_root)
    db_path = Path(args.db_path) if args.db_path else businessos_root / '03_DATA' / 'db' / 'businessos.db'
    config_path = Path(args.config_path) if args.config_path else businessos_root / '04_AUTOMATIONS' / 'configs' / 'telegram-sources.yaml'

    result = poll_telegram_updates(
        businessos_root=businessos_root,
        db_path=db_path,
        config_path=config_path,
        source_account=args.source_account,
    )
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
