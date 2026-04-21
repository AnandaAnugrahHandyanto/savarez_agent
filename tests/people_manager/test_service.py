from datetime import datetime
from zoneinfo import ZoneInfo

from people_manager.service import handle_people_message


def test_handle_people_message_creates_and_rejects_duplicate_report(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))

    created = handle_people_message(
        "New report: Alice Chen - Head of IR - own investor cadence",
        lane_id="telegram:c1",
        workspace="people",
    )
    duplicate = handle_people_message(
        "New report: Alice Chen - Head of IR - own investor cadence",
        lane_id="telegram:c1",
        workspace="people",
    )

    assert "Created report for Alice Chen" in created
    assert "Report already exists" in duplicate


def test_handle_people_message_returns_safe_missing_report_error(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))

    result = handle_people_message(
        "Prep Alice Chen",
        lane_id="telegram:c1",
        workspace="people",
    )

    assert "No direct report found" in result


def test_handle_people_message_team_question_uses_team_scan(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))

    handle_people_message(
        "New report: Alice Chen - Head of IR - own investor cadence",
        lane_id="telegram:c1",
        workspace="people",
    )
    handle_people_message(
        "Assessment Alice Chen: solid operator, rising, well matched, confidence medium",
        lane_id="telegram:c1",
        workspace="people",
    )

    result = handle_people_message(
        "Am I under-managing anyone?",
        lane_id="telegram:c1",
        workspace="people",
    )

    assert "Team scan" in result
    assert "Challenge lens" in result
    assert "Alice Chen" in result


def test_handle_people_message_returns_short_adhoc_prep_from_saved_state(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))

    from people_manager.storage import save_report

    handle_people_message(
        "New report: Fiona Cao - Chief of Staff - own follow-through",
        lane_id="telegram:c1",
        workspace="people",
    )
    from people_manager.storage import load_report

    report = load_report("fiona-cao")
    report["upcoming_one_on_one"] = {"topics": ["family summer travels"], "relationship_goal": "warm, encouraging"}
    save_report(report)

    result = handle_people_message(
        "1o1 prep Fiona",
        lane_id="telegram:c1",
        workspace="people",
    )

    assert result.splitlines()[0] == "Fiona Cao 1:1"
    assert "family summer travels" in result



def test_handle_people_message_reschedule_once_creates_override_and_log_entry(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))

    from people_manager.schedule_store import load_schedule_registry, save_schedule_registry
    from people_manager.storage import load_report

    handle_people_message(
        "New report: Alex Chen - COO - own operating cadence",
        lane_id="telegram:c1",
        workspace="people",
    )
    save_schedule_registry(
        {
            "version": 1,
            "timezone": "Asia/Singapore",
            "profiles": {
                "alex-chen": {
                    "name": "Alex Chen",
                    "enabled": True,
                    "delivery_target": "origin",
                    "meeting": {"type": "weekly", "weekday": 1, "time": "13:15"},
                    "prep_offset_minutes": 5,
                    "template_style": "ultra_short_telegram",
                }
            },
        }
    )

    result = handle_people_message(
        "Alex 1:1 rescheduled (one-off) to tomorrow 2:45pm",
        lane_id="telegram:c1",
        workspace="people",
        now=datetime(2026, 4, 20, 11, 0, tzinfo=ZoneInfo("Asia/Singapore")),
    )

    registry = load_schedule_registry()
    override = registry["profiles"]["alex-chen"]["overrides"][0]
    report = load_report("alex-chen")

    assert "Recurring cadence unchanged" in result
    assert override["kind"] == "reschedule_once"
    assert override["original_meeting_at"] == "2026-04-20T13:15:00+08:00"
    assert override["effective_meeting_at"] == "2026-04-21T14:45:00+08:00"
    assert override["status"] == "active"
    assert override["source"]["message_text"] == "Alex 1:1 rescheduled (one-off) to tomorrow 2:45pm"
    assert report["interaction_log"][-1]["type"] == "one_on_one_reschedule_override"
    assert report["interaction_log"][-1]["source"]["message_text"] == "Alex 1:1 rescheduled (one-off) to tomorrow 2:45pm"



def test_handle_people_message_returns_none_outside_people_workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))

    result = handle_people_message(
        "Update Alice Chen: shipped memo",
        lane_id="telegram:c1",
        workspace="speech",
    )

    assert result is None
