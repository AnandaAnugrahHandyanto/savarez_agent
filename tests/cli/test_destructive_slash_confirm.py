"""Tests for cli.HermesCLI._confirm_destructive_slash.

Drives the helper directly via __get__ on a SimpleNamespace stand-in so we
don't have to construct a full HermesCLI (which requires extensive setup).
"""

from __future__ import annotations

import threading
from types import SimpleNamespace
from unittest.mock import patch


def _bound(fn, instance):
    """Bind an unbound method to a stand-in instance."""
    return fn.__get__(instance, type(instance))


def _make_self(prompt_response):
    """Build a minimal stand-in 'self' for _confirm_destructive_slash."""
    return SimpleNamespace(
        _app=None,
        _prompt_text_input=lambda _prompt: prompt_response,
    )


def test_gate_off_returns_once_without_prompting():
    """When approvals.destructive_slash_confirm is False, return 'once'
    immediately (caller proceeds without showing a prompt)."""
    from cli import HermesCLI

    self_ = _make_self(prompt_response="should not be called")

    with patch(
        "cli.load_cli_config",
        return_value={"approvals": {"destructive_slash_confirm": False}},
    ):
        result = _bound(HermesCLI._confirm_destructive_slash, self_)(
            "clear", "detail",
        )

    assert result == "once"


def test_gate_on_choice_once_returns_once():
    """When the gate is on and the user picks '1', return 'once'."""
    from cli import HermesCLI

    self_ = _make_self(prompt_response="1")

    with patch(
        "cli.load_cli_config",
        return_value={"approvals": {"destructive_slash_confirm": True}},
    ):
        result = _bound(HermesCLI._confirm_destructive_slash, self_)(
            "clear", "detail",
        )

    assert result == "once"


def test_gate_on_choice_cancel_returns_none():
    """When the user picks '3' (cancel), return None — caller must abort."""
    from cli import HermesCLI

    self_ = _make_self(prompt_response="3")

    with patch(
        "cli.load_cli_config",
        return_value={"approvals": {"destructive_slash_confirm": True}},
    ):
        result = _bound(HermesCLI._confirm_destructive_slash, self_)(
            "clear", "detail",
        )

    assert result is None


def test_gate_on_no_input_returns_none():
    """No input (None / EOF / Ctrl-C) treated as cancel."""
    from cli import HermesCLI

    self_ = _make_self(prompt_response=None)

    with patch(
        "cli.load_cli_config",
        return_value={"approvals": {"destructive_slash_confirm": True}},
    ):
        result = _bound(HermesCLI._confirm_destructive_slash, self_)(
            "clear", "detail",
        )

    assert result is None


def test_gate_on_unknown_choice_returns_none():
    """Garbage input is treated as cancel — fail safe, don't destroy state."""
    from cli import HermesCLI

    self_ = _make_self(prompt_response="maybe")

    with patch(
        "cli.load_cli_config",
        return_value={"approvals": {"destructive_slash_confirm": True}},
    ):
        result = _bound(HermesCLI._confirm_destructive_slash, self_)(
            "clear", "detail",
        )

    assert result is None


def test_gate_on_choice_always_persists_and_returns_always():
    """User picks 'always' → returns 'always' AND
    save_config_value('approvals.destructive_slash_confirm', False) was called."""
    from cli import HermesCLI

    self_ = _make_self(prompt_response="2")

    saves = []

    def _fake_save(key, value):
        saves.append((key, value))
        return True

    with patch(
        "cli.load_cli_config",
        return_value={"approvals": {"destructive_slash_confirm": True}},
    ), patch("cli.save_config_value", _fake_save):
        result = _bound(HermesCLI._confirm_destructive_slash, self_)(
            "clear", "detail",
        )

    assert result == "always"
    assert ("approvals.destructive_slash_confirm", False) in saves


def test_gate_default_true_when_config_missing():
    """If load_cli_config raises or returns malformed data, treat as
    'gate on' (default safe) — must prompt."""
    from cli import HermesCLI

    self_ = _make_self(prompt_response="3")  # cancel

    with patch("cli.load_cli_config", side_effect=Exception("boom")):
        result = _bound(HermesCLI._confirm_destructive_slash, self_)(
            "clear", "detail",
        )

    # Got prompted (returned None from cancel) — meaning the gate was
    # treated as on despite the config error.  If the gate had been off
    # this would have returned 'once' without consulting the prompt.
    assert result is None


def test_prompting_slash_commands_use_worker_queue():
    """Destructive slash commands should not run inline in prompt_toolkit mode.

    The worker path now uses the native approval panel, leaving the UI thread
    free to capture numbered approval keystrokes.  Running inline regressed on
    newer prompt_toolkit because run_in_terminal returns an awaitable.
    """
    from cli import HermesCLI

    self_ = SimpleNamespace()
    should_inline = _bound(HermesCLI._should_handle_prompting_command_inline, self_)

    assert should_inline("/clear") is False
    assert should_inline("/new") is False
    assert should_inline("/reset") is False
    assert should_inline("/undo") is False
    assert should_inline("/reload-mcp") is False


def test_non_prompting_slash_commands_still_use_normal_queue():
    from cli import HermesCLI

    self_ = SimpleNamespace()
    should_inline = _bound(HermesCLI._should_handle_prompting_command_inline, self_)

    assert should_inline("/help") is False
    assert should_inline("/model") is False
    assert should_inline("hello") is False
    assert should_inline("/clear", has_images=True) is False


def test_prompt_toolkit_worker_uses_approval_panel_for_clear():
    """When a TUI app is active on the worker thread, use approval UI.

    This is the regression path for /clear: process_loop runs on a daemon
    thread, and the main prompt_toolkit thread must remain available to handle
    the user's 1/2/3 selection.
    """
    from cli import HermesCLI

    calls = []
    self_ = SimpleNamespace(
        _app=object(),
        _approval_callback=lambda command, detail, allow_permanent=True, choices=None: calls.append(
            (command, detail, allow_permanent, choices)
        ) or "once",
        _prompt_text_input=lambda _prompt: (_ for _ in ()).throw(
            AssertionError("legacy input prompt should not run in TUI worker path")
        ),
    )
    result_holder = []

    def _run():
        with patch(
            "cli.load_cli_config",
            return_value={"approvals": {"destructive_slash_confirm": True}},
        ):
            result_holder.append(
                _bound(HermesCLI._confirm_destructive_slash, self_)("clear", "detail")
            )

    t = threading.Thread(target=_run)
    t.start()
    t.join(timeout=2)

    assert not t.is_alive()
    assert result_holder == ["once"]
    assert calls == [("/clear", "detail", True, ["once", "always", "deny"])]
