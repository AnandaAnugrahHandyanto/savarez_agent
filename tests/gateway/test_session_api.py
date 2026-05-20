"""Focused tests for the API server session control surface.

The /api/sessions resource layer must stay a thin wrapper over SessionDB and
APIServerAdapter._run_agent.  It deliberately does not cover deferred admin,
memory, skills, jobs, or realtime voice expansion.
"""

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from unittest.mock import AsyncMock, patch

from gateway.config import PlatformConfig
from gateway.platforms.api_server import (
    APIServerAdapter,
    cors_middleware,
    security_headers_middleware,
)
from hermes_state import SessionDB


def _make_adapter(api_key: str = "") -> APIServerAdapter:
    extra = {}
    if api_key:
        extra["key"] = api_key
    return APIServerAdapter(PlatformConfig(enabled=True, extra=extra))


@pytest.fixture
def session_db(tmp_path):
    db = SessionDB(tmp_path / "state.db")
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def adapter(session_db):
    api = _make_adapter()
    api._session_db = session_db
    return api


@pytest.fixture
def auth_adapter(session_db):
    api = _make_adapter(api_key="sk-secret")
    api._session_db = session_db
    return api


def _create_session_app(adapter: APIServerAdapter) -> web.Application:
    mws = [mw for mw in (cors_middleware, security_headers_middleware) if mw is not None]
    app = web.Application(middlewares=mws)
    app.router.add_get("/v1/capabilities", adapter._handle_capabilities)
    app.router.add_get("/api/sessions", adapter._handle_list_sessions)
    app.router.add_post("/api/sessions", adapter._handle_create_session)
    app.router.add_get("/api/sessions/{session_id}", adapter._handle_get_session)
    app.router.add_patch("/api/sessions/{session_id}", adapter._handle_update_session)
    app.router.add_delete("/api/sessions/{session_id}", adapter._handle_delete_session)
    app.router.add_get("/api/sessions/{session_id}/messages", adapter._handle_get_session_messages)
    app.router.add_post("/api/sessions/{session_id}/fork", adapter._handle_fork_session)
    app.router.add_post("/api/sessions/{session_id}/chat", adapter._handle_session_chat)
    app.router.add_post("/api/sessions/{session_id}/chat/stream", adapter._handle_session_chat_stream)
    return app


class TestSessionCapabilities:
    @pytest.mark.asyncio
    async def test_capabilities_advertises_session_surface_and_deferred_features(self, adapter):
        app = _create_session_app(adapter)
        async with TestClient(TestServer(app)) as cli:
            resp = await cli.get("/v1/capabilities")
            assert resp.status == 200
            data = await resp.json()

        assert data["features"]["sessions"] is True
        assert data["features"]["session_messages"] is True
        assert data["features"]["session_chat"] is True
        assert data["features"]["session_chat_streaming"] is True
        assert data["features"]["session_fork"] is True
        assert data["features"]["admin_config"] is False
        assert data["features"]["audio_transcription"] is False
        assert data["features"]["audio_speech"] is False
        assert data["features"]["realtime_voice"] is False
        assert data["endpoints"]["sessions"]["path"] == "/api/sessions"
        assert data["endpoints"]["session_chat_stream"]["path"] == "/api/sessions/{session_id}/chat/stream"


class TestSessionCrud:
    @pytest.mark.asyncio
    async def test_session_crud_and_messages_use_session_db(self, adapter, session_db):
        app = _create_session_app(adapter)
        async with TestClient(TestServer(app)) as cli:
            created = await cli.post(
                "/api/sessions",
                json={"title": "Mobile Chat", "source": "mobile", "model": "hermes-agent"},
            )
            assert created.status == 201
            created_data = await created.json()
            session_id = created_data["session"]["id"]
            assert created_data["session"]["session_id"] == session_id
            assert created_data["session"]["title"] == "Mobile Chat"
            assert created.headers["X-Hermes-Session-Id"] == session_id

            listed = await cli.get("/api/sessions?limit=10&offset=0")
            assert listed.status == 200
            list_data = await listed.json()
            assert list_data["object"] == "list"
            assert list_data["total"] == 1
            assert list_data["items"][0]["id"] == session_id

            fetched = await cli.get(f"/api/sessions/{session_id}")
            assert fetched.status == 200
            assert (await fetched.json())["session"]["id"] == session_id

            patched = await cli.patch(f"/api/sessions/{session_id}", json={"title": "Renamed"})
            assert patched.status == 200
            assert (await patched.json())["session"]["title"] == "Renamed"

            session_db.append_message(session_id, "user", "hello")
            session_db.append_message(session_id, "assistant", "hi there")
            messages = await cli.get(f"/api/sessions/{session_id}/messages")
            assert messages.status == 200
            msg_data = await messages.json()
            assert msg_data["object"] == "list"
            assert msg_data["total"] == 2
            assert [m["role"] for m in msg_data["messages"]] == ["user", "assistant"]
            assert msg_data["data"][0]["content"] == "hello"

            deleted = await cli.delete(f"/api/sessions/{session_id}")
            assert deleted.status == 200
            assert (await deleted.json())["deleted"] is True

            missing = await cli.get(f"/api/sessions/{session_id}")
            assert missing.status == 404

    @pytest.mark.asyncio
    async def test_session_endpoints_require_auth_when_key_configured(self, auth_adapter):
        app = _create_session_app(auth_adapter)
        async with TestClient(TestServer(app)) as cli:
            unauth = await cli.get("/api/sessions")
            assert unauth.status == 401

            authed = await cli.get("/api/sessions", headers={"Authorization": "Bearer sk-secret"})
            assert authed.status == 200

    @pytest.mark.asyncio
    async def test_fork_creates_child_session_with_parent_link(self, adapter):
        app = _create_session_app(adapter)
        async with TestClient(TestServer(app)) as cli:
            created = await cli.post("/api/sessions", json={"title": "Root"})
            session_id = (await created.json())["session"]["id"]
            adapter._session_db.append_message(session_id, "user", "branch from here")
            adapter._session_db.append_message(session_id, "assistant", "ready")

            forked = await cli.post(f"/api/sessions/{session_id}/fork", json={"title": "Branch"})
            assert forked.status == 201
            child = (await forked.json())["session"]
            assert child["id"] != session_id
            assert child["parent_session_id"] == session_id
            assert child["title"] == "Branch"

            messages = await cli.get(f"/api/sessions/{child['id']}/messages")
            assert messages.status == 200
            assert [m["content"] for m in (await messages.json())["messages"]] == [
                "branch from here",
                "ready",
            ]


class TestSessionChat:
    @pytest.mark.asyncio
    async def test_session_chat_uses_path_session_and_existing_history(self, adapter, session_db):
        session_db.create_session("sess_api", "api_server")
        session_db.set_session_title("sess_api", "Chat")
        session_db.append_message("sess_api", "user", "prior")
        app = _create_session_app(adapter)

        async with TestClient(TestServer(app)) as cli:
            with patch.object(adapter, "_run_agent", new_callable=AsyncMock) as run_agent:
                run_agent.return_value = (
                    {"final_response": "answer", "session_id": "sess_api", "api_calls": 1},
                    {"input_tokens": 3, "output_tokens": 4, "total_tokens": 7},
                )
                resp = await cli.post("/api/sessions/sess_api/chat", json={"message": "next"})

            assert resp.status == 200
            assert resp.headers["X-Hermes-Session-Id"] == "sess_api"
            data = await resp.json()
            assert data["session_id"] == "sess_api"
            assert data["message"]["role"] == "assistant"
            assert data["message"]["content"] == "answer"
            assert data["response"] == "answer"

        kwargs = run_agent.call_args.kwargs
        assert kwargs["session_id"] == "sess_api"
        assert kwargs["user_message"] == "next"
        assert kwargs["conversation_history"] == [{"role": "user", "content": "prior"}]

    @pytest.mark.asyncio
    async def test_session_chat_streams_sse_and_threads_session_key(self, auth_adapter, session_db):
        session_db.create_session("sess_stream", "api_server")
        app = _create_session_app(auth_adapter)

        async def fake_run_agent(**kwargs):
            cb = kwargs.get("stream_delta_callback")
            if cb:
                cb("hel")
                cb("lo")
            return (
                {"final_response": "hello", "session_id": "sess_stream", "api_calls": 1},
                {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3},
            )

        async with TestClient(TestServer(app)) as cli:
            with patch.object(auth_adapter, "_run_agent", side_effect=fake_run_agent) as run_agent:
                resp = await cli.post(
                    "/api/sessions/sess_stream/chat/stream",
                    json={"message": "stream please"},
                    headers={
                        "Authorization": "Bearer sk-secret",
                        "X-Hermes-Session-Key": "mobile:user-1",
                    },
                )
                assert resp.status == 200
                assert "text/event-stream" in resp.headers.get("Content-Type", "")
                assert resp.headers["X-Hermes-Session-Id"] == "sess_stream"
                assert resp.headers["X-Hermes-Session-Key"] == "mobile:user-1"
                text = await resp.text()

        assert "hel" in text
        assert "lo" in text
        assert "data: [DONE]" in text
        assert run_agent.call_args.kwargs["session_id"] == "sess_stream"
        assert run_agent.call_args.kwargs["gateway_session_key"] == "mobile:user-1"

    @pytest.mark.asyncio
    async def test_session_key_requires_configured_api_key(self, adapter, session_db):
        session_db.create_session("sess_key", "api_server")
        app = _create_session_app(adapter)
        async with TestClient(TestServer(app)) as cli:
            resp = await cli.post(
                "/api/sessions/sess_key/chat",
                json={"message": "hi"},
                headers={"X-Hermes-Session-Key": "mobile:user-1"},
            )
            assert resp.status == 403
