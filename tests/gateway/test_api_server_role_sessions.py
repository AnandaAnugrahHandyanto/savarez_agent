"""Tests for API server role-session transport parity."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from gateway.config import PlatformConfig
from gateway.platforms.api_server import (
    APIServerAdapter,
    cors_middleware,
    security_headers_middleware,
)


def _create_app(adapter: APIServerAdapter) -> web.Application:
    mws = [mw for mw in (cors_middleware, security_headers_middleware) if mw is not None]
    app = web.Application(middlewares=mws)
    app["api_server_adapter"] = adapter
    app.router.add_post("/v1/chat/completions", adapter._handle_chat_completions)
    app.router.add_post("/v1/responses", adapter._handle_responses)
    return app


@pytest.fixture()
def adapter():
    return APIServerAdapter(PlatformConfig(enabled=True))


class TestAPIServerRoleSessions:
    @pytest.mark.asyncio
    async def test_run_agent_forwards_parent_session_id_to_create_agent(self, adapter):
        fake_agent = MagicMock()
        fake_agent.session_prompt_tokens = 0
        fake_agent.session_completion_tokens = 0
        fake_agent.session_total_tokens = 0
        fake_agent.run_conversation.return_value = {
            "final_response": "ok",
            "messages": [],
            "api_calls": 1,
        }

        with patch.object(adapter, "_create_agent", return_value=fake_agent) as mock_create:
            result, usage = await adapter._run_agent(
                user_message="hello",
                conversation_history=[],
                parent_session_id="lead-123",
            )

        assert result["final_response"] == "ok"
        assert usage["total_tokens"] == 0
        assert mock_create.call_args.kwargs["parent_session_id"] == "lead-123"

    @pytest.mark.asyncio
    async def test_chat_completions_accepts_parent_session_id_body(self, adapter):
        app = _create_app(adapter)
        async with TestClient(TestServer(app)) as cli:
            with patch.object(
                adapter,
                "_run_agent",
                new=AsyncMock(
                    return_value=(
                        {"final_response": "ok", "messages": [], "api_calls": 1},
                        {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
                    )
                ),
            ) as mock_run:
                resp = await cli.post(
                    "/v1/chat/completions",
                    json={
                        "model": "hermes-agent",
                        "messages": [{"role": "user", "content": "hello"}],
                        "parent_session_id": "lead-123",
                    },
                )

        assert resp.status == 200, await resp.text()
        assert mock_run.await_args.kwargs["parent_session_id"] == "lead-123"

    @pytest.mark.asyncio
    async def test_responses_accepts_parent_session_id_body(self, adapter):
        app = _create_app(adapter)
        async with TestClient(TestServer(app)) as cli:
            with patch.object(
                adapter,
                "_run_agent",
                new=AsyncMock(
                    return_value=(
                        {"final_response": "ok", "messages": [], "api_calls": 1},
                        {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
                    )
                ),
            ) as mock_run:
                resp = await cli.post(
                    "/v1/responses",
                    json={
                        "model": "hermes-agent",
                        "input": "hello",
                        "parent_session_id": "lead-123",
                    },
                )

            assert resp.status == 200, await resp.text()
            assert mock_run.await_args.kwargs["parent_session_id"] == "lead-123"
