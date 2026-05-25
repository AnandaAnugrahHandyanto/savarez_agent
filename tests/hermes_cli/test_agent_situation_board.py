"""Tests for the dashboard Agent Situation Board aggregator."""

from __future__ import annotations


def test_agent_from_active_discord_session_surfaces_working_status():
    from hermes_cli.web_server import _agent_from_session

    agent = _agent_from_session(
        {
            "id": "20260523_discord",
            "source": "discord",
            "title": "에이전트 상황판 만들기",
            "preview": "좋아 시작해",
            "started_at": 1000.0,
            "last_active": 1290.0,
            "ended_at": None,
            "model": "gpt-5.5",
            "is_active": True,
            "tool_call_count": 3,
            "message_count": 12,
        },
        now=1300.0,
    )

    assert agent["id"] == "session:20260523_discord"
    assert agent["name"] == "Hermes Discord"
    assert agent["kind"] == "hermes_session"
    assert agent["status"] == "working"
    assert agent["avatar"] == "hermes"
    assert agent["source"] == "discord"
    assert agent["title"] == "에이전트 상황판 만들기"
    assert agent["current_task"] == "좋아 시작해"
    assert agent["last_signal"] == "3 tool calls · 12 messages"
    assert agent["actions"] == ["peek", "open", "reply"]
    assert agent["links"] == [{"label": "Sessions", "href": "/sessions"}]


def test_agent_from_session_detects_needs_input_and_codex_identity():
    from hermes_cli.web_server import _agent_from_session

    agent = _agent_from_session(
        {
            "id": "codex_waiting",
            "source": "cli",
            "title": "Codex worker asks for approval",
            "preview": "Proceed? 승인 필요합니다",
            "started_at": 1000.0,
            "last_active": 1100.0,
            "ended_at": None,
            "is_active": False,
            "tool_call_count": 0,
            "message_count": 4,
        },
        now=1400.0,
    )

    assert agent["name"] == "Codex Worker"
    assert agent["kind"] == "codex_worker"
    assert agent["avatar"] == "codex"
    assert agent["status"] == "needs_input"
    assert "reply" in agent["actions"]


def test_agent_response_summary_counts_statuses_and_orders_attention_first():
    from hermes_cli.web_server import _build_agents_response

    response = _build_agents_response(
        [
            {
                "id": "idle_session",
                "source": "cli",
                "title": "Idle task",
                "preview": "waiting",
                "started_at": 1000.0,
                "last_active": 1000.0,
                "ended_at": None,
                "is_active": False,
                "tool_call_count": 0,
                "message_count": 1,
            },
            {
                "id": "blocked_session",
                "source": "discord",
                "title": "Blocked task",
                "preview": "Auth failed: token expired",
                "started_at": 1000.0,
                "last_active": 1290.0,
                "ended_at": None,
                "is_active": True,
                "tool_call_count": 1,
                "message_count": 6,
            },
        ],
        now=1300.0,
    )

    assert response["summary"]["blocked"] == 1
    assert response["summary"]["idle"] == 1
    assert response["summary"]["working"] == 0
    assert response["agents"][0]["status"] == "blocked"
    assert response["events"][0]["level"] == "warning"


def test_cron_job_agent_surfaces_scheduled_and_paused_state():
    from hermes_cli.web_server import _agent_from_cron_job

    scheduled = _agent_from_cron_job(
        {
            "id": "job_daily",
            "name": "Daily digest",
            "prompt": "Summarize overnight agent activity",
            "schedule_display": "0 9 * * *",
            "next_run_at": "2026-05-23T09:00:00+00:00",
            "last_run_at": "2026-05-22T09:00:00+00:00",
            "state": "scheduled",
            "enabled": True,
        },
        now=1000.0,
    )

    assert scheduled["id"] == "cron:job_daily"
    assert scheduled["name"] == "Cron: Daily digest"
    assert scheduled["kind"] == "cron_job"
    assert scheduled["status"] == "scheduled"
    assert scheduled["last_signal"] == "next: 2026-05-23T09:00:00+00:00 · 0 9 * * *"
    assert scheduled["links"] == [{"label": "Cron", "href": "/cron"}]

    paused = _agent_from_cron_job({"id": "job_paused", "name": "Paused", "enabled": False, "state": "paused"})
    assert paused["status"] == "idle"


def test_kanban_task_agent_maps_worker_status_and_failure_context():
    from hermes_cli.web_server import _agent_from_kanban_task

    running = _agent_from_kanban_task(
        {
            "id": "t_agentview",
            "title": "Implement adapter",
            "status": "running",
            "assignee": "codex",
            "priority": 7,
            "created_at": 900,
            "started_at": 950,
            "last_heartbeat_at": 990,
            "worker_pid": 4242,
            "consecutive_failures": 0,
        },
        board="default",
    )

    assert running["id"] == "kanban:default:t_agentview"
    assert running["name"] == "Kanban: codex"
    assert running["kind"] == "kanban_worker"
    assert running["status"] == "working"
    assert running["last_signal"] == "running · priority 7 · pid 4242"
    assert running["links"] == [{"label": "Kanban", "href": "/kanban?board=default"}]

    blocked = _agent_from_kanban_task(
        {
            "id": "t_blocked",
            "title": "Need auth",
            "status": "blocked",
            "assignee": "omx",
            "created_at": 900,
            "last_failure_error": "token expired",
            "consecutive_failures": 2,
        }
    )
    assert blocked["status"] == "blocked"
    assert blocked["avatar"] == "omx"
    assert blocked["metadata"]["consecutive_failures"] == 2


def test_background_process_agent_maps_running_and_failed_processes():
    from hermes_cli.web_server import _agent_from_background_process

    running = _agent_from_background_process(
        {
            "session_id": "proc_123",
            "command": "npm run dev",
            "cwd": "/repo/web",
            "pid": 1234,
            "started_at": "2026-05-23T10:00:00",
            "uptime_seconds": 42,
            "status": "running",
            "output_preview": "ready on 5173",
        },
        now=2000.0,
    )

    assert running["id"] == "process:proc_123"
    assert running["name"] == "Process: proc_123"
    assert running["kind"] == "background_process"
    assert running["status"] == "working"
    assert running["last_signal"] == "running · pid 1234 · 42s"
    assert running["links"] == [{"label": "Processes", "href": "/agents"}]

    failed = _agent_from_background_process({"session_id": "proc_bad", "command": "pytest", "status": "exited", "exit_code": 1})
    assert failed["status"] == "failed"


def test_agent_response_can_filter_by_source_and_status():
    from hermes_cli.web_server import _build_agents_response

    response = _build_agents_response(
        [
            {
                "id": "discord_active",
                "source": "discord",
                "title": "Active work",
                "preview": "still working",
                "started_at": 1000.0,
                "last_active": 1290.0,
                "ended_at": None,
                "is_active": True,
            },
            {
                "id": "cli_idle",
                "source": "cli",
                "title": "Idle work",
                "preview": "waiting",
                "started_at": 1000.0,
                "last_active": 1000.0,
                "ended_at": None,
                "is_active": False,
            },
        ],
        extra_agents=[
            {
                "id": "cron:nightly",
                "name": "Cron: Nightly",
                "kind": "cron_job",
                "avatar": "clock",
                "status": "scheduled",
                "source": "cron",
                "location": "scheduler",
                "title": "Nightly",
                "current_task": "Nightly",
                "progress": None,
                "started_at": None,
                "last_signal_at": 1200.0,
                "last_signal": "next: soon",
                "links": [{"label": "Cron", "href": "/cron"}],
                "actions": ["peek", "open"],
                "metadata": {},
            }
        ],
        now=1300.0,
        source_filter="cron",
        status_filter="scheduled",
    )

    assert [agent["id"] for agent in response["agents"]] == ["cron:nightly"]
    assert response["summary"]["scheduled"] == 1
    assert response["summary"]["working"] == 0
    assert response["filters"] == {"source": "cron", "status": "scheduled"}
