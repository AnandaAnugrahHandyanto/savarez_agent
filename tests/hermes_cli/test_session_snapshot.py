"""Tests for the pure ``hermes.session_snapshot.v1`` adapter.

Covers Kanban snapshots (running / completed / blocked runs, metadata and
artifact handling, invalid-metadata degradation, unknown statuses, aggregate
count consistency), the mutation-safety invariant (snapshot generation does
not change row counts), and the standalone-audit snapshot incl. the stale
source-of-truth warning mapping.

Run from the Hermes Agent repo root:

    python -m pytest tests/hermes_cli/test_session_snapshot.py -q -o 'addopts='
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from hermes_cli import kanban_db as kb
from hermes_cli import session_snapshot as ss


# ---------------------------------------------------------------------------
# Fixtures / raw insert helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def conn(tmp_path):
    """An initialised, isolated Kanban DB connection."""
    db_path = tmp_path / "kanban.db"
    kb.init_db(db_path=db_path)
    c = kb.connect(db_path=db_path)
    try:
        yield c
    finally:
        c.close()


def _insert_task(conn: sqlite3.Connection, task_id: str, *, status: str, **kw) -> None:
    cols = {
        "id": task_id,
        "title": kw.get("title", f"task {task_id}"),
        "status": status,
        "assignee": kw.get("assignee"),
        "priority": kw.get("priority", 0),
        "created_by": kw.get("created_by"),
        "created_at": kw.get("created_at", 1000),
        "started_at": kw.get("started_at"),
        "completed_at": kw.get("completed_at"),
        "workspace_kind": kw.get("workspace_kind", "scratch"),
        "tenant": kw.get("tenant"),
        "session_id": kw.get("session_id"),
        "current_run_id": kw.get("current_run_id"),
    }
    placeholders = ", ".join("?" for _ in cols)
    conn.execute(
        f"INSERT INTO tasks ({', '.join(cols)}) VALUES ({placeholders})",
        list(cols.values()),
    )
    conn.commit()


def _insert_run(
    conn: sqlite3.Connection,
    *,
    task_id: str,
    status: str,
    outcome=None,
    summary=None,
    metadata=None,
    profile="gond-cc",
    started_at=1000,
    ended_at=None,
    error=None,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO task_runs
            (task_id, profile, status, started_at, ended_at, outcome, summary, metadata, error)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (task_id, profile, status, started_at, ended_at, outcome, summary, metadata, error),
    )
    conn.commit()
    return int(cur.lastrowid)


def _insert_event(conn: sqlite3.Connection, *, task_id: str, kind: str, run_id=None) -> None:
    conn.execute(
        "INSERT INTO task_events (task_id, run_id, kind, payload, created_at) VALUES (?, ?, ?, ?, ?)",
        (task_id, run_id, kind, None, 1000),
    )
    conn.commit()


def _row_count(conn: sqlite3.Connection, table: str) -> int:
    return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


# ---------------------------------------------------------------------------
# Schema / version
# ---------------------------------------------------------------------------

def test_schema_version_constant():
    assert ss.SCHEMA_VERSION == "hermes.session_snapshot.v1"


def test_empty_kanban_snapshot_is_valid(conn):
    snap = ss.build_kanban_snapshot(conn)
    assert snap["schema_version"] == ss.SCHEMA_VERSION
    assert snap["kind"] == "kanban"
    assert snap["sessions"] == []
    assert snap["aggregate"]["session_count"] == 0
    assert ss.validate_snapshot(snap) == []


# ---------------------------------------------------------------------------
# Running / completed / blocked
# ---------------------------------------------------------------------------

def test_running_completed_blocked_runs(conn):
    # Running task with an open run.
    _insert_task(conn, "t_run", status="running", current_run_id=None)
    rid = _insert_run(conn, task_id="t_run", status="running", started_at=1000, ended_at=None)
    conn.execute("UPDATE tasks SET current_run_id = ? WHERE id = ?", (rid, "t_run"))
    conn.commit()

    # Completed task.
    _insert_task(conn, "t_done", status="done", completed_at=2000)
    _insert_run(
        conn, task_id="t_done", status="done", outcome="completed",
        summary="all good", started_at=1000, ended_at=1900,
    )

    # Blocked task.
    _insert_task(conn, "t_blk", status="blocked")
    _insert_run(
        conn, task_id="t_blk", status="blocked", outcome="blocked",
        summary="need approval", started_at=1000, ended_at=1500,
    )

    snap = ss.build_kanban_snapshot(conn)
    assert ss.validate_snapshot(snap) == []

    by_id = {s["task_id"]: s for s in snap["sessions"]}
    assert by_id["t_run"]["status"] == "running"
    assert by_id["t_run"]["latest_run"]["status"] == "running"
    assert by_id["t_run"]["latest_run"]["ended_at"] is None
    assert by_id["t_run"]["current_run_id"] == rid

    assert by_id["t_done"]["status"] == "done"
    assert by_id["t_done"]["latest_run"]["outcome"] == "completed"
    assert by_id["t_done"]["completed_at"] == 2000

    assert by_id["t_blk"]["status"] == "blocked"
    assert by_id["t_blk"]["latest_run"]["outcome"] == "blocked"

    assert snap["aggregate"]["run_status_counts"] == {
        "running": 1, "done": 1, "blocked": 1,
    }


def test_single_task_filter(conn):
    _insert_task(conn, "t_a", status="running")
    _insert_task(conn, "t_b", status="done")
    snap = ss.build_kanban_snapshot(conn, task_id="t_a")
    assert [s["task_id"] for s in snap["sessions"]] == ["t_a"]
    assert snap["source"]["task_id"] == "t_a"


def test_missing_task_filter_warns(conn):
    snap = ss.build_kanban_snapshot(conn, task_id="t_nope")
    assert snap["sessions"] == []
    assert any(w["code"] == "task_not_found" for w in snap["warnings"])
    assert ss.validate_snapshot(snap) == []


def test_assignee_filter(conn):
    _insert_task(conn, "t_a", status="running", assignee="gond-cc")
    _insert_task(conn, "t_b", status="running", assignee="mystra")
    snap = ss.build_kanban_snapshot(conn, assignee="gond-cc")
    assert [s["task_id"] for s in snap["sessions"]] == ["t_a"]


# ---------------------------------------------------------------------------
# Metadata / artifact handling
# ---------------------------------------------------------------------------

def test_artifact_and_metadata_extraction(conn):
    _insert_task(conn, "t_art", status="done")
    meta = {
        "artifacts": ["/tmp/a.md", "/tmp/b.json"],
        "changed_files": ["/tmp/a.md"],
        "decision": "ADOPT",
    }
    _insert_run(
        conn, task_id="t_art", status="done", outcome="completed",
        metadata=json.dumps(meta),
    )
    snap = ss.build_kanban_snapshot(conn)
    sess = snap["sessions"][0]
    run = sess["runs"][0]
    assert run["metadata_ok"] is True
    assert run["artifacts"] == ["/tmp/a.md", "/tmp/b.json"]
    assert run["changed_files"] == ["/tmp/a.md"]
    assert run["artifact_count"] == 2
    assert sess["artifact_count"] == 2
    assert snap["aggregate"]["artifact_count"] == 2
    assert ss.validate_snapshot(snap) == []


def test_no_metadata_is_not_an_error(conn):
    _insert_task(conn, "t_nm", status="done")
    _insert_run(conn, task_id="t_nm", status="done", metadata=None)
    snap = ss.build_kanban_snapshot(conn)
    run = snap["sessions"][0]["runs"][0]
    assert run["metadata_ok"] is True
    assert run["artifacts"] == []
    assert not snap["warnings"]


def test_invalid_metadata_json_degrades(conn):
    # Unparseable JSON -> kanban_db decodes to None -> no warning, empty artifacts.
    _insert_task(conn, "t_badjson", status="done")
    _insert_run(conn, task_id="t_badjson", status="done", metadata="{not valid json")
    snap = ss.build_kanban_snapshot(conn)
    run = snap["sessions"][0]["runs"][0]
    assert run["artifacts"] == []
    assert ss.validate_snapshot(snap) == []


def test_non_object_metadata_degrades_with_warning(conn):
    # Valid JSON but not an object (a list) -> degrade + warn.
    _insert_task(conn, "t_list", status="done")
    _insert_run(conn, task_id="t_list", status="done", metadata=json.dumps([1, 2, 3]))
    snap = ss.build_kanban_snapshot(conn)
    run = snap["sessions"][0]["runs"][0]
    assert run["metadata_ok"] is False
    assert run["artifacts"] == []
    assert any(w["code"] == "invalid_run_metadata" for w in snap["warnings"])
    assert ss.validate_snapshot(snap) == []


def test_invalid_artifacts_field_degrades(conn):
    _insert_task(conn, "t_badart", status="done")
    meta = {"artifacts": "not-a-list"}
    _insert_run(conn, task_id="t_badart", status="done", metadata=json.dumps(meta))
    snap = ss.build_kanban_snapshot(conn)
    run = snap["sessions"][0]["runs"][0]
    assert run["metadata_ok"] is False
    assert run["artifacts"] == []
    assert any(w["code"] == "invalid_artifacts" for w in snap["warnings"])


def test_partially_invalid_artifact_list_keeps_valid_entries(conn):
    _insert_task(conn, "t_mix", status="done")
    meta = {"artifacts": ["/tmp/ok.md", "", 42, None]}
    _insert_run(conn, task_id="t_mix", status="done", metadata=json.dumps(meta))
    snap = ss.build_kanban_snapshot(conn)
    run = snap["sessions"][0]["runs"][0]
    assert run["artifacts"] == ["/tmp/ok.md"]
    assert run["metadata_ok"] is False
    assert any(w["code"] == "invalid_artifacts" for w in snap["warnings"])


# ---------------------------------------------------------------------------
# Unknown statuses
# ---------------------------------------------------------------------------

def test_unknown_task_status_bucketed(conn):
    _insert_task(conn, "t_weird", status="frobnicated")
    snap = ss.build_kanban_snapshot(conn)
    sess = snap["sessions"][0]
    assert sess["status"] == "unknown"
    assert sess["raw_status"] == "frobnicated"
    assert sess["status_known"] is False
    assert snap["aggregate"]["unknown_status_count"] == 1
    assert snap["aggregate"]["status_counts"].get("unknown") == 1
    assert any(w["code"] == "unknown_task_status" for w in snap["warnings"])
    assert ss.validate_snapshot(snap) == []


# ---------------------------------------------------------------------------
# Aggregate count consistency
# ---------------------------------------------------------------------------

def test_aggregate_count_consistency(conn):
    _insert_task(conn, "t1", status="running")
    _insert_run(conn, task_id="t1", status="running")
    _insert_task(conn, "t2", status="done")
    _insert_run(conn, task_id="t2", status="done", metadata=json.dumps({"artifacts": ["x"]}))
    _insert_run(conn, task_id="t2", status="crashed")  # a retry
    _insert_task(conn, "t3", status="blocked")
    _insert_event(conn, task_id="t1", kind="started")
    _insert_event(conn, task_id="t2", kind="completed")

    snap = ss.build_kanban_snapshot(conn)
    agg = snap["aggregate"]
    assert agg["session_count"] == 3
    assert sum(agg["status_counts"].values()) == 3
    assert agg["run_count"] == 3
    assert sum(agg["run_status_counts"].values()) == 3
    assert agg["artifact_count"] == 1
    assert agg["event_count"] == 2
    assert ss.validate_snapshot(snap) == []


def test_validator_detects_inconsistent_aggregate(conn):
    _insert_task(conn, "t1", status="running")
    snap = ss.build_kanban_snapshot(conn)
    snap["aggregate"]["session_count"] = 99
    problems = ss.validate_snapshot(snap)
    assert any("session_count" in p for p in problems)


def test_validator_rejects_bad_schema_version():
    snap = {
        "schema_version": "wrong",
        "kind": "kanban",
        "sessions": [],
        "aggregate": {"session_count": 0, "status_counts": {}, "run_count": 0,
                      "run_status_counts": {}, "artifact_count": 0},
        "warnings": [],
        "source": {},
    }
    problems = ss.validate_snapshot(snap)
    assert any("schema_version" in p for p in problems)


# ---------------------------------------------------------------------------
# Mutation safety
# ---------------------------------------------------------------------------

def test_snapshot_generation_does_not_mutate_counts(conn):
    _insert_task(conn, "t1", status="running")
    rid = _insert_run(conn, task_id="t1", status="running")
    _insert_event(conn, task_id="t1", kind="started", run_id=rid)
    _insert_task(conn, "t2", status="done")
    _insert_run(conn, task_id="t2", status="done", metadata=json.dumps({"artifacts": ["a"]}))
    _insert_task(conn, "t_weird", status="bogus_status")

    before = {t: _row_count(conn, t) for t in ("tasks", "task_runs", "task_events")}
    snap = ss.build_kanban_snapshot(conn)
    ss.build_kanban_snapshot(conn, task_id="t1")
    after = {t: _row_count(conn, t) for t in ("tasks", "task_runs", "task_events")}

    assert before == after
    assert ss.validate_snapshot(snap) == []


# ---------------------------------------------------------------------------
# Standalone audit snapshot
# ---------------------------------------------------------------------------

_AUDIT_SAMPLE = [
    {
        "ts": "2026-05-28T08:00:00Z",
        "actor": "waukeen.risk_check.sandbox",
        "decision": "PASS",
        "gate": "research_only",
        "rule_results": [{"rule": "all", "status": "pass", "detail": "all checks passed"}],
        "policy_version": 1,
    },
    {
        "ts": "2026-05-28T09:15:00Z",
        "actor": "waukeen.risk_check.sandbox",
        "decision": "PASS_WITH_WARNINGS",
        "gate": "paper_trade",
        "rule_results": [
            {"rule": "max_daily_turnover_pct", "status": "warn",
             "detail": "turnover=11.20% > cap=10.00%"},
        ],
        "policy_version": 1,
    },
    {
        "ts": "2026-05-28T10:42:00Z",
        "actor": "waukeen.risk_check.sandbox",
        "decision": "BLOCK",
        "gate": "paper_trade",
        "rule_results": [
            {"rule": "forbidden_instrument", "status": "block", "detail": "XLEV.MI forbidden."},
            {"rule": "max_single_order_notional_czk", "status": "block", "detail": "over cap"},
        ],
        "policy_version": 1,
    },
]


def test_standalone_audit_decision_mapping():
    snap = ss.build_standalone_audit_snapshot(_AUDIT_SAMPLE, source="audit.jsonl")
    assert snap["schema_version"] == ss.SCHEMA_VERSION
    assert snap["kind"] == "standalone_audit"
    decisions = [s["decision"] for s in snap["sessions"]]
    assert decisions == ["pass", "pass_with_warnings", "block"]
    agg = snap["aggregate"]
    assert agg["decision_counts"] == {"pass": 1, "pass_with_warnings": 1, "block": 1}
    assert agg["warn_count"] == 1
    assert agg["block_count"] == 2
    assert ss.validate_snapshot(snap) == []


def test_standalone_audit_warn_rules_mapped_to_warnings():
    snap = ss.build_standalone_audit_snapshot(_AUDIT_SAMPLE)
    warn_codes = [w["code"] for w in snap["warnings"]]
    assert "audit_warn" in warn_codes
    audit_warn = next(w for w in snap["warnings"] if w["code"] == "audit_warn")
    assert audit_warn["rule"] == "max_daily_turnover_pct"
    assert audit_warn["gate"] == "paper_trade"


def test_standalone_unknown_decision_degrades():
    snap = ss.build_standalone_audit_snapshot([{"decision": "MAYBE", "rule_results": []}])
    assert snap["sessions"][0]["decision"] == "unknown"
    assert any(w["code"] == "unknown_audit_decision" for w in snap["warnings"])
    assert ss.validate_snapshot(snap) == []


def test_standalone_stale_sot_explicit_flag():
    snap = ss.build_standalone_audit_snapshot(_AUDIT_SAMPLE, source="audit.jsonl", sot_stale=True)
    stale = [w for w in snap["warnings"] if w["code"] == "stale_sot"]
    assert len(stale) == 1
    assert stale[0]["severity"] == "warn"
    assert snap["aggregate"]["stale_sot"] is True


def test_standalone_stale_sot_age_threshold():
    snap = ss.build_standalone_audit_snapshot(
        _AUDIT_SAMPLE, sot_age_seconds=7200, sot_stale_threshold_seconds=3600,
    )
    assert any(w["code"] == "stale_sot" for w in snap["warnings"])
    assert snap["aggregate"]["stale_sot"] is True


def test_standalone_fresh_sot_no_warning():
    snap = ss.build_standalone_audit_snapshot(
        _AUDIT_SAMPLE, sot_age_seconds=60, sot_stale_threshold_seconds=3600,
    )
    assert not any(w["code"] == "stale_sot" for w in snap["warnings"])
    assert snap["aggregate"]["stale_sot"] is False


def test_load_audit_log_skips_malformed(tmp_path):
    p = tmp_path / "audit.jsonl"
    lines = [
        json.dumps(_AUDIT_SAMPLE[0]),
        "",  # blank, skipped silently
        "{not json",  # malformed -> counted
        json.dumps([1, 2, 3]),  # non-object -> counted
        json.dumps(_AUDIT_SAMPLE[2]),
    ]
    p.write_text("\n".join(lines), encoding="utf-8")
    entries, skipped = ss.load_audit_log(str(p))
    assert len(entries) == 2
    assert skipped == 2
    snap = ss.build_standalone_audit_snapshot(entries, source=str(p), skipped_entries=skipped)
    assert any(w["code"] == "skipped_audit_lines" and w["count"] == 2 for w in snap["warnings"])
    assert snap["aggregate"]["decision_counts"] == {"pass": 1, "block": 1}
    assert ss.validate_snapshot(snap) == []


def test_load_audit_log_from_repo_fixture(tmp_path):
    """Exercise loading a copied real-world sample if one is reachable.

    The standalone audit fixture lives outside the repo; copy it into the
    test's tmp dir when present, else fall back to a synthesised file so the
    test is hermetic.
    """
    sample = Path(
        "/home/filip/spearhead-execution/20260528-batch6-gang/"
        "results/waukeen_sandbox/audit_log.sample.jsonl"
    )
    dest = tmp_path / "copied_audit.jsonl"
    if sample.exists():
        dest.write_text(sample.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        dest.write_text("\n".join(json.dumps(e) for e in _AUDIT_SAMPLE), encoding="utf-8")

    entries, skipped = ss.load_audit_log(str(dest))
    assert skipped == 0
    assert len(entries) >= 3
    snap = ss.build_standalone_audit_snapshot(entries, source=str(dest))
    assert ss.validate_snapshot(snap) == []
    assert snap["aggregate"]["session_count"] == len(entries)
