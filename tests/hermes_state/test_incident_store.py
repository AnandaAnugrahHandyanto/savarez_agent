"""Tests for incident store (SessionDB incident methods)."""

import json
import time

import pytest

from hermes_state import SessionDB


@pytest.fixture
def db(tmp_path):
    return SessionDB(tmp_path / "state.db")


class TestRecordIncident:
    def test_records_incident_and_returns_id(self, db):
        iid = db.record_incident("test_check", "failed", "something broke")
        assert isinstance(iid, int)
        assert iid > 0

    def test_records_with_detail_dict(self, db):
        detail = {"file": "config.yaml", "line": 42}
        iid = db.record_incident("test_check", "failed", "bad config", detail=detail)
        rows = db.get_recent_incidents(limit=5)
        assert len(rows) >= 1
        match = [r for r in rows if r["id"] == iid]
        assert len(match) == 1
        assert json.loads(match[0]["detail_json"]) == detail

    def test_records_ok_status(self, db):
        iid = db.record_incident("health", "ok", "all good")
        rows = db.get_recent_incidents(limit=5)
        match = [r for r in rows if r["id"] == iid]
        assert match[0]["status"] == "ok"


class TestGetRecentIncidents:
    def test_returns_newest_first(self, db):
        ids = []
        for i in range(5):
            ids.append(db.record_incident("chk", "failed", f"msg {i}"))
            time.sleep(0.001)
        recent = db.get_recent_incidents(limit=3)
        assert [r["message"] for r in recent] == [f"msg {4}", f"msg {3}", f"msg {2}"]

    def test_filters_by_status(self, db):
        db.record_incident("chk", "ok", "fine")
        db.record_incident("chk", "failed", "broken")
        ok_only = db.get_recent_incidents(limit=10, status_filter="ok")
        assert all(r["status"] == "ok" for r in ok_only)

    def test_empty_db_returns_empty_list(self, db):
        assert db.get_recent_incidents() == []


class TestSearchIncidents:
    def test_finds_by_message_text(self, db):
        db.record_incident("chk", "failed", "ImportError: numpy not found")
        db.record_incident("chk", "ok", "all imports resolved")
        results = db.search_incidents("ImportError", limit=5)
        assert any("ImportError" in r["message"] for r in results)

    def test_finds_by_check_name(self, db):
        db.record_incident("self_config_health", "failed", "config drift")
        db.record_incident("skills_integrity", "ok", "all good")
        results = db.search_incidents("self_config_health", limit=5)
        assert any(r["check_name"] == "self_config_health" for r in results)

    def test_empty_query_returns_empty(self, db):
        db.record_incident("chk", "failed", "some error")
        results = db.search_incidents("xyznonexistent9999", limit=5)
        assert results == []


class TestRecordFix:
    def test_records_fix_text(self, db):
        iid = db.record_incident("chk", "failed", "error")
        assert db.record_fix(iid, "restarted the service")
        rows = db.get_recent_incidents()
        match = [r for r in rows if r["id"] == iid]
        assert match[0]["fix"] == "restarted the service"

    def test_nonexistent_incident_returns_false(self, db):
        assert not db.record_fix(999999, "fix text")


class TestResolveIncident:
    def test_marks_resolved(self, db):
        iid = db.record_incident("chk", "failed", "error")
        assert db.resolve_incident(iid)
        rows = db.get_recent_incidents()
        match = [r for r in rows if r["id"] == iid]
        assert match[0]["resolved_at"] is not None

    def test_already_resolved_returns_false(self, db):
        iid = db.record_incident("chk", "failed", "error")
        db.resolve_incident(iid)
        assert not db.resolve_incident(iid)  # False — already resolved


class TestGetIncidentCounts:
    def test_groups_by_check_and_status(self, db):
        db.record_incident("chk_a", "failed", "err1")
        db.record_incident("chk_a", "failed", "err2")
        db.record_incident("chk_a", "ok", "fine")
        db.record_incident("chk_b", "failed", "err")
        counts = db.get_incident_counts()
        assert len(counts) == 3  # chk_a:failed, chk_a:ok, chk_b:failed

    def test_empty_db(self, db):
        assert db.get_incident_counts() == []


class TestGetUnresolvedIncidents:
    def test_returns_only_unresolved(self, db):
        iid1 = db.record_incident("chk", "failed", "err without fix")
        iid2 = db.record_incident("chk", "failed", "err with fix")
        db.record_fix(iid2, "fixed")
        iid3 = db.record_incident("chk", "failed", "err resolved")
        db.resolve_incident(iid3)
        unresolved = db.get_unresolved_incidents()
        ids = [r["id"] for r in unresolved]
        assert iid1 in ids
        assert iid2 not in ids  # has fix
        assert iid3 not in ids  # resolved
