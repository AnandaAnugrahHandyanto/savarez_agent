from __future__ import annotations

from typing import Any, Dict


def format_recall_receipt_summary(receipt: Dict[str, Any] | None) -> str:
    if not receipt:
        return "recall receipt: unavailable"
    query_type = receipt.get("query_type", "unknown")
    lanes_used = ",".join(receipt.get("lanes_used") or []) or "none"
    suppressed = len(receipt.get("suppressed_records") or [])
    degraded = ",".join(receipt.get("degraded_flags") or []) or "none"
    routes = ",".join(receipt.get("routes") or []) or "none"
    return (
        f"query_type={query_type} "
        f"routes={routes} "
        f"lanes_used={lanes_used} "
        f"suppressed={suppressed} "
        f"degraded={degraded}"
    )
