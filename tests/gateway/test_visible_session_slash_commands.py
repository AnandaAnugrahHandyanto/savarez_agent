"""Slash command tests for visible Telegram topic delegates."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from gateway.config import Platform
from gateway.platforms.base import MessageEvent
from gateway.run import GatewayRunner
from gateway.session import SessionSource
from gateway.visible_sessions import parse_prompt_topic_args, parse_spawn_topic_args
from hermes_cli.commands import GATEWAY_KNOWN_COMMANDS, resolve_command


PARENT_CHAT = "-1003933169427"


def _event(text: str) -> MessageEvent:
    return MessageEvent(
        text=text,
        source=SessionSource(
            platform=Platform.TELEGRAM,
            chat_id=PARENT_CHAT,
            chat_name="Hermes Sessions",
            chat_type="group",
            user_id="6605861022",
            user_name="alice",
            thread_id="1",
        ),
        message_id="m1",
    )


def _runner():
    runner = object.__new__(GatewayRunner)
    runner.create_visible_session = AsyncMock(
        return_value=SimpleNamespace(
            topic_name="PR Review",
            target=f"telegram:{PARENT_CHAT}:14",
            session_id="session-14",
            session_key=f"agent:main:telegram:group:{PARENT_CHAT}:14",
        )
    )
    runner.prompt_visible_session = AsyncMock(
        return_value=SimpleNamespace(
            topic_name="PR Review",
            target=f"telegram:{PARENT_CHAT}:14",
            session_id="session-14",
            session_key=f"agent:main:telegram:group:{PARENT_CHAT}:14",
        )
    )
    runner.list_visible_sessions = lambda parent_event=None: [
        SimpleNamespace(
            topic_name="PR Review",
            target=f"telegram:{PARENT_CHAT}:14",
            session_id="session-14",
            session_key=f"agent:main:telegram:group:{PARENT_CHAT}:14",
        )
    ]
    return runner


def test_parse_spawn_topic_args_splits_topic_and_prompt():
    topic, prompt = parse_spawn_topic_args("PR Review :: inspect branch")

    assert topic == "PR Review"
    assert prompt == "inspect branch"


def test_parse_prompt_topic_args_splits_handle_and_prompt():
    handle, prompt = parse_prompt_topic_args(f"telegram:{PARENT_CHAT}:14 :: focus tests")

    assert handle == f"telegram:{PARENT_CHAT}:14"
    assert prompt == "focus tests"


def test_visible_topic_commands_are_gateway_known():
    assert resolve_command("spawn") == resolve_command("spawn-topic")
    assert "spawn-topic" in GATEWAY_KNOWN_COMMANDS
    assert "prompt-topic" in GATEWAY_KNOWN_COMMANDS
    assert "visible-sessions" in GATEWAY_KNOWN_COMMANDS


@pytest.mark.asyncio
async def test_spawn_topic_command_calls_visible_session_manager():
    runner = _runner()
    event = _event("/spawn-topic PR Review :: inspect branch")

    response = await runner._handle_spawn_topic_command(event)

    runner.create_visible_session.assert_awaited_once()
    kwargs = runner.create_visible_session.await_args.kwargs
    assert kwargs["parent_event"] is event
    assert kwargs["platform"] == "telegram"
    assert kwargs["parent_chat_id"] == PARENT_CHAT
    assert kwargs["topic_name"] == "PR Review"
    assert kwargs["prompt"] == "inspect branch"
    assert "telegram:-1003933169427:14" in response


@pytest.mark.asyncio
async def test_prompt_topic_command_calls_visible_session_manager():
    runner = _runner()
    event = _event(f"/prompt-topic telegram:{PARENT_CHAT}:14 :: focus tests")

    response = await runner._handle_prompt_topic_command(event)

    runner.prompt_visible_session.assert_awaited_once()
    kwargs = runner.prompt_visible_session.await_args.kwargs
    assert kwargs["parent_event"] is event
    assert kwargs["handle"] == f"telegram:{PARENT_CHAT}:14"
    assert kwargs["prompt"] == "focus tests"
    assert kwargs["mode"] == "queue"
    assert "telegram:-1003933169427:14" in response


@pytest.mark.asyncio
async def test_visible_sessions_command_lists_handles():
    runner = _runner()

    response = await runner._handle_visible_sessions_command(_event("/visible-sessions"))

    assert "PR Review" in response
    assert f"telegram:{PARENT_CHAT}:14" in response
