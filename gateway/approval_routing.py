"""Helpers for routing and wording gateway approval prompts."""

from __future__ import annotations

import html
from typing import Any, Mapping


def _as_dict(value: Any) -> dict:
    return dict(value) if isinstance(value, Mapping) else {}


def _parse_target(target: str) -> tuple[str, str, str | None] | None:
    """Parse `platform:chat_id[:thread_id]` approval target strings."""
    raw = str(target or "").strip()
    if not raw or ":" not in raw:
        return None
    platform, rest = raw.split(":", 1)
    platform = platform.strip().lower()
    rest = rest.strip()
    if not platform or not rest:
        return None

    # Telegram supergroups are negative (`-100...`), so the final colon is
    # safe to treat as the optional topic/thread separator.
    chat_id, sep, thread_id = rest.rpartition(":")
    if sep and chat_id:
        return platform, chat_id.strip(), thread_id.strip() or None
    return platform, rest, None


def approval_target_for_adapter(
    *,
    adapter_name: str,
    default_chat_id: str,
    default_metadata: Mapping[str, Any] | None,
    approvals_config: Mapping[str, Any] | None,
) -> tuple[str, dict[str, Any] | None]:
    """Return where an approval prompt should be sent for this adapter.

    If `approvals.gateway_target` matches the current platform, route the
    prompt there. Otherwise keep the original chat/thread untouched.
    """
    metadata = _as_dict(default_metadata)
    cfg = _as_dict(approvals_config)
    parsed = _parse_target(str(cfg.get("gateway_target") or cfg.get("target") or ""))
    if not parsed:
        return str(default_chat_id), (metadata or None)

    target_platform, target_chat_id, target_thread_id = parsed
    if target_platform != str(adapter_name or "").lower():
        return str(default_chat_id), (metadata or None)

    routed_metadata = dict(metadata)
    # A prompt redirected to a central approvals topic should not reply to the
    # original message id from another topic/chat; Telegram rejects that and it
    # visually links the wrong conversation.
    routed_metadata.pop("reply_to_message_id", None)
    if target_thread_id:
        routed_metadata["thread_id"] = target_thread_id
    else:
        routed_metadata.pop("thread_id", None)
    return target_chat_id, (routed_metadata or None)


def source_label_from_source(source: Any) -> str:
    """Small human label for the project/session that requested approval."""
    description = getattr(source, "description", "") or ""
    if description:
        return str(description)
    chat_name = getattr(source, "chat_name", None)
    chat_id = getattr(source, "chat_id", None)
    thread_id = getattr(source, "thread_id", None)
    label = str(chat_name or chat_id or "unknown session")
    if thread_id:
        label += f" / topic {thread_id}"
    return label


def format_approval_prompt(
    *,
    command: str,
    description: str,
    source_label: str = "",
    language: str = "en",
    html_mode: bool = False,
) -> str:
    """Format a plain-language approval prompt."""
    cmd_preview = command[:3800] + "..." if len(command) > 3800 else command
    reason = description or "dangerous command"
    source = source_label or "current session"

    if html_mode:
        cmd = html.escape(cmd_preview)
        reason_text = html.escape(reason)
        source_text = html.escape(source)
    else:
        cmd = cmd_preview
        reason_text = reason
        source_text = source

    if str(language or "").lower().startswith("lv"):
        if html_mode:
            return (
                "⚠️ <b>Nepieciešams tavs apstiprinājums</b>\n\n"
                f"<b>No kurienes:</b> {source_text}\n"
                f"<b>Ko apstiprini:</b> šīs komandas palaišanu\n"
                f"<pre>{cmd}</pre>\n"
                f"<b>Kāpēc prasa:</b> {reason_text}\n\n"
                "Ja saproti un gribi ļaut, spied pogu. Ja nē — Deny."
            )
        return (
            "⚠️ **Nepieciešams tavs apstiprinājums**\n\n"
            f"No kurienes: {source_text}\n"
            "Ko apstiprini: šīs komandas palaišanu\n"
            f"```\n{cmd}\n```\n"
            f"Kāpēc prasa: {reason_text}\n\n"
            "Ja saproti un gribi ļaut, spied /approve. Ja nē — /deny."
        )

    if html_mode:
        return (
            "⚠️ <b>Command Approval Required</b>\n\n"
            f"<b>Source:</b> {source_text}\n"
            f"<b>Approving:</b> run this command\n"
            f"<pre>{cmd}</pre>\n\n"
            f"<b>Reason:</b> {reason_text}"
        )
    return (
        "⚠️ **Dangerous command requires approval:**\n"
        f"Source: {source_text}\n"
        f"```\n{cmd}\n```\n"
        f"Reason: {reason_text}"
    )
