import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from gateway import feed_images


class FakeResponse:
    def __init__(self, status_code=200, payload=None, content=b""):
        self.status_code = status_code
        self._payload = payload or {}
        self.content = content
        self.text = json.dumps(self._payload)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}: {self.text}")

    def json(self):
        return self._payload


@pytest.mark.asyncio
async def test_post_discord_feed_image_sends_multipart_with_jwt_and_metadata(monkeypatch, tmp_path):
    image_path = tmp_path / "input.png"
    image_path.write_bytes(b"png-bytes")
    calls = []

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return None

        async def post(self, url, **kwargs):
            calls.append((url, kwargs))
            return FakeResponse(payload={"id": 123, "status": "queued"})

    monkeypatch.setattr(feed_images.httpx, "AsyncClient", FakeAsyncClient)

    result = await feed_images.post_discord_feed_image(
        image_path=str(image_path),
        message_text="make it cute",
        source={
            "platform": "discord",
            "chat_id": "chan-1",
            "message_id": "msg-1",
            "user_id": "user-1",
        },
        api_base_url="https://dev-api.fanhearts.com",
        jwt="jwt-token",
    )

    assert result == {"id": 123, "status": "queued"}
    assert len(calls) == 1
    url, kwargs = calls[0]
    assert url == "https://dev-api.fanhearts.com/feed_images"
    assert kwargs["headers"]["Authorization"] == "Bearer jwt-token"
    assert "image" in kwargs["files"]
    assert json.loads(kwargs["data"]["metadata"])["discord_message_id"] == "msg-1"
    assert kwargs["data"]["prompt"] == "make it cute"


@pytest.mark.asyncio
async def test_process_queued_feed_images_claims_generates_and_updates(monkeypatch, tmp_path):
    input_image = tmp_path / "source.png"
    output_image = tmp_path / "generated.png"
    input_image.write_bytes(b"source")
    output_image.write_bytes(b"generated")
    calls = []

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return None

        async def get(self, url, **kwargs):
            calls.append(("GET", url, kwargs))
            return FakeResponse(payload={"feed_images": [{"id": "img-1", "image_url": "https://cdn/input.png", "prompt": "turn into fan art"}]})

        async def post(self, url, **kwargs):
            calls.append(("POST", url, kwargs))
            if url.endswith("/claim"):
                return FakeResponse(payload={"ok": True})
            raise AssertionError(url)

        async def put(self, url, **kwargs):
            calls.append(("PUT", url, kwargs))
            return FakeResponse(payload={"ok": True})

    async def fake_download(client, url, workdir):
        assert url == "https://cdn/input.png"
        return input_image

    def fake_generate_prompt(image_path, user_prompt):
        assert image_path == input_image
        return "generated prompt"

    def fake_generate_image(prompt, output_dir):
        assert prompt == "generated prompt"
        return output_image, "https://fal/generated.png"

    monkeypatch.setattr(feed_images.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(feed_images, "_download_image", fake_download)
    monkeypatch.setattr(feed_images, "build_transform_prompt", fake_generate_prompt)
    monkeypatch.setattr(feed_images, "generate_with_gpt_image_2", fake_generate_image)

    summary = await feed_images.process_queued_feed_images(
        api_base_url="https://dev-api.fanhearts.com",
        jwt="jwt-token",
        limit=1,
        workdir=tmp_path,
    )

    assert summary["completed"] == 1
    assert summary["failed"] == 0
    put_calls = [call for call in calls if call[0] == "PUT"]
    assert len(put_calls) == 1
    _, url, kwargs = put_calls[0]
    assert url == "https://dev-api.fanhearts.com/feed_images/img-1"
    assert kwargs["headers"]["Authorization"] == "Bearer jwt-token"
    assert kwargs["data"]["status"] == "completed"
    assert kwargs["data"]["transform_prompt"] == "generated prompt"
    assert "completed_image" in kwargs["files"]
