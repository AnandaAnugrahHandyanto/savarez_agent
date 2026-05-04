"""Tests for Mission Control dashboard helpers."""

from __future__ import annotations

import json
from pathlib import Path


def test_read_mission_control_projects_groups_inventory(tmp_path: Path, monkeypatch):
    from hermes_cli import web_server

    projects = tmp_path / "projects"
    (projects / "current").mkdir(parents=True)
    (projects / "planning").mkdir()
    (projects / "current" / "swiftpos.md").write_text("# SwiftPOS\n", encoding="utf-8")
    (projects / "planning" / "mission.md").write_text("# Mission Control\n", encoding="utf-8")
    (projects / "inventory.json").write_text(
        json.dumps(
            {
                "projects": [
                    {
                        "id": "swiftpos",
                        "name": "SwiftPOS",
                        "bucket": "current",
                        "priority": "P0",
                        "brief": "current/swiftpos.md",
                    },
                    {
                        "id": "mission-control",
                        "name": "Mission Control",
                        "bucket": "planning",
                        "priority": "P0",
                        "brief": "planning/mission.md",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    result = web_server._read_mission_control_projects(projects)

    assert result["total"] == 2
    assert result["counts"]["current"] == 1
    assert result["counts"]["planning"] == 1
    assert result["buckets"]["current"][0]["name"] == "SwiftPOS"
    assert result["buckets"]["planning"][0]["brief_path"].endswith("planning/mission.md")


def test_read_mission_control_projects_falls_back_to_markdown(tmp_path: Path):
    from hermes_cli import web_server

    projects = tmp_path / "projects"
    (projects / "future").mkdir(parents=True)
    (projects / "future" / "home-ai-rack.md").write_text("# Home AI Rack\n\nPlan.", encoding="utf-8")

    result = web_server._read_mission_control_projects(projects)

    assert result["total"] == 1
    assert result["counts"]["future"] == 1
    assert result["buckets"]["future"][0]["name"] == "Home AI Rack"


def test_parse_agent_process_line_detects_hermes_agent():
    from hermes_cli import web_server

    parsed = web_server._parse_agent_process_line(
        "12345 00:01:22 python3 python3 -m hermes_cli.main chat -q build mission control --token SECRET_TOKEN_123"
    )

    assert parsed is not None
    assert parsed["pid"] == 12345
    assert parsed["agent_type"] == "hermes"
    assert parsed["label"] == "Hermes Agent"
    assert parsed["current_work"] == "Hermes Agent process detected"
    assert "args" not in parsed
    assert "SECRET_TOKEN" not in parsed["current_work"]


def test_parse_agent_process_line_excludes_dashboard():
    from hermes_cli import web_server

    parsed = web_server._parse_agent_process_line(
        "12345 00:01:22 python3 python3 -m hermes_cli.main dashboard --port 9119"
    )

    assert parsed is None


def test_parse_agent_process_line_excludes_claude_desktop_helpers():
    from hermes_cli import web_server

    parsed = web_server._parse_agent_process_line(
        "12345 03-05:14:19 /Applications/Claude.app/Contents/MacOS/Claude /Applications/Claude.app/Contents/MacOS/Claude"
    )

    assert parsed is None


def test_parse_agent_process_line_keeps_claude_code():
    from hermes_cli import web_server

    parsed = web_server._parse_agent_process_line(
        "12345 00:02:01 /Users/edison/Library/Application /Users/edison/Library/Application Support/Claude/claude-code/2.1.121/claude.app/Contents/MacOS/claude --model opus --output-format stream-json"
    )

    assert parsed is not None
    assert parsed["agent_type"] == "claude"


def test_mission_control_cron_excludes_paused_jobs_from_upcoming(monkeypatch):
    from cron import jobs as cron_jobs
    from hermes_cli import web_server

    monkeypatch.setattr(cron_jobs, "list_jobs", lambda include_disabled=True: [
        {"id": "enabled", "enabled": True, "next_run_at": "2026-01-01T09:00:00"},
        {"id": "disabled", "enabled": False, "next_run_at": "2026-01-01T08:00:00"},
        {"id": "paused-state", "enabled": True, "state": "paused", "next_run_at": "2026-01-01T07:00:00"},
    ])

    result = web_server._mission_control_cron()

    assert result["total"] == 3
    assert result["enabled"] == 1
    assert result["paused"] == 2
    assert [job["id"] for job in result["upcoming"]] == ["enabled"]


def test_mission_control_skills_counts_disabled_without_undercounting(monkeypatch):
    from hermes_cli import skills_config, web_server
    from tools import skills_tool

    monkeypatch.setattr(skills_tool, "_find_all_skills", lambda skip_disabled=True: [
        {"name": "enabled-one", "category": "dev"},
        {"name": "enabled-two", "category": "dev"},
        {"name": "disabled-one", "category": "ops"},
    ])
    monkeypatch.setattr(skills_config, "get_disabled_skills", lambda config: {"disabled-one", "missing-disabled"})

    result = web_server._mission_control_skills()

    assert result["total"] == 3
    assert result["enabled"] == 2
    assert result["disabled"] == 1
    assert result["top_categories"] == [{"category": "dev", "count": 2}]


def test_mission_control_overview_endpoint_is_read_only_snapshot(monkeypatch):
    from fastapi.testclient import TestClient
    from hermes_cli import web_server

    async def fake_status():
        return {"gateway_running": True, "version": "test"}

    monkeypatch.setattr(web_server, "get_status", fake_status)
    monkeypatch.setattr(web_server, "_mission_control_sessions", lambda: {"active": [{"id": "s1"}], "recent": [], "total": 1})
    monkeypatch.setattr(web_server, "_scan_mission_control_agents", lambda: [{"pid": 42, "label": "Hermes Agent"}])
    monkeypatch.setattr(web_server, "_mission_control_usage", lambda days=7: {"period_days": days, "period": {"total_tokens": 10}})
    monkeypatch.setattr(web_server, "_read_mission_control_projects", lambda: {"total": 0, "counts": {}, "buckets": {}})
    monkeypatch.setattr(web_server, "_mission_control_cron", lambda: {"total": 0, "enabled": 0, "paused": 0, "upcoming": []})
    monkeypatch.setattr(web_server, "_mission_control_skills", lambda: {"total": 0, "enabled": 0, "disabled": 0, "top_categories": []})

    response = TestClient(web_server.app).get(
        "/api/mission-control/overview",
        headers={web_server._SESSION_HEADER_NAME: web_server._SESSION_TOKEN},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"]["gateway_running"] is True
    assert body["usage"]["period"]["total_tokens"] == 10
    assert body["agents"]["active_processes"] == 1
    assert body["agents"]["active_sessions"] == 1
