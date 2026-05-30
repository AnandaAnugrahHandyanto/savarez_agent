"""Unified vision image-source resolver."""
import base64

import pytest

from tools.image_source import (
    NotAnImage,
    ResolveContext,
    ResolvedImage,
    SourceTooLarge,
    SourceUnsafe,
    UnsupportedScheme,
    resolve_image_source,
)

PNG_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="


@pytest.mark.asyncio
async def test_data_url_resolves_to_bytes():
    res = await resolve_image_source(f"data:image/png;base64,{PNG_B64}", ResolveContext())
    assert isinstance(res, ResolvedImage)
    assert res.mime == "image/png"
    assert res.origin == "data"
    assert res.data == base64.b64decode(PNG_B64)


@pytest.mark.asyncio
async def test_data_url_non_image_rejected():
    with pytest.raises(NotAnImage):
        await resolve_image_source("data:text/plain;base64,aGk=", ResolveContext())


@pytest.mark.asyncio
async def test_data_url_oversize_rejected():
    big = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * (40 * 1024 * 1024)).decode()
    with pytest.raises(SourceTooLarge):
        await resolve_image_source(f"data:image/png;base64,{big}", ResolveContext())


@pytest.mark.asyncio
async def test_unknown_scheme_rejected():
    with pytest.raises(UnsupportedScheme):
        await resolve_image_source("s3://bucket/x.png", ResolveContext())


@pytest.mark.asyncio
async def test_blank_source_rejected():
    with pytest.raises(Exception):
        await resolve_image_source("   ", ResolveContext())


@pytest.mark.asyncio
async def test_http_url_downloads_bytes(monkeypatch):
    from tools import image_source

    png = base64.b64decode(PNG_B64)

    async def fake_download(url):
        return png

    monkeypatch.setattr(image_source, "_is_safe_http", lambda u: True)
    monkeypatch.setattr(image_source, "_download_to_bytes", fake_download)
    res = await resolve_image_source("https://ex.com/a.png", ResolveContext())
    assert res.origin == "http"
    assert res.data == png


@pytest.mark.asyncio
async def test_http_url_ssrf_blocked(monkeypatch):
    from tools import image_source

    monkeypatch.setattr(image_source, "_is_safe_http", lambda u: False)
    with pytest.raises(SourceUnsafe):
        await resolve_image_source("http://169.254.169.254/x.png", ResolveContext())
