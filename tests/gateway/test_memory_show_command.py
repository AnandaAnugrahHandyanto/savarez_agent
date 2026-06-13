"""Routing tests for `/memory show` on the gateway.

The readout shares the `/memory` command with the write-approval flow that
already lives on main. These tests prove both flows coexist: a leading `show`
token reaches the readout, while bare `/memory` and the approval subcommands
still fall through to handle_pending_subcommand untouched. The readout's own
formatting/parsing is covered in tests/tools/test_memory_{readout,format}.py.
"""

import pytest

from gateway.config import Platform
from gateway.platforms.base import MessageEvent
from gateway.session import SessionSource


def _event(text: str, platform: Platform = Platform.TELEGRAM) -> MessageEvent:
    source = SessionSource(
        platform=platform,
        user_id="u1",
        chat_id="c1",
        user_name="tester",
        chat_type="dm",
    )
    return MessageEvent(text=text, source=source, message_id="m1")


def _runner():
    from gateway.run import GatewayRunner

    # The `show` branch returns before any session/config machinery, so an
    # uninitialised runner is enough for the readout path. The fallthrough
    # test stubs the one collaborator it needs.
    return object.__new__(GatewayRunner)


@pytest.fixture()
def memdir(tmp_path, monkeypatch):
    """Point the store at an empty tmp dir and pin configured limits."""
    monkeypatch.setattr("tools.memory_tool.get_memory_dir", lambda: tmp_path)
    monkeypatch.setattr(
        "hermes_cli.config.load_config",
        lambda: {"memory": {"memory_char_limit": 500, "user_char_limit": 300}},
    )
    return tmp_path


@pytest.mark.asyncio
async def test_show_routes_to_readout(memdir):
    out = await _runner()._handle_memory_command(_event("/memory show"))
    # Markdown readout renders both sections.
    assert "── MEMORY ──" in out
    assert "── USER PROFILE ──" in out


@pytest.mark.asyncio
async def test_show_user_target_only(memdir):
    out = await _runner()._handle_memory_command(_event("/memory show user"))
    assert "── USER PROFILE ──" in out
    assert "── MEMORY ──" not in out


@pytest.mark.asyncio
async def test_show_reports_configured_limits(memdir):
    out = await _runner()._handle_memory_command(_event("/memory show memory"))
    # 500-char limit comes from the pinned config, not the 2200 default.
    assert "/500" in out


@pytest.mark.asyncio
async def test_show_unknown_target_errors(memdir):
    out = await _runner()._handle_memory_command(_event("/memory show bogus"))
    assert "bogus" in out
    assert "── MEMORY ──" not in out


@pytest.mark.asyncio
async def test_bare_memory_falls_through_to_approval(memdir, monkeypatch):
    import hermes_cli.write_approval_commands as wac

    seen = {}

    def _fake_pending(subsystem, args, **kwargs):
        seen["args"] = args
        return "APPROVAL-FLOW"

    monkeypatch.setattr(wac, "handle_pending_subcommand", _fake_pending)

    runner = _runner()
    runner._session_key_for_source = lambda _source: "k"

    out = await runner._handle_memory_command(_event("/memory"))
    assert out == "APPROVAL-FLOW"
    assert seen["args"] == []  # no `show` token reached the approval handler


@pytest.mark.asyncio
async def test_pending_subcommand_falls_through_to_approval(memdir, monkeypatch):
    import hermes_cli.write_approval_commands as wac

    seen = {}

    def _fake_pending(subsystem, args, **kwargs):
        seen["args"] = args
        return "APPROVAL-FLOW"

    monkeypatch.setattr(wac, "handle_pending_subcommand", _fake_pending)

    runner = _runner()
    runner._session_key_for_source = lambda _source: "k"

    out = await runner._handle_memory_command(_event("/memory pending"))
    assert out == "APPROVAL-FLOW"
    assert seen["args"] == ["pending"]
