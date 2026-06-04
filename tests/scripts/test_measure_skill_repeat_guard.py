"""Tests for marker-cohort skill repeat measurement."""

from __future__ import annotations

import importlib.util
import json
import sqlite3
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_measure_module():
    spec = importlib.util.spec_from_file_location(
        "_measure_skill_repeat_guard_under_test",
        REPO_ROOT / "scripts" / "measure_skill_repeat_guard.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _skill_call(name: str, file_path: str | None = None) -> str:
    args = {"name": name}
    if file_path is not None:
        args["file_path"] = file_path
    return json.dumps(
        [
            {
                "function": {
                    "name": "skill_view",
                    "arguments": json.dumps(args),
                }
            }
        ]
    )


def _write_fixture_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        """
        create table sessions (
            id text primary key,
            source text,
            started_at real,
            ended_at real,
            title text,
            system_prompt text
        )
        """
    )
    conn.execute(
        """
        create table messages (
            id integer primary key,
            session_id text,
            role text,
            content text,
            tool_calls text,
            timestamp real,
            active integer default 1
        )
        """
    )
    sessions = [
        ("guarded", "cli", 100.0, 120.0, "Guarded", "... skill-repeat-guard-v0 ..."),
        ("absent", "cli", 200.0, 220.0, "Absent", "plain prompt"),
        ("compressed", "cli", 300.0, 320.0, "Compressed", "plain prompt"),
    ]
    conn.executemany("insert into sessions values (?, ?, ?, ?, ?, ?)", sessions)
    messages = [
        (1, "guarded", "assistant", "", _skill_call("worldseed-phase-gate-workflow"), 101.0, 1),
        (2, "guarded", "assistant", "", _skill_call("worldseed-phase-gate-workflow"), 102.0, 1),
        (3, "guarded", "assistant", "", _skill_call("after-session-compression-handoff", "references/a.md"), 103.0, 1),
        (4, "guarded", "assistant", "", _skill_call("after-session-compression-handoff", "references/b.md"), 104.0, 1),
        (5, "absent", "assistant", "", _skill_call("test-driven-development"), 201.0, 1),
        (6, "compressed", "assistant", "", _skill_call("pre-compression-skill"), 300.0, 1),
        (7, "compressed", "user", "[CONTEXT COMPACTION — REFERENCE ONLY] previous turn", None, 301.0, 1),
        (8, "compressed", "assistant", "", _skill_call("post-compression-before-gate"), 301.5, 1),
        (9, "compressed", "user", "New phase: perform audit before commit/push hard gate", None, 302.0, 1),
        (10, "compressed", "assistant", "", _skill_call("requesting-code-review"), 303.0, 1),
        (11, "compressed", "assistant", "", _skill_call("requesting-code-review"), 304.0, 1),
    ]
    conn.executemany("insert into messages values (?, ?, ?, ?, ?, ?, ?)", messages)
    conn.commit()
    conn.close()


def test_marker_cohort_analysis_splits_guard_and_risk_cohorts(tmp_path):
    module = _load_measure_module()
    db_path = tmp_path / "state.db"
    _write_fixture_db(db_path)

    report = module.analyze_skill_repeat_guard(db_path)

    assert report["marker"] == "skill-repeat-guard-v0"
    assert report["cohorts"]["guard_present"]["session_count"] == 1
    assert report["cohorts"]["guard_absent"]["session_count"] == 2
    assert report["cohorts"]["after_compression"]["session_count"] == 1
    assert report["cohorts"]["hard_gate_or_new_phase"]["session_count"] == 1

    guarded = report["cohorts"]["guard_present"]
    assert guarded["skill_view_count"] == 4
    assert guarded["exact_repeat_count"] == 1
    assert guarded["same_skill_repeat_count"] == 2
    assert guarded["top_exact_repeats"][0]["skill"] == "worldseed-phase-gate-workflow"

    compressed = report["cohorts"]["after_compression"]
    assert compressed["skill_view_count"] == 3
    assert compressed["exact_repeat_count"] == 1

    hard_gate = report["cohorts"]["hard_gate_or_new_phase"]
    assert hard_gate["skill_view_count"] == 2
    assert hard_gate["exact_repeat_count"] == 1


def test_format_report_names_all_required_cohorts(tmp_path):
    module = _load_measure_module()
    db_path = tmp_path / "state.db"
    _write_fixture_db(db_path)

    text = module.format_report(module.analyze_skill_repeat_guard(db_path))

    assert "guard-present sessions" in text
    assert "guard-absent sessions" in text
    assert "after-compression sessions" in text
    assert "hard-gate/new-phase sessions" in text
    assert "skill-repeat-guard-v0" in text
