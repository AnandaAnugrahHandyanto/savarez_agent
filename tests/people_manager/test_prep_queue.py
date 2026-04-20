from datetime import datetime
from zoneinfo import ZoneInfo

from people_manager.storage import create_report



def _make_now(year, month, day, hour, minute, second=0, tz="Asia/Singapore"):
    return datetime(year, month, day, hour, minute, second, tzinfo=ZoneInfo(tz))



def _install_queue_fixture(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    from people_manager.schedule_store import save_schedule_registry
    from scripts.one_on_one_prep import main as prep_main

    create_report("Thomas Zhu", "COO", "Own operating cadence")
    save_schedule_registry(
        {
            "version": 1,
            "timezone": "Asia/Singapore",
            "profiles": {
                "thomas-zhu": {
                    "name": "Thomas Zhu",
                    "enabled": True,
                    "delivery_target": "origin",
                    "meeting": {"type": "weekly", "weekday": 1, "time": "13:15"},
                    "prep_offset_minutes": 5,
                    "template_style": "ultra_short_telegram",
                }
            },
        }
    )
    assert prep_main(["enqueue-due", "--now", "2026-04-20T13:10:00+08:00"]) == 0



def test_claim_next_for_miya_skips_event_with_active_claim_lock(tmp_path, monkeypatch):
    _install_queue_fixture(tmp_path, monkeypatch)
    from people_manager.prep_queue import acquire_transition_lock, claim_next_for_miya, load_queue_event

    dedupe_key = "thomas-zhu::2026-04-20T13:15:00+08:00"
    assert acquire_transition_lock(dedupe_key, lock_name="miya-claim", owner="test") is True

    claimed = claim_next_for_miya(now=_make_now(2026, 4, 20, 13, 10, 5))
    assert claimed is None
    assert load_queue_event(dedupe_key)["state"] == "queued_for_miya"



def test_fallback_candidates_skip_locked_occurrence(tmp_path, monkeypatch):
    _install_queue_fixture(tmp_path, monkeypatch)
    from people_manager.prep_queue import acquire_transition_lock, fallback_candidates

    dedupe_key = "thomas-zhu::2026-04-20T13:15:00+08:00"
    assert acquire_transition_lock(dedupe_key, lock_name="fallback-send", owner="test") is True

    candidates = fallback_candidates(now=_make_now(2026, 4, 20, 13, 11, 5))
    assert candidates == []
