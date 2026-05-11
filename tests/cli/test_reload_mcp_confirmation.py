"""Tests for ``HermesCLI._confirm_and_reload_mcp`` non-interactive safety."""

from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import patch


def _bound(fn, instance):
    return fn.__get__(instance, type(instance))


def _make_self(prompt_response="1"):
    calls = {"reload": 0, "prompt": 0, "busy": 0}

    def _reload():
        calls["reload"] += 1

    def _prompt(_text):
        calls["prompt"] += 1
        return prompt_response

    def _busy(_status):
        calls["busy"] += 1
        return nullcontext()

    self_ = SimpleNamespace(
        _app=None,
        _reload_mcp=_reload,
        _prompt_text_input=_prompt,
        _busy_command=_busy,
        _slow_command_status=lambda cmd: f"status:{cmd}",
    )
    return self_, calls


def test_reload_mcp_now_bypasses_confirmation():
    from cli import HermesCLI

    self_, calls = _make_self(prompt_response="3")

    with patch(
        "cli.load_cli_config",
        return_value={"approvals": {"mcp_reload_confirm": True}},
    ):
        _bound(HermesCLI._confirm_and_reload_mcp, self_)("/reload-mcp now")

    assert calls == {"reload": 1, "prompt": 0, "busy": 1}


def test_reload_mcp_always_persists_opt_out_and_reloads():
    from cli import HermesCLI

    self_, calls = _make_self(prompt_response="3")
    saves = []

    def _fake_save(key, value):
        saves.append((key, value))
        return True

    with patch(
        "cli.load_cli_config",
        return_value={"approvals": {"mcp_reload_confirm": True}},
    ), patch("cli.save_config_value", side_effect=_fake_save):
        _bound(HermesCLI._confirm_and_reload_mcp, self_)("/reload-mcp always")

    assert ("approvals.mcp_reload_confirm", False) in saves
    assert calls == {"reload": 1, "prompt": 0, "busy": 1}


def test_reload_mcp_noninteractive_context_warns_instead_of_blocking(capsys):
    from cli import HermesCLI

    self_, calls = _make_self(prompt_response="1")

    fake_stdin = SimpleNamespace(isatty=lambda: False)

    with patch(
        "cli.load_cli_config",
        return_value={"approvals": {"mcp_reload_confirm": True}},
    ), patch("sys.stdin", fake_stdin):
        _bound(HermesCLI._confirm_and_reload_mcp, self_)("/reload-mcp")

    output = capsys.readouterr().out
    assert "non-interactive" in output
    assert "/reload-mcp now" in output
    assert calls == {"reload": 0, "prompt": 0, "busy": 0}
