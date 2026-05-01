from argparse import Namespace

from hermes_cli import monitor as monitor_mod


def test_build_monitor_snapshot_summarizes_runtime_and_errors(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    (tmp_path / "sessions").mkdir(parents=True)
    (tmp_path / "sessions" / "sessions.json").write_text('{"s1": {}, "s2": {}}', encoding="utf-8")
    (tmp_path / "cron").mkdir(parents=True)
    (tmp_path / "cron" / "jobs.json").write_text(
        '{"jobs": ['
        '{"id": "a", "enabled": true, "last_status": "ok"},'
        '{"id": "b", "enabled": true, "last_status": "error", "last_error": "smtp down"},'
        '{"id": "c", "enabled": false, "last_status": "error", "last_error": "ignored disabled"}'
        ']}' ,
        encoding="utf-8",
    )

    monkeypatch.setattr(monitor_mod, "is_gateway_running", lambda: True)
    monkeypatch.setattr(
        monitor_mod,
        "read_runtime_status",
        lambda: {
            "gateway_state": "running",
            "active_agents": 3,
            "updated_at": "2026-04-25T12:00:00Z",
            "platforms": {
                "feishu": {"state": "running"},
                "telegram": {"state": "error", "error_message": "token invalid"},
            },
        },
    )

    snapshot = monitor_mod.build_monitor_snapshot()

    assert snapshot["gateway"]["running"] is True
    assert snapshot["gateway"]["state"] == "running"
    assert snapshot["gateway"]["active_agents"] == 3
    assert snapshot["sessions"]["active"] == 2
    assert snapshot["cron"]["total"] == 3
    assert snapshot["cron"]["enabled"] == 2
    assert snapshot["cron"]["failing"] == 1
    assert any(item["source"] == "platform:telegram" for item in snapshot["errors"])
    assert any(item["source"] == "cron:b" for item in snapshot["errors"])


def test_render_monitor_text_includes_error_summary():
    text = monitor_mod.render_monitor_text(
        {
            "gateway": {"running": True, "state": "running", "active_agents": 1, "updated_at": "now"},
            "sessions": {"active": 2},
            "cron": {"total": 3, "enabled": 2, "failing": 1},
            "errors": [
                {"source": "platform:telegram", "message": "token invalid"},
                {"source": "cron:job-2", "message": "smtp down"},
            ],
        }
    )

    assert "Hermes Monitor" in text
    assert "Gateway" in text
    assert "running" in text
    assert "Error Summary" in text
    assert "platform:telegram" in text
    assert "smtp down" in text


def test_monitor_command_once_prints_single_snapshot(monkeypatch, capsys):
    monkeypatch.setattr(monitor_mod, "build_monitor_snapshot", lambda: {
        "gateway": {"running": False, "state": "stopped", "active_agents": 0, "updated_at": "n/a"},
        "sessions": {"active": 0},
        "cron": {"total": 0, "enabled": 0, "failing": 0},
        "errors": [],
    })

    monitor_mod.monitor_command(Namespace(once=True, interval=0.01, iterations=1))
    out = capsys.readouterr().out
    assert "Hermes Monitor" in out
    assert "stopped" in out
