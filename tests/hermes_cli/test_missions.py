from gateway.config import GatewayConfig, PlatformConfig
from gateway.platforms.base import MessageEvent, MessageType, Platform
from gateway.run import GatewayRunner
from gateway.session import SessionSource
from hermes_cli.missions import (
    create_mission,
    format_mission_status,
    list_missions,
    parse_mission_start_args,
    resolve_mission,
)
from cron.jobs import create_job, get_job, pause_job, resume_job, trigger_job, remove_job, update_job


import pytest


@pytest.fixture()
def tmp_cron_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("cron.jobs.CRON_DIR", tmp_path / "cron")
    monkeypatch.setattr("cron.jobs.JOBS_FILE", tmp_path / "cron" / "jobs.json")
    monkeypatch.setattr("cron.jobs.OUTPUT_DIR", tmp_path / "cron" / "output")
    return tmp_path


def test_parse_mission_start_args_defaults_and_flags():
    spec = parse_mission_start_args('--every 15m --hours 1 --name nightly --tools terminal,file --workdir /tmp -- Fix the queue')

    assert spec.prompt == "Fix the queue"
    assert spec.every == "15m"
    assert spec.hours == 1
    assert spec.name == "nightly"
    assert spec.enabled_toolsets == ["terminal", "file"]
    assert spec.workdir == "/tmp"


def test_parse_mission_requires_prompt():
    with pytest.raises(ValueError, match="mission prompt is required"):
        parse_mission_start_args("--every 30m --hours 8")


def test_mission_command_is_registered_for_active_gateway_sessions():
    from hermes_cli.commands import ACTIVE_SESSION_BYPASS_COMMANDS, should_bypass_active_session

    assert "mission" in ACTIVE_SESSION_BYPASS_COMMANDS
    assert should_bypass_active_session("mission") is True


def test_fractional_hours_rounds_up_repeat_count(tmp_cron_dir):
    spec = parse_mission_start_args("--every 30m --hours 2.01 Check boundary")

    job = create_mission(spec, source=None)

    assert job["repeat"]["times"] == 5


@pytest.mark.parametrize("hours", ["0", "-1", "nan", "inf"])
def test_parse_mission_rejects_non_positive_or_non_finite_hours(hours):
    with pytest.raises(ValueError, match="hours must be greater than zero"):
        parse_mission_start_args(f"--every 30m --hours {hours} objective")


@pytest.mark.parametrize("args, message", [
    ("--workdir relative/path objective", "absolute path"),
    ("--workdir /tmp/../etc objective", "without '..'"),
    ("--every 1m --hours 800 objective", "exceeds maximum"),
    ("--all-tools objective", "HERMES_MISSION_ALLOW_ALL_TOOLS"),
])
def test_parse_mission_rejects_unsafe_bounds(args, message):
    with pytest.raises(ValueError, match=message):
        parse_mission_start_args(args)


def test_parse_mission_all_tools_requires_explicit_env(monkeypatch):
    monkeypatch.setenv("HERMES_MISSION_ALLOW_ALL_TOOLS", "1")

    spec = parse_mission_start_args("--all-tools objective")

    assert spec.enabled_toolsets is None


def test_create_mission_is_bounded_and_self_contextual(tmp_cron_dir):
    source = SessionSource(
        platform=Platform.DISCORD,
        chat_id="channel-1",
        chat_name="ops",
        chat_type="channel",
        user_id="u1",
        user_name="Henry",
        thread_id="thread-1",
    )
    spec = parse_mission_start_args("--every 15m --hours 1 --name queue-mission Investigate queue reliability")

    job = create_mission(spec, source=source)
    stored = get_job(job["id"])

    assert stored["mission"]["kind"] == "hermes_mission_v1"
    assert stored["mission"]["objective"] == "Investigate queue reliability"
    assert stored["repeat"]["times"] == 4
    assert stored["context_from"] == [stored["id"]]
    assert stored["deliver"] == "origin"
    assert stored["origin"]["platform"] == "discord"
    assert stored["origin"]["chat_id"] == "channel-1"
    assert stored["origin"]["thread_id"] == "thread-1"
    assert stored["enabled_toolsets"] == ["terminal", "file"]
    assert "Operating contract:" in stored["prompt"]
    assert "[MISSION COMPLETE]" in stored["prompt"]

    missions = list_missions(include_disabled=True)
    assert [m["id"] for m in missions] == [stored["id"]]

    status = format_mission_status(stored)
    assert "Investigate queue reliability" in status

    assert pause_job(stored["id"], reason="test")["state"] == "paused"
    assert resume_job(stored["id"])["state"] == "scheduled"
    assert trigger_job(stored["id"])["next_run_at"] is not None
    assert remove_job(stored["id"]) is True
    assert list_missions(include_disabled=True) == []


def test_resolve_mission_ignores_non_mission_name_collisions(tmp_cron_dir):
    regular = create_job(prompt="Regular cron", schedule="every 30m", name="nightly")
    spec = parse_mission_start_args("--every 30m --hours 1 --name nightly Mission work")
    mission = create_mission(spec, source=None)

    resolved = resolve_mission("nightly")
    assert resolved is not None
    assert resolved["id"] == mission["id"]
    assert resolve_mission(regular["id"]) is None


@pytest.mark.asyncio
async def test_gateway_mission_command_lifecycle(tmp_cron_dir):
    runner = object.__new__(GatewayRunner)
    runner.config = GatewayConfig(
        platforms={Platform.DISCORD: PlatformConfig(enabled=True, token="token")}
    )

    source = SessionSource(
        platform=Platform.DISCORD,
        chat_id="channel-1",
        chat_type="channel",
        user_id="u1",
        thread_id="thread-1",
    )
    event = MessageEvent(
        text="/mission start --every 30m --hours 1 Test mission handler",
        message_type=MessageType.TEXT,
        source=source,
        message_id="m1",
    )

    started = await GatewayRunner._handle_mission_command(runner, event)
    assert "Mission scheduled" in started
    missions = list_missions(include_disabled=True)
    assert len(missions) == 1
    mission_id = missions[0]["id"]

    status = await GatewayRunner._handle_mission_command(
        runner,
        MessageEvent(
            text=f"/mission status {mission_id}",
            message_type=MessageType.TEXT,
            source=source,
            message_id="m2",
        ),
    )
    assert "Test mission handler" in status

    paused = await GatewayRunner._handle_mission_command(
        runner,
        MessageEvent(
            text=f"/mission pause {mission_id}",
            message_type=MessageType.TEXT,
            source=source,
            message_id="m3",
        ),
    )
    assert "Mission paused" in paused
    assert get_job(mission_id)["state"] == "paused"


def test_scheduler_removes_mission_on_complete_marker(tmp_cron_dir, monkeypatch):
    import cron.scheduler as scheduler
    import cron.jobs as jobs

    spec = parse_mission_start_args("--every 30m --hours 8 Finish early")
    job = create_mission(spec, source=None)
    trigger_job(job["id"])

    monkeypatch.setattr(
        scheduler,
        "run_job",
        lambda due_job: (True, "# output", "  [mission complete] done", None),
    )

    assert scheduler.tick(verbose=False) == 1
    assert get_job(job["id"]) is None
    output_dir = jobs.OUTPUT_DIR / job["id"]
    assert output_dir.exists()
    assert any(output_dir.iterdir())


def test_scheduler_does_not_remove_failed_mission_with_complete_marker(tmp_cron_dir, monkeypatch):
    import cron.scheduler as scheduler

    spec = parse_mission_start_args("--every 30m --hours 8 Failed mission")
    job = create_mission(spec, source=None)
    trigger_job(job["id"])

    monkeypatch.setattr(
        scheduler,
        "run_job",
        lambda due_job: (False, "# output", "[MISSION COMPLETE] not really", "boom"),
    )

    assert scheduler.tick(verbose=False) == 1
    stored = get_job(job["id"])
    assert stored is not None
    assert stored["last_status"] == "error"


def test_scheduler_final_run_complete_marker_double_remove_is_benign(tmp_cron_dir, monkeypatch):
    import cron.scheduler as scheduler
    import cron.jobs as jobs

    spec = parse_mission_start_args("--every 30m --hours 0.5 Finish on final run")
    job = create_mission(spec, source=None)
    assert job["repeat"]["times"] == 1
    trigger_job(job["id"])

    monkeypatch.setattr(
        scheduler,
        "run_job",
        lambda due_job: (True, "# output", "[MISSION COMPLETE] final", None),
    )

    assert scheduler.tick(verbose=False) == 1
    assert get_job(job["id"]) is None
    output_dir = jobs.OUTPUT_DIR / job["id"]
    assert output_dir.exists()
    assert any(output_dir.iterdir())


def test_scheduler_does_not_remove_non_mission_job_with_complete_marker(tmp_cron_dir, monkeypatch):
    import cron.scheduler as scheduler

    job = create_job(prompt="Regular cron", schedule="every 30m")
    update_job(job["id"], {"mission": {"kind": "custom_metadata"}})
    trigger_job(job["id"])

    monkeypatch.setattr(
        scheduler,
        "run_job",
        lambda due_job: (True, "# output", "[MISSION COMPLETE] not a Hermes mission", None),
    )

    assert scheduler.tick(verbose=False) == 1
    assert get_job(job["id"]) is not None
