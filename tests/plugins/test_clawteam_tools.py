"""Tests for the bundled ClawTeam Hermes plugin tools."""

import json

from plugins.clawteam import tools


def _decode(payload: str):
    return json.loads(payload)


def test_cleanup_tool_is_registered_for_out_of_box_issue_team_cleanup():
    names = [name for name, _schema, _handler in tools.TOOLS]

    assert "clawteam_team_cleanup" in names


def test_cleanup_tool_uses_force_cleanup_command(monkeypatch):
    calls = []

    def fake_run(*args):
        calls.append(args)
        return {"removed": True}

    monkeypatch.setattr(tools, "run_clawteam_json", fake_run)

    cleanup = next(handler for name, _schema, handler in tools.TOOLS if name == "clawteam_team_cleanup")
    result = _decode(cleanup({"team": "issue-54-fix"}))

    assert calls == [("team", "cleanup", "issue-54-fix", "--force")]
    assert result["cleaned"] == {"removed": True}
    assert result["team"] == "issue-54-fix"
