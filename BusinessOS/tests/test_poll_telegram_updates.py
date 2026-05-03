import os
import sqlite3
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / '04_AUTOMATIONS' / 'scripts'
sys.path.insert(0, str(SCRIPTS_DIR))

import poll_telegram_updates


class FakeTelegramAPI:
    def get_me(self, token: str):
        return {'id': 123, 'is_bot': True, 'can_read_all_group_messages': True}

    def get_updates(self, token: str, offset=None, allowed_updates=None):
        return {
            'ok': True,
            'result': [
                {
                    'update_id': 64586390,
                    'message': {
                        'message_id': 101,
                        'date': 1714700000,
                        'chat': {'id': -1001234567890, 'title': 'Steady App Support'},
                        'from': {'id': 555001, 'username': 'poiuy'},
                        'text': '#todo follow up with Cloudflare billing',
                    },
                }
            ],
        }


def test_poll_telegram_updates_returns_imported_message_classification_details(tmp_path, monkeypatch):
    businessos_root = tmp_path / 'BusinessOS'
    db_path = businessos_root / '03_DATA' / 'db' / 'businessos.db'
    db_path.parent.mkdir(parents=True, exist_ok=True)
    config_path = businessos_root / '04_AUTOMATIONS' / 'configs' / 'telegram-sources.yaml'
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        '\n'.join(
            [
                'accounts:',
                '  - id: telegram-steady-support',
                '    source_type: telegram',
                '    chat_id: "-1001234567890"',
                '    app_id: steadyapp',
                '    lane: customer-support',
                '    bot_token_env: BUSINESSOS_TELEGRAM_BOT_TOKEN',
                '    live_poll: true',
                '',
            ]
        ),
        encoding='utf-8',
    )
    monkeypatch.setenv('BUSINESSOS_TELEGRAM_BOT_TOKEN', 'test-token')

    result = poll_telegram_updates.poll_telegram_updates(
        businessos_root=businessos_root,
        db_path=db_path,
        config_path=config_path,
        telegram_api=FakeTelegramAPI(),
    )

    assert result['imported_count'] == 1
    assert len(result['imported_messages']) == 1
    imported = result['imported_messages'][0]
    assert imported['category'] == 'task-capture'
    assert imported['assigned_queue'] == 'operator-review'
    assert imported['classification_label'] == 'todo / task-capture / operator-review'
    assert imported['sender_handle'] == '@poiuy'
    assert imported['normalized_path'].endswith('.json')
    assert result['accounts']['telegram-steady-support']['imported_count'] == 1
    assert result['accounts']['telegram-steady-support']['imported_messages'][0]['classification_label'] == 'todo / task-capture / operator-review'

    con = sqlite3.connect(db_path)
    row = con.execute('select category from communication_messages').fetchone()
    con.close()
    assert row[0] == 'task-capture'
