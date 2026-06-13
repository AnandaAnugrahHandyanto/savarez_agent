"""Gateway event routing primitives.

This module defines a small, dependency-free event contract for gateway/runtime
messages before they are rendered to a platform such as Discord.  Runtime code
may create these events before handing the preserved text to existing renderers;
keep this module pure so it can be unit-tested without gateway, Discord, cron,
or NATS dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


class EventVisibility(str, Enum):
    """Where an event is allowed to surface."""

    CONVERSATION = "conversation"
    ACTION_LOG = "action_log"
    OPS_LOG = "ops_log"
    SILENT = "silent"


class EventOrigin(str, Enum):
    """Component class that produced the event."""

    USER_DELEGATION = "user_delegation"
    CRON = "cron"
    SYSTEM = "system"
    TOOL = "tool"
    APPROVAL = "approval"


class EventSeverity(str, Enum):
    """Event severity used for incident routing."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class EventRiskLevel(str, Enum):
    """Risk label for events that may require human approval."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class CronDeliveryKind(str, Enum):
    """High-level cron delivery disposition before platform rendering."""

    COMPLETED = "completed"
    FAILED = "failed"
    SILENT = "silent"


class RouteAction(str, Enum):
    """Routing action selected for an event."""

    DROP = "drop"
    SEND_MAIN = "send_main"
    SEND_ACTION_LOG = "send_action_log"
    SEND_OPS_LOG = "send_ops_log"
    SEND_INCIDENT = "send_incident"


def new_event_id() -> str:
    """Return a unique gateway event id."""

    return f"evt_{uuid4().hex}"


def new_run_id() -> str:
    """Return a unique runtime run id."""

    return f"run_{uuid4().hex}"


@dataclass(frozen=True)
class GatewayEvent:
    """Structured gateway/runtime event before platform rendering."""

    event_id: str
    event_type: str
    visibility: EventVisibility
    origin: EventOrigin
    content: str = ""
    summary: str | None = None
    task_id: str | None = None
    run_id: str | None = None
    session_id: str | None = None
    session_key: str | None = None
    platform: str | None = None
    chat_id: str | None = None
    thread_id: str | None = None
    severity: EventSeverity = EventSeverity.INFO
    risk_level: EventRiskLevel | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        object.__setattr__(self, "visibility", EventVisibility(self.visibility))
        object.__setattr__(self, "origin", EventOrigin(self.origin))
        object.__setattr__(self, "severity", EventSeverity(self.severity))
        if self.risk_level is not None:
            object.__setattr__(self, "risk_level", EventRiskLevel(self.risk_level))
        if self.created_at.tzinfo is None:
            object.__setattr__(
                self,
                "created_at",
                self.created_at.replace(tzinfo=timezone.utc),
            )


@dataclass(frozen=True)
class RouteDecision:
    """Deterministic routing result for a gateway event."""

    action: RouteAction
    target_visibility: EventVisibility
    reason: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "action", RouteAction(self.action))
        object.__setattr__(
            self,
            "target_visibility",
            EventVisibility(self.target_visibility),
        )


def create_event(
    *,
    event_type: str,
    event_id: str | None = None,
    visibility: EventVisibility | str = EventVisibility.CONVERSATION,
    origin: EventOrigin | str = EventOrigin.SYSTEM,
    content: str = "",
    summary: str | None = None,
    task_id: str | None = None,
    run_id: str | None = None,
    session_id: str | None = None,
    session_key: str | None = None,
    platform: str | None = None,
    chat_id: str | None = None,
    thread_id: str | None = None,
    severity: EventSeverity | str = EventSeverity.INFO,
    risk_level: EventRiskLevel | str | None = None,
    metadata: dict[str, Any] | None = None,
    created_at: datetime | None = None,
) -> GatewayEvent:
    """Create a GatewayEvent with stable defaults.

    Explicit ``event_id``, ``run_id`` and ``task_id`` values are preserved so
    callers can propagate existing correlation identifiers.
    """

    coerced_risk_level = EventRiskLevel(risk_level) if risk_level is not None else None
    return GatewayEvent(
        event_id=event_id or new_event_id(),
        event_type=event_type,
        visibility=EventVisibility(visibility),
        origin=EventOrigin(origin),
        content=content,
        summary=summary,
        task_id=task_id,
        run_id=run_id or new_run_id(),
        session_id=session_id,
        session_key=session_key,
        platform=platform,
        chat_id=chat_id,
        thread_id=thread_id,
        severity=EventSeverity(severity),
        risk_level=coerced_risk_level,
        metadata=dict(metadata or {}),
        created_at=created_at or datetime.now(timezone.utc),
    )


def create_approval_event(
    *,
    event_type: str = "approval.requested",
    content: str = "",
    summary: str | None = None,
    severity: EventSeverity | str = EventSeverity.WARNING,
    **kwargs: Any,
) -> GatewayEvent:
    """Create a high-risk, user-visible approval event."""

    return create_event(
        event_type=event_type,
        visibility=EventVisibility.CONVERSATION,
        origin=EventOrigin.APPROVAL,
        content=content,
        summary=summary,
        severity=severity,
        risk_level=EventRiskLevel.HIGH,
        **kwargs,
    )


def create_tool_progress_event(
    *,
    event_type: str,
    tool_name: str | None = None,
    content: str = "",
    summary: str | None = None,
    preview: str | None = None,
    task_id: str | None = None,
    run_id: str | None = None,
    session_id: str | None = None,
    session_key: str | None = None,
    platform: str | None = None,
    chat_id: str | None = None,
    thread_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> GatewayEvent:
    """Create an action-log event for gateway tool progress.

    The current Discord UX still renders the preformatted ``content`` text.
    Structured fields are carried in metadata for future renderers without
    requiring runtime callbacks to publish to an external bus.
    """

    event_metadata = dict(metadata or {})
    if tool_name is not None:
        event_metadata.setdefault("tool_name", tool_name)
    if preview is not None:
        event_metadata.setdefault("preview", preview)

    return create_event(
        event_type=event_type,
        visibility=EventVisibility.ACTION_LOG,
        origin=EventOrigin.TOOL,
        content=content,
        summary=summary or content,
        task_id=task_id,
        run_id=run_id,
        session_id=session_id,
        session_key=session_key,
        platform=platform,
        chat_id=chat_id,
        thread_id=thread_id,
        severity=EventSeverity.INFO,
        metadata=event_metadata,
    )


def create_cron_delivery_event(
    *,
    job_id: str,
    job_name: str | None = None,
    success: bool,
    content: str = "",
    error: str | None = None,
    run_id: str | None = None,
    output_file: str | None = None,
    metadata: dict[str, Any] | None = None,
    silent_marker: str = "[SILENT]",
) -> GatewayEvent:
    """Create an ops/silent event for cron delivery routing.

    This helper intentionally does not deliver anything.  It only classifies a
    cron run's user-visible disposition so scheduler delivery can move toward
    the same event-routing contract as gateway action logs.
    """

    text = "" if content is None else str(content)
    normalized = text.strip().upper()
    event_metadata = dict(metadata or {})
    event_metadata.update(
        {
            "job_id": job_id,
            "job_name": job_name or job_id,
        }
    )
    if output_file:
        event_metadata["output_file"] = output_file
    if error:
        event_metadata["error"] = error

    if success and silent_marker.upper() in normalized:
        event_metadata["cron_delivery_kind"] = CronDeliveryKind.SILENT.value
        return create_event(
            event_type="cron.silent",
            visibility=EventVisibility.SILENT,
            origin=EventOrigin.CRON,
            content=text,
            summary=f"Cron job {job_name or job_id} was silent",
            task_id=job_id,
            run_id=run_id,
            severity=EventSeverity.INFO,
            metadata=event_metadata,
        )

    if success:
        event_metadata["cron_delivery_kind"] = CronDeliveryKind.COMPLETED.value
        return create_event(
            event_type="cron.completed",
            visibility=EventVisibility.OPS_LOG,
            origin=EventOrigin.CRON,
            content=text,
            summary=f"Cron job {job_name or job_id} completed",
            task_id=job_id,
            run_id=run_id,
            severity=EventSeverity.INFO,
            metadata=event_metadata,
        )

    event_metadata["cron_delivery_kind"] = CronDeliveryKind.FAILED.value
    return create_event(
        event_type="cron.failed",
        visibility=EventVisibility.OPS_LOG,
        origin=EventOrigin.CRON,
        content=text or (error or "Cron job failed"),
        summary=f"Cron job {job_name or job_id} failed",
        task_id=job_id,
        run_id=run_id,
        severity=EventSeverity.ERROR,
        metadata=event_metadata,
    )


def classify_event(event: GatewayEvent) -> RouteDecision:
    """Return the P0 route decision for a gateway event."""

    visibility = EventVisibility(event.visibility)
    severity = EventSeverity(event.severity)

    if visibility == EventVisibility.SILENT:
        return RouteDecision(
            action=RouteAction.DROP,
            target_visibility=visibility,
            reason="silent event",
        )
    if visibility == EventVisibility.CONVERSATION:
        return RouteDecision(
            action=RouteAction.SEND_MAIN,
            target_visibility=visibility,
            reason="conversation event",
        )
    if visibility == EventVisibility.ACTION_LOG:
        return RouteDecision(
            action=RouteAction.SEND_ACTION_LOG,
            target_visibility=visibility,
            reason="action log event",
        )
    if visibility == EventVisibility.OPS_LOG:
        if severity in {EventSeverity.ERROR, EventSeverity.CRITICAL}:
            return RouteDecision(
                action=RouteAction.SEND_INCIDENT,
                target_visibility=visibility,
                reason="ops log incident severity",
            )
        return RouteDecision(
            action=RouteAction.SEND_OPS_LOG,
            target_visibility=visibility,
            reason="ops log event",
        )

    # Kept as a defensive guard in case EventVisibility grows in the future.
    return RouteDecision(
        action=RouteAction.DROP,
        target_visibility=visibility,
        reason="unhandled visibility",
    )
