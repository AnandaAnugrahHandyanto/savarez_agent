"""Discord rendering helpers for gateway events.

The renderer is intentionally dependency-light and not wired into the runtime in
this slice.  It converts structured GatewayEvent objects into Discord-safe text
while preserving today's tool-progress UX for ACTION_LOG events.
"""

from __future__ import annotations

from collections.abc import Iterable

from gateway.event_routing import (
    EventSeverity,
    EventVisibility,
    GatewayEvent,
    RouteAction,
    classify_event,
)


def _sanitize_for_discord(text: str | None) -> str:
    """Return text hardened for Discord delivery.

    Reuse the existing cron Discord sanitizer because it already neutralizes
    mentions, Markdown hiding, and obvious secret-shaped output.  Keep a tiny
    fallback so this renderer remains safe in isolated unit tests.
    """

    value = "" if text is None else str(text)
    try:
        from cron.discord_delivery import sanitize_cron_output_for_discord

        return sanitize_cron_output_for_discord(value)
    except Exception:
        return value.replace("@everyone", "@\u200beveryone").replace("@here", "@\u200bhere")


def _event_text(event: GatewayEvent) -> str:
    return event.summary or event.content or event.event_type


def _short_id(value: str | None, *, fallback: str = "-") -> str:
    if not value:
        return fallback
    return value[:12]


def render_discord_event(event: GatewayEvent) -> str | None:
    """Render a GatewayEvent as Discord-safe text.

    P0/P1 semantics:
    - silent events return None
    - action_log events preserve event.content when provided
    - ops_log error/critical events are rendered as incidents
    - conversation events render their summary/content directly
    """

    decision = classify_event(event)
    if decision.action == RouteAction.DROP:
        return None

    text = _sanitize_for_discord(_event_text(event)).strip()
    if decision.action == RouteAction.SEND_MAIN:
        return text

    if decision.action == RouteAction.SEND_ACTION_LOG:
        # Action-log events carry today's already-formatted tool-progress UX in
        # content.  Prefer it over summary so structured summaries cannot change
        # the Discord text until a future renderer opts in explicitly.
        return _sanitize_for_discord(event.content or event.summary or event.event_type).strip()

    if decision.action == RouteAction.SEND_INCIDENT:
        title = "🚨 Agent incident"
        if event.severity == EventSeverity.CRITICAL:
            title = "🚨 Critical agent incident"
        return "\n".join(
            part
            for part in [
                title,
                f"type: `{_sanitize_for_discord(event.event_type)}`",
                f"run: `{_short_id(event.run_id)}`",
                f"task: `{_short_id(event.task_id)}`" if event.task_id else None,
                text,
            ]
            if part
        )

    if decision.action == RouteAction.SEND_OPS_LOG:
        return "\n".join(
            part
            for part in [
                "🛠️ Agent ops",
                f"type: `{_sanitize_for_discord(event.event_type)}`",
                f"run: `{_short_id(event.run_id)}`",
                text,
            ]
            if part
        )

    return None


def render_action_log_batch(events: Iterable[GatewayEvent], *, limit: int = 10) -> str | None:
    """Render multiple action-log events as a compact Discord-safe block."""

    lines: list[str] = []
    skipped = 0
    for event in events:
        if event.visibility != EventVisibility.ACTION_LOG:
            skipped += 1
            continue
        rendered = render_discord_event(event)
        if not rendered:
            continue
        if len(lines) < limit:
            lines.append(f"- {rendered}")
        else:
            skipped += 1

    if not lines:
        return None

    suffix = f"\n… +{skipped} dalších eventů" if skipped else ""
    return "Action log\n" + "\n".join(lines) + suffix
