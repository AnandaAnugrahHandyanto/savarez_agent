import json

import pytest

from gateway.platforms.discord import fetch_channel_history_via_api


class _FakeResponse:
    def __init__(self, status, payload):
        self.status = status
        self._payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def json(self, content_type=None):
        return self._payload

    async def text(self):
        return json.dumps(self._payload)


class _FakeSession:
    def __init__(self, payload, recorder):
        self._payload = payload
        self._recorder = recorder

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def get(self, url, headers=None, params=None, **kwargs):
        self._recorder["url"] = url
        self._recorder["headers"] = headers
        self._recorder["params"] = params
        self._recorder["kwargs"] = kwargs
        return _FakeResponse(200, self._payload)


class _FakeAioHttp:
    class ClientTimeout:
        def __init__(self, total):
            self.total = total

    def __init__(self, payload, recorder):
        self._payload = payload
        self._recorder = recorder

    def ClientSession(self, **kwargs):
        self._recorder["session_kwargs"] = kwargs
        return _FakeSession(self._payload, self._recorder)


@pytest.mark.asyncio
async def test_fetch_channel_history_via_api_normalizes_order_and_bot_messages(monkeypatch):
    recorder = {}
    payload = [
        {
            "id": "2",
            "channel_id": "123",
            "timestamp": "2026-04-16T00:00:02Z",
            "content": "bot reply",
            "author": {"id": "900", "username": "Friday", "bot": True},
            "type": 0,
        },
        {
            "id": "1",
            "channel_id": "123",
            "timestamp": "2026-04-16T00:00:01Z",
            "content": "",
            "attachments": [{"filename": "note.png"}],
            "author": {"id": "100", "username": "Trouble", "global_name": "Trouble", "bot": False},
            "type": 0,
        },
    ]

    monkeypatch.setattr("gateway.platforms.discord.resolve_proxy_url", lambda platform_env_var=None: None)
    monkeypatch.setattr("gateway.platforms.discord.proxy_kwargs_for_aiohttp", lambda proxy_url: ({}, {}))
    monkeypatch.setattr("aiohttp.ClientSession", _FakeAioHttp(payload, recorder).ClientSession)
    monkeypatch.setattr("aiohttp.ClientTimeout", _FakeAioHttp.ClientTimeout)

    messages = await fetch_channel_history_via_api("TOKEN", "123", limit=20)

    assert [m["message_id"] for m in messages] == ["1", "2"]
    assert messages[0]["author"] == "Trouble"
    assert messages[0]["content"] == "attachments: note.png"
    assert messages[1]["is_bot"] is True
    assert recorder["params"] == {"limit": "20"}
    assert recorder["headers"]["Authorization"] == "Bot TOKEN"


@pytest.mark.asyncio
async def test_fetch_channel_history_via_api_reports_permission_error(monkeypatch):
    class _ForbiddenResponse(_FakeResponse):
        async def text(self):
            return '{"message":"Missing Access"}'

    class _ForbiddenSession(_FakeSession):
        def get(self, url, headers=None, params=None, **kwargs):
            return _ForbiddenResponse(403, {"message": "Missing Access"})

    class _ForbiddenAioHttp(_FakeAioHttp):
        def ClientSession(self, **kwargs):
            return _ForbiddenSession([], {})

    monkeypatch.setattr("gateway.platforms.discord.resolve_proxy_url", lambda platform_env_var=None: None)
    monkeypatch.setattr("gateway.platforms.discord.proxy_kwargs_for_aiohttp", lambda proxy_url: ({}, {}))
    monkeypatch.setattr("aiohttp.ClientSession", _ForbiddenAioHttp([], {}).ClientSession)
    monkeypatch.setattr("aiohttp.ClientTimeout", _FakeAioHttp.ClientTimeout)

    with pytest.raises(PermissionError, match="Read Message History"):
        await fetch_channel_history_via_api("TOKEN", "123", limit=20)
