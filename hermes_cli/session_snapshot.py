"""Pure, read-only ``hermes.session_snapshot.v1`` adapter.

This module is the Hermes-native implementation of the session-snapshot
contract scoped by the design spike ``t_1939eeda`` (decision: *adopt
selectively* — build a read-only Hermes-native adapter, do **not** import
the upstream ECC code, and do not treat the existing raw Kanban/audit
fields as a canonical schema-versioned contract).

The upstream design artifact
(``hermes-session-snapshot-contract-spike.md``) lived in an ephemeral
scratch workspace that has since been reaped, so the concrete schema here
is reconstructed from the acceptance criteria of follow-up ``t_9bb6c05a``
and the live Hermes surfaces it adapts:

* the Kanban DB (:mod:`hermes_cli.kanban_db` — ``tasks`` / ``task_runs`` /
  ``task_events``), and
* a standalone gate/risk *audit log* (one JSON object per line, e.g. the
  Waukeen ``risk_check`` audit format with ``decision`` /
  ``rule_results``).

Design invariants
-----------------
* **Read only.** Every Kanban access goes through the ``SELECT``-only
  query helpers in :mod:`hermes_cli.kanban_db` (``get_task``,
  ``list_tasks``, ``list_runs``, ``list_events``). Building a snapshot
  never writes, so it cannot change ``tasks`` / ``task_runs`` /
  ``task_events`` row counts. The audit builder operates on already-parsed
  dicts and never touches the source file beyond an optional read.
* **Degrade, never raise, on dirty data.** Invalid run metadata, unknown
  task statuses, and malformed audit entries are normalised into the
  snapshot and surfaced as structured ``warnings`` rather than aborting
  generation.
* **Self-consistent aggregates.** ``derive_aggregate`` is the single
  source of the counts, and :func:`validate_snapshot` re-checks that the
  aggregate matches the materialised ``sessions`` list.

No scheduler hook, CLI command, tool, or dashboard surface imports this
module — exposure is deliberately deferred to a separate, approved change.
"""

from __future__ import annotations

import json
from typing import Any, Iterable, Mapping, Optional

try:  # pragma: no cover - import shim so the module is usable standalone
    from hermes_cli import kanban_db as _kb
except Exception:  # pragma: no cover
    _kb = None  # type: ignore[assignment]


SCHEMA_VERSION = "hermes.session_snapshot.v1"

#: Snapshot ``kind`` discriminator values.
KIND_KANBAN = "kanban"
KIND_STANDALONE_AUDIT = "standalone_audit"

#: Task statuses the adapter recognises. Mirrors
#: ``kanban_db.VALID_STATUSES`` but is duplicated here so the adapter still
#: classifies sanely if the source DB carries a status the current kernel
#: build does not know about (forward/backward compat). Anything outside
#: this set is bucketed as ``"unknown"`` while the raw value is preserved.
KNOWN_TASK_STATUSES = {
    "triage",
    "todo",
    "scheduled",
    "ready",
    "running",
    "blocked",
    "review",
    "done",
    "archived",
}

#: Normalised standalone-audit decisions.
_DECISION_MAP = {
    "PASS": "pass",
    "PASS_WITH_WARNINGS": "pass_with_warnings",
    "BLOCK": "block",
}

#: Run-metadata keys treated as artifact path lists.
_ARTIFACT_KEY = "artifacts"
_CHANGED_FILES_KEY = "changed_files"


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _coerce_str_list(value: Any) -> tuple[list[str], bool]:
    """Coerce ``value`` into a list of non-empty strings.

    Returns ``(items, ok)`` where ``ok`` is ``False`` when ``value`` was
    present but not a clean list of strings (the caller records a warning).
    A ``None``/missing value is *not* an error: ``([], True)``.
    """
    if value is None:
        return [], True
    if not isinstance(value, (list, tuple)):
        return [], False
    out: list[str] = []
    ok = True
    for item in value:
        if isinstance(item, str) and item.strip():
            out.append(item)
        else:
            ok = False
    return out, ok


def _warn(warnings: list[dict], code: str, **fields: Any) -> None:
    entry = {"code": code}
    entry.update(fields)
    warnings.append(entry)


# ---------------------------------------------------------------------------
# Kanban snapshot
# ---------------------------------------------------------------------------

def _build_run_record(run: Any, *, task_id: str, warnings: list[dict]) -> dict:
    """Normalise a :class:`kanban_db.Run` into a snapshot run record.

    ``run.metadata`` has already been JSON-decoded by ``Run.from_row``
    (``None`` on decode failure). We additionally degrade when it decoded
    to something other than a mapping (e.g. a JSON list or scalar).
    """
    metadata = run.metadata
    metadata_ok = True
    safe_metadata: dict[str, Any] = {}
    if metadata is None:
        # Either genuinely absent or unparseable upstream — indistinguishable
        # here, so only warn when the raw column actually held something.
        metadata_ok = True
    elif isinstance(metadata, Mapping):
        safe_metadata = dict(metadata)
    else:
        metadata_ok = False
        _warn(
            warnings,
            "invalid_run_metadata",
            task_id=task_id,
            run_id=run.id,
            detail=f"run metadata is {type(metadata).__name__}, expected object",
        )

    artifacts, art_ok = _coerce_str_list(safe_metadata.get(_ARTIFACT_KEY))
    changed_files, cf_ok = _coerce_str_list(safe_metadata.get(_CHANGED_FILES_KEY))
    if not art_ok:
        metadata_ok = False
        _warn(warnings, "invalid_artifacts", task_id=task_id, run_id=run.id)
    if not cf_ok:
        metadata_ok = False
        _warn(warnings, "invalid_changed_files", task_id=task_id, run_id=run.id)

    return {
        "run_id": run.id,
        "status": run.status,
        "outcome": run.outcome,
        "profile": run.profile,
        "step_key": run.step_key,
        "started_at": run.started_at,
        "ended_at": run.ended_at,
        "summary": run.summary,
        "error": run.error,
        "metadata_ok": metadata_ok,
        "artifacts": artifacts,
        "changed_files": changed_files,
        "artifact_count": len(artifacts),
    }


def _build_task_session(conn: Any, task: Any, *, warnings: list[dict]) -> dict:
    """Normalise one Kanban task (+ its runs/events) into a session record."""
    status = task.status
    status_known = status in KNOWN_TASK_STATUSES
    if not status_known:
        _warn(warnings, "unknown_task_status", task_id=task.id, raw_status=status)

    runs = [
        _build_run_record(r, task_id=task.id, warnings=warnings)
        for r in _kb.list_runs(conn, task.id)
    ]
    events = _kb.list_events(conn, task.id)
    artifact_count = sum(r["artifact_count"] for r in runs)

    return {
        "task_id": task.id,
        "title": task.title,
        "assignee": task.assignee,
        "status": status if status_known else "unknown",
        "raw_status": status,
        "status_known": status_known,
        "tenant": task.tenant,
        "session_id": task.session_id,
        "created_at": task.created_at,
        "started_at": task.started_at,
        "completed_at": task.completed_at,
        "current_run_id": task.current_run_id,
        "runs": runs,
        "run_count": len(runs),
        "event_count": len(events),
        "artifact_count": artifact_count,
        "latest_run": runs[-1] if runs else None,
    }


def build_kanban_snapshot(
    conn: Any,
    *,
    task_id: Optional[str] = None,
    assignee: Optional[str] = None,
    status: Optional[str] = None,
    include_archived: bool = False,
    generated_at: Optional[int] = None,
) -> dict:
    """Build a ``hermes.session_snapshot.v1`` snapshot from a Kanban DB.

    Pass ``task_id`` to snapshot a single task, or ``assignee`` / ``status``
    to snapshot a filtered slice of the board (omitting all three snapshots
    the whole board). Strictly read-only.

    ``generated_at`` is accepted (rather than read from the clock) so the
    function stays deterministic and resume-safe for callers/tests.
    """
    if _kb is None:  # pragma: no cover - defensive
        raise RuntimeError("hermes_cli.kanban_db is unavailable")

    warnings: list[dict] = []
    if task_id is not None:
        task = _kb.get_task(conn, task_id)
        tasks = [task] if task is not None else []
        if task is None:
            _warn(warnings, "task_not_found", task_id=task_id)
    else:
        tasks = _kb.list_tasks(
            conn,
            assignee=assignee,
            status=status,
            include_archived=include_archived,
        )

    sessions = [_build_task_session(conn, t, warnings=warnings) for t in tasks]
    aggregate = derive_aggregate(KIND_KANBAN, sessions)

    return {
        "schema_version": SCHEMA_VERSION,
        "kind": KIND_KANBAN,
        "generated_at": generated_at,
        "source": {
            "type": KIND_KANBAN,
            "task_id": task_id,
            "assignee": assignee,
            "status": status,
            "include_archived": include_archived,
        },
        "sessions": sessions,
        "aggregate": aggregate,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Standalone audit snapshot
# ---------------------------------------------------------------------------

def load_audit_log(path: str) -> tuple[list[dict], int]:
    """Read a JSON-lines audit log, returning ``(entries, skipped)``.

    Blank lines and lines that fail to parse as a JSON object are skipped
    and counted (rather than raising), so a partially-corrupt log still
    yields a usable snapshot. Read-only — never writes the file back.
    """
    entries: list[dict] = []
    skipped = 0
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                skipped += 1
                continue
            if isinstance(obj, dict):
                entries.append(obj)
            else:
                skipped += 1
    return entries, skipped


def _build_audit_session(entry: Mapping[str, Any], *, index: int, warnings: list[dict]) -> dict:
    raw_decision = entry.get("decision")
    normalized = _DECISION_MAP.get(raw_decision, "unknown")
    if normalized == "unknown":
        _warn(warnings, "unknown_audit_decision", index=index, raw_decision=raw_decision)

    rule_results = entry.get("rule_results")
    warn_rules: list[dict] = []
    block_rules: list[dict] = []
    if isinstance(rule_results, list):
        for rr in rule_results:
            if not isinstance(rr, Mapping):
                continue
            st = rr.get("status")
            if st == "warn":
                warn_rules.append(dict(rr))
            elif st == "block":
                block_rules.append(dict(rr))
    elif rule_results is not None:
        _warn(warnings, "invalid_rule_results", index=index)

    # PASS_WITH_WARNINGS (or any warn rule) maps to snapshot-level warnings so
    # callers can surface non-blocking gate concerns without re-parsing rules.
    for wr in warn_rules:
        _warn(
            warnings,
            "audit_warn",
            index=index,
            actor=entry.get("actor"),
            gate=entry.get("gate"),
            rule=wr.get("rule"),
            detail=wr.get("detail"),
        )

    return {
        "index": index,
        "ts": entry.get("ts"),
        "actor": entry.get("actor"),
        "gate": entry.get("gate"),
        "decision": normalized,
        "raw_decision": raw_decision,
        "policy_version": entry.get("policy_version"),
        "warn_rules": warn_rules,
        "block_rules": block_rules,
        "warn_count": len(warn_rules),
        "block_count": len(block_rules),
    }


def build_standalone_audit_snapshot(
    entries: Iterable[Mapping[str, Any]],
    *,
    source: Optional[str] = None,
    sot_stale: bool = False,
    sot_age_seconds: Optional[int] = None,
    sot_stale_threshold_seconds: Optional[int] = None,
    skipped_entries: int = 0,
    generated_at: Optional[int] = None,
) -> dict:
    """Build a ``hermes.session_snapshot.v1`` snapshot from audit entries.

    Each audit decision becomes one session record. Non-blocking warn rules
    (``PASS_WITH_WARNINGS``) are mapped to snapshot-level ``warnings``.

    Stale source-of-truth mapping: a standalone audit log is only a usable
    SOT while it is fresh. A ``stale_sot`` warning is emitted when either

    * ``sot_stale=True`` is passed explicitly, or
    * ``sot_age_seconds`` exceeds ``sot_stale_threshold_seconds`` (both
      provided).

    The age comparison is supplied by the caller (rather than read from the
    clock) to keep the builder deterministic and side-effect free.
    """
    warnings: list[dict] = []
    sessions: list[dict] = []
    for idx, entry in enumerate(entries):
        if not isinstance(entry, Mapping):
            _warn(warnings, "invalid_audit_entry", index=idx)
            continue
        sessions.append(_build_audit_session(entry, index=idx, warnings=warnings))

    if skipped_entries:
        _warn(warnings, "skipped_audit_lines", count=skipped_entries)

    stale = bool(sot_stale)
    if (
        not stale
        and sot_age_seconds is not None
        and sot_stale_threshold_seconds is not None
        and sot_age_seconds > sot_stale_threshold_seconds
    ):
        stale = True
    if stale:
        _warn(
            warnings,
            "stale_sot",
            severity="warn",
            source=source,
            age_seconds=sot_age_seconds,
            threshold_seconds=sot_stale_threshold_seconds,
            detail="standalone audit source-of-truth is stale",
        )

    aggregate = derive_aggregate(KIND_STANDALONE_AUDIT, sessions)
    aggregate["stale_sot"] = stale

    return {
        "schema_version": SCHEMA_VERSION,
        "kind": KIND_STANDALONE_AUDIT,
        "generated_at": generated_at,
        "source": {
            "type": KIND_STANDALONE_AUDIT,
            "path": source,
            "skipped_entries": skipped_entries,
        },
        "sessions": sessions,
        "aggregate": aggregate,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Aggregate derivation
# ---------------------------------------------------------------------------

def derive_aggregate(kind: str, sessions: list[dict]) -> dict:
    """Derive the aggregate counts block for ``sessions`` of ``kind``.

    The invariant enforced by :func:`validate_snapshot` is that the
    per-status / per-decision count maps sum back to ``session_count``.
    """
    if kind == KIND_KANBAN:
        status_counts: dict[str, int] = {}
        run_status_counts: dict[str, int] = {}
        run_count = 0
        artifact_count = 0
        event_count = 0
        unknown_status_count = 0
        for s in sessions:
            status_counts[s["status"]] = status_counts.get(s["status"], 0) + 1
            if not s["status_known"]:
                unknown_status_count += 1
            run_count += s["run_count"]
            artifact_count += s["artifact_count"]
            event_count += s["event_count"]
            for r in s["runs"]:
                run_status_counts[r["status"]] = run_status_counts.get(r["status"], 0) + 1
        return {
            "session_count": len(sessions),
            "status_counts": status_counts,
            "run_count": run_count,
            "run_status_counts": run_status_counts,
            "artifact_count": artifact_count,
            "event_count": event_count,
            "unknown_status_count": unknown_status_count,
        }

    if kind == KIND_STANDALONE_AUDIT:
        decision_counts: dict[str, int] = {}
        warn_count = 0
        block_count = 0
        for s in sessions:
            decision_counts[s["decision"]] = decision_counts.get(s["decision"], 0) + 1
            warn_count += s["warn_count"]
            block_count += s["block_count"]
        return {
            "session_count": len(sessions),
            "decision_counts": decision_counts,
            "warn_count": warn_count,
            "block_count": block_count,
        }

    raise ValueError(f"unknown snapshot kind: {kind!r}")


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_snapshot(snapshot: Any) -> list[str]:
    """Validate a snapshot dict; return a list of problem strings.

    An empty list means the snapshot is well-formed and its aggregate is
    self-consistent with the materialised ``sessions``.
    """
    problems: list[str] = []
    if not isinstance(snapshot, Mapping):
        return ["snapshot is not a mapping"]

    if snapshot.get("schema_version") != SCHEMA_VERSION:
        problems.append(
            f"schema_version must be {SCHEMA_VERSION!r}, "
            f"got {snapshot.get('schema_version')!r}"
        )

    kind = snapshot.get("kind")
    if kind not in (KIND_KANBAN, KIND_STANDALONE_AUDIT):
        problems.append(f"unknown kind: {kind!r}")

    for key in ("sessions", "aggregate", "warnings", "source"):
        if key not in snapshot:
            problems.append(f"missing required key: {key!r}")

    sessions = snapshot.get("sessions")
    aggregate = snapshot.get("aggregate")
    if not isinstance(sessions, list):
        problems.append("sessions must be a list")
        return problems
    if not isinstance(aggregate, Mapping):
        problems.append("aggregate must be a mapping")
        return problems
    if not isinstance(snapshot.get("warnings"), list):
        problems.append("warnings must be a list")

    if aggregate.get("session_count") != len(sessions):
        problems.append(
            f"aggregate.session_count ({aggregate.get('session_count')}) "
            f"!= len(sessions) ({len(sessions)})"
        )

    if kind == KIND_KANBAN:
        status_counts = aggregate.get("status_counts", {})
        if isinstance(status_counts, Mapping) and sum(status_counts.values()) != len(sessions):
            problems.append("aggregate.status_counts does not sum to session_count")
        run_total = sum(s.get("run_count", 0) for s in sessions if isinstance(s, Mapping))
        if aggregate.get("run_count") != run_total:
            problems.append("aggregate.run_count does not match summed run_count")
        run_status_counts = aggregate.get("run_status_counts", {})
        if isinstance(run_status_counts, Mapping) and sum(run_status_counts.values()) != run_total:
            problems.append("aggregate.run_status_counts does not sum to run_count")
        artifact_total = sum(
            s.get("artifact_count", 0) for s in sessions if isinstance(s, Mapping)
        )
        if aggregate.get("artifact_count") != artifact_total:
            problems.append("aggregate.artifact_count does not match summed artifact_count")

    elif kind == KIND_STANDALONE_AUDIT:
        decision_counts = aggregate.get("decision_counts", {})
        if isinstance(decision_counts, Mapping) and sum(decision_counts.values()) != len(sessions):
            problems.append("aggregate.decision_counts does not sum to session_count")

    return problems
