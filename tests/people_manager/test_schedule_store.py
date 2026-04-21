from datetime import datetime
from zoneinfo import ZoneInfo

from people_manager.storage import create_report



def _make_now(year, month, day, hour, minute, tz="Asia/Singapore"):
    return datetime(year, month, day, hour, minute, tzinfo=ZoneInfo(tz))



def test_weekly_next_occurrence_same_day_future_time(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))

    from people_manager.schedule_store import next_meeting_occurrence

    meeting = {"type": "weekly", "weekday": 1, "time": "13:15"}
    now = _make_now(2026, 4, 20, 13, 0)  # Monday

    actual = next_meeting_occurrence(meeting, now=now, timezone_name="Asia/Singapore")

    assert actual.isoformat() == "2026-04-20T13:15:00+08:00"



def test_biweekly_uses_anchor_date_parity(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))

    from people_manager.schedule_store import next_meeting_occurrence

    meeting = {
        "type": "biweekly",
        "weekday": 1,
        "time": "17:00",
        "anchor_date": "2026-04-06",
    }
    now = _make_now(2026, 4, 13, 9, 0)  # off week Monday

    actual = next_meeting_occurrence(meeting, now=now, timezone_name="Asia/Singapore")

    assert actual.isoformat() == "2026-04-20T17:00:00+08:00"



def test_monthly_nth_weekday_computes_third_tuesday(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))

    from people_manager.schedule_store import next_meeting_occurrence

    meeting = {"type": "monthly_nth_weekday", "weekday": 2, "ordinal": 3, "time": "09:15"}
    now = _make_now(2026, 4, 1, 8, 0)

    actual = next_meeting_occurrence(meeting, now=now, timezone_name="Asia/Singapore")

    assert actual.isoformat() == "2026-04-21T09:15:00+08:00"



def test_due_reminders_match_same_minute_and_skip_disabled_profiles(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))

    from people_manager.schedule_store import due_reminders, save_schedule_registry

    create_report("Thomas Zhu", "COO", "Own operating cadence")
    create_report("Fiona Cao", "Chief of Staff", "Own follow-through")
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
                },
                "fiona-cao": {
                    "name": "Fiona Cao",
                    "enabled": False,
                    "delivery_target": "origin",
                    "meeting": {"type": "weekly", "weekday": 1, "time": "13:15"},
                    "prep_offset_minutes": 5,
                    "template_style": "ultra_short_telegram",
                },
            },
        }
    )

    due_at = _make_now(2026, 4, 20, 13, 10)
    due = due_reminders(now=due_at)

    assert len(due) == 1
    assert due[0]["profile_slug"] == "thomas-zhu"
    assert due[0]["meeting_at"].isoformat() == "2026-04-20T13:15:00+08:00"


def test_due_reminders_skip_malformed_schedule_entries(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))

    from people_manager.schedule_store import due_reminders, save_schedule_registry

    create_report("Thomas Zhu", "COO", "Own operating cadence")
    create_report("Broken Profile", "Ops", "Broken cadence")
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
                },
                "broken-profile": {
                    "name": "Broken Profile",
                    "enabled": True,
                    "delivery_target": "origin",
                    "meeting": {"type": "monthly_nth_weekday", "weekday": 2, "ordinal": 6, "time": "13:15"},
                    "prep_offset_minutes": 5,
                    "template_style": "ultra_short_telegram",
                },
            },
        }
    )

    due = due_reminders(now=_make_now(2026, 4, 20, 13, 10))

    assert [entry["profile_slug"] for entry in due] == ["thomas-zhu"]



def test_due_reminders_prefers_active_reschedule_override_and_reports_base_occurrence(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))

    from people_manager.schedule_store import due_reminders, save_schedule_registry

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
                    "overrides": [
                        {
                            "override_id": "ovr_1",
                            "kind": "reschedule_once",
                            "original_meeting_at": "2026-04-20T13:15:00+08:00",
                            "effective_meeting_at": "2026-04-21T14:45:00+08:00",
                            "status": "active",
                            "created_at": "2026-04-20T11:00:00+08:00",
                            "source": {"message_text": "Thomas 1:1 rescheduled (one-off) to tomorrow 2:45pm"},
                        }
                    ],
                }
            },
        }
    )

    due = due_reminders(now=_make_now(2026, 4, 21, 14, 40))

    assert len(due) == 1
    assert due[0]["meeting_at"].isoformat() == "2026-04-21T14:45:00+08:00"
    assert due[0]["prep_at"].isoformat() == "2026-04-21T14:40:00+08:00"
    assert due[0]["base_meeting_at"].isoformat() == "2026-04-20T13:15:00+08:00"
    assert due[0]["base_prep_at"].isoformat() == "2026-04-20T13:10:00+08:00"
    assert due[0]["override"]["override_id"] == "ovr_1"
