import json
import sqlite3
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / '04_AUTOMATIONS' / 'scripts'
sys.path.insert(0, str(SCRIPTS_DIR))

import poll_telegram_updates


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
    cur.execute(
        "insert into ingestion_checkpoints (source_type, source_account, checkpoint_value, updated_at) values (?, ?, ?, ?)",
        ('telegram', 'telegram-steady-support', '70000000', '2026-05-02T00:00:00+00:00'),
    )
    con.commit()
    con.close()


def test_poll_telegram_updates_imports_operator_test_into_internal_queue(tmp_path, monkeypatch):
    businessos_root = tmp_path / 'BusinessOS'
    db_dir = businessos_root / '03_DATA' / 'db'
    db_dir.mkdir(parents=True)
    db_path = db_dir / 'businessos.db'
    _create_support_tables(db_path)

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
            'message_id': 21,
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
            'text': 'test 123',
        },
    }

    result = poll_telegram_updates.poll_telegram_updates(
        businessos_root=businessos_root,
        db_path=db_path,
        config_path=config_path,
        telegram_api=FakeTelegramAPI([update]),
    )

    assert result['imported_count'] == 1
    assert result['accounts']['telegram-steady-support']['imported_count'] == 1

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    checkpoint = cur.execute(
        "select checkpoint_value from ingestion_checkpoints where source_type='telegram' and source_account='telegram-steady-support'"
    ).fetchone()
    assert checkpoint['checkpoint_value'] == '70000001'

    thread = cur.execute("select * from communication_threads").fetchone()
    assert thread['assigned_queue'] == 'admin'
    assert thread['needs_human_reply'] == 0
    assert thread['id'].endswith('-internal-test')

    message = cur.execute("select * from communication_messages").fetchone()
    assert message['category'] == 'internal-test'
    assert message['priority'] == 'low'
    assert message['sender_handle'] == '@yuioppiime'
    assert Path(message['raw_path']).exists()
    assert Path(message['normalized_path']).exists()

    normalized = json.loads(Path(message['normalized_path']).read_text(encoding='utf-8'))
    assert normalized['text'] == 'test 123'
    assert normalized['category'] == 'internal-test'
    assert normalized['platform'] == 'telegram-bot'

    feedback = cur.execute("select * from feedback_items").fetchone()
    assert feedback['category'] == 'internal-test'
    assert feedback['thread_id'].endswith('-internal-test')

    source_account = cur.execute("select * from source_accounts where id='telegram-steady-support'").fetchone()
    assert source_account['external_ref'] == '-5087084218'

    con.close()


def test_poll_telegram_updates_keeps_operator_control_bot_out_of_customer_support_feedback(tmp_path, monkeypatch):
    businessos_root = tmp_path / 'BusinessOS'
    db_dir = businessos_root / '03_DATA' / 'db'
    db_dir.mkdir(parents=True)
    db_path = db_dir / 'businessos.db'
    _create_support_tables(db_path)

    config_dir = businessos_root / '04_AUTOMATIONS' / 'configs'
    config_dir.mkdir(parents=True)
    config_path = config_dir / 'telegram-sources.yaml'
    config_path.write_text(
        '\n'.join(
            [
                'accounts:',
                '  - id: telegram-businessos-operator',
                '    chat_id: "-9000000001"',
                '    chat_title: BusinessOS Operator',
                '    app_id: steadyapp',
                '    lane: operator-control',
                '    bot_token_env: BUSINESSOS_TELEGRAM_OPERATOR_BOT_TOKEN',
                '    auto_import: true',
                '    live_poll: true',
                '    operator_user_ids: [8760904576]',
                '    operator_usernames: [yuioppiime]',
                '',
            ]
        ),
        encoding='utf-8',
    )

    monkeypatch.setenv('BUSINESSOS_TELEGRAM_OPERATOR_BOT_TOKEN', 'fake-token')

    update = {
        'update_id': 81000001,
        'message': {
            'message_id': 44,
            'from': {
                'id': 8760904576,
                'is_bot': False,
                'first_name': 'Poiuy',
                'username': 'yuioppiime',
            },
            'chat': {
                'id': -9000000001,
                'title': 'BusinessOS Operator',
                'type': 'group',
            },
            'date': 1777700100,
            'text': '/todo Reconcile Helix receipts\nReminder: 2026-05-14T09:00:00-04:00',
        },
    }

    result = poll_telegram_updates.poll_telegram_updates(
        businessos_root=businessos_root,
        db_path=db_path,
        config_path=config_path,
        telegram_api=FakeTelegramAPI([update]),
    )

    assert result['imported_count'] == 1
    assert result['accounts']['telegram-businessos-operator']['imported_count'] == 1

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    thread = cur.execute("select * from communication_threads").fetchone()
    assert thread['assigned_queue'] == 'operator-control'
    assert thread['needs_human_reply'] == 0
    assert thread['unread_count'] == 0
    assert thread['last_customer_message_at'] is None
    assert thread['id'].endswith('-operator-control')

    message = cur.execute("select * from communication_messages").fetchone()
    assert message['category'] == 'operator-command'
    assert message['sender_role'] == 'operator'
    assert 'not customer support' in message['suggested_response'].lower()

    normalized = json.loads(Path(message['normalized_path']).read_text(encoding='utf-8'))
    assert normalized['task_operation']['action'] == 'create'
    assert normalized['sender_role'] == 'operator'
    assert normalized['routing_queue'] == 'operator-control'

    task = cur.execute("select * from task_items").fetchone()
    assert task['title'] == 'Reconcile Helix receipts'
    assert task['source_channel'] == 'telegram'
    assert task['source_account'] == 'telegram-businessos-operator'
    assert task['reminder_at'] == '2026-05-14T09:00:00-04:00'

    feedback_count = cur.execute("select count(*) from feedback_items").fetchone()[0]
    assert feedback_count == 0

    con.close()


def test_poll_telegram_updates_operator_control_accepts_hashtag_newtask_commands(tmp_path, monkeypatch):
    businessos_root = tmp_path / 'BusinessOS'
    db_path = businessos_root / '03_DATA' / 'db' / 'businessos.db'
    db_path.parent.mkdir(parents=True, exist_ok=True)
    _create_support_tables(db_path)

    config_dir = businessos_root / '04_AUTOMATIONS' / 'configs'
    config_dir.mkdir(parents=True)
    config_path = config_dir / 'telegram-sources.yaml'
    config_path.write_text(
        '\n'.join(
            [
                'accounts:',
                '  - id: telegram-businessos-operator',
                '    chat_id: ""',
                '    chat_title: BusinessOS Operator',
                '    app_id: steadyapp',
                '    lane: operator-control',
                '    bot_token_env: BUSINESSOS_TELEGRAM_OPERATOR_BOT_TOKEN',
                '    auto_import: true',
                '    live_poll: true',
                '    manual_only: false',
                '    reaction_mode: internal-ops',
                '    operator_user_ids: [8760904576]',
                '    operator_usernames: [yuioppiime]',
                '',
            ]
        ),
        encoding='utf-8',
    )

    monkeypatch.setenv('BUSINESSOS_TELEGRAM_OPERATOR_BOT_TOKEN', 'fake-token')

    update = {
        'update_id': 81000002,
        'message': {
            'message_id': 45,
            'from': {
                'id': 8760904576,
                'is_bot': False,
                'first_name': 'Poiuy',
                'username': 'yuioppiime',
            },
            'chat': {
                'id': 6765506693,
                'title': 'Poiuy',
                'type': 'private',
            },
            'date': 1777700200,
            'text': '#newtask Finish registering with Google Play Console',
        },
    }

    result = poll_telegram_updates.poll_telegram_updates(
        businessos_root=businessos_root,
        db_path=db_path,
        config_path=config_path,
        telegram_api=FakeTelegramAPI([update]),
    )

    assert result['imported_count'] == 1
    assert result['accounts']['telegram-businessos-operator']['imported_count'] == 1

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    message = cur.execute("select * from communication_messages").fetchone()
    assert message['category'] == 'operator-command'
    assert message['sender_role'] == 'operator'

    normalized = json.loads(Path(message['normalized_path']).read_text(encoding='utf-8'))
    assert normalized['task_operation']['action'] == 'create'

    task = cur.execute("select * from task_items").fetchone()
    assert task['title'] == 'Finish registering with Google Play Console'
    assert task['source_channel'] == 'telegram'
    assert task['source_account'] == 'telegram-businessos-operator'

    con.close()
