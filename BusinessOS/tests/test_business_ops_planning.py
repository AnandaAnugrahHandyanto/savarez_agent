import sqlite3
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / '04_AUTOMATIONS' / 'scripts'
sys.path.insert(0, str(SCRIPTS_DIR))

import business_ops_core


def test_apply_task_command_records_today_priority_for_existing_task(tmp_path, monkeypatch):
    db_path = tmp_path / 'businessos.db'
    monkeypatch.setattr(business_ops_core, 'utc_now_iso', lambda: '2026-05-03T12:30:00+00:00')

    task = business_ops_core.create_task(
        db_path=db_path,
        title='Finish Google Play registration',
        description=None,
        source_channel='telegram',
        author_handle='@poiuy',
        source_account='telegram-businessos-operator',
        source_message_id='msg-seed',
        source_thread_id='thread-seed',
        app_id='steadyapp',
    )

    command = business_ops_core.parse_task_command(text=f'/focus {task["id"]}')
    result = business_ops_core.apply_task_command(
        db_path=db_path,
        command=command,
        source_channel='telegram',
        source_account='telegram-businessos-operator',
        source_message_id='msg-focus',
        source_thread_id='thread-focus',
        author_handle='@poiuy',
        app_id='steadyapp',
    )

    assert result['action'] == 'focus'

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    row = con.execute('select * from daily_priorities').fetchone()
    con.close()

    assert row is not None
    assert row['focus_date'] == '2026-05-03'
    assert row['task_id'] == task['id']
    assert row['title'] == 'Finish Google Play registration'
    assert row['status'] == 'active'


def test_build_task_dashboard_report_includes_today_priorities_and_suggested_tasks(tmp_path):
    businessos_root = tmp_path / 'BusinessOS'
    db_path = businessos_root / '03_DATA' / 'db' / 'businessos.db'
    db_path.parent.mkdir(parents=True, exist_ok=True)

    con = sqlite3.connect(db_path)
    business_ops_core.ensure_business_ops_tables(con)
    con.executescript(
        '''
        create table if not exists daily_priorities (
            id text primary key,
            focus_date text not null,
            task_id text,
            title text not null,
            notes text,
            status text not null default 'active',
            source_channel text,
            source_account text,
            source_message_id text,
            source_thread_id text,
            author_handle text,
            created_at text not null,
            updated_at text not null
        );
        create table if not exists task_suggestions (
            id text primary key,
            source_channel text not null,
            source_account text,
            source_message_id text,
            source_thread_id text,
            message_id text,
            task_id text,
            title text not null,
            rationale text,
            category text,
            assigned_queue text,
            status text not null default 'suggested',
            created_at text not null,
            updated_at text not null
        );
        '''
    )
    con.execute(
        "insert into task_items (id, title, status, priority, created_at, updated_at) values (?, ?, ?, ?, ?, ?)",
        ('task-0001', 'Finish Google Play registration', 'created', 'medium', '2026-05-02T16:38:05+00:00', '2026-05-03T12:00:00+00:00'),
    )
    con.execute(
        "insert into daily_priorities (id, focus_date, task_id, title, notes, status, created_at, updated_at) values (?, ?, ?, ?, ?, ?, ?, ?)",
        ('focus-1', '2026-05-03', 'task-0001', 'Finish Google Play registration', 'Primary focus for today', 'active', '2026-05-03T12:30:00+00:00', '2026-05-03T12:30:00+00:00'),
    )
    con.execute(
        "insert into task_suggestions (id, source_channel, source_account, source_message_id, source_thread_id, message_id, task_id, title, rationale, category, assigned_queue, status, created_at, updated_at) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ('suggestion-1', 'email', 'helix-admin', 'refund-1@example.com', 'thread-1', 'msg-1', None, 'Respond to billing issue: Refund request', 'Billing issue needs human follow-up', 'billing', 'billing-support', 'suggested', '2026-05-03T12:30:00+00:00', '2026-05-03T12:30:00+00:00'),
    )
    con.commit()
    con.close()

    report_path = business_ops_core.build_task_dashboard_report(businessos_root=businessos_root, db_path=db_path)
    report_text = report_path.read_text(encoding='utf-8')

    assert '## Today\'s priorities' in report_text
    assert 'Primary focus for today' in report_text
    assert '## Suggested follow-up items' in report_text
    assert 'Respond to billing issue: Refund request' in report_text
