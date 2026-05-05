"""Audit log writer for the file-based test property loop.

One JSONL row per procedure step, schema mirrors `ucpm.audit_log` from the
canonical SOP global invariants:
    ts, property_id, procedure_id, step, persona, inputs_hash,
    action, output_ref, escalated_bool, operator_review_state.

The on-disk shape is stable so a future BigQuery loader can ingest these
files unchanged.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .schemas import AuditRow


def compute_inputs_hash(payload: Any) -> str:
    """Deterministic content hash of an arbitrary JSON-serializable payload.

    Used in `audit_row.inputs_hash` so replays are detectable and the
    BigQuery `audit_log` table can dedupe by content.
    """
    serialized = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class AuditWriter:
    """Append-only JSONL writer scoped to a single inbound message id.

    Each call to `write()` adds one line to `<audit_dir>/<msg_id>.jsonl`.
    The writer never reads or rewrites prior lines — appending only.
    """

    def __init__(self, audit_dir: Path, msg_id: str, property_id: str):
        self.audit_dir = audit_dir
        self.msg_id = msg_id
        self.property_id = property_id
        audit_dir.mkdir(parents=True, exist_ok=True)
        self._path = audit_dir / f"{msg_id}.jsonl"

    @property
    def path(self) -> Path:
        return self._path

    def write(
        self,
        *,
        procedure_id: str,
        step: str,
        persona: str,
        inputs_hash: str,
        action: str,
        output_ref: Optional[str] = None,
        escalated: bool = False,
        operator_review_state: str = "n/a",
        decision_criteria: Optional[dict[str, Any]] = None,
        notes: str = "",
    ) -> AuditRow:
        row = AuditRow(
            ts=datetime.now(timezone.utc),
            property_id=self.property_id,
            procedure_id=procedure_id,
            step=step,
            persona=persona,
            inputs_hash=inputs_hash,
            action=action,
            output_ref=output_ref,
            escalated_bool=escalated,
            operator_review_state=operator_review_state,  # type: ignore[arg-type]
            decision_criteria=decision_criteria or {},
            notes=notes,
        )
        # `mode_json` style ordered dict so on-disk fields read in audit-row
        # order (BigQuery-friendly).
        line = row.model_dump(mode="json")
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(line, separators=(",", ":")))
            fh.write("\n")
        return row

    def read_all(self) -> list[dict[str, Any]]:
        """Helper for tests: read back what we've written."""
        if not self._path.is_file():
            return []
        rows = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows
