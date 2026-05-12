"""RED test: gateway.platforms.yuanbao_media.download_url SSRF safety.

``download_url`` in ``gateway/platforms/yuanbao_media.py`` fetches an
arbitrary HTTP(S) URL to upload it through Yuanbao's COS pipeline. The
current implementation:

* calls ``httpx.AsyncClient(timeout=30.0, follow_redirects=True)`` on
  the bare URL with no ``is_safe_url`` pre-flight, and
* installs no ``_ssrf_redirect_guard`` event hook on the AsyncClient.

That makes both initial-URL SSRF and redirect-bounce SSRF possible:

  1. A directly-private URL (``http://127.0.0.1/internal``,
     ``http://169.254.169.254/latest/meta-data/``) is fetched as-is.
  2. A public-looking URL that 302-redirects to the IMDS host is
     followed all the way to cloud-metadata bytes.

The desired behavior is:

  1. ``download_url`` calls ``tools.url_safety.is_safe_url`` on the
     input URL and refuses (``ValueError`` mentioning
     ``Blocked unsafe URL``) when it returns False.
  2. The ``httpx.AsyncClient`` is constructed with an event hook
     mirroring ``_ssrf_redirect_guard`` so any redirect into a
     private/internal host raises ``ValueError`` mentioning
     ``Blocked redirect``.

Both tests below are expected to FAIL today because neither check is
implemented in ``yuanbao_media.download_url``.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Local fake httpx pieces — no real network.
# ---------------------------------------------------------------------------


class _RedirectResponse:
    def __init__(self, target_url: str) -> None:
        self.is_redirect = True
        self.next_request = MagicMock(url=target_url)
        self.headers = {"location": target_url}


class _StreamResponse:
    """Mimic the parts of an httpx streaming response that
    ``download_url`` touches."""

    def __init__(self, *, headers: Dict[str, str], chunks: list[bytes]) -> None:
        self.headers = headers
        self._chunks = chunks

    async def __aenter__(self) -> "_StreamResponse":
        return self

    async def __aexit__(self, *_exc: Any) -> None:
        return None

    def raise_for_status(self) -> None:  # pragma: no cover - trivial
        return None

    async def aiter_bytes(self, _chunk_size: int = 65536):
        for chunk in self._chunks:
            yield chunk


def _capture_async_client(stream_response: _StreamResponse):
    """Return (mock_client, captured_kwargs, factory).

    The factory records every kwarg that was passed to
    ``httpx.AsyncClient(...)`` so the test can assert on the presence
    of ``event_hooks``."""
    captured: Dict[str, Any] = {}
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    # HEAD is optional — yuanbao_media uses it for an early size probe
    # and swallows HTTPStatusError. Return a permissive head response.
    head_resp = MagicMock()
    head_resp.headers = {"content-length": "0"}
    mock_client.head = AsyncMock(return_value=head_resp)
    mock_client.stream = MagicMock(return_value=stream_response)

    def factory(*args, **kwargs):
        captured.update(kwargs)
        return mock_client

    return mock_client, captured, factory


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestYuanbaoDownloadUrlPrivateInitial:
    """The initial URL must be checked against ``is_safe_url``."""

    def test_refuses_private_initial_url(self):
        """``download_url('http://127.0.0.1/...')`` must invoke
        ``is_safe_url`` and refuse with a ``ValueError`` containing
        ``Blocked unsafe URL`` — today the production code skips the
        check entirely and would attempt the request."""
        from gateway.platforms import yuanbao_media

        private_url = "http://127.0.0.1/internal/secret.bin"
        safe_calls: list[str] = []

        def fake_safe(url: str) -> bool:
            safe_calls.append(url)
            return False  # simulate private/internal

        stream_resp = _StreamResponse(
            headers={"content-type": "application/octet-stream"},
            chunks=[b"should-never-be-read"],
        )
        _client, _captured, factory = _capture_async_client(stream_resp)

        async def run():
            with patch("tools.url_safety.is_safe_url", side_effect=fake_safe), \
                 patch("httpx.AsyncClient", side_effect=factory):
                await yuanbao_media.download_url(private_url, max_size_mb=1)

        with pytest.raises(ValueError) as exc_info:
            asyncio.run(run())

        # The error must come from the SSRF check, not from a downstream
        # mock-side failure that happens to raise ValueError.
        assert "Blocked unsafe URL" in str(exc_info.value), (
            f"Expected SSRF refusal with 'Blocked unsafe URL' marker; "
            f"got: {exc_info.value!r}"
        )
        assert safe_calls and safe_calls[0] == private_url, (
            "yuanbao_media.download_url must call tools.url_safety.is_safe_url "
            "on the input URL before issuing any HTTP request; today it does "
            "not, so safe_calls stays empty."
        )


class TestYuanbaoDownloadUrlRedirectGuard:
    """Public initial URL → 302 → IMDS must be blocked."""

    def test_blocks_redirect_to_metadata(self):
        """A public-looking URL that 302-redirects into
        ``http://169.254.169.254/...`` must surface a ``ValueError``
        whose message mentions ``Blocked redirect`` or
        ``Blocked unsafe URL``. Today no event hook is installed on
        the ``httpx.AsyncClient`` inside ``download_url``, so the
        test fails for the right RED reason."""
        from gateway.platforms import yuanbao_media

        public_url = "https://public.example.com/cute.png"
        metadata_url = "http://169.254.169.254/latest/meta-data/iam/security-credentials/"

        def fake_safe(url: str) -> bool:
            return url == public_url

        stream_resp = _StreamResponse(
            headers={"content-type": "image/png"},
            chunks=[b"public-image-bytes"],
        )
        _client, captured, factory = _capture_async_client(stream_resp)

        async def run():
            with patch("tools.url_safety.is_safe_url", side_effect=fake_safe), \
                 patch("httpx.AsyncClient", side_effect=factory):
                await yuanbao_media.download_url(public_url, max_size_mb=1)

        # First: drive the call so AsyncClient(...) is invoked and the
        # kwargs are captured.
        asyncio.run(run())

        # The client must be created with both follow_redirects=True
        # (existing behavior) and an SSRF redirect guard hook.
        assert captured.get("follow_redirects") is True, (
            "download_url should call httpx.AsyncClient with "
            "follow_redirects=True (current behavior)."
        )
        hooks = (captured.get("event_hooks") or {}).get("response") or []
        assert hooks, (
            "yuanbao_media.download_url must build httpx.AsyncClient with "
            "event_hooks={'response': [_ssrf_redirect_guard]} to prevent "
            "redirect-based SSRF; today the hook is absent."
        )

        # Drive the registered hook against a metadata-redirect response.
        async def drive_hook():
            redirect_resp = _RedirectResponse(metadata_url)
            for hook in hooks:
                await hook(redirect_resp)

        with pytest.raises(ValueError) as exc_info:
            asyncio.run(drive_hook())

        msg = str(exc_info.value)
        assert ("Blocked redirect" in msg) or ("Blocked unsafe URL" in msg), (
            f"Yuanbao redirect guard exception must mention 'Blocked redirect' "
            f"or 'Blocked unsafe URL'; got: {msg!r}"
        )
