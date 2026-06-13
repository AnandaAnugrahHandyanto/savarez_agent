from __future__ import annotations

from gateway.discord_event_renderer import render_action_log_batch, render_discord_event
from gateway.event_routing import (
    EventOrigin,
    EventSeverity,
    EventVisibility,
    create_event,
    create_tool_progress_event,
)


def test_render_silent_event_returns_none() -> None:
    event = create_event(
        event_type="debug.internal",
        visibility=EventVisibility.SILENT,
        origin=EventOrigin.SYSTEM,
        content="should not render",
    )

    assert render_discord_event(event) is None


def test_render_conversation_event_returns_sanitized_text() -> None:
    event = create_event(
        event_type="agent.response",
        visibility=EventVisibility.CONVERSATION,
        origin=EventOrigin.USER_DELEGATION,
        content="hello @everyone",
    )

    rendered = render_discord_event(event)

    assert rendered == "hello @\u200beveryone"


def test_render_action_log_preserves_current_tool_progress_text() -> None:
    event = create_tool_progress_event(
        event_type="tool.started",
        tool_name="read_file",
        content='📖 read_file: "gateway/run.py"',
        preview="gateway/run.py",
    )

    rendered = render_discord_event(event)

    assert rendered == event.content


def test_render_action_log_prefers_content_over_summary() -> None:
    event = create_event(
        event_type="tool.started",
        visibility=EventVisibility.ACTION_LOG,
        origin=EventOrigin.TOOL,
        content="current discord ux text",
        summary="structured summary for future renderer",
    )

    assert render_discord_event(event) == "current discord ux text"


def test_render_action_log_sanitizes_mentions_and_secret_lines() -> None:
    event = create_tool_progress_event(
        event_type="tool.started",
        tool_name="terminal",
        content="terminal: @here\nPASSWORD=placeholder",
    )

    rendered = render_discord_event(event)

    assert rendered is not None
    assert "@\u200bhere" in rendered
    assert "[REDACTED secret line]" in rendered
    assert "placeholder" not in rendered


def test_render_ops_log_info_uses_ops_format() -> None:
    event = create_event(
        event_type="cron.completed",
        visibility=EventVisibility.OPS_LOG,
        origin=EventOrigin.CRON,
        content="completed, 3 findings",
        run_id="run_123456789abcdef",
        severity=EventSeverity.INFO,
    )

    rendered = render_discord_event(event)

    assert rendered is not None
    assert rendered.startswith("🛠️ Agent ops")
    assert "cron.completed" in rendered
    assert "run_123456" in rendered
    assert "completed, 3 findings" in rendered


def test_render_ops_log_error_uses_incident_format() -> None:
    event = create_event(
        event_type="cron.failed",
        visibility=EventVisibility.OPS_LOG,
        origin=EventOrigin.CRON,
        content="failed after retries",
        run_id="run_error123456",
        task_id="task_error123456",
        severity=EventSeverity.ERROR,
    )

    rendered = render_discord_event(event)

    assert rendered is not None
    assert rendered.startswith("🚨 Agent incident")
    assert "cron.failed" in rendered
    assert "run_error123" in rendered
    assert "task_error12" in rendered
    assert "failed after retries" in rendered


def test_render_ops_log_critical_uses_critical_incident_title() -> None:
    event = create_event(
        event_type="cron.critical",
        visibility=EventVisibility.OPS_LOG,
        origin=EventOrigin.CRON,
        content="critical failure",
        severity=EventSeverity.CRITICAL,
    )

    rendered = render_discord_event(event)

    assert rendered is not None
    assert rendered.startswith("🚨 Critical agent incident")


def test_render_action_log_batch_only_includes_action_logs_and_counts_skipped() -> None:
    first = create_tool_progress_event(
        event_type="tool.started",
        tool_name="read_file",
        content="📖 read_file...",
    )
    second = create_tool_progress_event(
        event_type="tool.started",
        tool_name="terminal",
        content="💻 terminal...",
    )
    ops = create_event(
        event_type="cron.completed",
        visibility=EventVisibility.OPS_LOG,
        origin=EventOrigin.CRON,
        content="ops",
    )

    rendered = render_action_log_batch([first, second, ops], limit=1)

    assert rendered is not None
    assert rendered.startswith("Action log")
    assert "- 📖 read_file..." in rendered
    assert "💻 terminal..." not in rendered
    assert "… +2 dalších eventů" in rendered


def test_render_action_log_batch_returns_none_without_action_logs() -> None:
    ops = create_event(
        event_type="cron.completed",
        visibility=EventVisibility.OPS_LOG,
        origin=EventOrigin.CRON,
        content="ops",
    )

    assert render_action_log_batch([ops]) is None
