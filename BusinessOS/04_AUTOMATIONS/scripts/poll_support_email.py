from __future__ import annotations

import email
import hashlib
import imaplib
import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from email import policy
from email.message import Message
from email.utils import getaddresses, parseaddr, parsedate_to_datetime
from pathlib import Path
from typing import Any, Callable

import yaml

from business_ops_core import (
    apply_task_command,
    ensure_business_ops_tables,
    message_looks_like_document,
    parse_task_command,
    process_document_file,
    record_task_suggestion,
    save_email_attachments,
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _slugify(value: str) -> str:
    slug = re.sub(r'[^a-z0-9]+', '-', value.lower()).strip('-')
    return slug or 'message'


def _classification_label(category: str | None, assigned_queue: str | None, mailbox_role: str | None = None, task_operation: Any | None = None) -> str:
    category_value = str(category or '').strip()
    queue_value = str(assigned_queue or mailbox_role or 'unassigned').strip() or 'unassigned'
    if task_operation:
        primary = 'todo'
        semantic = 'task-capture'
    elif category_value == 'business-expense-record' or str(mailbox_role or '').strip() == 'expense-intake':
        primary = 'expense'
        semantic = category_value or 'business-expense-record'
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
    elif category_value == 'internal-test':
        primary = 'internal-test'
        semantic = category_value
    else:
        primary = 'support'
        semantic = category_value or 'support-request'
    return f'{primary} / {semantic} / {queue_value}'


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
        raise ValueError('support-inboxes.yaml must contain an accounts list')
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
            'address': account.get('address'),
            'host': account.get('host'),
            'mailbox': account.get('mailbox', 'INBOX'),
            'username': account.get('username'),
        },
        sort_keys=True,
    )
    con.execute(
        '''
        insert into source_accounts (id, source_type, external_ref, app_id, config_json, active, updated_at)
        values (?, 'email', ?, ?, ?, 1, ?)
        on conflict(id) do update set
            external_ref = excluded.external_ref,
            app_id = excluded.app_id,
            config_json = excluded.config_json,
            active = 1,
            updated_at = excluded.updated_at
        ''',
        (
            account['id'],
            account.get('address'),
            account.get('app_id'),
            config_json,
            _utc_now_iso(),
        ),
    )


def _extract_text_from_email(message: Message) -> str:
    parts: list[str] = []
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_maintype() == 'multipart':
                continue
            if part.get_filename():
                continue
            if part.get_content_type() != 'text/plain':
                continue
            payload = part.get_payload(decode=True) or b''
            charset = part.get_content_charset() or 'utf-8'
            parts.append(payload.decode(charset, errors='replace').strip())
    else:
        payload = message.get_payload(decode=True) or b''
        charset = message.get_content_charset() or 'utf-8'
        parts.append(payload.decode(charset, errors='replace').strip())
    return '\n'.join(part for part in parts if part).strip()


def _extract_attachment_manifest(message: Message) -> list[dict[str, Any]]:
    manifest: list[dict[str, Any]] = []
    for part in message.walk():
        filename = part.get_filename()
        if not filename:
            continue
        payload = part.get_payload(decode=True) or b''
        manifest.append(
            {
                'filename': filename,
                'content_type': part.get_content_type(),
                'size_bytes': len(payload),
            }
        )
    return manifest


def _select_alias(account: dict[str, Any], to_addresses: list[str]) -> dict[str, Any] | None:
    normalized = {address.lower() for address in to_addresses}
    for alias in account.get('aliases', []) or []:
        address = str(alias.get('address') or '').lower()
        if address and address in normalized:
            return alias
    return None


def _classify_email(subject: str, text: str, alias: dict[str, Any] | None) -> dict[str, Any]:
    combined = f'{subject} {text}'.strip().lower()
    task_command = parse_task_command(subject=subject, text=text)
    if 'test' in combined and ('support' not in combined and 'refund' not in combined and 'privacy' not in combined and 'legal' not in combined):
        return {
            'category': 'internal-test',
            'priority': 'low',
            'sentiment': 'neutral',
            'assigned_queue': 'admin',
            'needs_human_reply': 0,
            'theme': 'internal-test',
            'suggested_response': 'Administrative/vendor notification captured for BusinessOS review. No customer reply is needed by default.',
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
        }
    if any(signal in combined for signal in ('dun & bradstreet', 'dun and bradstreet', 'd-u-n-s', 'duns number')):
        return {
            'category': 'business-identity-record',
            'priority': 'medium',
            'sentiment': 'neutral',
            'assigned_queue': alias.get('queue') if alias and alias.get('queue') else 'admin',
            'needs_human_reply': 0,
            'theme': 'business-identity',
            'suggested_response': 'Administrative identity record captured for BusinessOS review. No outbound reply is needed by default.',
        }
    if alias and alias.get('queue'):
        queue = alias['queue']
        if queue == 'finance-review' or alias.get('mailbox_role') == 'expense-intake':
            return {
                'category': 'business-expense-record',
                'priority': 'medium',
                'sentiment': 'neutral',
                'assigned_queue': queue,
                'needs_human_reply': 0,
                'theme': 'finance-expense',
                'suggested_response': 'Business expense intake captured for BusinessOS finance review and tax documentation. No outbound reply is needed by default.',
            }
        if queue == 'billing-support' or any(keyword in combined for keyword in ('refund', 'charged', 'billing')):
            return {
                'category': 'billing',
                'priority': 'high',
                'sentiment': 'negative',
                'assigned_queue': queue,
                'needs_human_reply': 1,
                'theme': 'subscriptions',
                'suggested_response': "Hi there, thanks for contacting our billing team. We're reviewing the charge and refund details now and will follow up with the next steps shortly.",
            }
        if queue == 'privacy-review':
            return {
                'category': 'support-request',
                'priority': 'medium',
                'sentiment': 'neutral',
                'assigned_queue': queue,
                'needs_human_reply': 1,
                'theme': 'support-request',
                'suggested_response': "Hi there, thanks for reaching out about a privacy request. We've captured this for privacy review and will follow up after validating the request details.",
            }
        if queue == 'legal-review':
            return {
                'category': 'support-request',
                'priority': 'medium',
                'sentiment': 'neutral',
                'assigned_queue': queue,
                'needs_human_reply': 1,
                'theme': 'support-request',
                'suggested_response': "Hi there, thanks for your message. We've routed it to our legal review queue and will respond after the relevant team has reviewed it.",
            }
        return {
            'category': 'support-request',
            'priority': 'medium',
            'sentiment': 'neutral',
            'assigned_queue': queue,
            'needs_human_reply': 1,
            'theme': 'support-request',
            'suggested_response': "Hi there, thanks for contacting us. We've routed your note through the appropriate inbox and will follow up if we need any additional details.",
        }
    if any(keyword in combined for keyword in ('refund', 'charged', 'billing')):
        return {
            'category': 'billing',
            'priority': 'high',
            'sentiment': 'negative',
            'assigned_queue': 'billing-support',
            'needs_human_reply': 1,
            'theme': 'subscriptions',
            'suggested_response': "Hi there, thanks for contacting our billing team. We're reviewing the charge and refund details now and will follow up with the next steps shortly.",
        }
    return {
        'category': 'support-request',
        'priority': 'medium',
        'sentiment': 'neutral',
        'assigned_queue': 'general',
        'needs_human_reply': 1,
        'theme': 'support-request',
        'suggested_response': "Hi there, thanks for contacting us. We've received your message and will follow up with the next steps shortly.",
    }


def _parse_sent_at(message: Message) -> str:
    date_header = message.get('Date')
    if not date_header:
        return _utc_now_iso()
    try:
        return parsedate_to_datetime(date_header).isoformat()
    except Exception:
        return _utc_now_iso()


def _message_exists(con: sqlite3.Connection, message_id: str) -> bool:
    row = con.execute('select 1 from communication_messages where id = ?', (message_id,)).fetchone()
    return row is not None


def poll_support_email(
    businessos_root: str | Path | None = None,
    db_path: str | Path | None = None,
    config_path: str | Path | None = None,
    source_account: str | None = None,
    imap_factory: Callable[[str, int], Any] | None = None,
) -> dict[str, Any]:
    businessos_root = Path(businessos_root or Path(__file__).resolve().parents[2])
    db_path = Path(db_path or businessos_root / '03_DATA' / 'db' / 'businessos.db')
    config_path = Path(config_path or businessos_root / '04_AUTOMATIONS' / 'configs' / 'support-inboxes.yaml')
    imap_factory = imap_factory or (lambda host, port: imaplib.IMAP4_SSL(host, port))

    if not config_path.exists():
        return {'imported_count': 0, 'accounts': {}, 'imported_messages': [], 'status': 'missing-config'}

    accounts = _load_accounts(config_path)
    if source_account:
        accounts = [account for account in accounts if account.get('id') == source_account]

    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    _ensure_support_tables(con)
    ensure_business_ops_tables(con)
    con.row_factory = sqlite3.Row
    result: dict[str, Any] = {'imported_count': 0, 'accounts': {}, 'imported_messages': [], 'status': 'completed'}

    try:
        for account in accounts:
            account_id = account['id']
            password_env = account.get('password_env')
            password = os.environ.get(password_env or '') if password_env else None
            if not password:
                result['accounts'][account_id] = {'imported_count': 0, 'status': 'missing-env'}
                continue

            _upsert_source_account(con, account)
            con.commit()

            imap = imap_factory(account['host'], int(account.get('port', 993)))
            imap.login(account['username'], password)
            imap.select(account.get('mailbox', 'INBOX'))

            last_checkpoint = _get_checkpoint(con, 'email', account_id)
            start_uid = int(last_checkpoint) + 1 if last_checkpoint and last_checkpoint.isdigit() else 1
            status, search_data = imap.uid('SEARCH', None, f'{start_uid}:*')
            if status != 'OK':
                result['accounts'][account_id] = {'imported_count': 0, 'status': 'search-failed'}
                imap.logout()
                continue

            uid_bytes = search_data[0] if search_data else b''
            uid_text = uid_bytes.decode('utf-8') if isinstance(uid_bytes, bytes) else str(uid_bytes or '')
            uids = [uid for uid in uid_text.split() if uid]
            imported_for_account = 0
            account_imported_messages: list[dict[str, Any]] = []
            max_uid = last_checkpoint

            for uid in uids:
                fetch_status, fetch_data = imap.uid('FETCH', uid, '(RFC822)')
                if fetch_status != 'OK':
                    continue
                payload_bytes = b''
                for part in fetch_data:
                    if isinstance(part, tuple) and len(part) >= 2 and isinstance(part[1], (bytes, bytearray)):
                        payload_bytes = bytes(part[1])
                        break
                if not payload_bytes:
                    continue

                message = email.message_from_bytes(payload_bytes, policy=policy.default)
                raw_message_id = str(message.get('Message-ID') or f'{account_id}-uid-{uid}').strip()
                sender_address = parseaddr(message.get('From') or '')[1].strip().lower()
                to_addresses = [address.strip().lower() for _, address in getaddresses(message.get_all('To', [])) if address]
                subject = str(message.get('Subject') or '').strip()
                text = _extract_text_from_email(message)
                alias = _select_alias(account, to_addresses)
                classification = _classify_email(subject, text, alias)
                sent_at = _parse_sent_at(message)
                safe_message_id = _slugify(raw_message_id)
                is_internal_test = classification['category'] == 'internal-test'
                thread_id = safe_message_id + ('-internal-test' if is_internal_test else '')
                message_row_id = safe_message_id
                source_message_id = raw_message_id

                if _message_exists(con, message_row_id):
                    max_uid = uid
                    continue

                sent_dt = None
                try:
                    sent_dt = datetime.fromisoformat(sent_at)
                except Exception:
                    sent_dt = datetime.now(timezone.utc)
                year = sent_dt.strftime('%Y')
                month = sent_dt.strftime('%m')

                raw_dir = businessos_root / '00_INBOX' / 'communications' / 'email' / 'raw' / year / month / account_id
                raw_dir.mkdir(parents=True, exist_ok=True)
                raw_path = raw_dir / f'{safe_message_id}.eml'
                raw_path.write_bytes(payload_bytes)

                attachments_dir = businessos_root / '00_INBOX' / 'communications' / 'email' / 'attachments' / year / month / safe_message_id
                attachments_dir.mkdir(parents=True, exist_ok=True)
                attachment_manifest = save_email_attachments(message, attachments_dir)

                normalized_dir = businessos_root / '03_DATA' / 'normalized' / 'support' / year / month / 'email'
                normalized_dir.mkdir(parents=True, exist_ok=True)
                normalized_path = normalized_dir / f'{safe_message_id}.json'

                summary = ' '.join(part for part in [subject, text] if part).strip()
                linked_document_ids: list[str] = []
                for attachment in attachment_manifest:
                    saved_path = attachment.get('saved_path')
                    if not saved_path:
                        continue
                    document_result = process_document_file(
                        businessos_root=businessos_root,
                        db_path=db_path,
                        input_path=Path(saved_path),
                        source_channel='email-attachment',
                        source_account=account_id,
                        source_reference=source_message_id,
                        move_source=False,
                    )
                    linked_document_ids.append(document_result['document']['id'])

                if not linked_document_ids and message_looks_like_document(subject, text):
                    email_document = process_document_file(
                        businessos_root=businessos_root,
                        db_path=db_path,
                        input_path=raw_path,
                        source_channel='forwarded-email',
                        source_account=account_id,
                        source_reference=source_message_id,
                        fallback_text=summary,
                        move_source=False,
                    )
                    linked_document_ids.append(email_document['document']['id'])

                task_command = parse_task_command(subject=subject, text=text)
                task_result = None
                if task_command:
                    task_result = apply_task_command(
                        db_path=db_path,
                        command=task_command,
                        source_channel='email',
                        source_account=account_id,
                        source_message_id=source_message_id,
                        source_thread_id=thread_id,
                        author_handle=sender_address,
                        app_id=account.get('app_id'),
                        linked_document_ids=linked_document_ids,
                    )
                suggested_task = record_task_suggestion(
                    db_path=db_path,
                    source_channel='email',
                    source_account=account_id,
                    source_message_id=source_message_id,
                    source_thread_id=thread_id,
                    message_id=message_row_id,
                    subject=subject,
                    summary=summary,
                    category=classification['category'],
                    assigned_queue=classification['assigned_queue'],
                    task_operation=task_result,
                )

                normalized_payload = {
                    'thread_id': thread_id,
                    'message_id': message_row_id,
                    'source_item_id': source_message_id,
                    'source_channel': 'email',
                    'source_account': account_id,
                    'sender_handle': sender_address,
                    'sent_at': sent_at,
                    'subject': subject,
                    'text': text,
                    'summary': summary,
                    'app_id': account.get('app_id'),
                    'platform': None,
                    'rating': None,
                    'to_addresses': to_addresses,
                    'mailbox_role': alias.get('mailbox_role') if alias else None,
                    'routed_address': alias.get('address') if alias else None,
                    'mailbox_entity_id': alias.get('email_account_id') if alias else None,
                    'raw_path': str(raw_path),
                    'normalized_path': str(normalized_path),
                    'attachments_dir': str(attachments_dir),
                    'attachment_manifest': attachment_manifest,
                    'linked_document_ids': linked_document_ids,
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
                    ) values (?, 'email', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, current_timestamp, current_timestamp)
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
                        last_customer_message_at = excluded.last_customer_message_at,
                        unread_count = communication_threads.unread_count + 1,
                        needs_human_reply = excluded.needs_human_reply,
                        assigned_queue = excluded.assigned_queue,
                        updated_at = current_timestamp
                    ''',
                    (
                        thread_id,
                        account.get('app_id'),
                        sender_address,
                        subject,
                        classification['priority'],
                        classification['sentiment'],
                        summary,
                        classification['suggested_response'],
                        1 if classification['priority'] in {'high', 'critical'} else 0,
                        account_id,
                        sent_at,
                        sent_at,
                        sent_at,
                        1,
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
                    ) values (?, ?, ?, ?, 'customer', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''',
                    (
                        message_row_id,
                        thread_id,
                        source_message_id,
                        sender_address,
                        sent_at,
                        text,
                        summary,
                        classification['category'],
                        classification['priority'],
                        classification['sentiment'],
                        account.get('app_id'),
                        None,
                        classification['suggested_response'],
                        str(raw_path),
                        str(normalized_path),
                        len(attachment_manifest),
                        message.get('In-Reply-To'),
                        message.get('References'),
                        normalized_hash,
                        classification['theme'],
                    ),
                )

                con.execute(
                    '''
                    insert into feedback_items (
                        id, source_channel, source_item_id, app_id, thread_id, message_id, platform,
                        title, body, summary, category, priority, sentiment, duplicate_group_id,
                        launch_blocker_flag, planning_status, source_account, theme, fingerprint,
                        first_seen_at, last_seen_at, customer_impact_score
                    ) values (?, 'email', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 'new', ?, ?, ?, ?, ?, ?)
                    ''',
                    (
                        f'fb-{safe_message_id}',
                        source_message_id,
                        account.get('app_id'),
                        thread_id,
                        message_row_id,
                        None,
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
                    'message_id': message_row_id,
                    'source_message_id': source_message_id,
                    'thread_id': thread_id,
                    'source_account': account_id,
                    'sender_handle': sender_address,
                    'sent_at': sent_at,
                    'subject': subject,
                    'summary': summary,
                    'category': classification['category'],
                    'priority': classification['priority'],
                    'assigned_queue': classification['assigned_queue'],
                    'routed_address': alias.get('address') if alias else None,
                    'mailbox_role': alias.get('mailbox_role') if alias else None,
                    'task_operation': task_result,
                    'suggested_task': suggested_task,
                    'classification_label': _classification_label(
                        classification['category'],
                        classification['assigned_queue'],
                        alias.get('mailbox_role') if alias else None,
                        task_result,
                    ),
                    'normalized_path': str(normalized_path),
                    'raw_path': str(raw_path),
                    'linked_document_ids': linked_document_ids,
                    'attachment_count': len(attachment_manifest),
                }
                result['imported_messages'].append(imported_detail)
                account_imported_messages.append(imported_detail)
                imported_for_account += 1
                result['imported_count'] += 1
                max_uid = uid

            if max_uid:
                _set_checkpoint(con, 'email', account_id, str(max_uid))
                con.commit()
            imap.logout()
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
    parser = argparse.ArgumentParser(description='Poll configured BusinessOS support inboxes over IMAP.')
    parser.add_argument('--businessos-root', default=str(default_root))
    parser.add_argument('--db-path', default=None)
    parser.add_argument('--config-path', default=None)
    parser.add_argument('--source-account', default=None)
    args = parser.parse_args()

    businessos_root = Path(args.businessos_root)
    db_path = Path(args.db_path) if args.db_path else businessos_root / '03_DATA' / 'db' / 'businessos.db'
    config_path = Path(args.config_path) if args.config_path else businessos_root / '04_AUTOMATIONS' / 'configs' / 'support-inboxes.yaml'

    result = poll_support_email(
        businessos_root=businessos_root,
        db_path=db_path,
        config_path=config_path,
        source_account=args.source_account,
    )
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
