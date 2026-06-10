import json
import os
import sqlite3
from pathlib import Path

from gateway.claude_code_bridge import (
    build_claude_prompt,
    build_continuity_context,
    extract_explicit_workdir,
    is_claude_code_cli_config,
    resolve_workdir,
    run_claude_code_bridge_sync,
)


def test_detects_claude_code_cli_provider():
    assert is_claude_code_cli_config({"model": {"provider": "claude-code-cli"}})
    assert is_claude_code_cli_config({"clara_cli": {"enabled": True}})
    assert not is_claude_code_cli_config({"model": {"provider": "anthropic"}})


def test_extract_explicit_workdir(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    assert extract_explicit_workdir(f"클라라 리뷰해줘 {project}, diff 확인") == str(project)


def test_resolve_workdir_prefers_prompt_path(tmp_path):
    default = tmp_path / "default"
    explicit = tmp_path / "explicit"
    default.mkdir()
    explicit.mkdir()
    cfg = {"clara_cli": {"workdir": str(default)}}
    assert resolve_workdir(cfg, f"review {explicit}") == str(explicit)


def test_build_prompt_includes_write_authority_boundary():
    prompt = build_claude_prompt(
        message="테스트 실패 로그 분석해줘",
        context_prompt="ctx",
        channel_prompt="channel",
        history=[{"role": "user", "content": "이전 요청"}],
        workdir="/tmp/project",
        continuity_context="continuity packet",
    )
    assert "Clara/클라라" in prompt
    assert "same operational authority" in prompt
    assert "inspect, edit, run commands" in prompt
    assert "continuity packet" in prompt
    assert "테스트 실패 로그 분석해줘" in prompt
    assert "/tmp/project" in prompt


def test_build_prompt_in_clara_lead_overrides_hugo_channel_marker():
    prompt = build_claude_prompt(
        message="보고해줘",
        context_prompt="ctx",
        channel_prompt="Always start every Slack reply with '🟦 Hugo/휴고 — '",
        history=[],
        workdir="/tmp/project",
        role_mode="clara-lead",
    )
    assert "🟪 Clara/클라라 —" in prompt
    assert "Do not use the Hugo/휴고 marker" in prompt
    assert "🟦 Hugo/휴고 —" not in prompt


def test_build_continuity_context_reads_active_project_and_session_snippets(tmp_path):
    hermes_home = tmp_path / "hermes"
    hub = hermes_home / "wave-hub"
    hub.mkdir(parents=True)
    (hub / "current_context.json").write_text(
        json.dumps({
            "mode": "project",
            "scope": "project",
            "project_name": "WorkPilot_Commerce",
            "project_path": "/Users/392yes/project/001_WorkPilot_Commerce",
        }),
        encoding="utf-8",
    )
    con = sqlite3.connect(hermes_home / "state.db")
    con.executescript(
        """
        CREATE TABLE sessions (id TEXT PRIMARY KEY, title TEXT);
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY,
            session_id TEXT,
            role TEXT,
            content TEXT,
            timestamp REAL
        );
        CREATE VIRTUAL TABLE messages_fts USING fts5(content, content='messages', content_rowid='id');
        INSERT INTO sessions (id, title) VALUES ('s1', 'WPC order benchmark');
        INSERT INTO messages (id, session_id, role, content, timestamp)
        VALUES (1, 's1', 'assistant', 'WorkPilot_Commerce previous implementation decision', 100.0);
        INSERT INTO messages_fts(rowid, content) VALUES (1, 'WorkPilot_Commerce previous implementation decision');
        """
    )
    con.close()

    context = build_continuity_context(
        hermes_home=hermes_home,
        message="WorkPilot_Commerce 이어서 해줘",
        workdir="/Users/392yes/project/001_WorkPilot_Commerce",
    )
    assert "Mode-independent continuity context" in context
    assert "hugo-lead and clara-lead" in context
    assert "WorkPilot_Commerce" in context
    assert "WPC order benchmark" in context


def test_build_continuity_context_collapses_profile_home_to_canonical_root(tmp_path):
    canonical = tmp_path / ".hermes"
    profile_home = canonical / "profiles" / "wpcorderbot"
    (canonical / "wave-hub").mkdir(parents=True)
    profile_home.mkdir(parents=True)
    (canonical / "wave-hub" / "current_context.json").write_text(
        json.dumps({"mode": "project", "project_name": "WPC"}),
        encoding="utf-8",
    )

    context = build_continuity_context(
        hermes_home=profile_home,
        message="WPC 이어서",
        workdir=None,
    )
    assert f"Canonical Hermes home/session DB: {canonical}" in context
    assert "project_name: WPC" in context


def test_run_bridge_removes_anthropic_api_key_and_parses_noisy_json(tmp_path, monkeypatch):
    fake = tmp_path / "claude"
    fake.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        "assert 'ANTHROPIC_API_KEY' not in os.environ\n"
        "assert '--permission-mode' in sys.argv\n"
        "print('warn: noisy prefix')\n"
        "print(json.dumps({'type':'result','subtype':'success','is_error':False,'result':'OK'}))\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    workdir = tmp_path / "repo"
    workdir.mkdir()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "should-not-leak")
    result = run_claude_code_bridge_sync(
        config={
            "clara_cli": {
                "command": str(fake),
                "workdir": str(workdir),
                "allowed_tools": "Read",
                "max_turns": 1,
                "timeout_seconds": 10,
            }
        },
        message="ping",
        context_prompt=None,
        channel_prompt=None,
        history=[],
        hermes_home=tmp_path / "hermes",
    )
    assert result.exit_code == 0
    assert result.final_response.startswith("🟪 Clara/클라라 — OK")
    assert Path(result.log_dir, "result.json").exists()
    assert json.loads(Path(result.log_dir, "result.json").read_text())["result"] == "OK"


def test_run_bridge_does_not_duplicate_role_marker(tmp_path):
    # The model often emits the marker itself followed by a newline instead of
    # a trailing space; the bridge must still prepend exactly one marker.
    model_output = "🟪 Clara/클라라 —\n\n**결론: 준비 완료**"
    fake = tmp_path / "claude"
    fake.write_text(
        "#!/usr/bin/env python3\n"
        "import json\n"
        f"print(json.dumps({{'type':'result','subtype':'success','is_error':False,'result':{model_output!r}}}))\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    workdir = tmp_path / "repo"
    workdir.mkdir()
    result = run_claude_code_bridge_sync(
        config={
            "clara_cli": {
                "command": str(fake),
                "workdir": str(workdir),
                "allowed_tools": "Read",
                "max_turns": 1,
                "timeout_seconds": 10,
            }
        },
        message="ping",
        context_prompt=None,
        channel_prompt=None,
        history=[],
        hermes_home=tmp_path / "hermes",
    )
    assert result.exit_code == 0
    assert result.final_response.count("🟪 Clara/클라라 —") == 1
    assert result.final_response.startswith("🟪 Clara/클라라 — **결론: 준비 완료**")
