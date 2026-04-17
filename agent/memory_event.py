from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class MemoryEvent:
    event_id: str
    action: str
    target: str
    content: str
    source_lane: str
    target_lanes: List[str]
    scope: str = "global"
    scope_value: Optional[str] = None
    kind: str = "lesson"
    restore_critical: bool = False
    provenance_ref: str = ""
    materialization_status: Dict[str, str] = field(default_factory=dict)
    materialization_results: Dict[str, Any] = field(default_factory=dict)
    entry_id: Optional[str] = None
    supersedes_entry_id: Optional[str] = None
    created_at: str = ""
    flags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
