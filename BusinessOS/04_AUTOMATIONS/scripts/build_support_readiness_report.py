from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _read_text(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ''
    return path.read_text(encoding='utf-8')


def classify_email_step(script_path: str | Path) -> str:
    script_path = Path(script_path)
    if not script_path.exists() or not script_path.is_file():
        return 'missing-script'
    return 'available-not-run'


def classify_telegram_step(script_path: str | Path) -> str:
    script_path = Path(script_path)
    if not script_path.exists() or not script_path.is_file():
        return 'missing-script'

    script_text = _read_text(script_path)
    if 'Telegram polling diagnostics helper' in script_text:
        return 'diagnostic-helper-only'
    if 'warn_if_group_privacy_blocks_messages' in script_text and 'getUpdates' not in script_text:
        return 'diagnostic-helper-only'
    return 'available-not-run'


def _has_table(con: sqlite3.Connection, table_name: str) -> bool:
    row = con.execute(
        "select 1 from sqlite_master where type = 'table' and name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _read_env_var_names(env_file: Path) -> set[str]:
    if not env_file.exists() or not env_file.is_file():
        return set()

    names: set[str] = set()
    for raw_line in env_file.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        names.add(line.split('=', 1)[0].strip())
    return names


def _load_source_accounts(db_path: Path) -> list[sqlite3.Row]:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        if not _has_table(con, 'source_accounts'):
            return []
        return con.execute(
            'select id, source_type, external_ref, app_id from source_accounts order by id'
        ).fetchall()
    finally:
        con.close()


def _load_checkpoints(db_path: Path) -> list[sqlite3.Row]:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        if not _has_table(con, 'ingestion_checkpoints'):
            return []
        return con.execute(
            'select source_type, source_account, checkpoint_value, updated_at from ingestion_checkpoints order by source_type, source_account'
        ).fetchall()
    finally:
        con.close()


def build_support_readiness_report(
    businessos_root: str | Path,
    db_path: str | Path,
    output_dir: str | Path,
    env_file: str | Path | None = None,
    wrapper_path: str | Path | None = None,
) -> Path:
    businessos_root = Path(businessos_root)
    db_path = Path(db_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    scripts_dir = businessos_root / '04_AUTOMATIONS' / 'scripts'
    configs_dir = businessos_root / '04_AUTOMATIONS' / 'configs'
    email_script = scripts_dir / 'poll_support_email.py'
    telegram_script = scripts_dir / 'poll_telegram_updates.py'
    email_config = configs_dir / 'support-inboxes.yaml'
    telegram_config = configs_dir / 'telegram-sources.yaml'
    mirror_config = configs_dir / 'dropbox-mirror.yaml'
    env_file = Path(env_file or '/home/yuiop/.config/businessos/support-email.env')
    wrapper_path = Path(wrapper_path or '/home/yuiop/.local/bin/businessos-support-pipeline.sh')

    email_status = classify_email_step(email_script)
    telegram_status = classify_telegram_step(telegram_script)
    source_accounts = _load_source_accounts(db_path) if db_path.exists() else []
    checkpoints = _load_checkpoints(db_path) if db_path.exists() else []
    env_var_names = _read_env_var_names(env_file)
    wrapper_text = _read_text(wrapper_path)
    wrapper_requires_imap_password = 'BUSINESSOS_HELIX_ADMIN_IMAP_PASSWORD' in wrapper_text

    now = _utc_now()
    lines: list[str] = []
    lines.append('# Support Pipeline Readiness Audit')
    lines.append('')
    lines.append(f'Generated: {now.date().isoformat()}')
    lines.append('')
    lines.append('## Component status')
    lines.append('')
    lines.append('| Component | Status | Details |')
    lines.append('|---|---|---|')
    lines.append(f'| email script | {email_status} | Expected path: `{email_script}` |')
    lines.append(
        f'| email config | {"present" if email_config.exists() else "missing-config"} | Expected path: `{email_config}` |'
    )
    lines.append(f'| telegram script | {telegram_status} | Expected path: `{telegram_script}` |')
    lines.append(
        f'| telegram config | {"present" if telegram_config.exists() else "missing-config"} | Expected path: `{telegram_config}` |'
    )
    lines.append(
        f'| dropbox mirror config | {"present" if mirror_config.exists() else "missing-config"} | Expected path: `{mirror_config}` |'
    )
    lines.append(
        f'| wrapper env file | {"present" if env_file.exists() else "missing"} | Checked only for variable names, not secret values: `{env_file}` |'
    )
    lines.append(
        f'| wrapper IMAP password gate | {"enabled" if wrapper_requires_imap_password else "not-detected"} | Wrapper path: `{wrapper_path}` |'
    )
    lines.append(
        f'| env var name BUSINESSOS_HELIX_ADMIN_IMAP_PASSWORD | {"present" if "BUSINESSOS_HELIX_ADMIN_IMAP_PASSWORD" in env_var_names else "missing"} | Value intentionally not shown |'
    )
    lines.append(
        f'| env var name BUSINESSOS_TELEGRAM_SUPPORT_BOT_TOKEN | {"present" if "BUSINESSOS_TELEGRAM_SUPPORT_BOT_TOKEN" in env_var_names else "missing"} | Value intentionally not shown |'
    )
    lines.append('')
    lines.append('## Source accounts remembered in the DB')
    lines.append('')
    lines.append('| Account | Type | External ref | App ID |')
    lines.append('|---|---|---|---|')
    if source_accounts:
        for row in source_accounts:
            lines.append(
                f"| {row['id']} | {row['source_type'] or ''} | {row['external_ref'] or ''} | {row['app_id'] or ''} |"
            )
    else:
        lines.append('| - | - | - | - |')
    lines.append('')
    lines.append('## Ingestion checkpoints currently in the DB')
    lines.append('')
    lines.append('| Source | Account | Checkpoint | Updated at |')
    lines.append('|---|---|---|---|')
    if checkpoints:
        for row in checkpoints:
            lines.append(
                f"| {row['source_type'] or ''} | {row['source_account'] or ''} | {row['checkpoint_value'] or ''} | {row['updated_at'] or ''} |"
            )
    else:
        lines.append('| - | - | - | - |')
    lines.append('')
    lines.append('## Practical interpretation')
    lines.append('')
    if email_status == 'missing-script':
        lines.append('- Live email polling is not currently restorable from the on-disk script set alone because `poll_support_email.py` is missing.')
    elif email_config.exists() and 'BUSINESSOS_HELIX_ADMIN_IMAP_PASSWORD' in env_var_names:
        lines.append('- The live email poller script, config, and required IMAP password env-var name are all present, so the on-disk pipeline is ready to ingest fresh email when the wrapper or shell exports that env file.')
    else:
        lines.append('- An email poller script exists on disk, but the surrounding config/env surface is still incomplete, so treat live email intake as not-yet-ready until those missing pieces are restored.')
    if telegram_status == 'diagnostic-helper-only':
        lines.append('- The current `poll_telegram_updates.py` is a diagnostics helper for Telegram privacy-mode checks, not a live `getUpdates` ingestion poller.')
    elif telegram_status == 'missing-script':
        lines.append('- No Telegram helper or poller script is currently present on disk.')
    elif telegram_config.exists() and 'BUSINESSOS_TELEGRAM_SUPPORT_BOT_TOKEN' in env_var_names:
        lines.append('- The live Telegram poller script, source config, and required bot-token env-var name are all present, so the on-disk pipeline is ready to ingest fresh Telegram updates when the wrapper or shell exports that env file.')
    else:
        lines.append('- A Telegram poller script exists on disk, but the surrounding config/env surface is still incomplete, so treat live Telegram intake as not-yet-ready until those missing pieces are restored.')
    if not telegram_config.exists():
        lines.append('- The expected Telegram source config file is absent, so the current filesystem snapshot does not contain an active live Telegram lane definition.')
    if source_accounts:
        lines.append('- The SQLite DB preserves source-account rows and checkpoints, which helps distinguish historical state from newly-advancing intake when you compare the latest checkpoint timestamps after a run.')
    if wrapper_requires_imap_password and email_status == 'missing-script':
        lines.append('- The scheduled wrapper still enforces the IMAP password gate even though the current on-disk pipeline does not include the live email poller script. That is safe, but it can make the scheduler look stricter than the current pipeline actually needs.')

    filename = f'{now.date().isoformat()}-support-readiness-audit.md'
    output_path = output_dir / filename
    output_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return output_path


def main() -> None:
    import argparse

    default_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description='Write a BusinessOS support pipeline readiness audit.')
    parser.add_argument('--businessos-root', default=str(default_root))
    parser.add_argument('--db-path', default=None)
    parser.add_argument('--output-dir', default=None)
    parser.add_argument('--env-file', default='/home/yuiop/.config/businessos/support-email.env')
    parser.add_argument('--wrapper-path', default='/home/yuiop/.local/bin/businessos-support-pipeline.sh')
    args = parser.parse_args()

    businessos_root = Path(args.businessos_root)
    db_path = Path(args.db_path) if args.db_path else businessos_root / '03_DATA' / 'db' / 'businessos.db'
    output_dir = Path(args.output_dir) if args.output_dir else businessos_root / '05_REPORTS' / 'support'
    path = build_support_readiness_report(
        businessos_root=businessos_root,
        db_path=db_path,
        output_dir=output_dir,
        env_file=args.env_file,
        wrapper_path=args.wrapper_path,
    )
    print(path)


if __name__ == '__main__':
    main()
