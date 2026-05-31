"""Card-prep chat: let Rolly help prepare one Kanban card."""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import time
from dataclasses import dataclass
from typing import Optional

from hermes_cli import kanban_db as kb
from hermes_cli import kanban_ready_review

logger = logging.getLogger(__name__)

HERMES_KANBAN_CARD_CHAT_MAX_TOKENS = max(
    1500,
    int(os.getenv("HERMES_KANBAN_CARD_CHAT_MAX_TOKENS", "6000")),
)

_SYSTEM_PROMPT = """You are Rolly helping a human prepare one Kanban card for AI handoff.
Your job: have a focused prep conversation. Only edit the card when the human explicitly asks you to update/save/change the card.
The first-class job is helping the human create acceptance criteria; treat the chat like a normal Rolly conversation, not a form-filling wizard.

Be pushy about handoff quality, but do not overstuff the visible card. The card is not ready until it has:
- clear goal / outcome
- concrete scope and out-of-scope
- quantifiable acceptance criteria
- verification command or manual verification steps
- source/provenance for why the work exists
- agent/workdir hints when relevant

Return exactly one JSON object:
{
  "reply": "short conversational reply to the human; include the next missing question if not ready",
  "title": "optional replacement title, <= 100 chars, or null",
  "body": "complete replacement markdown body, or null if unchanged",
  "ready": true|false,
  "missing": ["one-line missing item", ...]
}

Rules:
- Preserve the user's meaning; do not invent requirements.
- Make acceptance criteria measurable/observable.
- Keep the card body concise; detailed notes can stay in the conversation/comments.
- Prefer concise markdown sections in body: Goal, Acceptance criteria, Verification, Notes.
- If the human is only asking/thinking, reply conversationally and title/body must be null.
- If the human asks for help/spec/criteria but does not explicitly ask to update or save the card, title/body must be null.
- Only return replacement title/body when the human explicitly says to update/save/change the card.
- If details are missing, ask one or two pointed questions in reply and still improve the card with what is known only when edits were explicitly requested.
- No preamble outside JSON.
"""

_USER_TEMPLATE = """Task id: {task_id}
Status: {status}
Assignee: {assignee}
Tenant: {tenant}
Workspace: {workspace}

Current title:
{title}

Current body:
{body}

Recent card conversation/comments:
{comments}

Human message:
{message}
"""

_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class CardChatOutcome:
    task_id: str
    ok: bool
    reply: str
    title: Optional[str] = None
    body: Optional[str] = None
    ready: bool = False
    missing: tuple[str, ...] = ()
    ready_review: Optional[dict] = None
    reason: str = ""


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _extract_json_blob(raw: str) -> Optional[dict]:
    if not raw:
        return None
    stripped = _FENCE_RE.sub("", raw.strip())
    first = stripped.find("{")
    last = stripped.rfind("}")
    if first == -1 or last == -1 or last <= first:
        return None
    try:
        parsed = json.loads(stripped[first : last + 1])
    except (ValueError, json.JSONDecodeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _comment_context(comments: list[kb.Comment], limit: int = 12) -> str:
    if not comments:
        return "(none)"
    lines = []
    for c in comments[-limit:]:
        body = _truncate(c.body or "", 1200)
        lines.append(f"[{c.author or 'anon'}] {body}")
    return "\n\n".join(lines)


def _profile_author() -> str:
    return (
        os.environ.get("HERMES_PROFILE")
        or os.environ.get("USER")
        or "rolly"
    )


_EXPLICIT_CARD_UPDATE_RE = re.compile(
    r"\b(update|save|change|edit|rewrite|set|replace|apply)\b.{0,32}\b(card|task|title|body|description|acceptance|criteria)\b"
    r"|\b(card|task|title|body|description|acceptance|criteria)\b.{0,32}\b(update|save|change|edit|rewrite|set|replace|apply)\b",
    re.IGNORECASE | re.DOTALL,
)


def _explicit_card_update_requested(message: str) -> bool:
    return bool(_EXPLICIT_CARD_UPDATE_RE.search(message or ""))


def _apply_card_update(
    conn: sqlite3.Connection,
    task_id: str,
    *,
    user_message: str,
    user_author: str,
    reply: str,
    title: Optional[str],
    body: Optional[str],
    missing: list[str],
) -> None:
    now = int(time.time())
    with kb.write_txn(conn):
        existing = conn.execute(
            "SELECT title, body FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
        if existing is None:
            raise ValueError(f"unknown task {task_id}")

        sets: list[str] = []
        vals: list[str] = []
        changed_fields: list[str] = []
        if title is not None:
            next_title = title.strip()
            if not next_title:
                raise ValueError("title cannot be blank")
            if next_title != (existing["title"] or ""):
                sets.append("title = ?")
                vals.append(next_title)
                changed_fields.append("title")
        if body is not None and body != (existing["body"] or ""):
            sets.append("body = ?")
            vals.append(body)
            changed_fields.append("body")
        if sets:
            vals.append(task_id)
            conn.execute(f"UPDATE tasks SET {', '.join(sets)} WHERE id = ?", vals)

        conn.execute(
            "INSERT INTO task_comments (task_id, author, body, created_at) VALUES (?, ?, ?, ?)",
            (task_id, user_author.strip() or "human", user_message.strip(), now),
        )
        conn.execute(
            "INSERT INTO task_comments (task_id, author, body, created_at) VALUES (?, ?, ?, ?)",
            (task_id, "rolly", reply.strip(), now),
        )
        kb._append_event(
            conn,
            task_id,
            "card_chat",
            {"changed_fields": changed_fields, "missing": missing},
        )


def chat_on_card(
    task_id: str,
    message: str,
    *,
    author: Optional[str] = None,
    timeout: Optional[int] = None,
) -> CardChatOutcome:
    """Send one prep-chat message, live-update the card, and append transcript comments."""
    message = (message or "").strip()
    if not message:
        return CardChatOutcome(task_id, False, "", reason="message is required")

    with kb.connect() as conn:
        task = kb.get_task(conn, task_id)
        comments = kb.list_comments(conn, task_id) if task else []
    if task is None:
        return CardChatOutcome(task_id, False, "", reason="unknown task id")

    try:
        from agent.auxiliary_client import get_auxiliary_extra_body, get_text_auxiliary_client
    except Exception as exc:  # pragma: no cover
        logger.debug("card_chat: auxiliary client import failed: %s", exc)
        return CardChatOutcome(task_id, False, "", reason="auxiliary client unavailable")

    try:
        client, model = get_text_auxiliary_client("kanban_card_chat")
    except Exception as exc:
        logger.debug("card_chat: get_text_auxiliary_client failed: %s", exc)
        return CardChatOutcome(task_id, False, "", reason="auxiliary client unavailable")

    if client is None or not model:
        return CardChatOutcome(task_id, False, "", reason="no auxiliary client configured")

    user_msg = _USER_TEMPLATE.format(
        task_id=task.id,
        status=task.status,
        assignee=task.assignee or "(unassigned)",
        tenant=task.tenant or "(none)",
        workspace=f"{task.workspace_kind}{(': ' + task.workspace_path) if task.workspace_path else ''}",
        title=_truncate(task.title or "", 500),
        body=_truncate(task.body or "(no body)", 6000),
        comments=_truncate(_comment_context(comments), 6000),
        message=_truncate(message, 4000),
    )

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.2,
            max_tokens=HERMES_KANBAN_CARD_CHAT_MAX_TOKENS,
            timeout=timeout or 120,
            extra_body=get_auxiliary_extra_body() or None,
        )
        raw = (resp.choices[0].message.content or "").strip()
    except Exception as exc:
        logger.info("card_chat: API call failed for %s (%s)", task_id, exc)
        return CardChatOutcome(task_id, False, "", reason=f"LLM error: {type(exc).__name__}")

    parsed = _extract_json_blob(raw)
    if parsed is None:
        return CardChatOutcome(task_id, False, "", reason="LLM returned malformed JSON")

    reply = parsed.get("reply") if isinstance(parsed.get("reply"), str) else ""
    title_val = parsed.get("title")
    body_val = parsed.get("body")
    title = title_val.strip() if isinstance(title_val, str) and title_val.strip() else None
    body = body_val if isinstance(body_val, str) and body_val.strip() else None
    ready = bool(parsed.get("ready"))
    missing_raw = parsed.get("missing")
    missing = [str(x).strip() for x in missing_raw if str(x).strip()] if isinstance(missing_raw, list) else []

    if not reply.strip():
        reply = "Updated the card. Next: define measurable acceptance criteria and verification."

    if not _explicit_card_update_requested(message):
        title = None
        body = None

    user_author = author or "human"
    try:
        with kb.connect() as conn:
            _apply_card_update(
                conn,
                task_id,
                user_message=message,
                user_author=user_author,
                reply=reply,
                title=title,
                body=body,
                missing=missing,
            )
            ready_review = kanban_ready_review.status_for_task(conn, task_id).to_dict()
    except ValueError as exc:
        return CardChatOutcome(task_id, False, "", reason=str(exc))

    return CardChatOutcome(
        task_id,
        True,
        reply,
        title=title,
        body=body,
        ready=ready,
        missing=tuple(missing),
        ready_review=ready_review,
    )
