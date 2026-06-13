from __future__ import annotations

from datetime import timezone

import pytest

from gateway.event_routing import (
    CronDeliveryKind,
    EventOrigin,
    EventRiskLevel,
    EventSeverity,
    EventVisibility,
    GatewayEvent,
    RouteAction,
    classify_event,
    create_approval_event,
    create_cron_delivery_event,
    create_event,
    create_tool_progress_event,
    new_event_id,
    new_run_id,
)


def test_conversation_event_routes_to_main() -> None:
    event = create_event(
        event_type="agent.response",
        visibility=EventVisibility.CONVERSATION,
        origin=EventOrigin.USER_DELEGATION,
    )

    decision = classify_event(event)

    assert decision.action == RouteAction.SEND_MAIN
    assert decision.target_visibility == EventVisibility.CONVERSATION


def test_action_log_event_routes_to_action_log() -> None:
    event = create_event(
        event_type="tool.started",
        visibility=EventVisibility.ACTION_LOG,
        origin=EventOrigin.TOOL,
    )

    decision = classify_event(event)

    assert decision.action == RouteAction.SEND_ACTION_LOG
    assert decision.target_visibility == EventVisibility.ACTION_LOG


@pytest.mark.parametrize(
    "severity",
    [EventSeverity.DEBUG, EventSeverity.INFO, EventSeverity.WARNING],
)
def test_ops_log_debug_info_and_warning_route_to_ops_log(severity: EventSeverity) -> None:
    event = create_event(
        event_type="cron.completed",
        visibility=EventVisibility.OPS_LOG,
        origin=EventOrigin.CRON,
        severity=severity,
    )

    decision = classify_event(event)

    assert decision.action == RouteAction.SEND_OPS_LOG
    assert decision.target_visibility == EventVisibility.OPS_LOG


@pytest.mark.parametrize("severity", [EventSeverity.ERROR, EventSeverity.CRITICAL])
def test_ops_log_error_and_critical_route_to_incident(severity: EventSeverity) -> None:
    event = create_event(
        event_type="cron.failed",
        visibility=EventVisibility.OPS_LOG,
        origin=EventOrigin.CRON,
        severity=severity,
    )

    decision = classify_event(event)

    assert decision.action == RouteAction.SEND_INCIDENT
    assert decision.target_visibility == EventVisibility.OPS_LOG


def test_silent_event_drops() -> None:
    event = create_event(
        event_type="tool.debug",
        visibility=EventVisibility.SILENT,
        origin=EventOrigin.SYSTEM,
    )

    decision = classify_event(event)

    assert decision.action == RouteAction.DROP
    assert decision.target_visibility == EventVisibility.SILENT


def test_create_event_preserves_explicit_ids() -> None:
    event = create_event(
        event_id="evt_explicit",
        run_id="run_explicit",
        task_id="task_explicit",
        event_type="agent.task.progress",
        visibility="action_log",
        origin="tool",
    )

    assert event.event_id == "evt_explicit"
    assert event.run_id == "run_explicit"
    assert event.task_id == "task_explicit"
    assert event.visibility == EventVisibility.ACTION_LOG
    assert event.origin == EventOrigin.TOOL


def test_gateway_event_rejects_invalid_visibility() -> None:
    with pytest.raises(ValueError):
        GatewayEvent(
            event_id="evt_bad",
            event_type="bad.visibility",
            visibility="bad",  # type: ignore[arg-type]
            origin=EventOrigin.SYSTEM,
        )


def test_gateway_event_rejects_invalid_severity() -> None:
    with pytest.raises(ValueError):
        GatewayEvent(
            event_id="evt_bad",
            event_type="bad.severity",
            visibility=EventVisibility.CONVERSATION,
            origin=EventOrigin.SYSTEM,
            severity="bad",  # type: ignore[arg-type]
        )


def test_new_event_id_has_prefix_and_is_unique() -> None:
    first = new_event_id()
    second = new_event_id()

    assert first.startswith("evt_")
    assert second.startswith("evt_")
    assert first != second


def test_new_run_id_has_prefix_and_is_unique() -> None:
    first = new_run_id()
    second = new_run_id()

    assert first.startswith("run_")
    assert second.startswith("run_")
    assert first != second


def test_create_event_generates_ids_and_utc_timestamp() -> None:
    event = create_event(event_type="agent.created")

    assert event.event_id.startswith("evt_")
    assert event.run_id is not None
    assert event.run_id.startswith("run_")
    assert event.created_at.tzinfo is not None
    assert event.created_at.utcoffset() == timezone.utc.utcoffset(event.created_at)


def test_create_approval_event_is_user_visible_high_risk() -> None:
    event = create_approval_event(
        event_type="approval.requested",
        content="Deploy to production?",
        task_id="task_approval",
    )

    assert event.origin == EventOrigin.APPROVAL
    assert event.visibility == EventVisibility.CONVERSATION
    assert event.risk_level == EventRiskLevel.HIGH
    assert event.severity == EventSeverity.WARNING
    assert event.task_id == "task_approval"
    assert classify_event(event).action == RouteAction.SEND_MAIN


def test_create_tool_progress_event_is_action_log_with_metadata() -> None:
    event = create_tool_progress_event(
        event_type="tool.started",
        tool_name="read_file",
        content='📖 read_file: "gateway/run.py"',
        preview="gateway/run.py",
        task_id="task_progress",
        run_id="run_progress",
        session_id="session_progress",
        session_key="discord:thread",
        platform="discord",
        chat_id="channel_1",
        thread_id="thread_1",
    )

    assert event.origin == EventOrigin.TOOL
    assert event.visibility == EventVisibility.ACTION_LOG
    assert event.summary == event.content
    assert event.task_id == "task_progress"
    assert event.run_id == "run_progress"
    assert event.session_id == "session_progress"
    assert event.session_key == "discord:thread"
    assert event.platform == "discord"
    assert event.chat_id == "channel_1"
    assert event.thread_id == "thread_1"
    assert event.metadata["tool_name"] == "read_file"
    assert event.metadata["preview"] == "gateway/run.py"
    assert classify_event(event).action == RouteAction.SEND_ACTION_LOG


def test_create_cron_delivery_event_success_routes_to_ops_log() -> None:
    event = create_cron_delivery_event(
        job_id="job_1",
        job_name="Daily report",
        success=True,
        content="completed",
        run_id="run_cron",
        output_file="/tmp/out.md",
    )

    assert event.event_type == "cron.completed"
    assert event.origin == EventOrigin.CRON
    assert event.visibility == EventVisibility.OPS_LOG
    assert event.severity == EventSeverity.INFO
    assert event.task_id == "job_1"
    assert event.run_id == "run_cron"
    assert event.metadata["cron_delivery_kind"] == CronDeliveryKind.COMPLETED.value
    assert event.metadata["output_file"] == "/tmp/out.md"
    assert classify_event(event).action == RouteAction.SEND_OPS_LOG


def test_create_cron_delivery_event_silent_routes_to_drop() -> None:
    event = create_cron_delivery_event(
        job_id="job_quiet",
        success=True,
        content="[SILENT]",
    )

    assert event.event_type == "cron.silent"
    assert event.visibility == EventVisibility.SILENT
    assert event.metadata["cron_delivery_kind"] == CronDeliveryKind.SILENT.value
    assert classify_event(event).action == RouteAction.DROP


def test_create_cron_delivery_event_failure_routes_to_incident() -> None:
    event = create_cron_delivery_event(
        job_id="job_broken",
        job_name="Broken job",
        success=False,
        content="failed",
        error="boom",
    )

    assert event.event_type == "cron.failed"
    assert event.origin == EventOrigin.CRON
    assert event.visibility == EventVisibility.OPS_LOG
    assert event.severity == EventSeverity.ERROR
    assert event.content == "failed"
    assert event.metadata["cron_delivery_kind"] == CronDeliveryKind.FAILED.value
    assert event.metadata["error"] == "boom"
    assert classify_event(event).action == RouteAction.SEND_INCIDENT
