"""Read-only OfficeState DTO skeleton for Hermes AI Office.

Stage 6 starts with an empty-but-valid DTO and explicit source-health entries.
Future slices will add read-only adapters that merge Kanban, cron, sessions,
topics, and provenance into this shape before final redaction serialization.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

from hermes_cli.office_redaction import RedactionReport


OFFICE_STATE_SCHEMA_VERSION = 1
_OFFICE_SOURCE_IDS = ("kanban", "cron", "sessions", "topics", "provenance")
SourceStatus = Literal["ok", "partial", "missing", "unavailable", "error"]


@dataclass(frozen=True)
class OfficeDataSource:
    id: str
    status: SourceStatus
    checked_at: str
    item_count: int = 0
    warning_count: int = 0
    error_summary: str | None = None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "id": self.id,
            "status": self.status,
            "checked_at": self.checked_at,
            "item_count": self.item_count,
            "warning_count": self.warning_count,
        }
        if self.error_summary:
            payload["error_summary"] = self.error_summary
        return payload


@dataclass(frozen=True)
class OfficeCapabilities:
    read_only: bool = True
    mutations_enabled: bool = False
    remote_mode: str = "unsupported"

    def to_dict(self) -> dict[str, object]:
        return {
            "read_only": self.read_only,
            "mutations_enabled": self.mutations_enabled,
            "remote_mode": self.remote_mode,
        }


@dataclass
class OfficeState:
    schema_version: int
    generated_at: str
    mode: str
    display_mode: str
    data_sources: list[OfficeDataSource] = field(default_factory=list)
    summary: dict[str, object] = field(default_factory=dict)
    rooms: list[dict[str, object]] = field(default_factory=list)
    agents: list[dict[str, object]] = field(default_factory=list)
    work_items: list[dict[str, object]] = field(default_factory=list)
    automations: list[dict[str, object]] = field(default_factory=list)
    topics: list[dict[str, object]] = field(default_factory=list)
    events: list[dict[str, object]] = field(default_factory=list)
    provenance: list[dict[str, object]] = field(default_factory=list)
    redactions: RedactionReport = field(default_factory=RedactionReport)
    capabilities: OfficeCapabilities = field(default_factory=OfficeCapabilities)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "generated_at": self.generated_at,
            "mode": self.mode,
            "display_mode": self.display_mode,
            "data_sources": [source.to_dict() for source in self.data_sources],
            "summary": dict(self.summary),
            "rooms": list(self.rooms),
            "agents": list(self.agents),
            "work_items": list(self.work_items),
            "automations": list(self.automations),
            "topics": list(self.topics),
            "events": list(self.events),
            "provenance": list(self.provenance),
            "redactions": self.redactions.to_dict(),
            "capabilities": self.capabilities.to_dict(),
        }


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_empty_office_state(*, display_mode: str = "localhost") -> OfficeState:
    """Build a read-only OfficeState with explicit empty source statuses."""

    generated_at = _utc_now_iso()
    return OfficeState(
        schema_version=OFFICE_STATE_SCHEMA_VERSION,
        generated_at=generated_at,
        mode="read_only",
        display_mode=display_mode,
        data_sources=[
            OfficeDataSource(id=source_id, status="missing", checked_at=generated_at)
            for source_id in _OFFICE_SOURCE_IDS
        ],
        summary={
            "needs_attention_count": None,
            "active_work_count": None,
            "automation_count": None,
            "warning_count": 0,
        },
    )


def _replace_source(
    sources: list[OfficeDataSource], replacement: OfficeDataSource
) -> list[OfficeDataSource]:
    replaced = False
    output: list[OfficeDataSource] = []
    for source in sources:
        if source.id == replacement.id:
            output.append(replacement)
            replaced = True
        else:
            output.append(source)
    if not replaced:
        output.append(replacement)
    return output


def _compute_summary(state: OfficeState) -> dict[str, object]:
    active_statuses = {"triage", "todo", "ready", "running"}
    needs_attention_statuses = {"blocked"}
    active_work_count = sum(
        1 for item in state.work_items if item.get("status") in active_statuses
    )
    needs_attention_count = sum(
        1 for item in state.work_items if item.get("status") in needs_attention_statuses
    )
    warning_count = sum(source.warning_count for source in state.data_sources)
    return {
        "needs_attention_count": needs_attention_count,
        "active_work_count": active_work_count,
        "automation_count": len(state.automations),
        "warning_count": warning_count,
    }


def build_office_state(
    *,
    display_mode: str = "localhost",
    include_kanban: bool = True,
    include_cron: bool = True,
    include_sessions: bool = True,
) -> OfficeState:
    """Build the read-only OfficeState projection from approved adapters."""

    state = build_empty_office_state(display_mode=display_mode)
    if include_kanban:
        from hermes_cli.office_adapters import collect_kanban_office_state

        kanban = collect_kanban_office_state()
        state.data_sources = _replace_source(state.data_sources, kanban.source)
        state.rooms.extend(kanban.rooms)
        state.agents.extend(kanban.agents)
        state.work_items.extend(kanban.work_items)
        state.automations.extend(kanban.automations)
        state.topics.extend(kanban.topics)
        state.events.extend(kanban.events)
        state.provenance.extend(kanban.provenance)
        state.redactions.merge(kanban.redactions)
    if include_cron:
        from hermes_cli.office_adapters import collect_cron_office_state

        cron = collect_cron_office_state()
        state.data_sources = _replace_source(state.data_sources, cron.source)
        state.rooms.extend(cron.rooms)
        state.agents.extend(cron.agents)
        state.work_items.extend(cron.work_items)
        state.automations.extend(cron.automations)
        state.topics.extend(cron.topics)
        state.events.extend(cron.events)
        state.provenance.extend(cron.provenance)
        state.redactions.merge(cron.redactions)
    if include_sessions:
        from hermes_cli.office_adapters import collect_session_office_state

        sessions = collect_session_office_state()
        state.data_sources = _replace_source(state.data_sources, sessions.source)
        state.rooms.extend(sessions.rooms)
        state.agents.extend(sessions.agents)
        state.work_items.extend(sessions.work_items)
        state.automations.extend(sessions.automations)
        state.topics.extend(sessions.topics)
        state.events.extend(sessions.events)
        state.provenance.extend(sessions.provenance)
        state.redactions.merge(sessions.redactions)
    state.summary = _compute_summary(state)
    return state
