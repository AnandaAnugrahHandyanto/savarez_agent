"""Tests for cron/delivery_registry.py — persistent message_id → job_name map."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def isolated_registry(tmp_path, monkeypatch):
    """Point the registry at a fresh tmp_path-backed file for each test."""
    fake_home = tmp_path / "hermes_home"
    fake_home.mkdir()

    # Reset the cached path so the test gets a fresh file location.
    import cron.delivery_registry as dr

    monkeypatch.setattr("cron.delivery_registry.get_hermes_home", lambda: fake_home)
    monkeypatch.setattr(dr, "_path_cache", None)

    yield fake_home / "cron" / "deliveries.jsonl"

    # Reset cache after the test so the next test starts clean.
    monkeypatch.setattr(dr, "_path_cache", None)


class TestRegisterAndLookup:
    def test_register_then_lookup_roundtrip(self, isolated_registry):
        from cron.delivery_registry import register, lookup

        register("discord", "chan1", ["msg1", "msg2", "msg3"], "mail-triage")

        assert lookup("discord", "chan1", "msg1") == "mail-triage"
        assert lookup("discord", "chan1", "msg2") == "mail-triage"
        assert lookup("discord", "chan1", "msg3") == "mail-triage"

    def test_lookup_returns_none_for_unknown_message(self, isolated_registry):
        from cron.delivery_registry import register, lookup

        register("discord", "chan1", ["msg1"], "mail-triage")
        assert lookup("discord", "chan1", "msg999") is None

    def test_lookup_respects_platform_and_chat_id(self, isolated_registry):
        from cron.delivery_registry import register, lookup

        register("discord", "chan1", ["msg1"], "job-a")
        # Same message_id under a different chat_id must NOT cross-match.
        assert lookup("discord", "chan2", "msg1") is None
        assert lookup("telegram", "chan1", "msg1") is None
        assert lookup("discord", "chan1", "msg1") == "job-a"

    def test_register_no_op_for_empty_inputs(self, isolated_registry):
        from cron.delivery_registry import register, lookup

        register("", "chan1", ["msg1"], "")
        register("discord", "", ["msg1"], "job")
        register("discord", "chan1", [], "job")
        register("discord", "chan1", [""], "job")
        assert lookup("discord", "chan1", "msg1") is None

    def test_newest_entry_wins_when_message_id_reused(self, isolated_registry):
        from cron.delivery_registry import register, lookup

        register("discord", "chan1", ["msg1"], "old-job")
        register("discord", "chan1", ["msg1"], "new-job")
        assert lookup("discord", "chan1", "msg1") == "new-job"


class TestPersistence:
    def test_survives_module_reset(self, isolated_registry, monkeypatch):
        """A second import (simulating a process restart) sees prior writes."""
        import cron.delivery_registry as dr

        dr.register("discord", "chan1", ["msg1"], "mail-triage")

        # Simulate restart: clear the path cache and re-resolve.
        monkeypatch.setattr(dr, "_path_cache", None)

        from cron.delivery_registry import lookup as fresh_lookup
        assert fresh_lookup("discord", "chan1", "msg1") == "mail-triage"

    def test_writes_jsonl_format(self, isolated_registry):
        from cron.delivery_registry import register

        register("discord", "chan1", ["msg1", "msg2"], "mail-triage")

        assert isolated_registry.exists()
        lines = isolated_registry.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2
        for line in lines:
            entry = json.loads(line)
            assert entry["platform"] == "discord"
            assert entry["chat_id"] == "chan1"
            assert entry["job_name"] == "mail-triage"
            assert entry["message_id"] in ("msg1", "msg2")


class TestTruncation:
    def test_truncate_keeps_recent_entries(self, isolated_registry, monkeypatch):
        import cron.delivery_registry as dr

        # Lower the thresholds so the test runs in milliseconds.
        monkeypatch.setattr(dr, "_MAX_ENTRIES", 10)
        monkeypatch.setattr(dr, "_TRUNCATE_TRIGGER", 15)

        for i in range(20):
            dr.register("discord", "chan1", [f"msg{i}"], f"job-{i}")

        # Oldest entries should have been pruned.
        assert dr.lookup("discord", "chan1", "msg0") is None
        assert dr.lookup("discord", "chan1", "msg5") is None
        # Most recent should still be present.
        assert dr.lookup("discord", "chan1", "msg19") == "job-19"
        assert dr.lookup("discord", "chan1", "msg15") == "job-15"

    def test_corrupt_lines_are_skipped(self, isolated_registry):
        from cron.delivery_registry import register, lookup

        register("discord", "chan1", ["msg1"], "job-a")

        # Inject a corrupt line between valid entries.
        with open(isolated_registry, "a", encoding="utf-8") as f:
            f.write("not valid json\n")

        register("discord", "chan1", ["msg2"], "job-b")

        assert lookup("discord", "chan1", "msg1") == "job-a"
        assert lookup("discord", "chan1", "msg2") == "job-b"
