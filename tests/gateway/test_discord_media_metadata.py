import inspect
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from gateway.config import Platform
from plugins.platforms.discord.adapter import DiscordAdapter


def test_discord_media_methods_accept_metadata_kwarg():
    for method_name in ("send_voice", "send_image_file", "send_image", "send_video", "send_document"):
        signature = inspect.signature(getattr(DiscordAdapter, method_name))
        assert "metadata" in signature.parameters, method_name


@pytest.mark.asyncio
async def test_discord_document_metadata_thread_id_targets_existing_thread(tmp_path):
    """Kanban artifact uploads to a forum subscription must use the task thread.

    Without this, send_document resolves the parent forum channel and Discord
    creates a new forum post named after the uploaded artifact.
    """
    uploaded = tmp_path / "handoff.md"
    uploaded.write_text("handoff", encoding="utf-8")

    sent = []

    class FakeThread:
        id = 222

        async def send(self, **kwargs):
            sent.append(kwargs)
            return SimpleNamespace(id=333)

    class FakeClient:
        def __init__(self):
            self.requested_ids = []

        def get_channel(self, channel_id):
            self.requested_ids.append(channel_id)
            if channel_id == 222:
                return FakeThread()
            raise AssertionError(f"attachment delivery targeted parent channel {channel_id}")

        async def fetch_channel(self, channel_id):  # pragma: no cover - get_channel should hit
            raise AssertionError(f"unexpected fetch for {channel_id}")

    adapter = object.__new__(DiscordAdapter)
    adapter.platform = Platform.DISCORD
    adapter._client = FakeClient()
    adapter._is_forum_parent = lambda channel: False

    result = await adapter.send_document(
        chat_id="111",
        file_path=str(uploaded),
        metadata={"thread_id": "222"},
    )

    assert result.success is True
    assert adapter._client.requested_ids == [222]
    assert len(sent) == 1
    assert sent[0]["file"].filename == "handoff.md"


@pytest.mark.asyncio
async def test_discord_multi_image_metadata_thread_id_targets_existing_thread(tmp_path):
    image = tmp_path / "chart.png"
    image.write_bytes(b"fake-png")

    class FakeThread:
        id = 222
        send = AsyncMock(return_value=SimpleNamespace(id=333))

    thread = FakeThread()

    class FakeClient:
        def __init__(self):
            self.requested_ids = []

        def get_channel(self, channel_id):
            self.requested_ids.append(channel_id)
            if channel_id == 222:
                return thread
            raise AssertionError(f"image delivery targeted parent channel {channel_id}")

        async def fetch_channel(self, channel_id):  # pragma: no cover - get_channel should hit
            raise AssertionError(f"unexpected fetch for {channel_id}")

    adapter = object.__new__(DiscordAdapter)
    adapter.platform = Platform.DISCORD
    adapter._client = FakeClient()
    adapter._is_forum_parent = lambda channel: False

    await adapter.send_multiple_images(
        chat_id="111",
        images=[(f"file://{image}", "")],
        metadata={"thread_id": "222"},
    )

    assert adapter._client.requested_ids == [222]
    thread.send.assert_awaited_once()
    kwargs = thread.send.await_args.kwargs
    assert kwargs["files"][0].filename == "chart.png"


@pytest.mark.asyncio
async def test_discord_voice_metadata_thread_id_targets_existing_thread(tmp_path):
    audio = tmp_path / "note.ogg"
    audio.write_bytes(b"fake-audio")

    class FakeThread:
        id = 222
        send = AsyncMock(return_value=SimpleNamespace(id=333))

    thread = FakeThread()

    class FakeHttp:
        async def request(self, route, form=None, **kwargs):
            assert getattr(route, "parameters", {}).get("channel_id") == 222
            return {"id": 444}

    class FakeClient:
        def __init__(self):
            self.http = FakeHttp()
            self.requested_ids = []

        def get_channel(self, channel_id):
            self.requested_ids.append(channel_id)
            if channel_id == 222:
                return thread
            raise AssertionError(f"voice delivery targeted parent channel {channel_id}")

        async def fetch_channel(self, channel_id):  # pragma: no cover - get_channel should hit
            raise AssertionError(f"unexpected fetch for {channel_id}")

    client = FakeClient()
    adapter = object.__new__(DiscordAdapter)
    adapter.platform = Platform.DISCORD
    adapter._client = client
    adapter._is_forum_parent = lambda channel: False

    result = await adapter.send_voice(
        chat_id="111",
        audio_path=str(audio),
        metadata={"thread_id": "222"},
    )

    assert result.success is True
    assert client.requested_ids == [222]


@pytest.mark.asyncio
async def test_discord_url_image_metadata_thread_id_targets_existing_thread(monkeypatch):
    sent = []

    class FakeResponse:
        status = 200
        headers = {"content-type": "image/png"}

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def read(self):
            return b"fake-image"

    class FakeSession:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        def get(self, *args, **kwargs):
            return FakeResponse()

    fake_aiohttp = SimpleNamespace(
        ClientSession=FakeSession,
        ClientTimeout=lambda **kwargs: None,
    )
    monkeypatch.setitem(sys.modules, "aiohttp", fake_aiohttp)

    class FakeThread:
        id = 222

        async def send(self, **kwargs):
            sent.append(kwargs)
            return SimpleNamespace(id=333)

    class FakeClient:
        def __init__(self):
            self.requested_ids = []

        def get_channel(self, channel_id):
            self.requested_ids.append(channel_id)
            if channel_id == 222:
                return FakeThread()
            raise AssertionError(f"image URL delivery targeted parent channel {channel_id}")

        async def fetch_channel(self, channel_id):  # pragma: no cover - get_channel should hit
            raise AssertionError(f"unexpected fetch for {channel_id}")

    client = FakeClient()
    adapter = object.__new__(DiscordAdapter)
    adapter.platform = Platform.DISCORD
    adapter._client = client
    adapter._is_forum_parent = lambda channel: False

    result = await adapter.send_image(
        chat_id="111",
        image_url="https://example.com/chart.png",
        metadata={"thread_id": "222"},
    )

    assert result.success is True
    assert client.requested_ids == [222]
    assert sent[0]["file"].filename == "image.png"
