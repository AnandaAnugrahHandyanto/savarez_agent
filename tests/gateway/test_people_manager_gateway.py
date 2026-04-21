from unittest.mock import MagicMock

import pytest

from gateway.platforms.base import MessageEvent
from gateway.session import SessionSource
from gateway.config import Platform


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
    runner._session_key_for_source = lambda source: f"{source.platform.value}:{source.chat_id}:{source.user_id}"
    runner._workspace_by_session_key = {
        runner._session_key_for_source(_make_source()): "people"
    }
    return runner


@pytest.mark.asyncio
async def test_people_workspace_mutating_message_intercepts(monkeypatch):
    runner = _make_runner()
    event = _make_event("Update Alice Chen: shipped memo")

    monkeypatch.setattr(
        "gateway.run.handle_people_message",
        lambda text, lane_id, workspace: "Profile updated for Alice Chen.",
    )

    result = await runner._maybe_handle_people_manager_message(event)

    assert result == "Profile updated for Alice Chen."


@pytest.mark.asyncio
async def test_people_workspace_read_message_intercepts(monkeypatch):
    runner = _make_runner()
    event = _make_event("Prep Alice Chen")

    monkeypatch.setattr(
        "gateway.run.handle_people_message",
        lambda text, lane_id, workspace: "Current read\nOpen loops",
    )

    result = await runner._maybe_handle_people_manager_message(event)

    assert "Current read" in result


@pytest.mark.asyncio
async def test_people_workspace_fastpath_intercepts_adhoc_one_on_one_prep(monkeypatch):
    runner = _make_runner()
    event = _make_event("1o1 prep Fiona")

    monkeypatch.setattr(
        "gateway.run.handle_people_message",
        lambda text, lane_id, workspace: "Fiona Cao 1:1\n- family summer travels",
    )

    result = await runner._maybe_handle_people_manager_message(event)

    assert result.startswith("Fiona Cao 1:1")


@pytest.mark.asyncio
async def test_non_people_workspace_does_not_intercept(monkeypatch):
    runner = _make_runner()
    runner._workspace_by_session_key = {}
    event = _make_event("Update Alice Chen: shipped memo")

    fake = MagicMock(return_value="should not be used")
    monkeypatch.setattr("gateway.run.handle_people_message", fake)

    result = await runner._maybe_handle_people_manager_message(event)

    assert result is None
    fake.assert_not_called()


@pytest.mark.asyncio
async def test_unmatched_text_falls_through(monkeypatch):
    runner = _make_runner()
    event = _make_event("Alice seems good")

    monkeypatch.setattr("gateway.run.handle_people_message", lambda text, lane_id, workspace: None)

    result = await runner._maybe_handle_people_manager_message(event)

    assert result is None


def test_workspace_for_source_uses_session_mapping_only():
    runner = _make_runner()
    source = _make_source()
    runner._workspace_by_session_key = {runner._session_key_for_source(source): "people"}

    assert runner._workspace_for_source(source) == "people"


def test_workspace_for_source_returns_none_without_session_mapping():
    runner = _make_runner()
    source = _make_source()
    runner._workspace_by_session_key = {}

    assert runner._workspace_for_source(source) is None


@pytest.mark.asyncio
async def test_workspace_switch_sets_session_override_without_global_prompt_bleed(monkeypatch):
    runner = _make_runner()
    source = _make_source()
    event = _make_event("/people")
    runner._ephemeral_system_prompt = "Global prompt"
    runner._ephemeral_system_prompt_by_session_key = {}
    runner._load_gateway_personalities = lambda: ({}, {}, None)

    async def _fake_reset(_event):
        return "reset ok"

    runner._handle_reset_command = _fake_reset

    result = await runner._handle_workspace_switch_command(event, "people")

    assert "Switched to /people workspace" in result
    assert runner._workspace_for_source(source) == "people"
    assert runner._get_session_prompt_override(runner._session_key_for_source(source)) != "Global prompt"
    assert runner._ephemeral_system_prompt == "Global prompt"


@pytest.mark.asyncio
async def test_personality_change_removes_people_workspace_mapping(monkeypatch):
    runner = _make_runner()
    source = _make_source()
    event = _make_event("/personality coach")
    runner._ephemeral_system_prompt = "People prompt"
    runner._ephemeral_system_prompt_by_session_key = {runner._session_key_for_source(source): "People prompt"}
    runner._load_gateway_personalities = lambda: ({"agent": {}}, {"coach": "Coach prompt"}, None)

    monkeypatch.setattr("gateway.run.atomic_yaml_write", lambda *args, **kwargs: None)

    result = await runner._handle_personality_command(event)

    assert "Personality set to **coach**" in result
    assert runner._workspace_for_source(source) is None
    assert runner._get_session_prompt_override(runner._session_key_for_source(source)) == "Coach prompt"
