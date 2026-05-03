import json
import sqlite3
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / '04_AUTOMATIONS' / 'scripts'
sys.path.insert(0, str(SCRIPTS_DIR))

import poll_support_email


class FakeIMAP:
    def __init__(self, messages_by_uid: dict[str, bytes]):
        self.messages_by_uid = messages_by_uid
        self.selected_mailbox = None
        self.logged_in = False

    def login(self, username: str, password: str):
        self.logged_in = True
        return 'OK', [b'Success']

    def select(self, mailbox: str):
        self.selected_mailbox = mailbox
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


def _create_support_tables(db_path: Path) -> None:
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.executescript(
        '''
        create table source_accounts (
            id text primary key,
            source_type text not null,
            external_ref text,
            app_id text,
            config_json text,
            active integer default 1,
            created_at text default current_timestamp,
            updated_at text default current_timestamp
        );
        create table ingestion_checkpoints (
            source_type text not null,
            source_account text not null,
            checkpoint_value text,
            updated_at text default current_timestamp,
            primary key (source_type, source_account)
        );
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
        create table feedback_items (
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
    con.close()


def test_poll_support_email_imports_new_messages_and_routes_alias_queue(tmp_path, monkeypatch):
    businessos_root = tmp_path / 'BusinessOS'
    db_dir = businessos_root / '03_DATA' / 'db'
    db_dir.mkdir(parents=True)
    db_path = db_dir / 'businessos.db'
    _create_support_tables(db_path)

    config_dir = businessos_root / '04_AUTOMATIONS' / 'configs'
    config_dir.mkdir(parents=True)
    config_path = config_dir / 'support-inboxes.yaml'
    config_path.write_text(
        '\n'.join(
            [
                'accounts:',
                '  - id: helix-admin',
                '    address: admin@helixsystems.cc',
                '    app_id: helixsystems-admin',
                '    host: imappro.zoho.com',
                '    port: 993',
                '    ssl: true',
                '    mailbox: INBOX',
                '    username: admin@helixsystems.cc',
                '    password_env: BUSINESSOS_HELIX_ADMIN_IMAP_PASSWORD',
                '    aliases:',
                '      - address: billing@helixsystems.cc',
                '        queue: billing-support',
                '        mailbox_role: billing-support',
                '        email_account_id: billing_helixsystems_cc',
                '',
            ]
        ),
        encoding='utf-8',
    )

    message_bytes = (
        b'From: Test Customer <customer@example.com>\r\n'
        b'To: billing@helixsystems.cc\r\n'
        b'Subject: Refund request\r\n'
        b'Message-ID: <refund-1@example.com>\r\n'
        b'Date: Fri, 02 May 2026 11:30:00 +0000\r\n'
        b'MIME-Version: 1.0\r\n'
        b'Content-Type: text/plain; charset=utf-8\r\n'
        b'\r\n'
        b'I need a refund because the app charged me twice.\r\n'
    )

    monkeypatch.setenv('BUSINESSOS_HELIX_ADMIN_IMAP_PASSWORD', 'fake-password')

    result = poll_support_email.poll_support_email(
        businessos_root=businessos_root,
        db_path=db_path,
        config_path=config_path,
        imap_factory=lambda host, port: FakeIMAP({'22': message_bytes}),
    )

    assert result['imported_count'] == 1
    assert result['accounts']['helix-admin']['imported_count'] == 1
    assert len(result['imported_messages']) == 1
    imported = result['imported_messages'][0]
    assert imported['subject'] == 'Refund request'
    assert imported['sender_handle'] == 'customer@example.com'
    assert imported['assigned_queue'] == 'billing-support'
    assert imported['source_account'] == 'helix-admin'
    assert imported['normalized_path'].endswith('.json')
    assert imported['suggested_task']['title'] == 'Respond to billing issue: Refund request'
    assert imported['suggested_task']['status'] == 'suggested'

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    checkpoint = cur.execute(
        "select checkpoint_value from ingestion_checkpoints where source_type='email' and source_account='helix-admin'"
    ).fetchone()
    assert checkpoint['checkpoint_value'] == '22'

    thread = cur.execute("select * from communication_threads").fetchone()
    assert thread['assigned_queue'] == 'billing-support'
    assert thread['source_account'] == 'helix-admin'
    assert thread['customer_handle'] == 'customer@example.com'

    message = cur.execute("select * from communication_messages").fetchone()
    assert message['category'] == 'billing'
    assert message['priority'] == 'high'
    assert Path(message['raw_path']).exists()
    assert Path(message['normalized_path']).exists()

    normalized = json.loads(Path(message['normalized_path']).read_text(encoding='utf-8'))
    assert normalized['routed_address'] == 'billing@helixsystems.cc'
    assert normalized['mailbox_role'] == 'billing-support'
    assert normalized['mailbox_entity_id'] == 'billing_helixsystems_cc'
    assert normalized['suggested_task']['title'] == 'Respond to billing issue: Refund request'
    assert normalized['suggested_task']['status'] == 'suggested'

    suggestion = cur.execute("select * from task_suggestions").fetchone()
    assert suggestion['title'] == 'Respond to billing issue: Refund request'
    assert suggestion['status'] == 'suggested'
    task_count = cur.execute("select count(*) from task_items").fetchone()[0]
    assert task_count == 0

    feedback = cur.execute("select * from feedback_items").fetchone()
    assert feedback['category'] == 'billing'
    assert feedback['source_account'] == 'helix-admin'

    source_account = cur.execute("select * from source_accounts where id='helix-admin'").fetchone()
    assert source_account['external_ref'] == 'admin@helixsystems.cc'

    con.close()


def test_poll_support_email_catalogs_dnb_identity_emails_as_business_records(tmp_path, monkeypatch):
    businessos_root = tmp_path / 'BusinessOS'
    db_dir = businessos_root / '03_DATA' / 'db'
    db_dir.mkdir(parents=True)
    db_path = db_dir / 'businessos.db'
    _create_support_tables(db_path)

    config_dir = businessos_root / '04_AUTOMATIONS' / 'configs'
    config_dir.mkdir(parents=True)
    config_path = config_dir / 'support-inboxes.yaml'
    config_path.write_text(
        '\n'.join(
            [
                'accounts:',
                '  - id: helix-admin',
                '    address: admin@helixsystems.cc',
                '    app_id: helixsystems-admin',
                '    host: imappro.zoho.com',
                '    port: 993',
                '    ssl: true',
                '    mailbox: INBOX',
                '    username: admin@helixsystems.cc',
                '    password_env: BUSINESSOS_HELIX_ADMIN_IMAP_PASSWORD',
                '    aliases:',
                '      - address: owner@helixsystems.cc',
                '        queue: admin',
                '        mailbox_role: owner',
                '        email_account_id: owner_helixsystems_cc',
                '',
            ]
        ),
        encoding='utf-8',
    )

    message_bytes = (
        b'From: Dun & Bradstreet <t.email@dnb.com>\r\n'
        b'To: owner@helixsystems.cc\r\n'
        b'Subject: Your DUNS Lookup Request for HELIX SYSTEMS LLC\r\n'
        b'Message-ID: <dnb-1@example.com>\r\n'
        b'Date: Sat, 02 May 2026 17:03:54 +0000\r\n'
        b'MIME-Version: 1.0\r\n'
        b'Content-Type: text/plain; charset=utf-8\r\n'
        b'\r\n'
        b'The following is the Dun & Bradstreet D-U-N-S Number for HELIX SYSTEMS LLC.\r\n'
        b'D-U-N-S number: 145775043\r\n'
        b'If this is your company, monitor your Dun & Bradstreet business credit file.\r\n'
    )

    monkeypatch.setenv('BUSINESSOS_HELIX_ADMIN_IMAP_PASSWORD', 'fake-password')

    result = poll_support_email.poll_support_email(
        businessos_root=businessos_root,
        db_path=db_path,
        config_path=config_path,
        imap_factory=lambda host, port: FakeIMAP({'24': message_bytes}),
    )

    assert result['imported_count'] == 1
    assert result['accounts']['helix-admin']['imported_count'] == 1

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    thread = cur.execute("select * from communication_threads").fetchone()
    message = cur.execute("select * from communication_messages").fetchone()
    document = cur.execute("select * from documents").fetchone()
    feedback = cur.execute("select * from feedback_items").fetchone()
    con.close()

    assert thread['assigned_queue'] == 'admin'
    assert thread['needs_human_reply'] == 0
    assert message['category'] == 'business-identity-record'
    assert message['priority'] == 'medium'

    normalized = json.loads(Path(message['normalized_path']).read_text(encoding='utf-8'))
    assert normalized['mailbox_role'] == 'owner'
    assert normalized['routed_address'] == 'owner@helixsystems.cc'
    assert normalized['mailbox_entity_id'] == 'owner_helixsystems_cc'
    assert normalized['linked_document_ids'] == [document['id']]

    assert document['document_type'] == 'business-identity-record'
    assert document['vendor_name'] == 'dun-and-bradstreet'
    assert document['finance_direction'] is None
    assert document['source_channel'] == 'forwarded-email'
    assert document['source_reference'] == '<dnb-1@example.com>'
    assert 'operations/business-identity/2026' in document['local_path']

    metadata_path = businessos_root / '03_DATA' / 'metadata' / f"{document['id']}.json"
    metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
    assert metadata['business_identity']['issuer'] == 'dun-and-bradstreet'
    assert metadata['business_identity']['company_name'] == 'HELIX SYSTEMS LLC'
    assert metadata['business_identity']['duns_number'] == '145775043'

    assert feedback['category'] == 'business-identity-record'
    assert feedback['theme'] == 'business-identity'


def test_poll_support_email_catalogs_expense_alias_emails_for_finance_and_tax(tmp_path, monkeypatch):
    businessos_root = tmp_path / 'BusinessOS'
    db_dir = businessos_root / '03_DATA' / 'db'
    db_dir.mkdir(parents=True)
    db_path = db_dir / 'businessos.db'
    _create_support_tables(db_path)

    config_dir = businessos_root / '04_AUTOMATIONS' / 'configs'
    config_dir.mkdir(parents=True)
    config_path = config_dir / 'support-inboxes.yaml'
    config_path.write_text(
        '\n'.join(
            [
                'accounts:',
                '  - id: helix-admin',
                '    address: admin@helixsystems.cc',
                '    app_id: helixsystems-admin',
                '    host: imappro.zoho.com',
                '    port: 993',
                '    ssl: true',
                '    mailbox: INBOX',
                '    username: admin@helixsystems.cc',
                '    password_env: BUSINESSOS_HELIX_ADMIN_IMAP_PASSWORD',
                '    aliases:',
                '      - address: expenses@helixsystems.cc',
                '        queue: finance-review',
                '        mailbox_role: expense-intake',
                '        email_account_id: expenses_helixsystems_cc',
                '',
            ]
        ),
        encoding='utf-8',
    )

    message_bytes = (
        b'From: Cloudflare Billing <billing@cloudflare.com>\r\n'
        b'To: expenses@helixsystems.cc\r\n'
        b'Subject: Fwd: Cloudflare invoice for domain renewal\r\n'
        b'Message-ID: <expense-1@example.com>\r\n'
        b'Date: Sat, 02 May 2026 18:10:00 +0000\r\n'
        b'MIME-Version: 1.0\r\n'
        b'Content-Type: text/plain; charset=utf-8\r\n'
        b'\r\n'
        b'Invoice total: $23.99\r\n'
        b'Cloudflare domain renewal for helixsystems.cc\r\n'
        b'Please capture this business expense for tax records.\r\n'
    )

    monkeypatch.setenv('BUSINESSOS_HELIX_ADMIN_IMAP_PASSWORD', 'fake-password')

    result = poll_support_email.poll_support_email(
        businessos_root=businessos_root,
        db_path=db_path,
        config_path=config_path,
        imap_factory=lambda host, port: FakeIMAP({'25': message_bytes}),
    )

    assert result['imported_count'] == 1
    assert result['accounts']['helix-admin']['imported_count'] == 1

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    thread = cur.execute("select * from communication_threads").fetchone()
    message = cur.execute("select * from communication_messages").fetchone()
    document = cur.execute("select * from documents").fetchone()
    tax = cur.execute("select * from expense_tax_treatment").fetchone()
    feedback = cur.execute("select * from feedback_items").fetchone()
    con.close()

    assert thread['assigned_queue'] == 'finance-review'
    assert thread['needs_human_reply'] == 0
    assert message['category'] == 'business-expense-record'
    assert message['priority'] == 'medium'

    normalized = json.loads(Path(message['normalized_path']).read_text(encoding='utf-8'))
    assert normalized['mailbox_role'] == 'expense-intake'
    assert normalized['routed_address'] == 'expenses@helixsystems.cc'
    assert normalized['mailbox_entity_id'] == 'expenses_helixsystems_cc'
    assert normalized['linked_document_ids'] == [document['id']]

    assert document['document_type'] == 'invoice'
    assert document['vendor_name'] == 'cloudflare'
    assert document['finance_direction'] == 'expense'
    assert document['source_channel'] == 'forwarded-email'
    assert document['source_reference'] == '<expense-1@example.com>'
    assert 'finance/expenses/2026' in document['local_path']

    metadata_path = businessos_root / '03_DATA' / 'metadata' / f"{document['id']}.json"
    metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
    assert metadata['finance_direction'] == 'expense'
    assert metadata['tax']['tax_relevance'] == 'deductible'
    assert metadata['tax']['tax_category_federal'] == 'web-hosting-and-domains'

    assert tax['document_id'] == document['id']
    assert tax['tax_relevance'] == 'deductible'
    assert tax['tax_category_federal'] == 'web-hosting-and-domains'
    assert tax['evidence_status'] == 'invoice-and-proof'

    assert feedback['category'] == 'business-expense-record'
    assert feedback['theme'] == 'finance-expense'


def test_poll_support_email_catalogs_google_purchase_receipts_from_expenses_alias_for_tax(tmp_path, monkeypatch):
    businessos_root = tmp_path / 'BusinessOS'
    db_dir = businessos_root / '03_DATA' / 'db'
    db_dir.mkdir(parents=True)
    db_path = db_dir / 'businessos.db'
    _create_support_tables(db_path)

    config_dir = businessos_root / '04_AUTOMATIONS' / 'configs'
    config_dir.mkdir(parents=True)
    config_path = config_dir / 'support-inboxes.yaml'
    config_path.write_text(
        '\n'.join(
            [
                'accounts:',
                '  - id: helix-admin',
                '    address: admin@helixsystems.cc',
                '    app_id: helixsystems-admin',
                '    host: imappro.zoho.com',
                '    port: 993',
                '    ssl: true',
                '    mailbox: INBOX',
                '    username: admin@helixsystems.cc',
                '    password_env: BUSINESSOS_HELIX_ADMIN_IMAP_PASSWORD',
                '    aliases:',
                '      - address: expenses@helixsystems.cc',
                '        queue: finance-review',
                '        mailbox_role: expense-intake',
                '        email_account_id: expenses_helixsystems_cc',
                '',
            ]
        ),
        encoding='utf-8',
    )

    message_bytes = (
        b'From: Ermal Lamcaj <ermal.lamcaj@gmail.com>\r\n'
        b'To: expenses@helixsystems.cc\r\n'
        b'Subject: Fwd: Google: Thank you\r\n'
        b'Message-ID: <expense-google-1@example.com>\r\n'
        b'Date: Sat, 02 May 2026 15:15:02 -0400\r\n'
        b'MIME-Version: 1.0\r\n'
        b'Content-Type: text/plain; charset=utf-8\r\n'
        b'\r\n'
        b'---------- Forwarded message ---------\r\n'
        b'From: Google Payments <payments-noreply@google.com>\r\n'
        b'Date: Sat, May 2, 2026, 1:23 PM\r\n'
        b'Subject: Google: Thank you\r\n'
        b'To: <ermal.lamcaj@gmail.com>\r\n'
        b'\r\n'
        b'Thank you\r\n'
        b"You've made a purchase from Google.\r\n"
        b'Item Quantity Price\r\n'
        b'Developer Registration Fee 1 $25.00\r\n'
        b'Tax $0.00\r\n'
        b'Total$25.00\r\n'
        b'Order number\r\n'
        b'PDS.5428-7184-3076-06268\r\n'
    )

    monkeypatch.setenv('BUSINESSOS_HELIX_ADMIN_IMAP_PASSWORD', 'fake-password')

    result = poll_support_email.poll_support_email(
        businessos_root=businessos_root,
        db_path=db_path,
        config_path=config_path,
        imap_factory=lambda host, port: FakeIMAP({'26': message_bytes}),
    )

    assert result['imported_count'] == 1

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    message = cur.execute("select * from communication_messages").fetchone()
    document = cur.execute("select * from documents").fetchone()
    tax = cur.execute("select * from expense_tax_treatment").fetchone()
    con.close()

    assert message['category'] == 'business-expense-record'
    assert document['document_type'] in {'receipt', 'invoice'}
    assert document['vendor_name'] == 'google'
    assert document['amount'] == 25.0
    assert document['finance_direction'] == 'expense'
    assert 'finance/expenses/2026' in document['local_path']

    metadata_path = businessos_root / '03_DATA' / 'metadata' / f"{document['id']}.json"
    metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
    assert metadata['tax']['tax_relevance'] == 'deductible'
    assert metadata['tax']['tax_category_federal'] == 'app-store-fees'

    assert tax['document_id'] == document['id']
    assert tax['tax_relevance'] == 'deductible'
    assert tax['tax_category_federal'] == 'app-store-fees'
