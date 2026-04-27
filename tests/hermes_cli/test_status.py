from types import SimpleNamespace
from unittest.mock import patch

from hermes_cli.status import _health_reason, _overall_health_grade, show_status


def test_overall_health_grade_levels():
    assert _overall_health_grade(inference_ready=True, inference_blocked=False, api_key_count=0, platform_count=1, active_jobs=0) == "healthy"
    assert _overall_health_grade(inference_ready=False, inference_blocked=True, api_key_count=0, platform_count=0, active_jobs=0) == "blocked"
    assert _overall_health_grade(inference_ready=True, inference_blocked=False, api_key_count=0, platform_count=0, active_jobs=0) == "degraded"
    assert _overall_health_grade(inference_ready=False, inference_blocked=False, api_key_count=0, platform_count=0, active_jobs=0) == "needs_setup"


def test_health_reason_levels():
    assert _health_reason(grade="healthy", inference_ready=True, inference_blocked=False, api_key_count=0, platform_count=1, active_jobs=1) == "inference OK, messaging configured, and automation running"
    assert _health_reason(grade="blocked", inference_ready=False, inference_blocked=True, api_key_count=0, platform_count=0, active_jobs=0) == "configured inference path exists, but auth/runtime access is unavailable"


def test_show_status_includes_tavily_key(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-1...cdef")

    show_status(SimpleNamespace(all=False, deep=False))

    output = capsys.readouterr().out
    assert "Quick Summary" in output
    assert "Health:" in output
    assert "Reason:" in output
    assert "Degraded" in output
    assert "API Access:" in output
    assert "Tavily" in output
    assert "tvly...cdef" in output


def test_show_status_surfaces_repo_context_capability(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    with patch(
        "hermes_cli.status._get_repo_context_capability_summary",
        return_value=[
            {
                "name": "mcp_claude_context_index_codebase",
                "group": "mcp-claude-context",
                "readiness_status": "ready",
                "identity_scope": "absolute_path",
                "workflow": "index/status/search/clear",
                "result_mode": "partial_or_complete",
            }
        ],
    ):
        show_status(SimpleNamespace(all=False, deep=False))

    output = capsys.readouterr().out
    assert "Repo Context" in output
    assert "mcp_claude_context_index_codebase" in output
    assert "absolute_path" in output
    assert "index/status/search/clear" in output


def test_show_status_termux_gateway_section_skips_systemctl(monkeypatch, capsys, tmp_path):
    from hermes_cli import status as status_mod
    import hermes_cli.auth as auth_mod
    import hermes_cli.gateway as gateway_mod

    monkeypatch.setenv("TERMUX_VERSION", "0.118.3")
    monkeypatch.setenv("PREFIX", "/data/data/com.termux/files/usr")
    monkeypatch.setattr(status_mod, "get_env_path", lambda: tmp_path / ".env", raising=False)
    monkeypatch.setattr(status_mod, "get_hermes_home", lambda: tmp_path, raising=False)
    monkeypatch.setattr(status_mod, "load_config", lambda: {"model": "gpt-5.4"}, raising=False)
    monkeypatch.setattr(status_mod, "resolve_requested_provider", lambda requested=None: "openai-codex", raising=False)
    monkeypatch.setattr(status_mod, "resolve_provider", lambda requested=None, **kwargs: "openai-codex", raising=False)
    monkeypatch.setattr(status_mod, "provider_label", lambda provider: "OpenAI Codex", raising=False)
    monkeypatch.setattr(auth_mod, "get_nous_auth_status", lambda: {}, raising=False)
    monkeypatch.setattr(auth_mod, "get_codex_auth_status", lambda: {}, raising=False)
    monkeypatch.setattr(gateway_mod, "find_gateway_pids", lambda exclude_pids=None: [], raising=False)

    def _unexpected_systemctl(*args, **kwargs):
        raise AssertionError("systemctl should not be called in the Termux status view")

    monkeypatch.setattr(status_mod.subprocess, "run", _unexpected_systemctl)

    status_mod.show_status(SimpleNamespace(all=False, deep=False))

    output = capsys.readouterr().out
    assert "Manager:      Termux / manual process" in output
    assert "Start with:   hermes gateway" in output
    assert "systemd (user)" not in output


def test_show_status_reports_nous_auth_error(monkeypatch, capsys, tmp_path):
    from hermes_cli import status as status_mod
    import hermes_cli.auth as auth_mod
    import hermes_cli.gateway as gateway_mod

    monkeypatch.setattr(status_mod, "get_env_path", lambda: tmp_path / ".env", raising=False)
    monkeypatch.setattr(status_mod, "get_hermes_home", lambda: tmp_path, raising=False)
    monkeypatch.setattr(status_mod, "load_config", lambda: {"model": "gpt-5.4"}, raising=False)
    monkeypatch.setattr(status_mod, "resolve_requested_provider", lambda requested=None: "openai-codex", raising=False)
    monkeypatch.setattr(status_mod, "resolve_provider", lambda requested=None, **kwargs: "openai-codex", raising=False)
    monkeypatch.setattr(status_mod, "provider_label", lambda provider: "OpenAI Codex", raising=False)
    monkeypatch.setattr(
        auth_mod,
        "get_nous_auth_status",
        lambda: {
            "logged_in": False,
            "portal_base_url": "https://portal.nousresearch.com",
            "access_expires_at": "2026-04-20T01:00:51+00:00",
            "agent_key_expires_at": "2026-04-20T04:54:24+00:00",
            "has_refresh_token": True,
            "error": "Refresh session has been revoked",
        },
        raising=False,
    )
    monkeypatch.setattr(auth_mod, "get_codex_auth_status", lambda: {}, raising=False)
    monkeypatch.setattr(auth_mod, "get_qwen_auth_status", lambda: {}, raising=False)
    monkeypatch.setattr(gateway_mod, "find_gateway_pids", lambda exclude_pids=None: [], raising=False)

    status_mod.show_status(SimpleNamespace(all=False, deep=False))

    output = capsys.readouterr().out
    assert "Nous Portal   ✗ not logged in (run: hermes auth add nous --type oauth)" in output
    assert "Error:      Refresh session has been revoked" in output
    assert "Access exp:" in output
    assert "Key exp:" in output
