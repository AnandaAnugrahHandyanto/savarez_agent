from __future__ import annotations

import sqlite3
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / '04_AUTOMATIONS' / 'scripts'
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from operator_updates import _record_notification, ensure_operator_update_tables, send_operator_update


def test_record_notification_allows_multiple_same_type_same_second(tmp_path):
    db_path = tmp_path / 'businessos.db'
    con = sqlite3.connect(db_path)
    ensure_operator_update_tables(con)
    con.close()

    created_at = '2026-05-03T03:04:54+00:00'
    _record_notification(
        db_path=db_path,
        notification_type='manual-replay',
        source_account='telegram-businessos-operator',
        related_run_id='manual-replay-20260503T030453Z',
        report_date=None,
        body='BusinessOS replay 1/3',
        status='sent',
        external_message_id='1001',
        sent_at=created_at,
        created_at=created_at,
    )
    _record_notification(
        db_path=db_path,
        notification_type='manual-replay',
        source_account='telegram-businessos-operator',
        related_run_id='manual-replay-20260503T030453Z',
        report_date=None,
        body='BusinessOS replay 2/3',
        status='sent',
        external_message_id='1002',
        sent_at=created_at,
        created_at=created_at,
    )

    con = sqlite3.connect(db_path)
    count = con.execute('select count(*) from operator_notifications').fetchone()[0]
    ids = [row[0] for row in con.execute('select id from operator_notifications order by id').fetchall()]
    con.close()

    assert count == 2
    assert ids[0] != ids[1]


def test_send_operator_update_sends_openable_document_attachments(tmp_path, monkeypatch):
    businessos_root = tmp_path / 'BusinessOS'
    db_path = tmp_path / 'businessos.db'
    con = sqlite3.connect(db_path)
    ensure_operator_update_tables(con)
    con.close()

    config_dir = businessos_root / '04_AUTOMATIONS' / 'configs'
    config_dir.mkdir(parents=True)
    operator_updates_config = config_dir / 'operator-updates.yaml'
    operator_updates_config.write_text(
        '\n'.join(
            [
                'enabled: true',
                'telegram_source_account: telegram-businessos-operator',
                '',
            ]
        ),
        encoding='utf-8',
    )
    telegram_sources = config_dir / 'telegram-sources.yaml'
    telegram_sources.write_text(
        '\n'.join(
            [
                'accounts:',
                '  - id: telegram-businessos-operator',
                '    chat_id: "6765506693"',
                '    bot_token_env: BUSINESSOS_TELEGRAM_OPERATOR_BOT_TOKEN',
                '',
            ]
        ),
        encoding='utf-8',
    )

    attachment = businessos_root / '05_REPORTS' / 'support' / '2026-05-03-support-health-check.md'
    attachment.parent.mkdir(parents=True, exist_ok=True)
    attachment.write_text('# report\n', encoding='utf-8')

    monkeypatch.setenv('BUSINESSOS_TELEGRAM_OPERATOR_BOT_TOKEN', 'token-123')

    class FakeTelegramAPI:
        def __init__(self):
            self.messages = []
            self.documents = []

        def send_message(self, token: str, chat_id: str, text: str):
            self.messages.append({'token': token, 'chat_id': chat_id, 'text': text})
            return {'message_id': 101}

        def send_document(self, token: str, chat_id: str, file_path: str | Path, caption: str | None = None):
            self.documents.append(
                {'token': token, 'chat_id': chat_id, 'file_path': str(file_path), 'caption': caption}
            )
            return {'message_id': 202}

    fake_api = FakeTelegramAPI()

    result = send_operator_update(
        businessos_root=businessos_root,
        db_path=db_path,
        text='BusinessOS run completed',
        notification_type='run-completed',
        config_path=operator_updates_config,
        telegram_config_path=telegram_sources,
        current_time='2026-05-03T16:30:23+00:00',
        telegram_api=fake_api,
        attachment_paths=[attachment, attachment, businessos_root / 'missing.md'],
    )

    assert result['status'] == 'sent'
    assert result['attachment_count'] == 1
    assert len(fake_api.messages) == 1
    assert len(fake_api.documents) == 1
    assert fake_api.documents[0]['file_path'] == str(attachment)
    assert fake_api.documents[0]['caption'] == 'BusinessOS document: 05_REPORTS/support/2026-05-03-support-health-check.md'
