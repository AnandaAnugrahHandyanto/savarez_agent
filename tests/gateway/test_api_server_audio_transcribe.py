from pathlib import Path

import pytest
from aiohttp import FormData, web
from aiohttp.test_utils import TestClient, TestServer

from gateway.config import PlatformConfig
from gateway.platforms.api_server import APIServerAdapter


@pytest.fixture
def auth_adapter():
    return APIServerAdapter(PlatformConfig(enabled=True, extra={"key": "sk-test"}))


def _create_app(adapter: APIServerAdapter) -> web.Application:
    app = web.Application()
    app.router.add_post("/api/audio/transcribe", adapter._handle_audio_transcribe)
    return app


@pytest.mark.asyncio
async def test_audio_transcribe_requires_auth(auth_adapter):
    app = _create_app(auth_adapter)
    async with TestClient(TestServer(app)) as cli:
        data = FormData()
        data.add_field("audio", b"abc", filename="voice.webm", content_type="audio/webm")
        resp = await cli.post("/api/audio/transcribe", data=data)

    assert resp.status == 401


@pytest.mark.asyncio
async def test_audio_transcribe_multipart_deletes_temp_file(auth_adapter, monkeypatch):
    seen = {}

    def fake_transcribe(path):
        seen["path"] = path
        assert Path(path).exists()
        return {"success": True, "transcript": "hello voice", "provider": "local"}

    monkeypatch.setattr("tools.transcription_tools.transcribe_audio", fake_transcribe)

    app = _create_app(auth_adapter)
    async with TestClient(TestServer(app)) as cli:
        data = FormData()
        data.add_field("audio", b"abc", filename="voice.webm", content_type="audio/webm")
        resp = await cli.post(
            "/api/audio/transcribe",
            data=data,
            headers={"Authorization": "Bearer sk-test"},
        )
        payload = await resp.json()

    assert resp.status == 200
    assert payload["ok"] is True
    assert payload["transcript"] == "hello voice"
    assert payload["provider"] == "local"
    assert seen["path"]
    assert not Path(seen["path"]).exists()


@pytest.mark.asyncio
async def test_audio_transcribe_rejects_extra_fields(auth_adapter):
    app = _create_app(auth_adapter)
    async with TestClient(TestServer(app)) as cli:
        data = FormData()
        data.add_field("audio", b"abc", filename="voice.webm", content_type="audio/webm")
        data.add_field("profile", "pga")
        resp = await cli.post(
            "/api/audio/transcribe",
            data=data,
            headers={"Authorization": "Bearer sk-test"},
        )
        payload = await resp.json()

    assert resp.status == 400
    assert payload["error"]["code"] == "unsupported_field"


@pytest.mark.asyncio
async def test_audio_transcribe_rejects_unsupported_mime(auth_adapter):
    app = _create_app(auth_adapter)
    async with TestClient(TestServer(app)) as cli:
        data = FormData()
        data.add_field("audio", b"abc", filename="voice.txt", content_type="text/plain")
        resp = await cli.post(
            "/api/audio/transcribe",
            data=data,
            headers={"Authorization": "Bearer sk-test"},
        )
        payload = await resp.json()

    assert resp.status == 415
    assert payload["error"]["code"] == "unsupported_audio_format"


@pytest.mark.asyncio
async def test_audio_transcribe_rejects_non_multipart(auth_adapter):
    app = _create_app(auth_adapter)
    async with TestClient(TestServer(app)) as cli:
        resp = await cli.post(
            "/api/audio/transcribe",
            json={"audio": "nope"},
            headers={"Authorization": "Bearer sk-test"},
        )
        payload = await resp.json()

    assert resp.status == 415
    assert payload["error"]["code"] == "invalid_content_type"
