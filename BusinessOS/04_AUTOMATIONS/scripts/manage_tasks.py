from __future__ import annotations

import argparse
import json
from pathlib import Path

from business_ops_core import (
    add_task_comment,
    build_task_dashboard_report,
    create_task,
    link_document_to_task,
    process_document_file,
    update_task_status,
    write_task_transcript_report,
)


def write_task_transcript(*, businessos_root: str | Path, db_path: str | Path, task_id: str) -> Path:
    return write_task_transcript_report(businessos_root=businessos_root, db_path=db_path, task_id=task_id)


def main() -> None:
    default_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description='Manage BusinessOS tasks.')
    parser.add_argument('--businessos-root', default=str(default_root))
    parser.add_argument('--db-path', default=None)
    subparsers = parser.add_subparsers(dest='command', required=True)

    add_parser = subparsers.add_parser('add')
    add_parser.add_argument('--title', required=True)
    add_parser.add_argument('--description', default='')
    add_parser.add_argument('--priority', default='medium')
    add_parser.add_argument('--due-at', default=None)
    add_parser.add_argument('--reminder-at', default=None)
    add_parser.add_argument('--author', default='cli')

    comment_parser = subparsers.add_parser('comment')
    comment_parser.add_argument('task_id')
    comment_parser.add_argument('body')
    comment_parser.add_argument('--author', default='cli')

    status_parser = subparsers.add_parser('status')
    status_parser.add_argument('task_id')
    status_parser.add_argument('status')
    status_parser.add_argument('--author', default='cli')

    link_parser = subparsers.add_parser('link-document')
    link_parser.add_argument('task_id')
    link_parser.add_argument('path')

    transcript_parser = subparsers.add_parser('transcript')
    transcript_parser.add_argument('task_id')

    subparsers.add_parser('dashboard')

    args = parser.parse_args()
    businessos_root = Path(args.businessos_root)
    db_path = Path(args.db_path) if args.db_path else businessos_root / '03_DATA' / 'db' / 'businessos.db'

    if args.command == 'add':
        task = create_task(
            db_path=db_path,
            title=args.title,
            description=args.description or None,
            priority=args.priority,
            source_channel='cli',
            author_handle=args.author,
            due_at=args.due_at,
            reminder_at=args.reminder_at,
        )
        print(json.dumps(task, indent=2))
        return

    if args.command == 'comment':
        comment = add_task_comment(
            db_path=db_path,
            task_id=args.task_id,
            body=args.body,
            source_channel='cli',
            author_handle=args.author,
        )
        print(json.dumps(comment, indent=2))
        return

    if args.command == 'status':
        task = update_task_status(
            db_path=db_path,
            task_id=args.task_id,
            status=args.status,
            source_channel='cli',
            author_handle=args.author,
        )
        print(json.dumps(task, indent=2))
        return

    if args.command == 'link-document':
        document = process_document_file(
            businessos_root=businessos_root,
            db_path=db_path,
            input_path=Path(args.path),
            source_channel='cli',
            related_task_id=args.task_id,
            move_source=False,
        )
        print(json.dumps(document, indent=2))
        return

    if args.command == 'transcript':
        path = write_task_transcript_report(businessos_root=businessos_root, db_path=db_path, task_id=args.task_id)
        print(path)
        return

    if args.command == 'dashboard':
        path = build_task_dashboard_report(businessos_root=businessos_root, db_path=db_path)
        print(path)
        return


if __name__ == '__main__':
    main()
