"""Active ContextOps cognitive hydration for the Hermes answer path.

This is the *active* (pre-answer) hydration adapter — distinct from the
read-only :mod:`contextops.hydrate` preview. It is invoked once per turn
inside the conversation loop to construct a compact restore/avoid/epistemic-
mode block that is appended to the API-call user context **before generation**.

Hard constraints (enforced by tests in
``tests/contextops/test_active_hydration.py``):

* **Metadata/context only.** This module never sends a message, mutates a
  Kanban board, writes memory, restarts the gateway, dispatches tools, or
  shells out. The injected text is text-only and ephemeral.
* **Disabled by default.** With no config — or an explicit ``enabled: false``
  — :func:`build_active_context` returns ``(None, {...})`` and the API-call
  context is unchanged.
* **Allowlist-gated.** Even when enabled, live injection only happens when the
  current channel identifier matches an explicit ``channel_allowlist`` entry.
* **Fail closed.** Missing seed, unreadable seed, missing channel identity, or
  any internal exception yields ``(None, {...})`` with a ``skipped_reason``;
  the caller's API-call context is left untouched.
* **No raw IDs, paths, transcripts, or tokens** appear in the injected text.
"""

from __future__ import annotations

import logging
from typing import Any

from contextops.hydrate import build_hydration_preview

__all__ = ["ACTIVE_HYDRATION_CONFIG_PATH", "build_active_context"]

logger = logging.getLogger(__name__)

# Naming reflects *active cognitive context*, not watchdog/suggestions. This
# is the config namespace callers (and tests) anchor on.
ACTIVE_HYDRATION_CONFIG_PATH: tuple[str, str] = (
    "contextops",
    "active_cognitive_hydration",
)

_MAX_RESTORE_ITEMS = 6
_MAX_AVOID_ITEMS = 5
_DEFAULT_PACK_ID = "pack-contextops-active"


def _cfg_section(config: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(config, dict):
        return None
    cur: Any = config
    for key in ACTIVE_HYDRATION_CONFIG_PATH:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    if not isinstance(cur, dict):
        return None
    return cur


def _channel_identity(agent: Any) -> str | None:
    """Derive a stable channel identifier from agent attributes.

    Prefers the gateway session key (already namespaced by platform/chat/thread)
    and falls back to a synthesized ``platform:chat:thread`` triple. Returns
    ``None`` if nothing usable is available, which forces fail-closed.
    """

    key = getattr(agent, "_gateway_session_key", None)
    if isinstance(key, str) and key.strip():
        return key.strip()
    platform = getattr(agent, "platform", None)
    chat_id = getattr(agent, "_chat_id", None)
    thread_id = getattr(agent, "_thread_id", None)
    if not platform or not chat_id:
        return None
    parts = [str(platform), str(chat_id)]
    if thread_id:
        parts.append(str(thread_id))
    return ":".join(parts)


def _health(
    *,
    enabled: bool,
    channel: str | None,
    allowlisted: bool,
    skipped_reason: str | None,
) -> dict[str, Any]:
    return {
        "enabled": enabled,
        "channel": channel,
        "allowlisted": allowlisted,
        "skipped_reason": skipped_reason,
    }


def _render_active_block(state: Any, channel: str) -> str:
    """Render the compact active-hydration block.

    Includes only restore/avoid items and an epistemic-mode marker. No raw
    thread/event IDs, no seed path, no channel key, no transcript text.
    """

    restore_items = list(state.context_pack.restore)[:_MAX_RESTORE_ITEMS]
    avoid_items = list(state.context_pack.avoid)[:_MAX_AVOID_ITEMS]

    lines = [
        "[ContextOps active cognitive context — metadata only, not user-visible]",
        "Epistemic mode: restore unresolved cognitive pressure for this channel; "
        "do not flatten open tensions into closed answers.",
        "",
        "Restore:",
    ]
    if restore_items:
        for item in restore_items:
            lines.append(f"  - {item}")
    else:
        lines.append("  - (no active restore directives)")
    lines.append("")
    lines.append("Avoid:")
    if avoid_items:
        for item in avoid_items:
            lines.append(f"  - {item}")
    else:
        lines.append("  - (no active avoid directives)")
    return "\n".join(lines)


def build_active_context(
    *,
    agent: Any,
    original_user_message: str | None,
    config: dict[str, Any] | None,
) -> tuple[str | None, dict[str, Any]]:
    """Build the active ContextOps cognitive-hydration injection for one turn.

    Returns a ``(injection_text, health)`` tuple. ``injection_text`` is
    ``None`` whenever the feature is disabled, not allowlisted for this
    channel, or any safety check fails — in which case the caller MUST leave
    the API-call context unchanged. ``health`` is always a dict suitable for
    structured logging.
    """

    section = _cfg_section(config)
    enabled = bool(section and section.get("enabled"))
    channel = _channel_identity(agent)

    if not enabled:
        return None, _health(
            enabled=False, channel=channel, allowlisted=False, skipped_reason="disabled"
        )

    message = original_user_message if isinstance(original_user_message, str) else ""
    if not message.strip():
        return None, _health(
            enabled=True,
            channel=channel,
            allowlisted=False,
            skipped_reason="empty_message",
        )

    if channel is None:
        return None, _health(
            enabled=True,
            channel=None,
            allowlisted=False,
            skipped_reason="no_channel",
        )

    raw_allowlist = section.get("channel_allowlist") if section else None
    if not isinstance(raw_allowlist, list) or not raw_allowlist:
        return None, _health(
            enabled=True,
            channel=channel,
            allowlisted=False,
            skipped_reason="non_allowlisted",
        )
    allowlist = {str(entry).strip() for entry in raw_allowlist if str(entry).strip()}
    if channel not in allowlist:
        return None, _health(
            enabled=True,
            channel=channel,
            allowlisted=False,
            skipped_reason="non_allowlisted",
        )

    seed_path = section.get("seed_path") if section else None
    if not isinstance(seed_path, str) or not seed_path.strip():
        return None, _health(
            enabled=True,
            channel=channel,
            allowlisted=True,
            skipped_reason="no_seed",
        )

    pack_id = section.get("pack_id") if section else None
    if not isinstance(pack_id, str) or not pack_id.strip():
        pack_id = _DEFAULT_PACK_ID

    try:
        state = build_hydration_preview(
            channel, message, seed_path, pack_id=pack_id
        )
    except FileNotFoundError:
        return None, _health(
            enabled=True,
            channel=channel,
            allowlisted=True,
            skipped_reason="seed_unavailable",
        )
    except OSError:
        return None, _health(
            enabled=True,
            channel=channel,
            allowlisted=True,
            skipped_reason="seed_unavailable",
        )
    except Exception as exc:  # noqa: BLE001 - fail closed on any builder failure
        logger.warning("ContextOps active hydration build failed: %s", exc)
        return None, _health(
            enabled=True,
            channel=channel,
            allowlisted=True,
            skipped_reason="build_failed",
        )

    try:
        text = _render_active_block(state, channel)
    except Exception as exc:  # noqa: BLE001 - fail closed on render failure
        logger.warning("ContextOps active hydration render failed: %s", exc)
        return None, _health(
            enabled=True,
            channel=channel,
            allowlisted=True,
            skipped_reason="render_failed",
        )

    return text, _health(
        enabled=True,
        channel=channel,
        allowlisted=True,
        skipped_reason=None,
    )
