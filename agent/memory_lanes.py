from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class MemoryLane:
    name: str
    authority: str
    derived: bool
    supports_recovery: bool
    recovery_safe: bool
    description: str


_LANES: Dict[str, MemoryLane] = {
    "sqlite_memory": MemoryLane(
        name="sqlite_memory",
        authority="canonical",
        derived=False,
        supports_recovery=False,
        recovery_safe=False,
        description="SQLite-backed durable local fact store.",
    ),
    "wiki_compiled": MemoryLane(
        name="wiki_compiled",
        authority="derived",
        derived=True,
        supports_recovery=False,
        recovery_safe=False,
        description="Markdown/wiki synthesis lane derived from durable memory.",
    ),
    "session_search": MemoryLane(
        name="session_search",
        authority="transcript",
        derived=False,
        supports_recovery=False,
        recovery_safe=False,
        description="Compact transcript recall from prior sessions.",
    ),
    "clerk_reset": MemoryLane(
        name="clerk_reset",
        authority="reset_continuity",
        derived=False,
        supports_recovery=True,
        recovery_safe=True,
        description="Single-turn continuity recovered after /reset.",
    ),
    "chain_of_shells": MemoryLane(
        name="chain_of_shells",
        authority="external_recovery_truth",
        derived=False,
        supports_recovery=True,
        recovery_safe=True,
        description="External continuity truth lane for restore-critical state.",
    ),
    "file_anchors": MemoryLane(
        name="file_anchors",
        authority="external_recovery_truth",
        derived=False,
        supports_recovery=True,
        recovery_safe=True,
        description="Local anchor breadcrumb lane for restore-critical state.",
    ),
}


def get_lane(name: str) -> MemoryLane:
    return _LANES[name]


def list_lanes() -> List[MemoryLane]:
    return list(_LANES.values())
