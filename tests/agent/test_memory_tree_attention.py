from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _write_ledger(home: Path, records: list[dict]) -> Path:
    path = home / "data" / "active-work" / "ledger.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "schema": "hermes-active-work-ledger-v1",
                "updated_at": "2026-05-18T16:28:52+08:00",
                "records": records,
            }
        ),
        encoding="utf-8",
    )
    return path


def test_scan_attention_returns_no_items_for_clean_recent_ledger(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    now = datetime(2026, 5, 18, tzinfo=timezone.utc)
    _write_ledger(
        tmp_path,
        [
            {
                "id": "recent-active-work",
                "title": "Recent active work",
                "status": "active",
                "owner": "Hermes",
                "updated_at": (now - timedelta(hours=2)).isoformat(),
            }
        ],
    )

    from agent.memory_tree_attention import scan_attention

    assert scan_attention(now=now) == []


def test_scan_attention_surfaces_stale_active_ledger_records(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    now = datetime(2026, 5, 18, tzinfo=timezone.utc)
    _write_ledger(
        tmp_path,
        [
            {
                "id": "stale-openhuman-import",
                "title": "OpenHuman feature import",
                "status": "active",
                "owner": "Hermes",
                "updated_at": (now - timedelta(days=12)).isoformat(),
                "purpose": "Keep OpenHuman import moving.",
            }
        ],
    )

    from agent.memory_tree_attention import scan_attention

    items = scan_attention(now=now, stale_days=7)
    assert len(items) == 1
    item = items[0]
    assert item.kind == "stale_active_work"
    assert item.severity == "attention"
    assert item.title == "OpenHuman feature import"
    assert item.source_id == "stale-openhuman-import"
    assert "12d" in item.age
    assert "ledger.json" in str(item.source_path)
    assert "Review whether this is still active" in item.next_action


def test_scan_attention_surfaces_failed_cron_like_ledger_records(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    now = datetime(2026, 5, 18, tzinfo=timezone.utc)
    _write_ledger(
        tmp_path,
        [
            {
                "id": "nightly-memory-tree-lite-build",
                "title": "Nightly Memory Tree Lite build",
                "status": "active",
                "owner": "Hermes",
                "runtime": {"cron_job_id": "abc123", "last_status": "failed"},
                "verification": {"last_status": "error", "last_error": "builder traceback"},
                "updated_at": now.isoformat(),
            }
        ],
    )

    from agent.memory_tree_attention import scan_attention

    items = scan_attention(now=now)
    assert len(items) == 1
    item = items[0]
    assert item.kind == "failed_automation"
    assert item.severity == "failure"
    assert item.source_id == "nightly-memory-tree-lite-build"
    assert "abc123" in item.evidence
    assert "builder traceback" in item.evidence


def test_scan_attention_does_not_flag_failure_behavior_text_as_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    now = datetime(2026, 5, 18, tzinfo=timezone.utc)
    _write_ledger(
        tmp_path,
        [
            {
                "id": "healthy-cron",
                "title": "Healthy cron",
                "status": "active",
                "owner": "Hermes",
                "updated_at": now.isoformat(),
                "failure_behavior": "Send alerts to Discord on failure.",
                "runtime": {"cron_job_id": "ok123", "last_status": "ok"},
                "verification": {"last_status": "ok"},
            }
        ],
    )

    from agent.memory_tree_attention import scan_attention

    assert scan_attention(now=now) == []


def test_scan_attention_does_not_flag_error_trigger_text_as_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    now = datetime(2026, 5, 18, tzinfo=timezone.utc)
    _write_ledger(
        tmp_path,
        [
            {
                "id": "healthy-error-alerts",
                "title": "Healthy error alerts",
                "status": "active",
                "owner": "Hermes",
                "updated_at": now.isoformat(),
                "runtime": {
                    "cron_job_id": "ok123",
                    "last_status": "ok",
                    "trigger": "n8n Error Trigger",
                    "purpose": "Send notifications when failures happen.",
                },
                "verification": {"last_status": "ok"},
            }
        ],
    )

    from agent.memory_tree_attention import scan_attention

    assert scan_attention(now=now) == []


def test_scan_attention_does_not_flag_healthy_ok_status_with_error_context(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    now = datetime(2026, 5, 18, tzinfo=timezone.utc)
    _write_ledger(
        tmp_path,
        [
            {
                "id": "ok-with-contextual-errors",
                "title": "OK with contextual errors",
                "status": "active",
                "owner": "Hermes",
                "updated_at": now.isoformat(),
                "runtime": {"cron_job_id": "ok123", "last_status": "ok_with_personal_rclone_errors"},
                "verification": {"status": "ok_with_personal_rclone_errors"},
            }
        ],
    )

    from agent.memory_tree_attention import scan_attention

    assert scan_attention(now=now) == []


def test_scan_attention_does_not_flag_negated_failure_phrases(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    now = datetime(2026, 5, 18, tzinfo=timezone.utc)
    _write_ledger(
        tmp_path,
        [
            {
                "id": "zero-errors",
                "title": "Zero errors",
                "status": "active",
                "owner": "Hermes",
                "updated_at": now.isoformat(),
                "runtime": {"cron_job_id": "ok123", "last_status": "zero errors"},
                "verification": {"status": "without error"},
            }
        ],
    )

    from agent.memory_tree_attention import scan_attention

    assert scan_attention(now=now) == []


def test_format_attention_report_is_bounded_and_source_aware(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    now = datetime(2026, 5, 18, tzinfo=timezone.utc)
    _write_ledger(
        tmp_path,
        [
            {
                "id": "stale-work",
                "title": "Stale work",
                "status": "active",
                "owner": "Hermes",
                "updated_at": (now - timedelta(days=30)).isoformat(),
                "purpose": "x" * 1000,
            }
        ],
    )

    from agent.memory_tree_attention import format_attention_report, scan_attention

    report = format_attention_report(scan_attention(now=now), max_chars=420)
    assert report.startswith("Memory Tree attention")
    assert "stale_active_work" in report
    assert "source:" in report
    assert "next:" in report
    assert len(report) <= 420
    assert report.rstrip().endswith("chars]")


def test_format_attention_json_is_bounded_and_source_rich(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    now = datetime(2026, 5, 18, tzinfo=timezone.utc)
    _write_ledger(
        tmp_path,
        [
            {
                "id": "stale-json-record",
                "title": "Stale JSON record",
                "status": "active",
                "owner": "Hermes",
                "updated_at": (now - timedelta(days=12)).isoformat(),
                "source_of_truth": "Hermes cron job stale123",
                "purpose": "x" * 1000,
            }
        ],
    )

    from agent.memory_tree_attention import format_attention_json, scan_attention

    payload = json.loads(format_attention_json(scan_attention(now=now), max_chars=520))
    assert payload["schema"] == "memory-tree-attention-v1"
    assert payload["truncated"] is True
    assert payload["total_items"] == 1
    assert payload["items"][0]["source_id"] == "stale-json-record"
    assert payload["items"][0]["source_path"].endswith("ledger.json")
    assert len(json.dumps(payload)) <= 520


def test_scan_attention_flags_missing_source_of_truth_before_unknown_age(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    now = datetime(2026, 5, 18, tzinfo=timezone.utc)
    _write_ledger(
        tmp_path,
        [
            {
                "id": "source-free-active",
                "title": "Source-free active automation",
                "status": "active",
                "owner": "Hermes",
            }
        ],
    )

    from agent.memory_tree_attention import scan_attention

    items = scan_attention(now=now)
    assert len(items) == 1
    assert items[0].kind == "missing_source_of_truth"
    assert items[0].source_id == "source-free-active"
    assert "source_of_truth" in items[0].evidence
