import sqlite3
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / '04_AUTOMATIONS' / 'scripts'
sys.path.insert(0, str(SCRIPTS_DIR))

from build_support_health_report import build_support_health_report


def _seed_db(db_path: Path) -> None:
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.executescript(
        '''
        create table communication_threads (
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
        create table communication_messages (
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
        create table ingestion_checkpoints (
            source_type text not null,
            source_account text not null,
            checkpoint_value text,
            updated_at text default current_timestamp,
            primary key (source_type, source_account)
        );
        '''
    )
    cur.execute(
        "insert into communication_threads (id, source_channel, source_account, customer_handle, subject, priority, last_seen_at, needs_human_reply, assigned_queue) values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ('telegram-5087084218-6765506693', 'telegram', 'telegram-steady-support', '@liliput66321', 'Steady App Support', 'medium', '2026-05-02T12:14:44+00:00', 1, 'general'),
    )
    cur.execute(
        "insert into communication_threads (id, source_channel, source_account, customer_handle, subject, priority, last_seen_at, needs_human_reply, assigned_queue) values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ('email-helix-admin-thread-1', 'email', 'helix-admin', 'noreply@zoho.com', 'Zoho Notice', 'low', '2026-05-02T12:10:00+00:00', 0, 'admin'),
    )
    cur.execute(
        "insert into communication_messages (id, thread_id, source_message_id, sender_handle, sent_at, text, category, priority, platform, created_at) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ('5087084218-20', 'telegram-5087084218-6765506693', '-5087084218-20', '@liliput66321', '2026-05-02T12:14:44+00:00', 'one more telegram test message', 'support-request', 'medium', 'telegram-bot', '2026-05-02T12:15:25+00:00'),
    )
    cur.execute(
        "insert into communication_messages (id, thread_id, source_message_id, sender_handle, sent_at, text, category, priority, platform, created_at) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ('email-msg-22', 'email-helix-admin-thread-1', '<msg22@example.com>', 'noreply@zoho.com', '2026-05-02T12:10:00+00:00', 'Welcome to Zoho', 'admin-notification', 'low', None, '2026-05-02T12:10:05+00:00'),
    )
    cur.execute(
        "insert into ingestion_checkpoints (source_type, source_account, checkpoint_value, updated_at) values (?, ?, ?, ?)",
        ('telegram', 'telegram-steady-support', '64586383', '2026-05-02T12:21:32+00:00'),
    )
    cur.execute(
        "insert into ingestion_checkpoints (source_type, source_account, checkpoint_value, updated_at) values (?, ?, ?, ?)",
        ('email', 'helix-admin', '22', '2026-05-02T12:21:31+00:00'),
    )
    con.commit()
    con.close()


def test_support_health_report_includes_current_run_summary_and_latest_ingested_activity(tmp_path):
    db_path = tmp_path / 'businessos.db'
    _seed_db(db_path)
    output_dir = tmp_path / 'reports'

    report_path = build_support_health_report(
        db_path,
        output_dir,
        run_summary={
            'generated_at': '2026-05-02T12:23:59+00:00',
            'email': {'status': 'completed', 'imported_count': 0},
            'telegram': {'status': 'completed', 'imported_count': 0},
        },
    )

    content = report_path.read_text(encoding='utf-8')
    assert '## Current pipeline run' in content
    assert '| email | completed | 0 | 2026-05-02T12:10:00+00:00 | 2026-05-02T12:10:05+00:00 | Welcome to Zoho |' in content
    assert '| telegram | completed | 0 | 2026-05-02T12:14:44+00:00 | 2026-05-02T12:15:25+00:00 | one more telegram test message |' in content


def test_support_health_report_uses_run_generated_timestamp_when_provided(tmp_path):
    db_path = tmp_path / 'businessos.db'
    _seed_db(db_path)
    output_dir = tmp_path / 'reports'

    report_path = build_support_health_report(
        db_path,
        output_dir,
        run_summary={
            'generated_at': '2026-05-02T12:23:59+00:00',
            'email': {'status': 'completed', 'imported_count': 1},
            'telegram': {'status': 'completed', 'imported_count': 2},
        },
    )

    content = report_path.read_text(encoding='utf-8')
    assert 'Generated: 2026-05-02T12:23:59+00:00' in content
    assert '| email | completed | 1 |' in content
    assert '| telegram | completed | 2 |' in content
