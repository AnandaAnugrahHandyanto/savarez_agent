import sqlite3
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / '04_AUTOMATIONS' / 'scripts'
sys.path.insert(0, str(SCRIPTS_DIR))

import build_support_readiness_report


def test_classify_telegram_step_detects_diagnostic_helper(tmp_path):
    script_path = tmp_path / 'poll_telegram_updates.py'
    script_path.write_text(
        "def main():\n    parser_description = 'Telegram polling diagnostics helper.'\n",
        encoding='utf-8',
    )

    assert build_support_readiness_report.classify_telegram_step(script_path) == 'diagnostic-helper-only'


def test_build_support_readiness_report_describes_missing_live_components(tmp_path):
    businessos_root = tmp_path / 'BusinessOS'
    scripts_dir = businessos_root / '04_AUTOMATIONS' / 'scripts'
    configs_dir = businessos_root / '04_AUTOMATIONS' / 'configs'
    output_dir = businessos_root / '05_REPORTS' / 'support'
    db_dir = businessos_root / '03_DATA' / 'db'
    scripts_dir.mkdir(parents=True)
    configs_dir.mkdir(parents=True)
    db_dir.mkdir(parents=True)

    (scripts_dir / 'poll_telegram_updates.py').write_text(
        "def main():\n    parser_description = 'Telegram polling diagnostics helper.'\n",
        encoding='utf-8',
    )
    (configs_dir / 'dropbox-mirror.yaml').write_text('source_root: test\n', encoding='utf-8')

    db_path = db_dir / 'businessos.db'
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.executescript(
        '''
        create table source_accounts (
            id text primary key,
            source_type text,
            external_ref text,
            app_id text
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
        'insert into source_accounts (id, source_type, external_ref, app_id) values (?, ?, ?, ?)',
        ('telegram-steady-support', 'telegram', '-5087084218', 'steadyapp'),
    )
    cur.execute(
        'insert into ingestion_checkpoints (source_type, source_account, checkpoint_value, updated_at) values (?, ?, ?, ?)',
        ('telegram', 'telegram-steady-support', '64586377', '2026-05-02 04:00:59'),
    )
    con.commit()
    con.close()

    env_file = tmp_path / 'support-email.env'
    env_file.write_text(
        'BUSINESSOS_HELIX_ADMIN_IMAP_PASSWORD=dummy\nBUSINESSOS_TELEGRAM_SUPPORT_BOT_TOKEN=dummy\n',
        encoding='utf-8',
    )
    wrapper_path = tmp_path / 'businessos-support-pipeline.sh'
    wrapper_path.write_text(
        'if [[ -z "${BUSINESSOS_HELIX_ADMIN_IMAP_PASSWORD:-}" ]]; then\n  exit 1\nfi\n',
        encoding='utf-8',
    )

    report_path = build_support_readiness_report.build_support_readiness_report(
        businessos_root=businessos_root,
        db_path=db_path,
        output_dir=output_dir,
        env_file=env_file,
        wrapper_path=wrapper_path,
    )

    content = report_path.read_text(encoding='utf-8')
    assert report_path.exists()
    assert 'diagnostic-helper-only' in content
    assert 'missing-config' in content
    assert 'telegram-steady-support' in content
    assert 'BUSINESSOS_TELEGRAM_SUPPORT_BOT_TOKEN' in content
