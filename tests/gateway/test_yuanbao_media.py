"""Tests for Yuanbao media download helpers."""

from types import SimpleNamespace

import pytest

from gateway.platforms import yuanbao_media


class _UnexpectedAsyncClient:
    def __init__(self, *args, **kwargs):
        raise AssertionError("network client should not be created for unsafe URLs")


@pytest.mark.asyncio
async def test_download_url_blocks_private_hosts_before_fetch(monkeypatch):
    monkeypatch.setattr(yuanbao_media.httpx, "AsyncClient", _UnexpectedAsyncClient)

    with pytest.raises(ValueError, match="Blocked unsafe URL"):
        await yuanbao_media.download_url("http://127.0.0.1/latest/meta-data")


@pytest.mark.asyncio
async def test_download_url_installs_redirect_guard(monkeypatch):
    captured = {}
    monkeypatch.setattr(yuanbao_media, "is_safe_url", lambda url: True)

    class FakeHeadResponse:
        headers = {}

    class FakeStreamResponse:
        headers = {"content-type": "text/plain"}

        def raise_for_status(self):
            return None

        async def aiter_bytes(self, chunk_size):
            yield b"ok"

    class FakeStream:
        async def __aenter__(self):
            return FakeStreamResponse()

        async def __aexit__(self, exc_type, exc, tb):
            return None

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            captured["event_hooks"] = kwargs.get("event_hooks")

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def head(self, url):
            return FakeHeadResponse()

        def stream(self, method, url):
            return FakeStream()

    monkeypatch.setattr(yuanbao_media.httpx, "AsyncClient", FakeAsyncClient)

    data, content_type = await yuanbao_media.download_url("https://example.com/file.txt")

    assert data == b"ok"
    assert content_type == "text/plain"
    assert captured["event_hooks"] == {
        "response": [yuanbao_media._yuanbao_ssrf_redirect_guard],
    }


@pytest.mark.asyncio
async def test_download_url_redirect_guard_blocks_private_redirect(monkeypatch):
    monkeypatch.setattr(
        yuanbao_media,
        "is_safe_url",
        lambda url: not url.startswith("http://169.254.169.254"),
    )

    response = SimpleNamespace(
        is_redirect=True,
        next_request=SimpleNamespace(url="http://169.254.169.254/latest/meta-data"),
    )

    with pytest.raises(ValueError, match="Blocked redirect"):
        await yuanbao_media._yuanbao_ssrf_redirect_guard(response)


def test_download_url_trusted_private_hosts_are_opt_in(monkeypatch):
    monkeypatch.setattr(yuanbao_media, "is_safe_url", lambda url: False)
    monkeypatch.setattr(yuanbao_media, "is_always_blocked_url", lambda url: False)

    media_url = "https://bucket.cos.accelerate.myqcloud.com/image.png"

    assert yuanbao_media._is_safe_download_url(media_url) is False
    assert (
        yuanbao_media._is_safe_download_url(
            media_url,
            allow_trusted_private_hosts=True,
        )
        is True
    )
