"""Tests for /btw temporary gateway agent cleanup."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gateway.config import Platform
from gateway.session import SessionSource


def _make_runner():
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner.adapters = {}
    runner._voice_mode = {}
    runner._session_db = None
    runner._reasoning_config = None
    runner._provider_routing = {}
    runner._fallback_model = None
    runner._running_agents = {}
    runner._background_tasks = set()
    runner.session_store = MagicMock()
    runner.session_store.get_or_create_session.return_value = MagicMock(session_id="sess-1")
    runner.session_store.load_transcript.return_value = [
        {"role": "user", "content": "prior question"},
        {"role": "assistant", "content": "prior answer"},
    ]
    return runner


@pytest.mark.asyncio
async def test_btw_agent_closed_after_success():
    runner = _make_runner()
    mock_adapter = AsyncMock()
    mock_adapter.send = AsyncMock()
    mock_adapter.extract_media = MagicMock(return_value=([], "short answer"))
    mock_adapter.extract_images = MagicMock(return_value=([], "short answer"))
    runner.adapters[Platform.TELEGRAM] = mock_adapter

    source = SessionSource(
        platform=Platform.TELEGRAM,
        user_id="12345",
        chat_id="67890",
        user_name="testuser",
    )

    with patch("gateway.run._resolve_runtime_agent_kwargs", return_value={"api_key": "test-key"}), \
         patch("run_agent.AIAgent") as MockAgent:
        mock_agent_instance = MagicMock()
        mock_agent_instance.run_conversation.return_value = {"final_response": "short answer"}
        MockAgent.return_value = mock_agent_instance

        await runner._run_btw_task("what changed?", source, "sess-key", "btw_test")

    mock_agent_instance.close.assert_called_once()
    mock_agent_instance.shutdown_memory_provider.assert_not_called()
    mock_adapter.send.assert_called_once()


@pytest.mark.asyncio
async def test_btw_agent_closed_after_failure():
    runner = _make_runner()
    mock_adapter = AsyncMock()
    mock_adapter.send = AsyncMock()
    runner.adapters[Platform.TELEGRAM] = mock_adapter

    source = SessionSource(
        platform=Platform.TELEGRAM,
        user_id="12345",
        chat_id="67890",
        user_name="testuser",
    )

    with patch("gateway.run._resolve_runtime_agent_kwargs", return_value={"api_key": "test-key"}), \
         patch("run_agent.AIAgent") as MockAgent:
        mock_agent_instance = MagicMock()
        mock_agent_instance.run_conversation.side_effect = RuntimeError("boom")
        MockAgent.return_value = mock_agent_instance

        await runner._run_btw_task("what changed?", source, "sess-key", "btw_test")

    mock_agent_instance.close.assert_called_once()
    mock_agent_instance.shutdown_memory_provider.assert_not_called()
    mock_adapter.send.assert_called_once()
    content = mock_adapter.send.call_args[1].get(
        "content",
        mock_adapter.send.call_args[0][1] if len(mock_adapter.send.call_args[0]) > 1 else "",
    )
    assert "failed" in content.lower()
