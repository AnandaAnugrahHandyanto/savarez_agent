import json
import sqlite3
import sys
from email.message import EmailMessage
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / '04_AUTOMATIONS' / 'scripts'
sys.path.insert(0, str(SCRIPTS_DIR))

import business_ops_core
import manage_tasks
import poll_support_email
import poll_telegram_updates
import run_support_pipeline


class FakeIMAP:
    def __init__(self, messages_by_uid: dict[str, bytes]):
        self.messages_by_uid = messages_by_uid

    def login(self, username: str, password: str):
        return 'OK', [b'Success']

    def select(self, mailbox: str):
        return 'OK', [str(len(self.messages_by_uid)).encode()]

    def uid(self, command: str, *args):
        normalized = command.upper()
        if normalized == 'SEARCH':
            criterion = args[-1]
            if isinstance(criterion, bytes):
                criterion = criterion.decode('utf-8')
            start_uid = int(str(criterion).split(':', 1)[0])
            matching = [uid for uid in sorted(self.messages_by_uid, key=int) if int(uid) >= start_uid]
            return 'OK', [' '.join(matching).encode('utf-8')]
        if normalized == 'FETCH':
            uid = args[0]
            if isinstance(uid, bytes):
                uid = uid.decode('utf-8')
            payload = self.messages_by_uid[uid]
            return 'OK', [(f'{uid} (RFC822 {{{len(payload)}}})'.encode('utf-8'), payload), b')']
        raise AssertionError(f'Unexpected UID command: {command} {args!r}')

    def logout(self):
        return 'BYE', [b'LOGOUT']


class FakeTelegramAPI:
    def __init__(self, updates):
        self.updates = updates

    def get_me(self, token: str) -> dict:
        return {
            'id': 8210492819,
            'is_bot': True,
            'username': 'steady_support_bot',
            'can_join_groups': True,
            'can_read_all_group_messages': True,
        }

    def get_updates(self, token: str, offset: int | None = None, allowed_updates=None) -> dict:
        return {'ok': True, 'result': self.updates}


def _init_empty_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    business_ops_core.ensure_business_ops_tables(con)
    con.commit()
    con.close()


def test_process_document_file_logs_business_expense_for_tax_use(tmp_path):
    businessos_root = tmp_path / 'BusinessOS'
    db_path = businessos_root / '03_DATA' / 'db' / 'businessos.db'
    _init_empty_db(db_path)

    inbox_dir = businessos_root / '00_INBOX' / 'manual-drop'
    inbox_dir.mkdir(parents=True)
    source_path = inbox_dir / 'cloudflare-invoice.txt'
    source_path.write_text(
        'Cloudflare invoice\nDate: 2026-05-02\nAmount Due: $19.99\nSteady app domain and hosting\n',
        encoding='utf-8',
    )

    result = business_ops_core.process_document_file(
        businessos_root=businessos_root,
        db_path=db_path,
        input_path=source_path,
        source_channel='manual-drop',
        move_source=True,
    )

    assert result['status'] == 'processed'
    assert result['document']['finance_direction'] == 'expense'
    assert result['document']['vendor_name'] == 'cloudflare'
    assert Path(result['document']['local_path']).exists()
    assert 'finance/expenses/2026' in result['document']['local_path']
    assert not source_path.exists()

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    document = con.execute('select * from documents').fetchone()
    tax = con.execute(
        'select tax_relevance, tax_category_federal from expense_tax_treatment where document_id = ?',
        (document['id'],),
    ).fetchone()
    con.close()

    assert document['finance_direction'] == 'expense'
    assert tax['tax_relevance'] == 'deductible'
    assert tax['tax_category_federal'] == 'web-hosting-and-domains'

    metadata_path = businessos_root / '03_DATA' / 'metadata' / f"{document['id']}.json"
    metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
    assert metadata['finance_direction'] == 'expense'
    assert metadata['tax']['tax_category_federal'] == 'web-hosting-and-domains'


def test_task_manager_keeps_status_comments_reminders_document_links_and_transcript(tmp_path):
    businessos_root = tmp_path / 'BusinessOS'
    db_path = businessos_root / '03_DATA' / 'db' / 'businessos.db'
    _init_empty_db(db_path)

    task = business_ops_core.create_task(
        db_path=db_path,
        title='Prepare Q2 support and tax review',
        description='Compile support receipts and tax notes.',
        source_channel='cli',
        author_handle='Poiuy',
        due_at='2026-05-20T17:00:00-04:00',
        reminder_at='2026-05-18T09:00:00-04:00',
    )
    business_ops_core.update_task_status(
        db_path=db_path,
        task_id=task['id'],
        status='in_progress',
        source_channel='cli',
        author_handle='Poiuy',
    )
    business_ops_core.add_task_comment(
        db_path=db_path,
        task_id=task['id'],
        body='Started review and gathered the first batch of receipts.',
        source_channel='cli',
        author_handle='Poiuy',
    )

    doc_source = businessos_root / '00_INBOX' / 'manual-drop' / 'zoho-receipt.txt'
    doc_source.parent.mkdir(parents=True, exist_ok=True)
    doc_source.write_text(
        'Zoho Mail receipt\nDate: 2026-05-03\nAmount: $15.00\nBusiness email subscription\n',
        encoding='utf-8',
    )
    document = business_ops_core.process_document_file(
        businessos_root=businessos_root,
        db_path=db_path,
        input_path=doc_source,
        source_channel='manual-drop',
        related_task_id=task['id'],
        move_source=True,
    )['document']

    transcript_path = manage_tasks.write_task_transcript(
        businessos_root=businessos_root,
        db_path=db_path,
        task_id=task['id'],
    )

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    task_row = con.execute('select * from task_items where id = ?', (task['id'],)).fetchone()
    reminder = con.execute('select * from reminders where item_type = ? and item_id = ?', ('task', task['id'])).fetchone()
    link = con.execute('select * from task_documents where task_id = ? and document_id = ?', (task['id'], document['id'])).fetchone()
    comment = con.execute('select * from task_comments where task_id = ?', (task['id'],)).fetchone()
    event_count = con.execute('select count(*) as c from task_events where task_id = ?', (task['id'],)).fetchone()['c']
    con.close()

    assert task_row['status'] == 'in_progress'
    assert reminder['due_date'] == '2026-05-18T09:00:00-04:00'
    assert link['relationship_type'] == 'reference'
    assert 'Started review' in comment['body']
    assert event_count >= 4

    transcript = transcript_path.read_text(encoding='utf-8')
    assert task['id'] in transcript
    assert 'Prepare Q2 support and tax review' in transcript
    assert 'status_changed' in transcript
    assert 'document_linked' in transcript
    assert document['stored_filename'] in transcript


def test_poll_support_email_creates_task_and_links_attachment_document(tmp_path, monkeypatch):
    businessos_root = tmp_path / 'BusinessOS'
    db_path = businessos_root / '03_DATA' / 'db' / 'businessos.db'
    _init_empty_db(db_path)

    config_dir = businessos_root / '04_AUTOMATIONS' / 'configs'
    config_dir.mkdir(parents=True)
    config_path = config_dir / 'support-inboxes.yaml'
    config_path.write_text(
        '\n'.join(
            [
                'accounts:',
                '  - id: helix-admin',
                '    address: admin@helixsystems.cc',
                '    app_id: steadyapp',
                '    host: imappro.zoho.com',
                '    port: 993',
                '    ssl: true',
                '    mailbox: INBOX',
                '    username: admin@helixsystems.cc',
                '    password_env: BUSINESSOS_HELIX_ADMIN_IMAP_PASSWORD',
                '    aliases:',
                '      - address: support@helixsystems.cc',
                '        queue: customer-support',
                '        mailbox_role: customer-support',
                '        email_account_id: support_helixsystems_cc',
                '',
            ]
        ),
        encoding='utf-8',
    )

    email_message = EmailMessage()
    email_message['From'] = 'Poiuy <poiuy@example.com>'
    email_message['To'] = 'support@helixsystems.cc'
    email_message['Subject'] = 'TODO: Reconcile Cloudflare renewal'
    email_message['Message-ID'] = '<todo-1@example.com>'
    email_message['Date'] = 'Sat, 02 May 2026 11:30:00 +0000'
    email_message.set_content('Please track this renewal for taxes and ops.\nReminder: 2026-05-12T09:00:00-04:00\n')
    email_message.add_attachment(
        b'Cloudflare invoice\nDate: 2026-05-02\nAmount Due: $19.99\nSteady app hosting\n',
        maintype='text',
        subtype='plain',
        filename='cloudflare-renewal.txt',
    )

    monkeypatch.setenv('BUSINESSOS_HELIX_ADMIN_IMAP_PASSWORD', 'fake-password')

    result = poll_support_email.poll_support_email(
        businessos_root=businessos_root,
        db_path=db_path,
        config_path=config_path,
        imap_factory=lambda host, port: FakeIMAP({'22': email_message.as_bytes()}),
    )

    assert result['imported_count'] == 1

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    task_row = con.execute('select * from task_items').fetchone()
    document_row = con.execute('select * from documents').fetchone()
    link = con.execute('select * from task_documents').fetchone()
    reminder = con.execute('select * from reminders where item_type = ?', ('task',)).fetchone()
    con.close()

    assert task_row['title'] == 'Reconcile Cloudflare renewal'
    assert task_row['source_channel'] == 'email'
    assert document_row['finance_direction'] == 'expense'
    assert link['task_id'] == task_row['id']
    assert link['document_id'] == document_row['id']
    assert reminder['due_date'] == '2026-05-12T09:00:00-04:00'


def test_poll_telegram_updates_creates_task_from_todo_command(tmp_path, monkeypatch):
    businessos_root = tmp_path / 'BusinessOS'
    db_path = businessos_root / '03_DATA' / 'db' / 'businessos.db'
    _init_empty_db(db_path)

    config_dir = businessos_root / '04_AUTOMATIONS' / 'configs'
    config_dir.mkdir(parents=True)
    config_path = config_dir / 'telegram-sources.yaml'
    config_path.write_text(
        '\n'.join(
            [
                'accounts:',
                '  - id: telegram-steady-support',
                '    chat_id: "-5087084218"',
                '    app_id: steadyapp',
                '    lane: customer-support',
                '    bot_token_env: BUSINESSOS_TELEGRAM_SUPPORT_BOT_TOKEN',
                '    auto_import: true',
                '    live_poll: true',
                '    operator_user_ids: [8760904576]',
                '    operator_usernames: [yuioppiime]',
                '',
            ]
        ),
        encoding='utf-8',
    )

    monkeypatch.setenv('BUSINESSOS_TELEGRAM_SUPPORT_BOT_TOKEN', 'fake-token')

    update = {
        'update_id': 70000001,
        'message': {
            'message_id': 31,
            'from': {
                'id': 8760904576,
                'is_bot': False,
                'first_name': 'Poiuy',
                'username': 'yuioppiime',
            },
            'chat': {
                'id': -5087084218,
                'title': 'Steady App Support',
                'type': 'group',
            },
            'date': 1777700000,
            'text': '/todo Draft the Q2 support operations checklist\nReminder: 2026-05-15T09:00:00-04:00',
        },
    }

    result = poll_telegram_updates.poll_telegram_updates(
        businessos_root=businessos_root,
        db_path=db_path,
        config_path=config_path,
        telegram_api=FakeTelegramAPI([update]),
    )

    assert result['imported_count'] == 1

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    task_row = con.execute('select * from task_items').fetchone()
    reminder = con.execute('select * from reminders where item_type = ?', ('task',)).fetchone()
    event = con.execute('select * from task_events where task_id = ?', (task_row['id'],)).fetchone()
    con.close()

    assert task_row['title'] == 'Draft the Q2 support operations checklist'
    assert task_row['source_channel'] == 'telegram'
    assert reminder['due_date'] == '2026-05-15T09:00:00-04:00'
    assert event['source_message_id'] == '-5087084218-31'


def test_build_finance_reports_infers_direction_for_legacy_expense_rows(tmp_path):
    businessos_root = tmp_path / 'BusinessOS'
    db_path = businessos_root / '03_DATA' / 'db' / 'businessos.db'
    _init_empty_db(db_path)

    con = sqlite3.connect(db_path)
    business_ops_core.ensure_business_ops_tables(con)
    con.execute(
        '''
        insert into documents (
            id, original_filename, stored_filename, document_type, status, document_date, amount, currency,
            vendor_name, source_channel, local_path, extracted_text_path, sha256, tags_json, review_state,
            notes, created_at, updated_at, finance_direction
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            'doc-legacy-1',
            'legacy-cloudflare.pdf',
            'legacy-cloudflare.pdf',
            'invoice',
            'recorded',
            '2026-04-26',
            19.99,
            'USD',
            'cloudflare',
            'forwarded-email',
            str(businessos_root / '01_DOCUMENTS' / 'finance' / 'expenses' / '2026' / 'legacy-cloudflare.pdf'),
            str(businessos_root / '03_DATA' / 'extracted-text' / 'doc-legacy-1.txt'),
            'sha256-legacy',
            json.dumps(['invoice', 'cloudflare']),
            'auto-recorded',
            'legacy row without finance_direction',
            '2026-04-26T00:00:00+00:00',
            '2026-04-26T00:00:00+00:00',
            None,
        ),
    )
    con.execute(
        '''
        insert into expense_tax_treatment (
            document_id, tax_relevance, tax_category_federal, tax_category_nj, deduction_confidence,
            tax_year, schedule_or_return_section, evidence_status, business_purpose_note,
            mixed_use_flag, business_use_percent, nj_adjustment_required, nj_review_required,
            reviewed_by_human, review_notes, created_at, updated_at
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            'doc-legacy-1',
            'deductible',
            'web-hosting-and-domains',
            'web-hosting-and-domains',
            0.93,
            2026,
            None,
            'invoice-and-proof',
            'Legacy hosting expense',
            0,
            100.0,
            0,
            0,
            0,
            None,
            '2026-04-26T00:00:00+00:00',
            '2026-04-26T00:00:00+00:00',
        ),
    )
    con.commit()
    con.close()

    reports = business_ops_core.build_finance_reports(businessos_root=businessos_root, db_path=db_path)
    finance_text = reports['finance_summary_path'].read_text(encoding='utf-8')
    deductible_text = reports['deductible_summary_path'].read_text(encoding='utf-8')

    assert '- Total expenses: $19.99' in finance_text
    assert '| 2026-04-26 | expense | invoice | cloudflare | $19.99 | web-hosting-and-domains |' in finance_text
    assert '| web-hosting-and-domains | 1 | $19.99 |' in deductible_text


def test_run_pipeline_processes_document_inbox_and_builds_ops_reports(tmp_path):
    businessos_root = tmp_path / 'BusinessOS'
    db_path = businessos_root / '03_DATA' / 'db' / 'businessos.db'
    _init_empty_db(db_path)

    inbox_dir = businessos_root / '00_INBOX' / 'manual-drop'
    inbox_dir.mkdir(parents=True)
    (inbox_dir / 'hosting-invoice.txt').write_text(
        'Cloudflare invoice\nDate: 2026-05-02\nAmount Due: $19.99\nSteady hosting\n',
        encoding='utf-8',
    )

    business_ops_core.create_task(
        db_path=db_path,
        title='Review May operating expenses',
        description='Check the new hosting invoice and update records.',
        source_channel='cli',
        author_handle='Poiuy',
        reminder_at='2026-05-12T09:00:00-04:00',
    )

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

    assert result['steps']['document_inbox'] == 'completed'
    assert result['steps']['task_dashboard'] == 'completed'
    assert result['steps']['finance_reports'] == 'completed'
    assert result['document_intake']['processed_count'] == 1

    task_dashboard_path = Path(result['task_dashboard_path'])
    finance_summary_path = Path(result['finance_summary_path'])
    deductible_summary_path = Path(result['deductible_summary_path'])

    assert task_dashboard_path.exists()
    assert finance_summary_path.exists()
    assert deductible_summary_path.exists()
    assert 'Review May operating expenses' in task_dashboard_path.read_text(encoding='utf-8')
    assert '$19.99' in finance_summary_path.read_text(encoding='utf-8')
    assert 'web-hosting-and-domains' in deductible_summary_path.read_text(encoding='utf-8')
