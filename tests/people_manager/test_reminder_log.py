from datetime import datetime
from zoneinfo import ZoneInfo



def test_append_and_detect_sent_occurrence(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))

    from people_manager.reminder_log import append_reminder_log, was_sent_for_occurrence

    meeting_at = datetime(2026, 4, 20, 13, 15, tzinfo=ZoneInfo("Asia/Singapore"))
    sent_at = datetime(2026, 4, 20, 13, 10, 1, tzinfo=ZoneInfo("Asia/Singapore"))

    append_reminder_log(
        {
            "profile_slug": "thomas-zhu",
            "meeting_at": meeting_at.isoformat(),
            "prep_sent_at": sent_at.isoformat(),
            "delivery_target": "origin",
            "template_style": "ultra_short_telegram",
            "message_preview": "Thomas Zhu 1:1 in 5m",
            "status": "sent",
        }
    )

    assert was_sent_for_occurrence("thomas-zhu", meeting_at)
    assert not was_sent_for_occurrence(
        "thomas-zhu", datetime(2026, 4, 27, 13, 15, tzinfo=ZoneInfo("Asia/Singapore"))
    )



def test_claim_occurrence_is_atomic_until_released(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))

    from people_manager.reminder_log import claim_occurrence, release_occurrence_claim

    meeting_at = datetime(2026, 4, 20, 13, 15, tzinfo=ZoneInfo("Asia/Singapore"))

    assert claim_occurrence("thomas-zhu", meeting_at) is True
    assert claim_occurrence("thomas-zhu", meeting_at) is False

    release_occurrence_claim("thomas-zhu", meeting_at)

    assert claim_occurrence("thomas-zhu", meeting_at) is True
