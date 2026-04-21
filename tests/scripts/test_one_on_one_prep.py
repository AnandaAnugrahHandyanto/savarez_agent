from datetime import datetime
from zoneinfo import ZoneInfo

from people_manager.storage import create_report



def _install_schedule(tmp_path, monkeypatch, *, include_bad_target=False):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    from people_manager.schedule_store import save_schedule_registry

    create_report("Thomas Zhu", "COO", "Own operating cadence")
    profiles = {
        "thomas-zhu": {
            "name": "Thomas Zhu",
            "enabled": True,
            "delivery_target": "origin",
            "meeting": {"type": "weekly", "weekday": 1, "time": "13:15"},
            "prep_offset_minutes": 5,
            "template_style": "ultra_short_telegram",
        }
    }
    if include_bad_target:
        create_report("Broken Target", "Ops", "Own broken target")
        profiles["broken-target"] = {
            "name": "Broken Target",
            "enabled": True,
            "delivery_target": "bad-target",
            "meeting": {"type": "weekly", "weekday": 1, "time": "13:15"},
            "prep_offset_minutes": 5,
            "template_style": "ultra_short_telegram",
        }
    save_schedule_registry(
        {
            "version": 1,
            "timezone": "Asia/Singapore",
            "profiles": profiles,
        }
    )



def test_preview_command_renders_without_sending(tmp_path, monkeypatch, capsys):
    _install_schedule(tmp_path, monkeypatch)
    from scripts.one_on_one_prep import main

    exit_code = main(["preview", "thomas-zhu", "--now", "2026-04-20T13:10:00+08:00"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Thomas Zhu 1:1 in 5m" in output



def test_run_once_sends_only_unsent_due_occurrence(tmp_path, monkeypatch):
    _install_schedule(tmp_path, monkeypatch)
    from scripts.one_on_one_prep import main

    sent_messages = []
    monkeypatch.setattr(
        "scripts.one_on_one_prep.send_telegram_message",
        lambda text, delivery_target: sent_messages.append((text, delivery_target)) or {"success": True},
    )

    exit_code = main(["run-once", "--now", "2026-04-20T13:10:30+08:00"])
    second_exit_code = main(["run-once", "--now", "2026-04-20T13:10:45+08:00"])

    assert exit_code == 0
    assert second_exit_code == 0
    assert len(sent_messages) == 1
    assert sent_messages[0][1] == "origin"
    assert "Thomas Zhu 1:1 in 5m" in sent_messages[0][0]


def test_add_biweekly_requires_anchor_date(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))

    from scripts.one_on_one_prep import main

    exit_code = main(["add", "--slug", "thomas-zhu", "--biweekly", "mon", "13:15"])
    output = capsys.readouterr()

    assert exit_code == 1
    assert "anchor_date" in output.err



def test_run_once_continues_after_delivery_failure(tmp_path, monkeypatch, capsys):
    _install_schedule(tmp_path, monkeypatch, include_bad_target=True)
    from scripts.one_on_one_prep import main

    sent_messages = []

    def _fake_send(text, delivery_target):
        if delivery_target == "bad-target":
            raise RuntimeError("Unsupported delivery target: bad-target")
        sent_messages.append((text, delivery_target))
        return {"success": True}

    monkeypatch.setattr("scripts.one_on_one_prep.send_telegram_message", _fake_send)

    exit_code = main(["run-once", "--now", "2026-04-20T13:10:30+08:00"])
    output = capsys.readouterr()

    assert exit_code == 0
    assert len(sent_messages) == 1
    assert sent_messages[0][1] == "origin"
    assert "delivery failed for broken-target" in output.err


def test_show_command_prints_schedule_details(tmp_path, monkeypatch, capsys):
    _install_schedule(tmp_path, monkeypatch)
    from scripts.one_on_one_prep import main

    exit_code = main(["show", "thomas-zhu"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert '"thomas-zhu"' in output
    assert '"type": "weekly"' in output


def test_disable_and_enable_commands_toggle_schedule(tmp_path, monkeypatch):
    _install_schedule(tmp_path, monkeypatch)
    from scripts.one_on_one_prep import main
    from people_manager.schedule_store import load_schedule_registry

    assert main(["disable", "thomas-zhu"]) == 0
    assert load_schedule_registry()["profiles"]["thomas-zhu"]["enabled"] is False

    assert main(["enable", "thomas-zhu"]) == 0
    assert load_schedule_registry()["profiles"]["thomas-zhu"]["enabled"] is True



def test_update_command_changes_existing_schedule(tmp_path, monkeypatch):
    _install_schedule(tmp_path, monkeypatch)
    from scripts.one_on_one_prep import main
    from people_manager.schedule_store import load_schedule_registry

    assert main(["update", "--slug", "thomas-zhu", "--weekly", "tue", "14:45", "--delivery-target", "telegram:546950872"]) == 0

    schedule = load_schedule_registry()["profiles"]["thomas-zhu"]
    assert schedule["meeting"] == {"type": "weekly", "weekday": 2, "time": "14:45"}
    assert schedule["delivery_target"] == "telegram:546950872"



def test_remove_with_archive_moves_schedule_out_of_active_profiles(tmp_path, monkeypatch):
    _install_schedule(tmp_path, monkeypatch)
    from scripts.one_on_one_prep import main
    from people_manager.schedule_store import load_schedule_registry

    assert main(["remove", "thomas-zhu", "--archive"]) == 0

    registry = load_schedule_registry()
    assert "thomas-zhu" not in registry["profiles"]
    assert "thomas-zhu" in registry["archived_profiles"]



def test_log_command_filters_by_slug_and_limit(tmp_path, monkeypatch, capsys):
    _install_schedule(tmp_path, monkeypatch)
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from people_manager.reminder_log import append_reminder_log
    from scripts.one_on_one_prep import main

    append_reminder_log(
        {
            "profile_slug": "thomas-zhu",
            "meeting_at": datetime(2026, 4, 20, 13, 15, tzinfo=ZoneInfo("Asia/Singapore")).isoformat(),
            "prep_sent_at": datetime(2026, 4, 20, 13, 10, tzinfo=ZoneInfo("Asia/Singapore")).isoformat(),
            "delivery_target": "origin",
            "template_style": "ultra_short_telegram",
            "message_preview": "Thomas Zhu 1:1 in 5m",
            "status": "sent",
        }
    )
    append_reminder_log(
        {
            "profile_slug": "other-person",
            "meeting_at": datetime(2026, 4, 20, 14, 15, tzinfo=ZoneInfo("Asia/Singapore")).isoformat(),
            "prep_sent_at": datetime(2026, 4, 20, 14, 10, tzinfo=ZoneInfo("Asia/Singapore")).isoformat(),
            "delivery_target": "origin",
            "template_style": "ultra_short_telegram",
            "message_preview": "Other 1:1 in 5m",
            "status": "sent",
        }
    )

    exit_code = main(["log", "--month", "2026-04", "--slug", "thomas-zhu", "--limit", "1"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "thomas-zhu" in output
    assert "other-person" not in output



def test_audit_reports_missing_schedule_report_and_sparse_metadata(tmp_path, monkeypatch, capsys):
    _install_schedule(tmp_path, monkeypatch)
    from people_manager.schedule_store import load_schedule_registry, save_schedule_registry
    from people_manager.storage import create_report
    from scripts.one_on_one_prep import main

    create_report("Unscheduled Person", "Ops", "Own unscheduled work")
    registry = load_schedule_registry()
    registry["profiles"]["missing-report"] = {
        "name": "Missing Report",
        "enabled": True,
        "delivery_target": "origin",
        "meeting": {"type": "monthly_nth_weekday", "weekday": 2, "ordinal": 6, "time": "13:15"},
        "prep_offset_minutes": 5,
        "template_style": "ultra_short_telegram",
    }
    save_schedule_registry(registry)

    exit_code = main(["audit"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "scheduled without report" in output.lower()
    assert "unscheduled reports" in output.lower()
    assert "sparse prep metadata" in output.lower()
    assert "malformed schedules" in output.lower()



def test_list_and_show_include_next_occurrence_visibility(tmp_path, monkeypatch, capsys):
    _install_schedule(tmp_path, monkeypatch)
    from scripts.one_on_one_prep import main

    assert main(["list", "--now", "2026-04-20T13:10:00+08:00"]) == 0
    list_output = capsys.readouterr().out
    assert "next_meeting_at=2026-04-20T13:15:00+08:00" in list_output
    assert "next_prep_at=2026-04-20T13:10:00+08:00" in list_output

    assert main(["show", "thomas-zhu", "--now", "2026-04-20T13:10:00+08:00"]) == 0
    show_output = capsys.readouterr().out
    assert '"next_meeting_at": "2026-04-20T13:15:00+08:00"' in show_output
    assert '"next_prep_at": "2026-04-20T13:10:00+08:00"' in show_output



def test_reschedule_once_commands_surface_base_vs_effective_occurrence(tmp_path, monkeypatch, capsys):
    _install_schedule(tmp_path, monkeypatch)
    from people_manager.schedule_store import load_schedule_registry
    from scripts.one_on_one_prep import main

    assert main(
        [
            "reschedule-once",
            "thomas-zhu",
            "--effective-meeting-at",
            "2026-04-21T14:45:00+08:00",
            "--now",
            "2026-04-20T11:00:00+08:00",
            "--message-text",
            "Thomas Zhu 1:1 rescheduled (one-off) to tomorrow 2:45pm",
        ]
    ) == 0

    registry = load_schedule_registry()
    override = registry["profiles"]["thomas-zhu"]["overrides"][0]
    assert override["original_meeting_at"] == "2026-04-20T13:15:00+08:00"
    assert override["effective_meeting_at"] == "2026-04-21T14:45:00+08:00"

    assert main(["overrides", "thomas-zhu"]) == 0
    overrides_output = capsys.readouterr().out
    assert "status=active" in overrides_output
    assert "effective_meeting_at=2026-04-21T14:45:00+08:00" in overrides_output

    assert main(["list", "--now", "2026-04-20T11:00:00+08:00"]) == 0
    list_output = capsys.readouterr().out
    assert "base_meeting_at=2026-04-20T13:15:00+08:00" in list_output
    assert "effective_meeting_at=2026-04-21T14:45:00+08:00" in list_output

    assert main(["preview", "thomas-zhu", "--now", "2026-04-20T11:00:00+08:00"]) == 0
    preview_output = capsys.readouterr().out
    assert "base_meeting_at=2026-04-20T13:15:00+08:00" in preview_output
    assert "effective_meeting_at=2026-04-21T14:45:00+08:00" in preview_output

    assert main(["due-now", "--now", "2026-04-21T14:40:00+08:00"]) == 0
    due_output = capsys.readouterr().out
    assert "base_meeting_at=2026-04-20T13:15:00+08:00" in due_output
    assert "effective_meeting_at=2026-04-21T14:45:00+08:00" in due_output



def test_enqueue_due_creates_queue_event_with_dedupe_key(tmp_path, monkeypatch):
    _install_schedule(tmp_path, monkeypatch)
    from people_manager.prep_queue import list_queue_events
    from scripts.one_on_one_prep import main

    assert main(["enqueue-due", "--now", "2026-04-20T13:10:00+08:00"]) == 0

    events = list_queue_events()
    assert len(events) == 1
    event = events[0]
    assert event["type"] == "one_on_one_prep_due"
    assert event["profile_slug"] == "thomas-zhu"
    assert event["dedupe_key"] == "thomas-zhu::2026-04-20T13:15:00+08:00"
    assert event["state"] == "queued_for_miya"
    assert event["delivery_outcome"] is None
    assert event["deadline_at"] == "2026-04-20T13:11:00+08:00"



def test_rescheduled_occurrence_uses_effective_timestamp_and_is_consumed_when_sent(tmp_path, monkeypatch):
    _install_schedule(tmp_path, monkeypatch)
    from people_manager.prep_queue import load_queue_event
    from people_manager.schedule_store import load_schedule_registry
    from scripts.one_on_one_prep import main

    assert main(
        [
            "reschedule-once",
            "thomas-zhu",
            "--effective-meeting-at",
            "2026-04-21T14:45:00+08:00",
            "--now",
            "2026-04-20T11:00:00+08:00",
        ]
    ) == 0
    assert main(["enqueue-due", "--now", "2026-04-21T14:40:00+08:00"]) == 0
    event = load_queue_event("thomas-zhu::2026-04-21T14:45:00+08:00")
    assert event is not None
    assert event["meeting_at"] == "2026-04-21T14:45:00+08:00"
    assert event["dedupe_key"] == "thomas-zhu::2026-04-21T14:45:00+08:00"

    assert main(
        [
            "miya-mark-sent",
            "--dedupe-key",
            "thomas-zhu::2026-04-21T14:45:00+08:00",
            "--sent-at",
            "2026-04-21T14:40:20+08:00",
        ]
    ) == 0

    override = load_schedule_registry()["profiles"]["thomas-zhu"]["overrides"][0]
    assert override["status"] == "consumed"
    assert override["consumed_at"] == "2026-04-21T14:40:20+08:00"



def test_earlier_reschedule_consumption_suppresses_original_recurring_slot(tmp_path, monkeypatch):
    _install_schedule(tmp_path, monkeypatch)
    from people_manager.schedule_store import due_reminders
    from scripts.one_on_one_prep import main

    monkeypatch.setattr(
        "scripts.one_on_one_prep.send_telegram_message",
        lambda text, delivery_target: {"success": True},
    )

    assert main(
        [
            "reschedule-once",
            "thomas-zhu",
            "--effective-meeting-at",
            "2026-04-20T09:00:00+08:00",
            "--now",
            "2026-04-20T08:00:00+08:00",
        ]
    ) == 0
    assert main(["run-once", "--now", "2026-04-20T08:55:30+08:00"]) == 0

    due = due_reminders(now=datetime(2026, 4, 20, 13, 10, tzinfo=ZoneInfo("Asia/Singapore")))

    assert due == []



def test_miya_sent_before_deadline_suppresses_fallback(tmp_path, monkeypatch):
    _install_schedule(tmp_path, monkeypatch)
    from people_manager.prep_queue import load_queue_event
    from scripts.one_on_one_prep import main

    sent_messages = []
    monkeypatch.setattr(
        "scripts.one_on_one_prep.send_telegram_message",
        lambda text, delivery_target: sent_messages.append((text, delivery_target)) or {"success": True},
    )

    assert main(["enqueue-due", "--now", "2026-04-20T13:10:00+08:00"]) == 0
    assert main(["miya-claim-next", "--now", "2026-04-20T13:10:05+08:00"]) == 0
    assert main(
        [
            "miya-mark-sent",
            "--dedupe-key",
            "thomas-zhu::2026-04-20T13:15:00+08:00",
            "--sent-at",
            "2026-04-20T13:10:20+08:00",
        ]
    ) == 0
    assert main(["run-fallback", "--now", "2026-04-20T13:11:10+08:00"]) == 0

    event = load_queue_event("thomas-zhu::2026-04-20T13:15:00+08:00")
    assert event["state"] == "sent_by_miya"
    assert event["delivery_outcome"] == "sent_by_miya"
    assert sent_messages == []



def test_fallback_fires_once_after_sla_miss(tmp_path, monkeypatch):
    _install_schedule(tmp_path, monkeypatch)
    from people_manager.prep_queue import load_queue_event
    from scripts.one_on_one_prep import main

    sent_messages = []
    monkeypatch.setattr(
        "scripts.one_on_one_prep.send_telegram_message",
        lambda text, delivery_target: sent_messages.append((text, delivery_target)) or {"success": True},
    )

    assert main(["enqueue-due", "--now", "2026-04-20T13:10:00+08:00"]) == 0
    assert main(["run-fallback", "--now", "2026-04-20T13:11:05+08:00"]) == 0
    assert main(["run-fallback", "--now", "2026-04-20T13:11:20+08:00"]) == 0

    event = load_queue_event("thomas-zhu::2026-04-20T13:15:00+08:00")
    assert event["state"] == "fallback_sent"
    assert event["delivery_outcome"] == "fallback_sent"
    assert len(sent_messages) == 1
    assert sent_messages[0][1] == "origin"
    assert "Thomas Zhu 1:1 in 5m" in sent_messages[0][0]
    assert "Miya response delayed" in sent_messages[0][0]



def test_late_miya_completion_after_fallback_is_suppressed_and_logged(tmp_path, monkeypatch, capsys):
    _install_schedule(tmp_path, monkeypatch)
    from people_manager.prep_queue import load_queue_event
    from scripts.one_on_one_prep import main

    monkeypatch.setattr(
        "scripts.one_on_one_prep.send_telegram_message",
        lambda text, delivery_target: {"success": True},
    )

    assert main(["enqueue-due", "--now", "2026-04-20T13:10:00+08:00"]) == 0
    assert main(["run-fallback", "--now", "2026-04-20T13:11:05+08:00"]) == 0
    assert main(
        [
            "miya-mark-sent",
            "--dedupe-key",
            "thomas-zhu::2026-04-20T13:15:00+08:00",
            "--sent-at",
            "2026-04-20T13:11:30+08:00",
        ]
    ) == 0
    assert main(["log", "--month", "2026-04", "--slug", "thomas-zhu", "--limit", "10"]) == 0
    log_output = capsys.readouterr().out

    event = load_queue_event("thomas-zhu::2026-04-20T13:15:00+08:00")
    assert event["state"] == "stale_completion_suppressed"
    assert event["delivery_outcome"] == "fallback_sent"
    assert "status=stale_completion_suppressed" in log_output
    assert "status=fallback_sent" in log_output



def test_audit_surfaces_queue_state_counts(tmp_path, monkeypatch, capsys):
    _install_schedule(tmp_path, monkeypatch)
    from scripts.one_on_one_prep import main

    assert main(["enqueue-due", "--now", "2026-04-20T13:10:00+08:00"]) == 0
    assert main(["miya-claim-next", "--now", "2026-04-20T13:10:05+08:00"]) == 0
    assert main(["audit"] ) == 0
    output = capsys.readouterr().out

    assert "Occurrence queue state" in output
    assert "claimed_by_miya: 1" in output



def test_enqueue_and_fallback_are_idempotent_across_retries(tmp_path, monkeypatch):
    _install_schedule(tmp_path, monkeypatch)
    from people_manager.prep_queue import list_queue_events
    from scripts.one_on_one_prep import main

    sent_messages = []
    monkeypatch.setattr(
        "scripts.one_on_one_prep.send_telegram_message",
        lambda text, delivery_target: sent_messages.append((text, delivery_target)) or {"success": True},
    )

    assert main(["enqueue-due", "--now", "2026-04-20T13:10:00+08:00"]) == 0
    assert main(["enqueue-due", "--now", "2026-04-20T13:10:20+08:00"]) == 0
    assert len(list_queue_events()) == 1

    assert main(["run-fallback", "--now", "2026-04-20T13:11:05+08:00"]) == 0
    assert main(["run-fallback", "--now", "2026-04-20T13:11:40+08:00"]) == 0
    assert len(sent_messages) == 1



def test_cancel_override_falls_back_to_recurring_cadence(tmp_path, monkeypatch, capsys):
    _install_schedule(tmp_path, monkeypatch)
    from scripts.one_on_one_prep import main

    assert main(
        [
            "reschedule-once",
            "thomas-zhu",
            "--effective-meeting-at",
            "2026-04-21T14:45:00+08:00",
            "--now",
            "2026-04-20T11:00:00+08:00",
        ]
    ) == 0
    assert main(["cancel-override", "thomas-zhu", "--now", "2026-04-20T11:05:00+08:00"]) == 0
    assert main(["list", "--now", "2026-04-20T11:05:00+08:00"]) == 0
    output = capsys.readouterr().out

    assert "effective_meeting_at=2026-04-20T13:15:00+08:00" in output
    assert "active_override=none" in output



def test_cancelled_override_is_not_claimable_or_sent_after_queueing(tmp_path, monkeypatch, capsys):
    _install_schedule(tmp_path, monkeypatch)
    from people_manager.prep_queue import load_queue_event
    from scripts.one_on_one_prep import main

    monkeypatch.setattr(
        "scripts.one_on_one_prep.send_telegram_message",
        lambda text, delivery_target: {"success": True},
    )

    assert main(
        [
            "reschedule-once",
            "thomas-zhu",
            "--effective-meeting-at",
            "2026-04-21T14:45:00+08:00",
            "--now",
            "2026-04-20T11:00:00+08:00",
        ]
    ) == 0
    assert main(["enqueue-due", "--now", "2026-04-21T14:40:00+08:00"]) == 0
    assert main(["cancel-override", "thomas-zhu", "--now", "2026-04-21T14:40:10+08:00"]) == 0
    assert main(["miya-claim-next", "--now", "2026-04-21T14:40:20+08:00"]) == 0
    claim_output = capsys.readouterr().out

    event = load_queue_event("thomas-zhu::2026-04-21T14:45:00+08:00")

    assert "No queued occurrences for Miya" in claim_output
    assert event["state"] == "cancelled_override"
    assert event["delivery_outcome"] == "cancelled_override"



def test_reschedule_once_rejects_conflicting_active_override(tmp_path, monkeypatch, capsys):
    _install_schedule(tmp_path, monkeypatch)
    from scripts.one_on_one_prep import main

    assert main(
        [
            "reschedule-once",
            "thomas-zhu",
            "--effective-meeting-at",
            "2026-04-21T14:45:00+08:00",
            "--now",
            "2026-04-20T11:00:00+08:00",
        ]
    ) == 0
    exit_code = main(
        [
            "reschedule-once",
            "thomas-zhu",
            "--effective-meeting-at",
            "2026-04-22T09:30:00+08:00",
            "--now",
            "2026-04-20T11:01:00+08:00",
        ]
    )
    output = capsys.readouterr()

    assert exit_code == 1
    assert "active override already exists" in output.err.lower()



def test_original_already_sent_keeps_history_and_schedules_additional_one_off(tmp_path, monkeypatch):
    _install_schedule(tmp_path, monkeypatch)
    from people_manager.reminder_log import load_reminder_entries
    from scripts.one_on_one_prep import main

    sent_messages = []
    monkeypatch.setattr(
        "scripts.one_on_one_prep.send_telegram_message",
        lambda text, delivery_target: sent_messages.append((text, delivery_target)) or {"success": True},
    )

    assert main(["run-once", "--now", "2026-04-20T13:10:30+08:00"]) == 0
    assert main(
        [
            "reschedule-once",
            "thomas-zhu",
            "--effective-meeting-at",
            "2026-04-20T14:45:00+08:00",
            "--now",
            "2026-04-20T13:11:00+08:00",
        ]
    ) == 0
    assert main(["run-once", "--now", "2026-04-20T14:40:30+08:00"]) == 0

    entries = load_reminder_entries(month="2026-04", profile_slug="thomas-zhu", limit=10)
    meeting_times = [entry.get("meeting_at") for entry in entries if entry.get("status") == "sent"]

    assert "2026-04-20T13:15:00+08:00" in meeting_times
    assert "2026-04-20T14:45:00+08:00" in meeting_times
    assert len(sent_messages) == 2
