"""G1 (S-0429-01) — cron scheduler propagates user_id through origin.

When a cron job fires, the gateway respawn injects ``HERMES_SESSION_USER_ID``
into the agent process env so the MCP subprocess (downstream of
``_run_stdio``) can bind to the right user. This requires the scheduler to
know which user_id to inject — sourced either from ``origin.user_id`` (jobs
created post-G1) or via reverse-lookup from ``slack_channel.txt`` sidecar
files (legacy jobs).
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest


class TestResolveOriginUserIdForward:
    """New jobs persist ``origin.user_id`` directly; ``_resolve_origin``
    surfaces it unchanged."""

    def test_origin_with_user_id_is_returned(self):
        from cron.scheduler import _resolve_origin

        job = {
            "origin": {
                "platform": "slack",
                "chat_id": "D1ABC",
                "user_id": "U0AQW54L1UN",
            }
        }
        origin = _resolve_origin(job)
        assert origin is not None
        assert origin.get("user_id") == "U0AQW54L1UN"


class TestResolveOriginUserIdReverseLookup:
    """Legacy jobs lack ``origin.user_id``. Reverse-resolve via the
    per-user ``slack_channel.txt`` sidecar files written by the Slack
    gateway adapter."""

    @pytest.fixture
    def hermes_home(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        # Plant two users; only one matches the job's chat_id.
        (tmp_path / "artemis" / "U0ALICE").mkdir(parents=True)
        (tmp_path / "artemis" / "U0ALICE" / "slack_channel.txt").write_text(
            "D1ALICE"
        )
        (tmp_path / "artemis" / "U0BOB").mkdir(parents=True)
        (tmp_path / "artemis" / "U0BOB" / "slack_channel.txt").write_text("D1BOB")
        return tmp_path

    def test_legacy_job_reverse_resolves_user_id(self, hermes_home):
        from cron.scheduler import _resolve_origin

        job = {"origin": {"platform": "slack", "chat_id": "D1ALICE"}}
        origin = _resolve_origin(job)
        assert origin is not None
        assert origin.get("user_id") == "U0ALICE"

    def test_legacy_job_no_match_leaves_user_id_none(self, hermes_home):
        from cron.scheduler import _resolve_origin

        job = {"origin": {"platform": "slack", "chat_id": "D1UNKNOWN"}}
        origin = _resolve_origin(job)
        assert origin is not None
        assert origin.get("user_id") is None

    def test_explicit_user_id_wins_over_reverse_lookup(self, hermes_home):
        """When origin already has user_id, don't second-guess it via
        sidecar lookup. The persisted value is authoritative."""
        from cron.scheduler import _resolve_origin

        job = {
            "origin": {
                "platform": "slack",
                "chat_id": "D1ALICE",  # would resolve to U0ALICE via sidecar
                "user_id": "U0EXPLICIT",
            }
        }
        origin = _resolve_origin(job)
        assert origin.get("user_id") == "U0EXPLICIT"


class TestEmptyOriginUnchanged:
    """Jobs with no origin at all (script-created, no platform context)
    should keep returning None — reverse-lookup must not invent one."""

    def test_no_origin_returns_none(self):
        from cron.scheduler import _resolve_origin

        assert _resolve_origin({}) is None
        assert _resolve_origin({"origin": None}) is None


class TestUnresolvableLegacyOriginLogsError:
    """B-0504-01 followup #1: legacy origin without user_id and no matching
    sidecar means MCP layer will fail-closed downstream. Make the failure
    visible at the orchestration boundary instead of silent."""

    @pytest.fixture
    def hermes_home(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        # Empty artemis tree — no user has a sidecar file.
        (tmp_path / "artemis").mkdir(parents=True)
        return tmp_path

    def test_unresolvable_legacy_origin_logs_error(self, hermes_home, caplog):
        import logging

        from cron.scheduler import _resolve_origin

        job = {
            "id": "abc123def456",
            "origin": {"platform": "slack", "chat_id": "D1NOSIDECAR"},
        }
        with caplog.at_level(logging.ERROR, logger="cron.scheduler"):
            origin = _resolve_origin(job)

        assert origin is not None
        assert origin.get("user_id") is None
        # Caller (scheduler.py) checks origin.get("user_id") and skips env
        # injection if missing — so this log is the only signal that the
        # cron will fail-closed at MCP layer.
        assert any(
            "abc123def456" in r.message and "D1NOSIDECAR" in r.message
            for r in caplog.records
        ), f"expected ERROR mentioning job id and chat_id, got: {[r.message for r in caplog.records]}"

    def test_resolvable_legacy_origin_does_not_log(self, tmp_path, monkeypatch, caplog):
        """Sanity: when reverse-lookup succeeds, no error log fires."""
        import logging

        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        (tmp_path / "artemis" / "U0CAROL").mkdir(parents=True)
        (tmp_path / "artemis" / "U0CAROL" / "slack_channel.txt").write_text(
            "D1CAROL"
        )
        from cron.scheduler import _resolve_origin

        job = {"id": "ok123", "origin": {"platform": "slack", "chat_id": "D1CAROL"}}
        with caplog.at_level(logging.ERROR, logger="cron.scheduler"):
            origin = _resolve_origin(job)
        assert origin.get("user_id") == "U0CAROL"
        assert caplog.records == [], "no error expected on successful resolve"
