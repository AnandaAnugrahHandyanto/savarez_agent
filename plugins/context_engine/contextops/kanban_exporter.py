"""Read-only Hermes Kanban -> ContextOps event exporter.

Harness-specific quarantine: this module is NOT part of the top-level
``contextops`` core API. Hermes-aware callers import it from the
``plugins.context_engine.contextops`` namespace; the harness-agnostic
core must never depend on it.

The exporter reads the Hermes Kanban SQLite file ``read-only`` (URI
``mode=ro``) and emits sanitized ``contextops.models.Event`` rows as
JSONL. Every emitted line carries only deterministic opaque
``ref:<hex>`` provenance pointers -- never the raw task id, run id,
session id, channel/discord id, payload body, or absolute path. The
exporter has its own last-line-of-defence leak gate that scans every
line before it is written, and a public :func:`scan_jsonl_for_leaks`
function the test suite uses to re-scan committed fixtures.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping

from contextops.models import Event

KANBAN_SOURCE = "hermes_kanban"
REF_NAMESPACE_TASK = "task"
REF_NAMESPACE_TASK_EVENT = "task_event"
REF_PREFIX = "ref:"
_REF_HEX_LEN = 24

# Only short identifier-like tokens survive into the emitted text/metadata.
# Anything else (free-text status notes, embedded paths, secret material)
# is replaced with the opaque label "redacted". The exporter never echoes
# raw bodies, titles, or payloads.
_SAFE_TOKEN_RE = re.compile(r"^[A-Za-z0-9._-]{1,32}$")
_REF_TOKEN_RE = re.compile(r"^ref:[0-9a-f]{6,64}$")
_RAW_ID_VALUE_RE = re.compile(
    r"(?i)\b(?:t_[0-9a-f]{6,}|task[-_][a-z0-9-]*\d[a-z0-9-]*"
    r"|msg[-_][a-z0-9-]*\d[a-z0-9-]*|sess(?:ion)?[-_][a-z0-9-]*\d[a-z0-9-]*)\b"
)

# Leak categories the exporter forbids in its own output. Mirrors the
# adapter's defence-in-depth gate; intentionally redundant with the
# per-field sanitization above so a regression in one layer still cannot
# leak raw Hermes data into emitted JSONL.
_LEAK_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "raw-id-field-name",
        re.compile(
            r"(?i)\b(?:task_id|event_id|run_id|session_id|chat_id|thread_id"
            r"|user_id|message_id|channel_id|guild_id)\b"
        ),
    ),
    (
        "raw-id-shaped-value",
        _RAW_ID_VALUE_RE,
    ),
    (
        "raw-payload-field-name",
        re.compile(
            r'"(?:payload|body|messages|content|tool_calls|transcript)"\s*:'
        ),
    ),
    (
        "absolute-or-home-path",
        re.compile(r"(?:^|\s|\")(?:/[^\s/\"]|~/|[A-Za-z]:[\\/])"),
    ),
    (
        "aws-access-key",
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    ),
    (
        "jwt-like-token",
        re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"),
    ),
    (
        "long-hex-blob",
        re.compile(r"\b[0-9a-fA-F]{32,}\b"),
    ),
    (
        "snowflake-id",
        re.compile(r"\b\d{17,}\b"),
    ),
)


def opaque_ref(value: str, *, namespace: str = REF_NAMESPACE_TASK) -> str:
    """Return a deterministic opaque ``ref:<hex>`` for a raw identifier.

    The digest is namespaced so that the task and task_event opaque ids
    for the same underlying raw value are distinct, but the result for a
    given (namespace, value) pair is stable across runs.
    """

    if not isinstance(value, str) or not value.strip():
        raise ValueError("opaque_ref requires a non-empty string")
    digest = hashlib.sha256(f"{namespace}:{value}".encode("utf-8")).hexdigest()[:_REF_HEX_LEN]
    return f"{REF_PREFIX}{digest}"


def _safe_token(value: Any) -> str:
    if not isinstance(value, str) or not _SAFE_TOKEN_RE.match(value):
        return "redacted"
    if _RAW_ID_VALUE_RE.search(value):
        return "redacted"
    for _label, pattern in _LEAK_PATTERNS:
        if pattern.search(value):
            return "redacted"
    return value


def _ts_from_db(value: Any) -> datetime:
    if isinstance(value, int) and value >= 0:
        return datetime.fromtimestamp(value, tz=timezone.utc)
    # Fall back to a deterministic zero timestamp rather than now() so
    # exporter output stays reproducible even on rows with missing
    # timestamps (which should not happen in a healthy Kanban DB).
    return datetime.fromtimestamp(0, tz=timezone.utc)


def task_row_to_event(row: Mapping[str, Any]) -> Event:
    """Convert one ``tasks`` row into a sanitized :class:`Event`."""

    task_id = row.get("id")
    if not isinstance(task_id, str) or not task_id.strip():
        raise ValueError("task row missing non-empty 'id'")
    status = _safe_token(row.get("status"))
    task_ref = opaque_ref(task_id, namespace=REF_NAMESPACE_TASK)
    return Event(
        id=task_ref,
        source=KANBAN_SOURCE,
        text=f"kanban task observed (status {status})",
        refs=[task_ref],
        created_at=_ts_from_db(row.get("created_at")),
        metadata={"kind": "kanban_task", "status": status},
    )


def task_event_row_to_event(row: Mapping[str, Any]) -> Event:
    """Convert one ``task_events`` row into a sanitized :class:`Event`."""

    event_seq = row.get("id")
    task_id = row.get("task_id")
    if event_seq is None:
        raise ValueError("task_event row missing 'id'")
    if not isinstance(task_id, str) or not task_id.strip():
        raise ValueError("task_event row missing non-empty 'task_id'")
    kind = _safe_token(row.get("kind"))
    task_ref = opaque_ref(task_id, namespace=REF_NAMESPACE_TASK)
    event_ref = opaque_ref(f"{task_id}:{event_seq}", namespace=REF_NAMESPACE_TASK_EVENT)
    return Event(
        id=event_ref,
        source=KANBAN_SOURCE,
        text=f"kanban event (kind {kind})",
        refs=[event_ref, task_ref],
        created_at=_ts_from_db(row.get("created_at")),
        metadata={"kind": "kanban_task_event", "task_event_kind": kind},
    )


def _open_readonly(db_path: Path) -> sqlite3.Connection:
    # ``mode=ro`` makes sqlite refuse any write attempt on this handle.
    uri = f"file:{Path(db_path).resolve()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def iter_kanban_events(db_path: Path) -> Iterator[Event]:
    """Yield sanitized :class:`Event` rows from the Kanban DB read-only."""

    conn = _open_readonly(Path(db_path))
    try:
        for row in conn.execute(
            "SELECT id, status, created_at FROM tasks ORDER BY id ASC"
        ):
            yield task_row_to_event(dict(row))
        for row in conn.execute(
            "SELECT id, task_id, kind, created_at FROM task_events ORDER BY id ASC"
        ):
            yield task_event_row_to_event(dict(row))
    finally:
        conn.close()


def export_kanban_to_jsonl(db_path: Path, output_path: Path) -> int:
    """Export sanitized events to ``output_path`` as JSONL.

    Returns the number of lines written. Every line is independently
    re-scanned by :func:`assert_line_safe` before being written, so a
    leak (raw id, path, secret, non-opaque ref) is a hard failure
    rather than a silent emission. The source DB is opened read-only.
    The output file may be created outside Hermes' state directory and
    is the only file this function writes to.
    """

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output.open("w", encoding="utf-8") as fh:
        for event in iter_kanban_events(Path(db_path)):
            line = event.model_dump_json()
            assert_line_safe(line)
            fh.write(line)
            fh.write("\n")
            count += 1
    return count


def assert_line_safe(line: str) -> None:
    """Raise :class:`ValueError` if ``line`` would leak raw Kanban data."""

    reason = _scan_leak(line)
    if reason is not None:
        raise ValueError(f"exporter line rejected by leak gate: {reason}")


def scan_jsonl_for_leaks(jsonl_path: Path) -> list[str]:
    """Re-scan a JSONL file for leaks. Empty list = clean.

    Useful for verifying a committed golden fixture or a freshly exported
    file from outside the exporter (e.g. a supervisor sanity check).
    """

    leaks: list[str] = []
    with Path(jsonl_path).open("r", encoding="utf-8") as fh:
        for line_no, raw in enumerate(fh, start=1):
            line = raw.rstrip("\n")
            if not line.strip():
                continue
            reason = _scan_leak(line)
            if reason is not None:
                leaks.append(f"line {line_no}: {reason}")
    return leaks


def _scan_leak(line: str) -> str | None:
    for label, pattern in _LEAK_PATTERNS:
        match = pattern.search(line)
        if match:
            return f"{label}: matched {match.group(0)!r}"
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        return "line is not valid JSON"
    if not isinstance(obj, dict):
        return "line is not a JSON object"
    refs = obj.get("refs", [])
    if not isinstance(refs, list):
        return "refs is not a list"
    for ref in refs:
        if not isinstance(ref, str) or not _REF_TOKEN_RE.match(ref):
            return f"non-opaque ref {ref!r}"
    return None
