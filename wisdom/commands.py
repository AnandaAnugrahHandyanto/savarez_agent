"""Command parser and dispatcher for /wisdom."""

from __future__ import annotations

from dataclasses import dataclass

from wisdom.apply import create_application_proposals
from wisdom.capture import capture_text, effective_capture_mode, effective_enabled
from wisdom.config import load_wisdom_config
from wisdom.db import WisdomDB
from wisdom.interpret import interpret_capture
from wisdom.models import WisdomConfig
from wisdom.redaction import detect_secret_like_text
from wisdom.render import (
    render_applications,
    render_blocked_secret,
    render_capture,
    render_captures,
    render_error,
    render_help,
    render_interpretation,
    render_not_found,
    render_original,
    render_review,
    render_status,
)


@dataclass(frozen=True)
class WisdomCommandContext:
    channel: str = "gateway"
    source_kind: str = "command"
    session_key: object | None = None
    message_ref: object | None = None


def handle_wisdom_command(
    raw_args: str,
    *,
    context: WisdomCommandContext | None = None,
    config: WisdomConfig | None = None,
    db: WisdomDB | None = None,
) -> str:
    config = config or load_wisdom_config()
    db = db or WisdomDB(config.db_path)
    db.init()
    context = context or WisdomCommandContext()

    raw_args = (raw_args or "").strip()
    subcommand, arg = _split(raw_args)
    subcommand = subcommand.lower() if subcommand else "help"

    if subcommand in {"help", "-h", "--help"}:
        return render_help()
    if subcommand == "status":
        return render_status(db.status_snapshot(config))
    if subcommand == "on":
        db.set_setting("enabled", "true")
        db.set_setting("capture_mode", "explicit")
        return "Wisdom is on. Capture mode: explicit."
    if subcommand == "off":
        db.set_setting("enabled", "false")
        db.set_setting("capture_mode", "off")
        return "Wisdom is off. Status/help/on still work."

    if not effective_enabled(db, config):
        return "Wisdom is off. Use /wisdom on to enable it."

    if subcommand == "capture":
        if not arg:
            return "Usage: /wisdom capture <text>"
        if detect_secret_like_text(arg):
            return render_blocked_secret()
        outcome = capture_text(
            arg,
            channel=context.channel,
            source_kind=context.source_kind,
            session_key=context.session_key,
            message_ref=context.message_ref,
            config=config,
            db=db,
            require_enabled=True,
        )
        if outcome.status == "captured" and outcome.capture:
            return render_capture(outcome.capture)
        if outcome.status == "blocked_secret":
            return render_blocked_secret()
        return outcome.message or render_error()

    if subcommand == "inbox":
        return render_captures("Wisdom inbox", db.list_captures(limit=config.max_results))

    if subcommand == "search":
        if not arg:
            return "Usage: /wisdom search <query>"
        return render_captures("Wisdom search", db.search(arg, limit=config.max_results))

    if subcommand == "original":
        capture_id = _parse_id(arg)
        if capture_id is None:
            return "Usage: /wisdom original <id>"
        capture = db.get_capture(capture_id)
        return render_original(capture) if capture else render_not_found(capture_id)

    if subcommand == "interpret":
        capture_id = _parse_id(arg)
        if capture_id is None:
            return "Usage: /wisdom interpret <id>"
        if db.get_capture(capture_id) is None:
            return render_not_found(capture_id)
        return render_interpretation(interpret_capture(db, capture_id, create=True))

    if subcommand == "apply":
        capture_id = _parse_id(arg)
        if capture_id is None:
            return "Usage: /wisdom apply <id>"
        if db.get_capture(capture_id) is None:
            return render_not_found(capture_id)
        return render_applications(capture_id, create_application_proposals(db, capture_id))

    if subcommand == "archive":
        capture_id = _parse_id(arg)
        if capture_id is None:
            return "Usage: /wisdom archive <id>"
        return f"Archived #{capture_id}." if db.archive_capture(capture_id) else render_not_found(capture_id)

    if subcommand == "review":
        recent = db.list_captures(limit=config.max_results)
        unapplied = db.unapplied_captures(limit=config.max_results)
        return render_review(db.count_by_category(), recent, unapplied)

    return render_help()


def can_natural_capture(db: WisdomDB, config: WisdomConfig) -> bool:
    return effective_enabled(db, config) and effective_capture_mode(db, config) == "explicit"


def _split(raw_args: str) -> tuple[str, str]:
    if not raw_args:
        return "", ""
    parts = raw_args.split(maxsplit=1)
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


def _parse_id(text: str) -> int | None:
    text = (text or "").strip().lstrip("#")
    if not text:
        return None
    try:
        value = int(text.split()[0])
    except ValueError:
        return None
    return value if value > 0 else None
