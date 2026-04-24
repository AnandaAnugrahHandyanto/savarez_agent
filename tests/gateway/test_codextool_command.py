import threading
from types import SimpleNamespace

import pytest

import gateway.run as gateway_run
from gateway.config import Platform
from gateway.platforms.base import MessageEvent
from gateway.session import SessionSource


def _make_runner():
    runner = object.__new__(gateway_run.GatewayRunner)
    runner.adapters = {}
    runner._ephemeral_system_prompt = ""
    runner._prefill_messages = []
    runner._reasoning_config = None
    runner._service_tier = None
    runner._provider_routing = {}
    runner._fallback_model = None
    runner._running_agents = {}
    runner._pending_model_notes = {}
    runner._session_db = None
    runner._agent_cache = {}
    runner._agent_cache_lock = threading.Lock()
    runner._session_model_overrides = {}
    runner.hooks = SimpleNamespace(loaded_hooks=False, emit=lambda *a, **k: None)
    runner.config = SimpleNamespace(streaming=None)
    runner.session_store = SimpleNamespace(
        get_or_create_session=lambda source: SimpleNamespace(session_id="session-1", session_key="agent:main:telegram:dm:12345"),
        load_transcript=lambda session_id: [],
    )
    return runner


def _make_event(text: str) -> MessageEvent:
    source = SessionSource(
        platform=Platform.TELEGRAM,
        chat_id="12345",
        chat_type="dm",
        user_id="user-1",
    )
    return MessageEvent(text=text, source=source, message_id="m1")


@pytest.mark.asyncio
async def test_gateway_codextool_usage_when_no_args():
    runner = _make_runner()

    result = await runner._handle_codextool_command(_make_event("/codexTool"))

    assert "Usage: /codexTool" in result
    assert "watch" in result


@pytest.mark.asyncio
async def test_gateway_codextool_returns_stdout_block():
    runner = _make_runner()
    runner._run_codextool_gateway = lambda argv: (0, '{"ok": true}\n', "")

    result = await runner._handle_codextool_command(_make_event("/codexTool probe --json"))

    assert '{"ok": true}' in result
    assert "```" in result


@pytest.mark.asyncio
async def test_gateway_command_router_includes_codextool_branch():
    text = (gateway_run.Path(gateway_run.__file__).read_text(encoding="utf-8"))

    assert 'if canonical == "codextool":' in text
    assert 'return await self._handle_codextool_command(event)' in text


@pytest.mark.asyncio
async def test_gateway_codextool_dispatches_watch_subcommand():
    runner = _make_runner()
    calls = []
    runner._run_codextool_gateway = lambda argv: calls.append(argv) or (0, "ok\n", "")

    result = await runner._handle_codextool_command(_make_event("/codexTool watch --once --skip-request"))

    assert calls == [["watch", "--once", "--skip-request"]]
    assert "ok" in result
