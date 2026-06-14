"""Tests for the optional curl_cffi-backed httpx client."""
from __future__ import annotations

import httpx

from agent.curl_cffi_transport import CurlCffiClient, build_curl_cffi_http_client


class _FakeHeaders(dict):
    def multi_items(self):
        return list(self.items())


class _FakeCurlResponse:
    def __init__(self, *, content=b"body", chunks=None):
        self.status_code = 200
        self.headers = _FakeHeaders({"content-encoding": "gzip", "x-test": "ok"})
        self.content = content
        self._chunks = chunks or [b"a", b"b"]
        self.closed = False

    def iter_content(self, chunk_size=65536):
        yield from self._chunks

    def close(self):
        self.closed = True


class _FakeCurlSession:
    def __init__(self, response):
        self.response = response
        self.calls = []
        self.closed = False

    def request(self, **kwargs):
        self.calls.append(kwargs)
        return self.response

    def close(self):
        self.closed = True


def test_curl_cffi_client_is_httpx_client():
    client = build_curl_cffi_http_client("chrome124")
    try:
        assert isinstance(client, httpx.Client)
    finally:
        client.close()


def test_send_strips_httpx_bot_headers_and_content_encoding():
    response = _FakeCurlResponse(content=b"ok")
    session = _FakeCurlSession(response)
    client = CurlCffiClient("chrome124")
    object.__setattr__(client, "_curl_session", session)
    request = client.build_request(
        "POST",
        "https://example.test/path",
        headers={"User-Agent": "python-httpx/0.28.1", "Accept": "*/*", "X-Keep": "1"},
        content=b"payload",
    )

    try:
        got = client.send(request)
    finally:
        client.close()

    sent_headers = {k.lower(): v for k, v in session.calls[0]["headers"]}
    assert "user-agent" not in sent_headers
    assert "accept" not in sent_headers
    assert sent_headers["x-keep"] == "1"
    assert got.status_code == 200
    assert got.content == b"ok"
    assert got.headers["x-test"] == "ok"
    assert "content-encoding" not in got.headers


def test_streaming_response_preserves_chunks_and_closes_curl_response():
    response = _FakeCurlResponse(chunks=[b"chunk-1", b"chunk-2"])
    session = _FakeCurlSession(response)
    client = CurlCffiClient("chrome124")
    object.__setattr__(client, "_curl_session", session)
    request = client.build_request("GET", "https://example.test/stream")

    try:
        got = client.send(request, stream=True)
        assert got.status_code == 200
        assert list(got.iter_bytes()) == [b"chunk-1", b"chunk-2"]
        got.close()
    finally:
        client.close()

    assert session.calls[0]["stream"] is True
    assert response.closed is True
