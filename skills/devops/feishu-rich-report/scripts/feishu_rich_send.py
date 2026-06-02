#!/usr/bin/env python3
"""Send Feishu chat messages as rich post (markdown) via lark-cli — tables render correctly.

Hermes core send() downgrades markdown tables to plain text. Use this for important
reports with headings, lists, and tables. Does not modify Hermes gateway code.

After a successful side delivery, stdout includes ``side_delivery.status: "done"`` and
``completion_ack_required: true`` so the agent knows it must still send a normal Hermes
IM reply (Phase B ack).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

# Feishu post body practical limit; lark-cli may split — keep one message reasonable.
_MAX_CHARS = 24_000
_DONE_MARKER = "FEISHU_SIDE_DELIVERY_DONE"


def _read_markdown(args: argparse.Namespace) -> str:
    if args.markdown is not None:
        return args.markdown
    if args.markdown_file:
        return Path(args.markdown_file).read_text(encoding="utf-8")
    if args.markdown_stdin:
        return sys.stdin.read()
    raise SystemExit("Provide --markdown, --markdown-file, or --markdown-stdin")


def _resolve_chat_id(args: argparse.Namespace) -> str:
    chat_id = (args.chat_id or os.environ.get("HERMES_SESSION_CHAT_ID") or "").strip()
    if not chat_id:
        raise SystemExit("chat_id required: --chat-id or env HERMES_SESSION_CHAT_ID")
    return chat_id


def _resolve_thread_id(args: argparse.Namespace) -> str:
    return (
        args.thread_id
        or os.environ.get("HERMES_SESSION_THREAD_ID")
        or os.environ.get("HERMES_SESSION_MESSAGE_ID")
        or ""
    ).strip()


def build_lark_args(
    *,
    chat_id: str,
    markdown: str,
    thread_id: str = "",
    as_identity: str = "bot",
) -> list[str]:
    base = ["lark-cli", "im", "--as", as_identity]
    if thread_id:
        return [
            *base,
            "+messages-reply",
            "--message-id",
            thread_id,
            "--reply-in-thread",
            "--markdown",
            markdown,
        ]
    return [
        *base,
        "+messages-send",
        "--chat-id",
        chat_id,
        "--markdown",
        markdown,
    ]


def extract_message_id(lark_payload: dict[str, Any]) -> str:
    """Best-effort message_id from lark-cli JSON."""
    for key in ("message_id", "msg_id"):
        if lark_payload.get(key):
            return str(lark_payload[key])
    data = lark_payload.get("data")
    if isinstance(data, dict):
        for key in ("message_id", "msg_id"):
            if data.get(key):
                return str(data[key])
    return ""


def format_completion_ack(
    *,
    task_label: str,
    doc_link: str = "",
    message_id: str = "",
    chat_id: str = "",
) -> str:
    """Human-readable Phase B reply the agent should send via Hermes IM."""
    label = (task_label or "任务").strip()
    lines = [f"✅ 已完成：{label}"]
    if doc_link.strip():
        lines.append(f"📎 {doc_link.strip()}")
    if message_id.strip():
        lines.append(f"↪ 侧链已发：message_id={message_id.strip()}")
    elif chat_id.strip():
        lines.append(f"↪ 侧链已发：chat_id={chat_id.strip()}")
    return "\n".join(lines)


def wrap_side_delivery_result(
    lark_payload: dict[str, Any],
    *,
    chat_id: str,
    thread_id: str = "",
    task_label: str = "",
    doc_link: str = "",
    dry_run: bool = False,
) -> dict[str, Any]:
    """Augment lark-cli output with explicit done semantics for the agent loop."""
    message_id = extract_message_id(lark_payload)
    status = "dry_run" if dry_run else "done"
    suggested = format_completion_ack(
        task_label=task_label,
        doc_link=doc_link,
        message_id=message_id,
        chat_id=chat_id,
    )
    return {
        **lark_payload,
        "side_delivery": {
            "status": status,
            "channel": "lark-cli",
            "chat_id": chat_id,
            "thread_id": thread_id or None,
            "message_id": message_id or None,
            "doc_link": doc_link.strip() or None,
        },
        "completion_ack_required": not dry_run,
        "suggested_chat_reply": suggested,
        "done_marker": _DONE_MARKER if not dry_run else None,
    }


def send_markdown(
    chat_id: str,
    markdown: str,
    *,
    thread_id: str = "",
    as_identity: str = "bot",
    dry_run: bool = False,
    task_label: str = "",
    doc_link: str = "",
) -> dict:
    body = markdown.strip()
    if not body:
        raise ValueError("empty markdown body")
    if len(body) > _MAX_CHARS:
        raise ValueError(
            f"markdown too long ({len(body)} chars > {_MAX_CHARS}); "
            "split into parts or attach a doc link"
        )
    args = build_lark_args(
        chat_id=chat_id,
        markdown=body,
        thread_id=thread_id,
        as_identity=as_identity,
    )
    if dry_run:
        base = {"dry_run": True, "argv": args, "chars": len(body)}
        return wrap_side_delivery_result(
            base,
            chat_id=chat_id,
            thread_id=thread_id,
            task_label=task_label,
            doc_link=doc_link,
            dry_run=True,
        )
    proc = subprocess.run(args, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        err = proc.stderr.strip() or proc.stdout.strip() or f"exit {proc.returncode}"
        raise RuntimeError(f"lark-cli failed: {err}")
    raw = proc.stdout.strip()
    start = raw.find("{")
    if start >= 0:
        lark_payload = json.loads(raw[start:])
    else:
        lark_payload = {"ok": True, "raw": raw}
    return wrap_side_delivery_result(
        lark_payload,
        chat_id=chat_id,
        thread_id=thread_id,
        task_label=task_label,
        doc_link=doc_link,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Send Feishu rich markdown (post) via lark-cli; tables supported."
    )
    parser.add_argument("--chat-id", help="oc_xxx; default HERMES_SESSION_CHAT_ID")
    parser.add_argument(
        "--thread-id",
        help="om_xxx to reply in thread; default HERMES_SESSION_THREAD_ID",
    )
    parser.add_argument("--as", dest="as_identity", default="bot", choices=("bot", "user"))
    parser.add_argument("--markdown", help="Markdown body (use $'...' in shell)")
    parser.add_argument("--markdown-file", type=Path, help="Read markdown from file")
    parser.add_argument(
        "--markdown-stdin",
        action="store_true",
        help="Read markdown from stdin",
    )
    parser.add_argument(
        "--task-label",
        default="",
        help="Short label for suggested Phase B Hermes IM ack (e.g. '验收报告')",
    )
    parser.add_argument(
        "--doc-link",
        default="",
        help="Optional Feishu doc URL to include in suggested_chat_reply",
    )
    parser.add_argument(
        "--suggested-reply-only",
        action="store_true",
        help="Print only suggested_chat_reply (after successful send)",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    chat_id = _resolve_chat_id(args)
    thread_id = _resolve_thread_id(args)
    body = _read_markdown(args)
    try:
        out = send_markdown(
            chat_id,
            body,
            thread_id=thread_id,
            as_identity=args.as_identity,
            dry_run=args.dry_run,
            task_label=args.task_label,
            doc_link=args.doc_link,
        )
    except (ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.suggested_reply_only:
        print(out.get("suggested_chat_reply", ""))
        return 0

    print(json.dumps(out, ensure_ascii=False, indent=2))
    if out.get("done_marker") == _DONE_MARKER:
        print(_DONE_MARKER, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
