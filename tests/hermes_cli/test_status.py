import json
from types import SimpleNamespace

from hermes_cli.status import show_status


def test_show_status_includes_tavily_key(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-1234567890abcdef")

    show_status(SimpleNamespace(all=False, deep=False))

    output = capsys.readouterr().out
    assert "Tavily" in output
    assert "tvly...cdef" in output


def test_show_status_json_emits_bootstrap_snapshot(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-1234567890")

    show_status(SimpleNamespace(all=False, deep=False, json=True))

    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == 1
    assert payload["providers"]["readiness"]["configured"] is True
    assert "bootstrap" in payload
    assert "recommended_next_steps" in payload["bootstrap"]
