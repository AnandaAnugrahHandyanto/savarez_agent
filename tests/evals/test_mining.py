from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from evals.mining import (
    MinedCandidate,
    export_candidates_report,
    export_draft_cases,
    mine_from_session_db,
)
from evals.schemas import load_eval_case_file
from scripts import mine_eval_cases


def _make_state_db(path: Path) -> Path:
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE sessions (
            id TEXT PRIMARY KEY,
            source TEXT,
            model TEXT,
            system_prompt TEXT,
            started_at REAL,
            ended_at REAL,
            end_reason TEXT,
            tool_call_count INTEGER,
            input_tokens INTEGER,
            output_tokens INTEGER,
            billing_provider TEXT,
            estimated_cost_usd REAL,
            title TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY,
            session_id TEXT,
            role TEXT,
            content TEXT,
            tool_calls TEXT
        )
        """
    )

    conn.execute(
        """
        INSERT INTO sessions (
            id, source, model, system_prompt, started_at, ended_at, end_reason,
            tool_call_count, input_tokens, output_tokens, billing_provider,
            estimated_cost_usd, title
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "sess_1234567890abcdef",
            "cli",
            "gpt-5.4",
            "system context",
            1000.0,
            1002.5,
            "completed",
            2,
            150,
            60,
            "openai-codex",
            0.12,
            "Useful mining session",
        ),
    )

    conn.executemany(
        "INSERT INTO messages (id, session_id, role, content, tool_calls) VALUES (?, ?, ?, ?, ?)",
        [
            (1, "sess_1234567890abcdef", "user", "Research the topic and summarize it.", None),
            (
                2,
                "sess_1234567890abcdef",
                "assistant",
                "",
                json.dumps(
                    [
                        {"function": {"name": "web_search"}},
                        {"function": {"name": "web_extract"}},
                    ]
                ),
            ),
            (3, "sess_1234567890abcdef", "tool", "search results", None),
            (4, "sess_1234567890abcdef", "assistant", "Final grounded answer.", None),
        ],
    )
    conn.commit()
    conn.close()
    return path


def test_mine_from_session_db_extracts_candidate_fields(tmp_path):
    db_path = _make_state_db(tmp_path / "state.db")

    result = mine_from_session_db(db_path, source="cli", min_tool_calls=1, min_tokens=100, limit=10)

    assert result.source_name == "state-db"
    assert result.total_sessions_scanned == 1
    assert result.total_candidates == 1

    candidate = result.candidates[0]
    assert candidate.candidate_id == "mined.state.sess_1234567"
    assert candidate.session_id == "sess_1234567890abcdef"
    assert candidate.prompt == "Research the topic and summarize it."
    assert candidate.final_response == "Final grounded answer."
    assert candidate.tool_names == ["web_search", "web_extract"]
    assert candidate.tool_call_count == 2
    assert candidate.failed is False
    assert candidate.provider == "openai-codex"
    assert candidate.elapsed_ms == 2500
    assert candidate.reason == "used 2 tool(s): web_search, web_extract"


def test_export_draft_cases_writes_schema_valid_yaml(tmp_path):
    candidate = MinedCandidate(
        candidate_id="mined.state.demo_case",
        source="state-db",
        session_id="sess_demo",
        prompt="Research the product launch and summarize findings.",
        final_response="Summary ready.",
        tool_names=["web_search", "web_extract"],
        tool_call_count=2,
        failed=False,
        mined_at="2026-05-26T12:00:00Z",
        model="gpt-5.4",
        provider="openai-codex",
        title=None,
        context="system context",
        reason="used 2 tool(s): web_search, web_extract",
    )

    written = export_draft_cases([candidate], output_dir=tmp_path)

    assert len(written) == 1
    case = load_eval_case_file(written[0])
    assert case.case_id == "mined.state.demo_case"
    assert case.suite == "mined"
    assert case.task_type == "briefing"
    assert case.enabled_toolsets == ["web"]
    assert case.expected_tools == ["web_extract", "web_search"]
    assert case.context == "system context"
    assert any(assertion.kind == "non_empty_output" for assertion in case.assertions)



def test_export_candidates_report_contains_candidate_row(tmp_path):
    candidate = MinedCandidate(
        candidate_id="mined.state.demo_case",
        source="state-db",
        session_id="sess_demo_123456789",
        prompt="Prompt",
        final_response="Answer",
        tool_names=["terminal"],
        tool_call_count=1,
        failed=True,
        mined_at="2026-05-26T12:00:00Z",
        model="gpt-5.4",
        provider="openai-codex",
        reason="session ended with error",
    )

    report_path = export_candidates_report([candidate], tmp_path / "MINED_REPORT.md")

    text = report_path.read_text(encoding="utf-8")
    assert "# Mined eval case candidates" in text
    assert "mined.state.demo_case" in text
    assert "session ended with error" in text
    assert "❌" in text



def test_mine_eval_cases_main_exports_files_and_returns_zero(tmp_path):
    db_path = _make_state_db(tmp_path / "state.db")
    out_dir = tmp_path / "drafts"

    exit_code = mine_eval_cases.main(
        [
            "--source",
            "state-db",
            "--db-path",
            str(db_path),
            "--source-filter",
            "cli",
            "--min-tool-calls",
            "1",
            "--min-tokens",
            "100",
            "--limit",
            "5",
            "--output",
            str(out_dir),
        ]
    )

    assert exit_code == 0
    draft_files = sorted(out_dir.glob("draft_*.yaml"))
    assert len(draft_files) == 1
    assert (out_dir / "MINED_REPORT.md").exists()
