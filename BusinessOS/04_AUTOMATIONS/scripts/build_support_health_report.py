from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return None


def _truncate_snippet(text: str | None, limit: int = 80) -> str:
    snippet = (text or '').replace('\n', ' ').strip()
    if len(snippet) > limit:
        return snippet[: limit - 3] + '...'
    return snippet


def _coerce_generated_at(run_summary: dict[str, Any] | None) -> tuple[datetime, str]:
    now = _utc_now()
    if not run_summary:
        return now, now.date().isoformat()

    value = run_summary.get('generated_at')
    parsed = _parse_timestamp(value)
    if parsed is None:
        return now, now.date().isoformat()
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc), value


def _latest_activity_by_source(cur: sqlite3.Cursor) -> dict[str, dict[str, str]]:
    rows = cur.execute(
        '''
        select
            ct.source_channel as source_type,
            ct.source_account,
            cm.sent_at,
            cm.created_at,
            cm.text,
            cm.id
        from communication_messages cm
        join communication_threads ct on ct.id = cm.thread_id
        order by coalesce(cm.sent_at, cm.created_at) desc, cm.created_at desc, cm.id desc
        '''
    ).fetchall()

    latest: dict[str, dict[str, str]] = {}
    for row in rows:
        source_type = row['source_type'] or 'unknown'
        if source_type in latest:
            continue
        latest[source_type] = {
            'source_account': row['source_account'] or '',
            'sent_at': row['sent_at'] or '',
            'created_at': row['created_at'] or '',
            'snippet': _truncate_snippet(row['text']),
        }
    return latest


def _ordered_sources(sources: set[str]) -> list[str]:
    preferred = {'email': 0, 'telegram': 1}
    return sorted(sources, key=lambda source: (preferred.get(source, 99), source))


def build_support_health_report(
    db_path: str | Path,
    output_dir: str | Path,
    run_summary: dict[str, Any] | None = None,
) -> Path:
    db_path = Path(db_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    checkpoint_rows = cur.execute(
        'select source_type, source_account, checkpoint_value, updated_at from ingestion_checkpoints order by source_type, source_account'
    ).fetchall()
    queue_rows = cur.execute(
        'select assigned_queue, count(*) as thread_count, sum(needs_human_reply) as needs_reply from communication_threads group by assigned_queue order by thread_count desc, assigned_queue'
    ).fetchall()
    latest_messages = cur.execute(
        'select cm.id, ct.source_account, ct.customer_handle, cm.category, cm.priority, cm.text, cm.created_at from communication_messages cm join communication_threads ct on ct.id = cm.thread_id order by cm.created_at desc limit 5'
    ).fetchall()
    latest_activity_by_source = _latest_activity_by_source(cur)
    con.close()

    generated_at, generated_label = _coerce_generated_at(run_summary)
    lines: list[str] = []
    lines.append('# Support Intake Health Check')
    lines.append('')
    lines.append(f'Generated: {generated_label}')
    lines.append('')

    if run_summary is not None:
        lines.append('## Current pipeline run')
        lines.append('')
        lines.append('| Source | Step status | New imports this run | Latest message sent at | Latest message imported at | Latest snippet |')
        lines.append('|---|---|---:|---|---|---|')

        sources = {row['source_type'] for row in checkpoint_rows if row['source_type']}
        sources.update(latest_activity_by_source.keys())
        sources.update(key for key, value in run_summary.items() if key != 'generated_at' and isinstance(value, dict))

        for source in _ordered_sources(sources):
            summary = run_summary.get(source, {}) if run_summary else {}
            latest = latest_activity_by_source.get(source, {})
            lines.append(
                '| {source} | {status} | {imported_count} | {sent_at} | {created_at} | {snippet} |'.format(
                    source=source,
                    status=summary.get('status', 'not-provided') or 'not-provided',
                    imported_count=summary.get('imported_count', 0),
                    sent_at=latest.get('sent_at', ''),
                    created_at=latest.get('created_at', ''),
                    snippet=latest.get('snippet', ''),
                )
            )
        if not sources:
            lines.append('| - | - | 0 | - | - | - |')
        lines.append('')

    lines.append('## Source checkpoints')
    lines.append('')
    lines.append('| Source | Account | Checkpoint | Updated at | Age |')
    lines.append('|---|---|---|---|---|')
    for row in checkpoint_rows:
        updated_at = row['updated_at']
        parsed = _parse_timestamp(updated_at)
        age_text = 'unknown'
        if parsed is not None:
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            age = generated_at - parsed.astimezone(timezone.utc)
            minutes = int(age.total_seconds() // 60)
            age_text = f'{minutes} min'
        lines.append(
            f"| {row['source_type']} | {row['source_account']} | {row['checkpoint_value'] or ''} | {updated_at or ''} | {age_text} |"
        )
    if not checkpoint_rows:
        lines.append('| - | - | - | - | - |')
    lines.append('')
    lines.append('## Queue snapshot')
    lines.append('')
    lines.append('| Queue | Open threads | Needs reply |')
    lines.append('|---|---:|---:|')
    for row in queue_rows:
        lines.append(f"| {row['assigned_queue'] or 'unassigned'} | {row['thread_count']} | {row['needs_reply'] or 0} |")
    if not queue_rows:
        lines.append('| unassigned | 0 | 0 |')
    lines.append('')
    lines.append('## Latest messages')
    lines.append('')
    lines.append('| Account | Customer | Category | Priority | Imported at | Snippet |')
    lines.append('|---|---|---|---|---|---|')
    for row in latest_messages:
        lines.append(
            f"| {row['source_account'] or ''} | {row['customer_handle'] or ''} | {row['category'] or ''} | {row['priority'] or ''} | {row['created_at'] or ''} | {_truncate_snippet(row['text'])} |"
        )
    if not latest_messages:
        lines.append('| - | - | - | - | - | - |')

    filename = f"{generated_at.date().isoformat()}-support-health-check.md"
    output_path = output_dir / filename
    output_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return output_path


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description='Write a BusinessOS support intake health report.')
    parser.add_argument('db_path')
    parser.add_argument('output_dir')
    args = parser.parse_args()
    path = build_support_health_report(args.db_path, args.output_dir)
    print(path)


if __name__ == '__main__':
    main()
