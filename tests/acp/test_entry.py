"""Tests for acp_adapter.entry startup wiring."""

import logging

import acp
import pytest

from acp_adapter import entry


def test_main_enables_unstable_protocol(monkeypatch):
    calls = {}

    async def fake_run_agent(agent, **kwargs):
        calls["kwargs"] = kwargs

    monkeypatch.setattr(entry, "_setup_logging", lambda: None)
    monkeypatch.setattr(entry, "_load_env", lambda: None)
    monkeypatch.setattr(acp, "run_agent", fake_run_agent)

    entry.main()

    assert calls["kwargs"]["use_unstable_protocol"] is True


def test_main_forwards_skills_to_agent(monkeypatch):
    """``hermes -s foo,bar acp`` reaches ``HermesACPAgent`` as default_skills."""
    captured = {}

    async def fake_run_agent(agent, **_kwargs):
        captured["agent"] = agent

    def fake_resolve(skills, _logger):
        captured["raw_skills"] = skills
        return ["foo", "bar"]

    monkeypatch.setattr(entry, "_setup_logging", lambda: None)
    monkeypatch.setattr(entry, "_load_env", lambda: None)
    monkeypatch.setattr(entry, "_resolve_default_skills", fake_resolve)
    monkeypatch.setattr(acp, "run_agent", fake_run_agent)

    entry.main(skills=["foo,bar"])

    assert captured["raw_skills"] == ["foo,bar"]
    agent = captured["agent"]
    assert agent.session_manager._default_skills == ["foo", "bar"]


def test_main_passes_none_skills_when_unused(monkeypatch):
    """Default invocation must still produce a SessionManager with no skills."""
    captured = {}

    async def fake_run_agent(agent, **_kwargs):
        captured["agent"] = agent

    monkeypatch.setattr(entry, "_setup_logging", lambda: None)
    monkeypatch.setattr(entry, "_load_env", lambda: None)
    monkeypatch.setattr(acp, "run_agent", fake_run_agent)

    entry.main()

    assert captured["agent"].session_manager._default_skills == []


def test_resolve_default_skills_returns_empty_for_none():
    assert entry._resolve_default_skills(None, logging.getLogger("test")) == []
    assert entry._resolve_default_skills("", logging.getLogger("test")) == []


def test_resolve_default_skills_exits_on_unknown_skill(monkeypatch, capsys):
    """Unknown skill names cause sys.exit(1) so editor clients see the error."""
    monkeypatch.setattr(
        "agent.skill_commands.build_preloaded_skills_prompt",
        lambda parsed, task_id=None: ("", [], ["does-not-exist"]),
    )

    with pytest.raises(SystemExit) as excinfo:
        entry._resolve_default_skills("does-not-exist", logging.getLogger("test"))

    assert excinfo.value.code == 1
    err = capsys.readouterr().err
    assert "Unknown skill(s)" in err
    assert "does-not-exist" in err
