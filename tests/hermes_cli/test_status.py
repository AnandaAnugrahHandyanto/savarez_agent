from types import SimpleNamespace
from unittest.mock import MagicMock

from hermes_cli import status as status_mod
from hermes_cli.status import show_status


def test_show_status_includes_tavily_key(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-1234567890abcdef")

    show_status(SimpleNamespace(all=False, deep=False))

    output = capsys.readouterr().out
    assert "Tavily" in output
    assert "tvly...cdef" in output


def test_resolve_anthropic_key_for_status_logs_warning_and_falls_back(monkeypatch):
    warning = MagicMock()
    monkeypatch.setattr(status_mod.logger, "warning", warning)
    monkeypatch.setattr(
        "agent.anthropic_adapter.resolve_anthropic_token",
        lambda: (_ for _ in ()).throw(RuntimeError("bad creds")),
    )
    monkeypatch.setattr(
        status_mod,
        "get_env_value",
        lambda name: "sk-ant-api03-fallback" if name == "ANTHROPIC_API_KEY" else "",
        raising=False,
    )

    resolved = status_mod._resolve_anthropic_key_for_status()

    assert resolved == "sk-ant-api03-fallback"
    warning.assert_called_once()
    assert "Failed to resolve Anthropic credentials in status" in warning.call_args.args[0]
    assert warning.call_args.kwargs["exc_info"] is True
