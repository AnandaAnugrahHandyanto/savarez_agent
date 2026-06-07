"""Non-live gateway fixture tests for a future `/beast` command.

These tests prove the Hermes gateway command-hook boundary only.  They do not
register `/beast` live, call Telegram, write AI Beast registries/bindings, or
execute AI Beast side effects.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from gateway.config import GatewayConfig, Platform, PlatformConfig
from gateway.platforms.base import MessageEvent
from gateway.session import SessionEntry, SessionSource, build_session_key


READ_ONLY_BEAST_SUBCOMMANDS = {
    "whereami": "beast fixture: whereami (read-only)",
    "projects": "beast fixture: projects (read-only)",
    "sessions interaction-routing-layer": (
        "beast fixture: sessions interaction-routing-layer (read-only metadata)"
    ),
}
STATE_CHANGING_BEAST_SUBCOMMANDS = (
    "task create demo",
    "steer route demo",
    "bindtopic interaction-routing-layer",
    "move project elsewhere",
)
FORBIDDEN_SYSTEMS = (
    "bindings_created",
    "registry_json_written",
    "routing_performed",
    "inbox_persisted",
    "audit_written",
    "memory_written",
    "kanban_mutated",
    "durable_continuation_invoked",
    "telegram_catalogue_edited",
    "live_service_called",
)


class BeastFixtureSideEffects:
    """Tripwires for systems the non-live fixture must not touch."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def record(self, name: str) -> None:
        self.calls.append(name)


@pytest.fixture
def beast_side_effects() -> BeastFixtureSideEffects:
    return BeastFixtureSideEffects()


def _make_source() -> SessionSource:
    return SessionSource(
        platform=Platform.TELEGRAM,
        user_id="u1",
        chat_id="c1",
        user_name="tester",
        chat_type="dm",
    )


def _make_event(text: str) -> MessageEvent:
    return MessageEvent(text=text, source=_make_source(), message_id="m1")


def _make_runner():
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner.config = GatewayConfig(
        platforms={Platform.TELEGRAM: PlatformConfig(enabled=True, token="***")}
    )
    runner.config.command_hook_commands = {
        "beast": {"description": "AI Beast non-live fixture command"}
    }
    adapter = MagicMock()
    adapter.send = AsyncMock()
    runner.adapters = {Platform.TELEGRAM: adapter}
    runner._voice_mode = {}
    runner.hooks = SimpleNamespace(
        emit=AsyncMock(),
        emit_collect=AsyncMock(return_value=[]),
        loaded_hooks=False,
    )

    session_entry = SessionEntry(
        session_key=build_session_key(_make_source()),
        session_id="sess-1",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        platform=Platform.TELEGRAM,
        chat_type="dm",
    )
    runner.session_store = MagicMock()
    runner.session_store.get_or_create_session.return_value = session_entry
    runner.session_store.load_transcript.return_value = []
    runner.session_store.has_any_sessions.return_value = True
    runner.session_store.append_to_transcript = MagicMock()
    runner.session_store.rewrite_transcript = MagicMock()
    runner.session_store.update_session = MagicMock()
    runner._running_agents = {}
    runner._pending_messages = {}
    runner._pending_approvals = {}
    runner._session_db = None
    runner._reasoning_config = None
    runner._provider_routing = {}
    runner._fallback_model = None
    runner._show_reasoning = False
    runner._is_user_authorized = lambda _source: True
    runner._set_session_env = lambda _context: None
    runner._should_send_voice_reply = lambda *_args, **_kwargs: False
    runner._send_voice_reply = AsyncMock()
    runner._capture_gateway_honcho_if_configured = lambda *args, **kwargs: None
    runner._emit_gateway_run_progress = AsyncMock()
    return runner


async def _install_non_live_beast_fixture_hook(
    runner, side_effects: BeastFixtureSideEffects
) -> list[dict[str, str]]:
    hook_calls: list[dict[str, str]] = []

    async def _emit_collect(event_type, ctx):
        if event_type != "command:beast":
            return []
        subcommand = str(ctx.get("raw_args", "")).strip()
        hook_calls.append(
            {
                "event_type": event_type,
                "command": str(ctx.get("command", "")),
                "raw_args": subcommand,
            }
        )
        for forbidden_system in FORBIDDEN_SYSTEMS:
            assert forbidden_system not in side_effects.calls
        if subcommand in READ_ONLY_BEAST_SUBCOMMANDS:
            return [
                {
                    "decision": "handled",
                    "message": READ_ONLY_BEAST_SUBCOMMANDS[subcommand],
                }
            ]
        return [
            {
                "decision": "deny",
                "message": f"beast fixture denied: {subcommand or '<missing>'}",
            }
        ]

    runner.hooks.emit_collect = AsyncMock(side_effect=_emit_collect)
    return hook_calls


def _patch_runtime(monkeypatch) -> None:
    import gateway.run as gateway_run

    monkeypatch.setattr(
        gateway_run, "_resolve_runtime_agent_kwargs", lambda: {"api_key": "***"}
    )


def _assert_no_forbidden_side_effects(side_effects: BeastFixtureSideEffects) -> None:
    assert side_effects.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("/beast whereami", READ_ONLY_BEAST_SUBCOMMANDS["whereami"]),
        ("/beast projects", READ_ONLY_BEAST_SUBCOMMANDS["projects"]),
        (
            "/beast sessions interaction-routing-layer",
            READ_ONLY_BEAST_SUBCOMMANDS["sessions interaction-routing-layer"],
        ),
    ],
)
async def test_beast_read_only_fixture_commands_reach_command_hook_without_agent(
    monkeypatch, beast_side_effects, message, expected
):
    """Configured /beast read-only fixture commands are hook-only dispatchable."""
    _patch_runtime(monkeypatch)
    runner = _make_runner()
    runner._run_agent = AsyncMock(
        side_effect=AssertionError("/beast fixture command leaked to the agent")
    )
    hook_calls = await _install_non_live_beast_fixture_hook(runner, beast_side_effects)

    result = await runner._handle_message(_make_event(message))

    assert result == expected
    runner._run_agent.assert_not_called()
    assert hook_calls == [
        {
            "event_type": "command:beast",
            "command": "beast",
            "raw_args": message.removeprefix("/beast").strip(),
        }
    ]
    _assert_no_forbidden_side_effects(beast_side_effects)


@pytest.mark.asyncio
@pytest.mark.parametrize("message", ["/beast unknown", "/beast", "/beast   "])
async def test_beast_unknown_or_malformed_fixture_input_fails_closed(
    monkeypatch, beast_side_effects, message
):
    """Malformed or unsupported /beast input is denied by the fixture hook."""
    _patch_runtime(monkeypatch)
    runner = _make_runner()
    runner._run_agent = AsyncMock(
        side_effect=AssertionError("denied /beast fixture command leaked to the agent")
    )
    await _install_non_live_beast_fixture_hook(runner, beast_side_effects)

    result = await runner._handle_message(_make_event(message))

    assert result is not None
    assert result.startswith("beast fixture denied:")
    runner._run_agent.assert_not_called()
    _assert_no_forbidden_side_effects(beast_side_effects)


@pytest.mark.asyncio
@pytest.mark.parametrize("subcommand", STATE_CHANGING_BEAST_SUBCOMMANDS)
async def test_beast_state_changing_fixture_subcommands_are_denied_not_executed(
    monkeypatch, beast_side_effects, subcommand
):
    """State-changing /beast forms fail closed and touch no mutation systems."""
    _patch_runtime(monkeypatch)
    runner = _make_runner()
    runner._run_agent = AsyncMock(
        side_effect=AssertionError("state-changing /beast command leaked to the agent")
    )
    await _install_non_live_beast_fixture_hook(runner, beast_side_effects)

    result = await runner._handle_message(_make_event(f"/beast {subcommand}"))

    assert result == f"beast fixture denied: {subcommand}"
    runner._run_agent.assert_not_called()
    _assert_no_forbidden_side_effects(beast_side_effects)


@pytest.mark.asyncio
async def test_beast_fixture_does_not_hijack_status_or_sessions(
    monkeypatch, beast_side_effects
):
    """Hermes-owned command names never route to the /beast fixture hook."""
    _patch_runtime(monkeypatch)
    runner = _make_runner()
    runner._handle_status_command = AsyncMock(return_value="status: ok")
    runner._run_agent = AsyncMock(return_value="sessions handled by Hermes fallback")
    await _install_non_live_beast_fixture_hook(runner, beast_side_effects)

    status_result = await runner._handle_message(_make_event("/status"))
    sessions_result = await runner._handle_message(_make_event("/sessions"))

    assert status_result == "status: ok"
    assert sessions_result is not None
    assert "beast fixture" not in sessions_result
    assert "Unknown command" not in sessions_result
    runner._handle_status_command.assert_awaited_once()
    emitted_events = [call.args[0] for call in runner.hooks.emit_collect.await_args_list]
    assert "command:beast" not in emitted_events
    _assert_no_forbidden_side_effects(beast_side_effects)


@pytest.mark.asyncio
@pytest.mark.parametrize("message", ["/task", "/steer"])
async def test_beast_fixture_does_not_change_top_level_task_or_steer_boundaries(
    monkeypatch, beast_side_effects, message
):
    """Top-level /task and /steer remain Hermes-owned or unavailable, not /beast."""
    _patch_runtime(monkeypatch)
    runner = _make_runner()
    runner._run_agent = AsyncMock(
        side_effect=AssertionError(f"{message} leaked to the agent")
    )
    await _install_non_live_beast_fixture_hook(runner, beast_side_effects)

    result = await runner._handle_message(_make_event(message))

    assert result is not None
    assert "beast fixture" not in result
    runner._run_agent.assert_not_called()
    emitted_events = [call.args[0] for call in runner.hooks.emit_collect.await_args_list]
    assert "command:beast" not in emitted_events
    _assert_no_forbidden_side_effects(beast_side_effects)


@pytest.mark.asyncio
async def test_beast_fixture_without_hook_returns_registered_hook_guidance(
    monkeypatch, beast_side_effects
):
    """The fixture does not wire live /beast; without a hook it is not handled."""
    _patch_runtime(monkeypatch)
    runner = _make_runner()
    runner._run_agent = AsyncMock(
        side_effect=AssertionError("unhandled /beast command leaked to the agent")
    )
    runner.hooks.emit_collect = AsyncMock(return_value=[])

    result = await runner._handle_message(_make_event("/beast whereami"))

    assert result is not None
    assert "registered for command hooks" in result
    assert "/beast" in result
    runner._run_agent.assert_not_called()
    runner.hooks.emit_collect.assert_awaited_once()
    _assert_no_forbidden_side_effects(beast_side_effects)
