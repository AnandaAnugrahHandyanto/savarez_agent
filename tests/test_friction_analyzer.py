"""Tests for the Session Friction Analyzer."""

import json
import os
import tempfile
import time
import pytest

from agent.friction_analyzer import FrictionAnalyzer, FrictionReport, FRICTION_PATTERNS


def make_session(session_id: str, texts: list[str]) -> dict:
    """Helper to build a minimal session dict."""
    return {
        "id": session_id,
        "started_at": time.time(),
        "messages": [{"content": t, "role": "assistant"} for t in texts],
    }


class TestFrictionPatternDetection:

    def test_error_loop_detected(self):
        analyzer = FrictionAnalyzer()
        session = make_session("s1", [
            "Error: connection refused",
            "Error: connection refused",
            "Error: connection refused",
        ])
        events = analyzer._analyze_session(session)
        cats = [e.category for e in events]
        assert "error_loop" in cats

    def test_error_loop_not_triggered_below_threshold(self):
        analyzer = FrictionAnalyzer()
        session = make_session("s2", [
            "Error: something went wrong",
            "Fixed successfully",
        ])
        events = analyzer._analyze_session(session)
        cats = [e.category for e in events]
        assert "error_loop" not in cats

    def test_api_credential_failure_detected(self):
        analyzer = FrictionAnalyzer()
        session = make_session("s3", ["HTTP 401 Unauthorized — invalid API key"])
        events = analyzer._analyze_session(session)
        cats = [e.category for e in events]
        assert "api_credential_failure" in cats

    def test_infrastructure_broken_detected(self):
        analyzer = FrictionAnalyzer()
        session = make_session("s4", ["No such file or directory: /usr/local/bin/tool"])
        events = analyzer._analyze_session(session)
        cats = [e.category for e in events]
        assert "infrastructure_broken" in cats

    def test_memory_dropout_detected(self):
        analyzer = FrictionAnalyzer()
        session = make_session("s5", ["Didn't you know I already told you this?"])
        events = analyzer._analyze_session(session)
        cats = [e.category for e in events]
        assert "memory_dropout" in cats

    def test_clean_session_no_events(self):
        analyzer = FrictionAnalyzer()
        session = make_session("s6", [
            "Sure, let me help with that.",
            "Done! The file has been created.",
            "Everything looks good.",
        ])
        events = analyzer._analyze_session(session)
        # Should have no or minimal events (premature_declaration might fire
        # for "done" but error_loop/credentials/infra should not)
        critical = [e for e in events if e.category in
                    ("error_loop", "api_credential_failure", "infrastructure_broken", "memory_dropout")]
        assert len(critical) == 0


class TestFrictionReport:

    def test_full_analyze_returns_report(self):
        analyzer = FrictionAnalyzer()
        # No DB or sessions dir — should return empty report gracefully
        report = analyzer.analyze(days=7)
        assert isinstance(report, FrictionReport)
        assert report.sessions_scanned == 0
        assert report.total_friction_score == 0

    def test_format_clean_report(self):
        analyzer = FrictionAnalyzer()
        report = FrictionReport(
            days_analyzed=7,
            sessions_scanned=5,
            total_friction_score=0,
        )
        output = analyzer.format_report(report)
        assert "Clean" in output or "no significant" in output.lower()

    def test_format_report_with_events(self):
        from agent.friction_analyzer import FrictionEvent
        analyzer = FrictionAnalyzer()
        report = FrictionReport(
            days_analyzed=7,
            sessions_scanned=10,
            total_friction_score=15,
            category_counts={"api_credential_failure": 3, "error_loop": 2},
            category_weights={"api_credential_failure": 12, "error_loop": 6},
        )
        output = analyzer.format_report(report)
        assert "api_credential_failure" in output
        assert "error_loop" in output


class TestRuleGeneration:

    def test_generates_credential_rule(self):
        analyzer = FrictionAnalyzer()
        report = FrictionReport(
            days_analyzed=7,
            sessions_scanned=5,
            total_friction_score=8,
            category_counts={"api_credential_failure": 3},
            category_weights={"api_credential_failure": 12},
        )
        rules = analyzer.generate_rules(report)
        assert any("api-credential-failure" in r for r in rules)

    def test_generates_infra_rule(self):
        analyzer = FrictionAnalyzer()
        report = FrictionReport(
            days_analyzed=7,
            sessions_scanned=5,
            total_friction_score=6,
            category_counts={"infrastructure_broken": 2},
            category_weights={"infrastructure_broken": 6},
        )
        rules = analyzer.generate_rules(report)
        assert any("infrastructure-broken" in r for r in rules)

    def test_no_rules_for_clean_session(self):
        analyzer = FrictionAnalyzer()
        report = FrictionReport(
            days_analyzed=7,
            sessions_scanned=5,
            total_friction_score=0,
            category_counts={},
        )
        rules = analyzer.generate_rules(report)
        assert len(rules) == 0


class TestJSONLSessionLoading:

    def test_loads_jsonl_sessions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Write a sample session file
            session_file = os.path.join(tmpdir, "session_001.jsonl")
            with open(session_file, "w") as f:
                f.write(json.dumps({"content": "Error: connection refused", "role": "assistant"}) + "\n")
                f.write(json.dumps({"content": "Error: connection refused", "role": "assistant"}) + "\n")
                f.write(json.dumps({"content": "Error: connection refused", "role": "assistant"}) + "\n")

            from datetime import datetime, timezone
            analyzer = FrictionAnalyzer(sessions_dir=tmpdir)
            sessions = analyzer._load_from_jsonl(
                datetime(2020, 1, 1, tzinfo=timezone.utc)  # old cutoff = include all
            )
            assert len(sessions) == 1
            assert len(sessions[0]["messages"]) == 3
