"""Append-only JSONL event store for ContextOps/ESE.

A single bounded slice: define the event contract (lane / kind /
sanitized_payload / provenance) and an append-only JSONL store. The store is
the ONLY scoped sink ContextOps writes to; it never mutates upstream memory,
dispatcher, board, or live-routing state of any host runtime.

Every payload/provenance value passes the same fail-closed leak gate that
protects ``ContextPack``: raw transcripts, provider payloads, secrets, raw
ids, and absolute paths are rejected, not scrubbed. Dictionary *keys* are
NOT scanned, so structural field names like ``sanitized_payload`` and
``provenance`` cannot trip the gate.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .contracts import SCHEMA_VERSION
from .safety import assert_text_safe, scan_unsafe

_JsonScalar = (str, int, float, bool, type(None))


@dataclass(frozen=True)
class ContextOpsEvent:
    """One append-only ContextOps event row.

    ``lane`` is the cognitive lane label (e.g. ``observation``,
    ``context_pack``, ``state_delta``). ``kind`` is the event-type label
    within that lane. ``sanitized_payload`` carries already-scrubbed values
    intended for replay/inspection; ``provenance`` carries opaque adapter
    metadata (source label, opaque refs). The full leak gate runs over every
    string value before the event is constructed.
    """

    lane: str
    kind: str
    sanitized_payload: Mapping[str, Any] = field(default_factory=dict)
    provenance: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        """Return a deterministic, JSON-ready row for JSONL serialisation."""

        return {
            "schema_version": self.schema_version,
            "lane": self.lane,
            "kind": self.kind,
            "sanitized_payload": _canonicalise(self.sanitized_payload),
            "provenance": _canonicalise(self.provenance),
        }


def _scan_value(value: Any, path: str) -> None:
    """Run the leak gate over every string value, recursively.

    Mapping *keys* are intentionally not scanned to avoid false positives
    from legitimate structural field names (e.g. ``sanitized_payload``).
    """

    if isinstance(value, str):
        reason = scan_unsafe(value)
        if reason is not None:
            raise ValueError(f"{path} rejected by leak gate: {reason}")
        return
    if isinstance(value, Mapping):
        for k, v in value.items():
            if not isinstance(k, str):
                raise ValueError(f"{path} key must be a string")
            _scan_value(v, f"{path}.{k}")
        return
    if isinstance(value, (list, tuple)):
        for i, item in enumerate(value):
            _scan_value(item, f"{path}[{i}]")
        return
    if isinstance(value, _JsonScalar):
        return
    raise ValueError(f"{path} unsupported value type {type(value).__name__}")


def _canonicalise(value: Any) -> Any:
    """Sort mapping keys recursively so JSONL output is deterministic."""

    if isinstance(value, Mapping):
        return {k: _canonicalise(value[k]) for k in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_canonicalise(v) for v in value]
    return value


def build_event(
    *,
    lane: str,
    kind: str,
    sanitized_payload: Mapping[str, Any] | None = None,
    provenance: Mapping[str, Any] | None = None,
) -> ContextOpsEvent:
    """Build a leak-gated :class:`ContextOpsEvent`.

    Lane/kind are validated as printable cognitive labels; every string
    value inside ``sanitized_payload``/``provenance`` is run through the
    same fail-closed safety scan that gates ``ContextPack``.
    """

    lane_v = assert_text_safe(lane, "lane")
    kind_v = assert_text_safe(kind, "kind")
    if not lane_v.strip():
        raise ValueError("lane must not be empty")
    if not kind_v.strip():
        raise ValueError("kind must not be empty")
    payload = dict(sanitized_payload or {})
    prov = dict(provenance or {})
    _scan_value(payload, "sanitized_payload")
    _scan_value(prov, "provenance")
    return ContextOpsEvent(
        lane=lane_v,
        kind=kind_v,
        sanitized_payload=payload,
        provenance=prov,
    )


class JsonlEventStore:
    """Append-only JSONL sink for sanitised ContextOps events.

    The store opens the underlying file in append mode for every write, so
    on-disk row order matches call order and the file is never rewritten in
    place. Reads return parsed rows but do not re-validate them; the
    write-time leak gate is the single source of truth for safety.
    """

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event: ContextOpsEvent) -> dict[str, Any]:
        """Serialise ``event`` and append one JSONL row; return the row dict."""

        row = event.to_dict()
        line = json.dumps(row, ensure_ascii=False, separators=(",", ":"))
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        return row

    def read_all(self) -> list[dict[str, Any]]:
        """Return parsed rows in append order; empty list if file is absent."""

        if not self.path.exists():
            return []
        rows: list[dict[str, Any]] = []
        with self.path.open("r", encoding="utf-8") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                rows.append(json.loads(raw))
        return rows
