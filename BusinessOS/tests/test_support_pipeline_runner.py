import sqlite3
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / '04_AUTOMATIONS' / 'scripts'
sys.path.insert(0, str(SCRIPTS_DIR))

import run_support_pipeline


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
        ('telegram-1', 'telegram', 'telegram-steady-support', '@tester', 'Steady App Support', 'medium', '2026-05-02 04:00:59', 1, 'general'),
    )
    cur.execute(
        "insert into communication_messages (id, thread_id, text, category, priority, created_at) values (?, ?, ?, ?, ?, ?)",
        ('5087084218-999', 'telegram-1', 'Need help with splash screen', 'support-request', 'medium', '2026-05-02 04:00:59'),
    )
    cur.execute(
        "insert into ingestion_checkpoints (source_type, source_account, checkpoint_value, updated_at) values (?, ?, ?, ?)",
        ('telegram', 'telegram-steady-support', '64586377', '2026-05-02 04:00:59'),
    )
    con.commit()
    con.close()


def test_run_pipeline_writes_health_report_and_mirrors_it(tmp_path):
    businessos_root = tmp_path / 'BusinessOS'
    db_dir = businessos_root / '03_DATA' / 'db'
    db_dir.mkdir(parents=True)
    db_path = db_dir / 'businessos.db'
    _seed_db(db_path)

    config_dir = businessos_root / '04_AUTOMATIONS' / 'configs'
    config_dir.mkdir(parents=True)
    mirror_config = config_dir / 'dropbox-mirror.yaml'
    mirror_config.write_text(
        '\n'.join(
            [
                f'source_root: {businessos_root}',
                f'dropbox_root: {tmp_path / "Dropbox" / "BusinessOS"}',
                'include_paths:',
                '  - 05_REPORTS',
                'prune: false',
                '',
            ]
        ),
        encoding='utf-8',
    )

    result = run_support_pipeline.run_pipeline(
        businessos_root=businessos_root,
        db_path=db_path,
        mirror_config_path=mirror_config,
        skip_email=True,
        skip_telegram=True,
    )

    report_path = Path(result['health_report_path'])
    readiness_path = Path(result['readiness_report_path'])
    mirrored_report = tmp_path / 'Dropbox' / 'BusinessOS' / '05_REPORTS' / 'support' / report_path.name
    mirrored_readiness = tmp_path / 'Dropbox' / 'BusinessOS' / '05_REPORTS' / 'support' / readiness_path.name

    assert report_path.exists()
    assert readiness_path.exists()
    assert mirrored_report.exists()
    assert mirrored_readiness.exists()
    assert result['dropbox_mirror']['copied_count'] >= 1
    assert 'telegram-steady-support' in report_path.read_text(encoding='utf-8')
    assert 'missing-script' in readiness_path.read_text(encoding='utf-8')
    assert result['steps']['email'] == 'skipped'
    assert result['steps']['telegram'] == 'skipped'
    assert result['steps']['readiness_report'] == 'completed'


def test_run_pipeline_executes_live_pollers_when_configs_exist(tmp_path, monkeypatch):
    businessos_root = tmp_path / 'BusinessOS'
    db_dir = businessos_root / '03_DATA' / 'db'
    db_dir.mkdir(parents=True)
    db_path = db_dir / 'businessos.db'
    _seed_db(db_path)

    scripts_dir = businessos_root / '04_AUTOMATIONS' / 'scripts'
    scripts_dir.mkdir(parents=True)
    (scripts_dir / 'poll_support_email.py').write_text('def main():\n    pass\n', encoding='utf-8')
    (scripts_dir / 'poll_telegram_updates.py').write_text('def getUpdates():\n    return []\n', encoding='utf-8')

    config_dir = businessos_root / '04_AUTOMATIONS' / 'configs'
    config_dir.mkdir(parents=True)
    (config_dir / 'support-inboxes.yaml').write_text('accounts: []\n', encoding='utf-8')
    (config_dir / 'telegram-sources.yaml').write_text('accounts: []\n', encoding='utf-8')
    mirror_config = config_dir / 'dropbox-mirror.yaml'
    mirror_config.write_text(
        '\n'.join(
            [
                f'source_root: {businessos_root}',
                f'dropbox_root: {tmp_path / "Dropbox" / "BusinessOS"}',
                'include_paths:',
                '  - 05_REPORTS',
                'prune: false',
                '',
            ]
        ),
        encoding='utf-8',
    )

    email_calls = []
    telegram_calls = []

    def fake_poll_support_email(*, businessos_root, db_path, config_path, source_account=None):
        email_calls.append((Path(businessos_root), Path(db_path), Path(config_path), source_account))
        return {'imported_count': 2, 'accounts': {'helix-admin': {'imported_count': 2, 'status': 'completed'}}, 'status': 'completed'}

    def fake_poll_telegram_updates(*, businessos_root, db_path, config_path, source_account=None):
        telegram_calls.append((Path(businessos_root), Path(db_path), Path(config_path), source_account))
        return {'imported_count': 3, 'accounts': {'telegram-steady-support': {'imported_count': 3, 'status': 'completed'}}, 'status': 'completed'}

    monkeypatch.setattr(run_support_pipeline, 'poll_support_email', fake_poll_support_email)
    monkeypatch.setattr(run_support_pipeline, 'poll_telegram_updates', fake_poll_telegram_updates)

    result = run_support_pipeline.run_pipeline(
        businessos_root=businessos_root,
        db_path=db_path,
        mirror_config_path=mirror_config,
        skip_email=False,
        skip_telegram=False,
    )

    assert result['steps']['email'] == 'completed'
    assert result['steps']['telegram'] == 'completed'
    assert result['email']['imported_count'] == 2
    assert result['telegram']['imported_count'] == 3
    assert email_calls == [(businessos_root, db_path, config_dir / 'support-inboxes.yaml', None)]
    assert telegram_calls == [(businessos_root, db_path, config_dir / 'telegram-sources.yaml', None)]


def test_build_previous_day_summary_writes_report_and_ledger(tmp_path):
    businessos_root = tmp_path / 'BusinessOS'
    db_dir = businessos_root / '03_DATA' / 'db'
    db_dir.mkdir(parents=True)
    db_path = db_dir / 'businessos.db'
    _seed_db(db_path)

    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.executescript(
        '''
        create table if not exists documents (
            id text primary key,
            document_type text,
            amount real,
            vendor_name text,
            finance_direction text,
            local_path text,
            created_at text,
            document_date text
        );
        create table if not exists expense_tax_treatment (
            document_id text primary key,
            tax_relevance text,
            tax_category_federal text,
            created_at text,
            updated_at text
        );
        create table if not exists task_items (
            id text primary key,
            title text not null,
            status text not null,
            priority text default 'medium',
            reminder_at text,
            due_at text,
            created_at text not null,
            updated_at text not null
        );
        create table if not exists task_events (
            id text primary key,
            task_id text not null,
            event_type text not null,
            summary text,
            created_at text not null
        );
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
        create table if not exists pipeline_runs (
            id text primary key,
            started_at text not null,
            completed_at text,
            status text not null,
            summary_json text,
            created_at text not null
        );
        '''
    )
    cur.execute(
        "insert into documents (id, document_type, amount, vendor_name, finance_direction, local_path, created_at, document_date) values (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            'doc-1',
            'receipt',
            25.0,
            'google',
            'expense',
            str(businessos_root / '01_DOCUMENTS' / 'finance' / 'expenses' / '2026' / '2026-05-02__receipt__google__25-00__forwarded-email.eml'),
            '2026-05-02T16:00:00+00:00',
            '2026-05-02',
        ),
    )
    cur.execute(
        "insert into expense_tax_treatment (document_id, tax_relevance, tax_category_federal, created_at, updated_at) values (?, ?, ?, ?, ?)",
        ('doc-1', 'deductible', 'app-store-fees', '2026-05-02T16:00:00+00:00', '2026-05-02T16:00:00+00:00'),
    )
    cur.execute(
        "insert into task_items (id, title, status, priority, reminder_at, due_at, created_at, updated_at) values (?, ?, ?, ?, ?, ?, ?, ?)",
        ('task-1', 'Finish Google Play registration', 'completed', 'medium', None, None, '2026-05-02T16:35:00+00:00', '2026-05-02T18:10:00+00:00'),
    )
    cur.execute(
        "insert into task_items (id, title, status, priority, reminder_at, due_at, created_at, updated_at) values (?, ?, ?, ?, ?, ?, ?, ?)",
        ('task-2', 'Follow up on billing refund queue', 'created', 'high', '2026-05-03T13:00:00+00:00', None, '2026-05-01T16:35:00+00:00', '2026-05-03T11:30:00+00:00'),
    )
    cur.execute(
        "insert into task_events (id, task_id, event_type, summary, created_at) values (?, ?, ?, ?, ?)",
        ('event-1', 'task-1', 'completed', 'Completed Google Play registration follow-up', '2026-05-02T18:10:00+00:00'),
    )
    cur.execute(
        "insert into daily_priorities (id, focus_date, task_id, title, notes, status, source_channel, source_account, source_message_id, source_thread_id, author_handle, created_at, updated_at) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            'focus-1',
            '2026-05-03',
            'task-2',
            'Follow up on billing refund queue',
            'Prioritize refund cleanup first today',
            'active',
            'telegram',
            'telegram-businessos-operator',
            'msg-1',
            'thread-1',
            '@poiuy',
            '2026-05-03T12:00:00+00:00',
            '2026-05-03T12:00:00+00:00'
        ),
    )
    cur.execute(
        "insert into pipeline_runs (id, started_at, completed_at, status, summary_json, created_at) values (?, ?, ?, ?, ?, ?)",
        (
            'run-1',
            '2026-05-02T17:00:00+00:00',
            '2026-05-02T17:01:00+00:00',
            'completed',
            '{"email": {"imported_count": 1}, "telegram": {"imported_count": 1}, "document_intake": {"processed_count": 1}}',
            '2026-05-02T17:00:00+00:00',
        ),
    )
    con.commit()
    con.close()

    summary = run_support_pipeline.build_previous_day_summary(
        businessos_root=businessos_root,
        db_path=db_path,
        current_time='2026-05-03T12:30:00+00:00',
        timezone_name='America/New_York',
    )

    report_path = Path(summary['report_path'])
    assert summary['report_date'] == '2026-05-02'
    assert report_path.exists()
    report_text = report_path.read_text(encoding='utf-8')
    assert 'Pipeline runs: 1' in report_text
    assert 'New communication messages: 1' in report_text
    assert 'Expense documents: 1 totaling $25.00' in report_text
    assert 'Completed tasks: 1' in report_text
    assert '## Remaining open work' in report_text
    assert 'Follow up on billing refund queue' in report_text
    assert '## Today\'s priorities' in report_text
    assert 'Prioritize refund cleanup first today' in report_text
    assert 'Google: Thank you' in report_text or 'google' in report_text.lower()

    con = sqlite3.connect(db_path)
    row = con.execute(
        "select report_date, report_path, metrics_json from daily_summary_reports where report_date = '2026-05-02'"
    ).fetchone()
    con.close()
    assert row is not None
    assert row[0] == '2026-05-02'
    assert row[1] == str(report_path)
    assert 'expense_documents' in row[2]


def test_run_pipeline_sends_operator_updates_and_daily_summary_status(tmp_path, monkeypatch):
    businessos_root = tmp_path / 'BusinessOS'
    db_dir = businessos_root / '03_DATA' / 'db'
    db_dir.mkdir(parents=True)
    db_path = db_dir / 'businessos.db'
    _seed_db(db_path)

    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.executescript(
        '''
        create table if not exists pipeline_runs (
            id text primary key,
            started_at text not null,
            completed_at text,
            status text not null,
            summary_json text,
            created_at text not null
        );
        create table if not exists task_items (
            id text primary key,
            title text not null,
            status text not null,
            created_at text not null,
            updated_at text not null
        );
        '''
    )
    cur.execute(
        "insert into task_items (id, title, status, created_at, updated_at) values (?, ?, ?, ?, ?)",
        ('task-1', 'Review previous day digest', 'created', '2026-05-02T11:20:00+00:00', '2026-05-02T11:20:00+00:00'),
    )
    con.commit()
    con.close()

    scripts_dir = businessos_root / '04_AUTOMATIONS' / 'scripts'
    scripts_dir.mkdir(parents=True)
    (scripts_dir / 'poll_support_email.py').write_text('def main():\n    pass\n', encoding='utf-8')
    (scripts_dir / 'poll_telegram_updates.py').write_text('def getUpdates():\n    return []\n', encoding='utf-8')

    config_dir = businessos_root / '04_AUTOMATIONS' / 'configs'
    config_dir.mkdir(parents=True)
    (config_dir / 'support-inboxes.yaml').write_text('accounts: []\n', encoding='utf-8')
    (config_dir / 'telegram-sources.yaml').write_text(
        '\n'.join(
            [
                'accounts:',
                '  - id: telegram-businessos-operator',
                '    chat_id: "6765506693"',
                '    app_id: steadyapp',
                '    lane: operator-control',
                '    bot_token_env: BUSINESSOS_TELEGRAM_OPERATOR_BOT_TOKEN',
                '    live_poll: false',
                '    auto_import: false',
                '    manual_only: false',
                '    reaction_mode: internal-ops',
                '',
            ]
        ),
        encoding='utf-8',
    )
    (config_dir / 'operator-updates.yaml').write_text(
        '\n'.join(
            [
                'enabled: true',
                'telegram_source_account: telegram-businessos-operator',
                'timezone: America/New_York',
                'morning_digest_local_time: "08:00"',
                'send_run_started: true',
                'send_step_updates: true',
                'send_run_completed: true',
                'send_daily_summary: true',
                '',
            ]
        ),
        encoding='utf-8',
    )
    mirror_config = config_dir / 'dropbox-mirror.yaml'
    mirror_config.write_text(
        '\n'.join(
            [
                f'source_root: {businessos_root}',
                f'dropbox_root: {tmp_path / "Dropbox" / "BusinessOS"}',
                'include_paths:',
                '  - 05_REPORTS',
                'prune: false',
                '',
            ]
        ),
        encoding='utf-8',
    )

    notification_calls = []

    def fake_send_operator_update(*args, **kwargs):
        notification_calls.append({'args': args, 'kwargs': kwargs})
        return {'status': 'sent'}

    monkeypatch.setattr(run_support_pipeline, 'send_operator_update', fake_send_operator_update, raising=False)

    result = run_support_pipeline.run_pipeline(
        businessos_root=businessos_root,
        db_path=db_path,
        mirror_config_path=mirror_config,
        skip_email=False,
        skip_telegram=True,
        current_time='2026-05-03T12:30:00+00:00',
        operator_updates_config_path=config_dir / 'operator-updates.yaml',
    )

    assert len(notification_calls) >= 2
    assert result['operator_notifications']['sent_count'] >= 2
    assert result['daily_summary']['status'] in {'generated', 'sent'}
    assert Path(result['daily_summary']['report_path']).exists()


def test_run_pipeline_completion_notification_includes_imported_items_and_copied_paths(tmp_path, monkeypatch):
    businessos_root = tmp_path / 'BusinessOS'
    db_dir = businessos_root / '03_DATA' / 'db'
    db_dir.mkdir(parents=True)
    db_path = db_dir / 'businessos.db'
    _seed_db(db_path)

    scripts_dir = businessos_root / '04_AUTOMATIONS' / 'scripts'
    scripts_dir.mkdir(parents=True)
    (scripts_dir / 'poll_support_email.py').write_text('def main():\n    pass\n', encoding='utf-8')
    (scripts_dir / 'poll_telegram_updates.py').write_text('def getUpdates():\n    return []\n', encoding='utf-8')

    config_dir = businessos_root / '04_AUTOMATIONS' / 'configs'
    config_dir.mkdir(parents=True)
    (config_dir / 'support-inboxes.yaml').write_text('accounts: []\n', encoding='utf-8')
    (config_dir / 'telegram-sources.yaml').write_text(
        '\n'.join(
            [
                'accounts:',
                '  - id: telegram-businessos-operator',
                '    chat_id: "6765506693"',
                '    app_id: steadyapp',
                '    lane: operator-control',
                '    bot_token_env: BUSINESSOS_TELEGRAM_OPERATOR_BOT_TOKEN',
                '    live_poll: false',
                '    auto_import: false',
                '    manual_only: false',
                '    reaction_mode: internal-ops',
                '',
            ]
        ),
        encoding='utf-8',
    )
    (config_dir / 'operator-updates.yaml').write_text(
        '\n'.join(
            [
                'enabled: true',
                'telegram_source_account: telegram-businessos-operator',
                'timezone: America/New_York',
                'morning_digest_local_time: "08:00"',
                'send_run_started: true',
                'send_step_updates: true',
                'send_run_completed: true',
                'send_daily_summary: true',
                '',
            ]
        ),
        encoding='utf-8',
    )
    mirror_config = config_dir / 'dropbox-mirror.yaml'
    mirror_config.write_text(
        '\n'.join(
            [
                f'source_root: {businessos_root}',
                f'dropbox_root: {tmp_path / "Dropbox" / "BusinessOS"}',
                'include_paths:',
                '  - 05_REPORTS',
                'prune: false',
                '',
            ]
        ),
        encoding='utf-8',
    )

    notifications = []
    document_path = (
        businessos_root
        / '01_DOCUMENTS'
        / 'finance'
        / 'expenses'
        / '2026'
        / '2026-05-02__receipt__google__25-00__forwarded-email.eml'
    )
    document_path.parent.mkdir(parents=True, exist_ok=True)
    document_path.write_text('receipt email', encoding='utf-8')
    metadata_path = businessos_root / '03_DATA' / 'metadata' / 'doc-2026-05-02-b5a53038.json'
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text('{"id": "doc-2026-05-02-b5a53038"}', encoding='utf-8')

    def fake_send_operator_update(*, text, attachment_paths=None, **kwargs):
        notifications.append({'text': text, 'attachment_paths': list(attachment_paths or [])})
        return {'status': 'sent', 'attachment_count': len(attachment_paths or [])}

    def fake_poll_support_email(**kwargs):
        return {
            'imported_count': 1,
            'accounts': {'helix-admin': {'imported_count': 1, 'status': 'completed'}},
            'imported_messages': [
                {
                    'source_account': 'helix-admin',
                    'subject': 'Fwd: Google: Thank you',
                    'sender_handle': 'payments-noreply@google.com',
                    'category': 'business-expense-record',
                    'assigned_queue': 'finance-review',
                    'normalized_path': '/tmp/email1.json',
                    'linked_document_ids': ['doc-2026-05-02-b5a53038'],
                }
            ],
            'status': 'completed',
        }

    def fake_poll_telegram_updates(**kwargs):
        return {'imported_count': 0, 'accounts': {'telegram-steady-support': {'imported_count': 0, 'status': 'completed'}}, 'imported_messages': [], 'status': 'completed'}

    def fake_process_document_inbox(**kwargs):
        return {
            'processed_count': 1,
            'documents': [
                {
                    'id': 'doc-2026-05-02-b5a53038',
                    'document_type': 'receipt',
                    'vendor_name': 'google',
                    'amount': 25.0,
                    'local_path': str(document_path),
                }
            ],
            'status': 'completed',
        }

    def fake_run_dropbox_mirror(*args, **kwargs):
        return {
            'copied_count': 2,
            'deleted_count': 0,
            'copied': [
                '01_DOCUMENTS/finance/expenses/2026/2026-05-02__receipt__google__25-00__forwarded-email.eml',
                '03_DATA/metadata/doc-2026-05-02-b5a53038.json',
            ],
            'deleted': [],
        }

    monkeypatch.setattr(run_support_pipeline, 'send_operator_update', fake_send_operator_update, raising=False)
    monkeypatch.setattr(run_support_pipeline, 'poll_support_email', fake_poll_support_email)
    monkeypatch.setattr(run_support_pipeline, 'poll_telegram_updates', fake_poll_telegram_updates)
    monkeypatch.setattr(run_support_pipeline, 'process_document_inbox', fake_process_document_inbox)
    monkeypatch.setattr(run_support_pipeline, 'run_dropbox_mirror', fake_run_dropbox_mirror)

    run_support_pipeline.run_pipeline(
        businessos_root=businessos_root,
        db_path=db_path,
        mirror_config_path=mirror_config,
        skip_email=False,
        skip_telegram=False,
        current_time='2026-05-03T12:30:00+00:00',
        operator_updates_config_path=config_dir / 'operator-updates.yaml',
    )

    completion_notifications = [item for item in notifications if item['text'].startswith('BusinessOS run completed')]
    assert len(completion_notifications) == 1
    completion_notification = completion_notifications[0]
    completion_message = completion_notification['text']
    assert 'Fwd: Google: Thank you' in completion_message
    assert 'payments-noreply@google.com' in completion_message
    assert 'Classification: expense / business-expense-record / finance-review' in completion_message
    assert 'doc-2026-05-02-b5a53038' in completion_message
    assert '2026-05-02__receipt__google__25-00__forwarded-email.eml' in completion_message
    assert '03_DATA/metadata/doc-2026-05-02-b5a53038.json' in completion_message
    completion_attachment_paths = {Path(path).resolve() for path in completion_notification['attachment_paths']}
    assert document_path.resolve() in completion_attachment_paths
    assert metadata_path.resolve() in completion_attachment_paths
    assert any(path.name.endswith('-support-health-check.md') for path in completion_attachment_paths)
    assert any(path.name.endswith('-support-readiness-audit.md') for path in completion_attachment_paths)
    assert any(path.name.endswith('-task-dashboard.md') for path in completion_attachment_paths)
    assert any(path.name.endswith('-finance-summary.md') for path in completion_attachment_paths)
    assert any(path.name.endswith('-deductible-summary.md') for path in completion_attachment_paths)

    email_step_notifications = [item for item in notifications if 'Step: email' in item['text']]
    assert len(email_step_notifications) == 1
    assert 'Fwd: Google: Thank you' in email_step_notifications[0]['text']
    assert 'payments-noreply@google.com' in email_step_notifications[0]['text']
    assert 'Classification: expense / business-expense-record / finance-review' in email_step_notifications[0]['text']

    dropbox_step_notifications = [item for item in notifications if 'Step: dropbox_mirror' in item['text']]
    assert len(dropbox_step_notifications) == 1
    assert '03_DATA/metadata/doc-2026-05-02-b5a53038.json' in dropbox_step_notifications[0]['text']
    dropbox_attachment_paths = {Path(path).resolve() for path in dropbox_step_notifications[0]['attachment_paths']}
    assert document_path.resolve() in dropbox_attachment_paths
    assert metadata_path.resolve() in dropbox_attachment_paths
