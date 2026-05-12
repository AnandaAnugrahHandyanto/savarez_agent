"""RED test: WeCom media download must re-validate redirects.

``WeComAdapter._download_remote_bytes`` (gateway/platforms/wecom.py) is
the single entry point for fetching outbound media and inbound
attachments from a remote HTTP(S) URL. It performs an
``is_safe_url`` pre-flight check, then builds an
``httpx.AsyncClient(timeout=30.0, follow_redirects=True)`` *without*
the shared ``_ssrf_redirect_guard`` event hook.

Consequence: a public-looking URL that 302-redirects to
``http://169.254.169.254/latest/meta-data/`` is silently followed and
returns cloud-metadata bytes that get uploaded to WeCom servers.

The desired behavior — re-validating each redirect target via
``event_hooks={'response': [_ssrf_redirect_guard]}`` — raises
``ValueError('Blocked redirect to private/internal address: ...')``.

This RED test asserts:
  1. The ``httpx.AsyncClient`` used by ``_download_remote_bytes`` is
     configured with a response event hook (the redirect guard).
  2. Invoking that hook against a redirect-to-metadata response raises
     a ``ValueError`` whose message mentions ``Blocked redirect`` or
     ``Blocked unsafe URL``.

Today both assertions fail because no hook is installed.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gateway.config import PlatformConfig


# ---------------------------------------------------------------------------
# Local fake httpx pieces — no real network.
# ---------------------------------------------------------------------------


class _FakeStreamResponse:
    """Mimic the parts of an httpx streaming response that
    ``_download_remote_bytes`` touches."""

    def __init__(self, *, headers: Dict[str, str], chunks: List[bytes]):
        self.headers = headers
        self._chunks = chunks

    async def __aenter__(self) -> "_FakeStreamResponse":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    def raise_for_status(self) -> None:  # pragma: no cover - trivial
        return None

    async def aiter_bytes(self):
        for chunk in self._chunks:
            yield chunk


class _RedirectResponse:
    """An httpx-shaped redirect response used to drive the guard."""

    def __init__(self, target_url: str) -> None:
        self.is_redirect = True
        self.next_request = MagicMock(url=target_url)
        self.headers = {"location": target_url}


def _capture_async_client():
    """Return (mock_client, captured_kwargs, factory)."""
    captured: Dict[str, Any] = {}
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    def factory(*args, **kwargs):
        captured.update(kwargs)
        return mock_client

    return mock_client, captured, factory


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestWeComDownloadRemoteBytesRedirect:
    """``_download_remote_bytes`` must re-validate redirects."""

    def test_async_client_uses_redirect_guard_hook(self):
        """``httpx.AsyncClient(...)`` constructed inside
        ``_download_remote_bytes`` must register a response event hook
        so each redirect target is re-checked. Today the call passes
        only ``timeout`` + ``follow_redirects`` — no hook — so this
        fails for the right RED reason."""
        from gateway.platforms.wecom import WeComAdapter

        adapter = WeComAdapter(PlatformConfig(enabled=True))
        adapter._http_client = None  # force the per-call client path

        mock_client, captured, factory = _capture_async_client()

        # The stream context returns immediately with empty bytes — we
        # only care about what was passed to httpx.AsyncClient(...).
        mock_client.stream = MagicMock(
            return_value=_FakeStreamResponse(
                headers={"content-length": "0", "content-type": "image/png"},
                chunks=[],
            )
        )

        async def run():
            with patch("tools.url_safety.is_safe_url", return_value=True), \
                 patch("gateway.platforms.wecom.httpx.AsyncClient", side_effect=factory):
                await adapter._download_remote_bytes(
                    "https://public.example.com/image.png",
                    max_bytes=4096,
                )

        asyncio.run(run())

        # ``follow_redirects=True`` without an event hook is the bug.
        assert captured.get("follow_redirects") is True
        event_hooks = captured.get("event_hooks") or {}
        response_hooks = event_hooks.get("response") or []
        assert response_hooks, (
            "WeComAdapter._download_remote_bytes must build httpx.AsyncClient "
            "with event_hooks={'response': [_ssrf_redirect_guard]} to prevent "
            "redirect-based SSRF; today the hook is absent."
        )

    def test_redirect_to_metadata_raises_blocked_message(self):
        """The redirect hook registered by ``_download_remote_bytes``
        must reject a 302 → 169.254.169.254 with a ``ValueError`` whose
        message mentions ``Blocked redirect`` or ``Blocked unsafe URL``."""
        from gateway.platforms.wecom import WeComAdapter

        adapter = WeComAdapter(PlatformConfig(enabled=True))
        adapter._http_client = None

        mock_client, captured, factory = _capture_async_client()
        mock_client.stream = MagicMock(
            return_value=_FakeStreamResponse(
                headers={"content-length": "0"},
                chunks=[],
            )
        )

        public_url = "https://public.example.com/file.bin"
        metadata_url = "http://169.254.169.254/latest/meta-data/iam/security-credentials/"

        def fake_safe(url: str) -> bool:
            return url == public_url

        async def run():
            with patch("tools.url_safety.is_safe_url", side_effect=fake_safe), \
                 patch("gateway.platforms.wecom.httpx.AsyncClient", side_effect=factory):
                await adapter._download_remote_bytes(public_url, max_bytes=4096)

        asyncio.run(run())

        hooks = (captured.get("event_hooks") or {}).get("response") or []
        assert hooks, (
            "WeCom _download_remote_bytes did not install a redirect guard "
            "hook on httpx.AsyncClient — SSRF redirect protection is missing."
        )

        async def drive_hook():
            redirect_resp = _RedirectResponse(metadata_url)
            for hook in hooks:
                await hook(redirect_resp)

        with pytest.raises(ValueError) as exc_info:
            asyncio.run(drive_hook())

        msg = str(exc_info.value)
        assert ("Blocked redirect" in msg) or ("Blocked unsafe URL" in msg), (
            f"WeCom redirect guard exception must mention 'Blocked redirect' "
            f"or 'Blocked unsafe URL'; got: {msg!r}"
        )
