"""Data models for Symphony tracker integrations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Issue:
    """Normalized tracker issue candidate."""

    id: str
    identifier: str
    title: str
    url: str
    state: str
    labels: list[str]
    priority: int | None
    blocked_by_ids: list[str]
    created_at: str
