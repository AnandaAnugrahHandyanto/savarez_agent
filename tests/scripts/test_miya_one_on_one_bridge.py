import subprocess
from zoneinfo import ZoneInfo

from people_manager.storage import create_report



def _install_schedule(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    from people_manager.schedule_store import save_schedule_registry

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



def test_bridge_run_once_claims_and_marks_sent(tmp_path, monkeypatch):
    _install_schedule(tmp_path, monkeypatch)
    from people_manager.prep_queue import load_queue_event
    from scripts.miya_one_on_one_bridge import main
    from scripts.one_on_one_prep import main as prep_main

    assert prep_main(["enqueue-due", "--now", "2026-04-20T13:10:00+08:00"]) == 0

    calls = []

    def _fake_run(cmd, capture_output, text, check, cwd, env):
        calls.append((cmd, cwd))
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout="SENT dedupe_key=thomas-zhu::2026-04-20T13:15:00+08:00\nsession_id: miya-session\n",
            stderr="",
        )

    monkeypatch.setattr("scripts.miya_one_on_one_bridge.subprocess.run", _fake_run)

    assert main([
        "run-once",
        "--now",
        "2026-04-20T13:10:05+08:00",
        "--profile",
        "miya",
        "--miya-target",
        "telegram:546950872",
    ]) == 0

    event = load_queue_event("thomas-zhu::2026-04-20T13:15:00+08:00")
    assert event["state"] == "sent_by_miya"
    assert event["delivery_outcome"] == "sent_by_miya"
    assert calls
    command, _cwd = calls[0]
    assert command[:4] == [__import__('sys').executable, "-m", "hermes_cli.main", "chat"]
    assert "telegram:546950872" in command[-1]
    assert "thomas-zhu::2026-04-20T13:15:00+08:00" in command[-1]



def test_bridge_run_once_marks_failed_when_miya_bridge_fails(tmp_path, monkeypatch):
    _install_schedule(tmp_path, monkeypatch)
    from people_manager.prep_queue import load_queue_event
    from scripts.miya_one_on_one_bridge import main
    from scripts.one_on_one_prep import main as prep_main

    assert prep_main(["enqueue-due", "--now", "2026-04-20T13:10:00+08:00"]) == 0

    def _fake_run(cmd, capture_output, text, check, cwd, env):
        return subprocess.CompletedProcess(cmd, 1, stdout="FAILED\n", stderr="boom")

    monkeypatch.setattr("scripts.miya_one_on_one_bridge.subprocess.run", _fake_run)

    assert main([
        "run-once",
        "--now",
        "2026-04-20T13:10:05+08:00",
        "--profile",
        "miya",
        "--miya-target",
        "telegram:546950872",
    ]) == 1

    event = load_queue_event("thomas-zhu::2026-04-20T13:15:00+08:00")
    assert event["state"] == "failed"
    assert event["delivery_outcome"] is None



def test_bridge_prompt_includes_event_contract_and_report_context(tmp_path, monkeypatch):
    _install_schedule(tmp_path, monkeypatch)
    from people_manager.prep_queue import load_queue_event
    from scripts.miya_one_on_one_bridge import build_miya_bridge_prompt
    from scripts.one_on_one_prep import main as prep_main
    from people_manager.storage import load_report

    assert prep_main(["enqueue-due", "--now", "2026-04-20T13:10:00+08:00"]) == 0
    event = load_queue_event("thomas-zhu::2026-04-20T13:15:00+08:00")
    report = load_report("thomas-zhu")

    prompt = build_miya_bridge_prompt(event, report, miya_target="telegram:546950872")

    assert "one_on_one_prep_due" in prompt
    assert "telegram:546950872" in prompt
    assert "thomas-zhu::2026-04-20T13:15:00+08:00" in prompt
    assert "Thomas Zhu" in prompt



def test_bridge_run_once_loads_target_from_profile_env(tmp_path, monkeypatch):
    _install_schedule(tmp_path, monkeypatch)
    from people_manager.prep_queue import load_queue_event
    from scripts.miya_one_on_one_bridge import main
    from scripts.one_on_one_prep import main as prep_main

    profile_home = tmp_path / "profiles" / "miya"
    profile_home.mkdir(parents=True)
    (profile_home / ".env").write_text("MIYA_ONE_ON_ONE_DELIVERY_TARGET=telegram:546950872\n", encoding="utf-8")
    monkeypatch.setattr("scripts.miya_one_on_one_bridge.get_profile_dir", lambda profile: profile_home)
    assert prep_main(["enqueue-due", "--now", "2026-04-20T13:10:00+08:00"]) == 0

    calls = []

    def _fake_run(cmd, capture_output, text, check, cwd, env):
        calls.append((cmd, env))
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout="SENT dedupe_key=thomas-zhu::2026-04-20T13:15:00+08:00\n",
            stderr="",
        )

    monkeypatch.setattr("scripts.miya_one_on_one_bridge.subprocess.run", _fake_run)

    assert main(["run-once", "--now", "2026-04-20T13:10:05+08:00", "--profile", "miya"]) == 0
    event = load_queue_event("thomas-zhu::2026-04-20T13:15:00+08:00")
    assert event["state"] == "sent_by_miya"
    assert calls
    assert "telegram:546950872" in calls[0][0][-1]
    assert calls[0][1]["HERMES_HOME"] == str(profile_home)
