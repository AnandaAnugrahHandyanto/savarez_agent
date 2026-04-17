from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List


@dataclass(frozen=True)
class RecallReceipt:
    receipt_id: str
    query: str
    query_type: str
    routes: List[str]
    lanes_considered: List[str]
    lanes_used: List[str]
    winning_records: List[Dict[str, Any]] = field(default_factory=list)
    suppressed_records: List[Dict[str, Any]] = field(default_factory=list)
    suppression_reasons: List[str] = field(default_factory=list)
    degraded_flags: List[str] = field(default_factory=list)
    budget: Dict[str, Any] = field(default_factory=dict)
    context_block: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
