"""RED test: Feishu media download must re-validate redirects.

``FeishuAdapter._download_remote_document`` (gateway/platforms/feishu.py)
is the entry point for fetching remote document/animation media before
re-uploading to the Lark/Feishu APIs. It performs an ``is_safe_url``
pre-flight check, then builds an
``httpx.AsyncClient(timeout=30.0, follow_redirects=True)`` *without*
the shared ``_ssrf_redirect_guard`` event hook.

Consequence: a public-looking URL that 302-redirects to
``http://169.254.169.254/latest/meta-data/`` is silently followed and
the cloud-metadata bytes get cached + re-uploaded.

The desired behavior — re-validating each redirect target via
``event_hooks={'response': [_ssrf_redirect_guard]}`` — raises
``ValueError('Blocked redirect to private/internal address: ...')``.

This RED test asserts:
  1. The ``httpx.AsyncClient`` used by ``_download_remote_document``
     is configured with a response event hook (the redirect guard).
  2. Invoking that hook against a redirect-to-metadata response raises
     a ``ValueError`` whose message mentions ``Blocked redirect`` or
     ``Blocked unsafe URL``.

We additionally exercise the public-facing call path so a future
``_download_remote_bytes`` helper that other Feishu code might call
remains covered. Today both assertions fail because no hook is
installed.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gateway.config import PlatformConfig


# ---------------------------------------------------------------------------
# Local fake httpx pieces — no real network.
# ---------------------------------------------------------------------------


class _FakeResponse:
    """Mimic the parts of an httpx response that the Feishu code touches."""

    def __init__(
        self,
        *,
        headers: Dict[str, str] | None = None,
        content: bytes = b"",
    ) -> None:
        self.headers = headers or {"Content-Type": "application/octet-stream"}
        self.content = content

    def raise_for_status(self) -> None:  # pragma: no cover - trivial
        return None


class _FakeAsyncClient:
    """Capture kwargs at construction time so the test can assert that
    ``event_hooks={"response": [_ssrf_redirect_guard]}`` was passed."""

    def __init__(self, *_args: Any, **kwargs: Any) -> None:
        _FakeAsyncClient.captured_kwargs = kwargs  # type: ignore[attr-defined]

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(self, *_exc: Any) -> None:
        return None

    async def get(self, *_args: Any, **_kwargs: Any) -> _FakeResponse:
        return _FakeResponse(
            headers={"Content-Type": "application/octet-stream"},
            content=b"public-doc-bytes",
        )


class _RedirectResponse:
    def __init__(self, target_url: str) -> None:
        self.is_redirect = True
        self.next_request = MagicMock(url=target_url)
        self.headers = {"location": target_url}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFeishuDownloadRemoteDocumentRedirect:
    """``_download_remote_document`` must re-validate redirects."""

    def test_async_client_uses_redirect_guard_hook(self):
        """The ``httpx.AsyncClient`` built inside
        ``_download_remote_document`` must register a response event
        hook so each redirect target is re-checked. Today the call
        passes only ``timeout`` + ``follow_redirects`` — no hook — so
        this fails for the right RED reason."""
        from gateway.platforms.feishu import FeishuAdapter

        adapter = FeishuAdapter(PlatformConfig())

        # Reset captured state — each test instance gets a fresh slate.
        _FakeAsyncClient.captured_kwargs = {}  # type: ignore[attr-defined]

        async def run():
            with patch("tools.url_safety.is_safe_url", return_value=True), \
                 patch("httpx.AsyncClient", _FakeAsyncClient), \
                 patch(
                     "gateway.platforms.feishu.cache_document_from_bytes",
                     return_value="/tmp/cached-doc.bin",
                 ):
                return await adapter._download_remote_document(
                    "https://public.example.com/document.pdf",
                    default_ext=".pdf",
                    preferred_name="document",
                )

        asyncio.run(run())

        captured = getattr(_FakeAsyncClient, "captured_kwargs", {})
        assert captured.get("follow_redirects") is True
        event_hooks = captured.get("event_hooks") or {}
        response_hooks = event_hooks.get("response") or []
        assert response_hooks, (
            "FeishuAdapter._download_remote_document must build httpx.AsyncClient "
            "with event_hooks={'response': [_ssrf_redirect_guard]} to prevent "
            "redirect-based SSRF; today the hook is absent."
        )

    def test_redirect_to_metadata_raises_blocked_message(self):
        """The redirect hook registered by ``_download_remote_document``
        must reject a 302 → 169.254.169.254 with a ``ValueError`` whose
        message mentions ``Blocked redirect`` or ``Blocked unsafe URL``."""
        from gateway.platforms.feishu import FeishuAdapter

        adapter = FeishuAdapter(PlatformConfig())

        _FakeAsyncClient.captured_kwargs = {}  # type: ignore[attr-defined]

        public_url = "https://public.example.com/document.pdf"
        metadata_url = "http://169.254.169.254/latest/meta-data/iam/security-credentials/"

        def fake_safe(url: str) -> bool:
            return url == public_url

        async def run():
            with patch("tools.url_safety.is_safe_url", side_effect=fake_safe), \
                 patch("httpx.AsyncClient", _FakeAsyncClient), \
                 patch(
                     "gateway.platforms.feishu.cache_document_from_bytes",
                     return_value="/tmp/cached-doc.bin",
                 ):
                await adapter._download_remote_document(
                    public_url,
                    default_ext=".pdf",
                    preferred_name="document",
                )

        asyncio.run(run())

        captured = getattr(_FakeAsyncClient, "captured_kwargs", {})
        hooks = (captured.get("event_hooks") or {}).get("response") or []
        assert hooks, (
            "Feishu _download_remote_document did not install a redirect "
            "guard hook on httpx.AsyncClient — SSRF redirect protection "
            "is missing."
        )

        async def drive_hook():
            redirect_resp = _RedirectResponse(metadata_url)
            for hook in hooks:
                await hook(redirect_resp)

        with pytest.raises(ValueError) as exc_info:
            asyncio.run(drive_hook())

        msg = str(exc_info.value)
        assert ("Blocked redirect" in msg) or ("Blocked unsafe URL" in msg), (
            f"Feishu redirect guard exception must mention 'Blocked redirect' "
            f"or 'Blocked unsafe URL'; got: {msg!r}"
        )


class TestFeishuDownloadRemoteBytesRedirect:
    """When Feishu acquires a generic ``_download_remote_bytes`` (parity with
    WeCom) it must also install the redirect guard. Today the helper does
    not exist on FeishuAdapter; until it does, this test guards against any
    refactor that re-introduces ``follow_redirects=True`` without the hook.

    Implementation note: the FeishuAdapter currently funnels every remote
    fetch through ``_download_remote_document`` (and ``cache_image_from_url``
    in base.py, which is already guarded). The test below uses
    ``_download_remote_document`` as the canonical bytes-fetching entry
    point and asserts the same redirect-guard contract — so any future
    rename to ``_download_remote_bytes`` continues to be covered by name.
    """

    def test_remote_document_bytes_path_blocks_redirect_to_imds(self):
        from gateway.platforms.feishu import FeishuAdapter

        adapter = FeishuAdapter(PlatformConfig())
        _FakeAsyncClient.captured_kwargs = {}  # type: ignore[attr-defined]

        public_url = "https://public.example.com/data.bin"
        metadata_url = "http://169.254.169.254/latest/meta-data/"

        def fake_safe(url: str) -> bool:
            return url == public_url

        async def run():
            with patch("tools.url_safety.is_safe_url", side_effect=fake_safe), \
                 patch("httpx.AsyncClient", _FakeAsyncClient), \
                 patch(
                     "gateway.platforms.feishu.cache_document_from_bytes",
                     return_value="/tmp/cached-doc.bin",
                 ):
                await adapter._download_remote_document(
                    public_url,
                    default_ext=".bin",
                    preferred_name="data",
                )

        asyncio.run(run())

        captured = getattr(_FakeAsyncClient, "captured_kwargs", {})
        hooks = (captured.get("event_hooks") or {}).get("response") or []
        assert hooks, (
            "Feishu remote-bytes fetch must build httpx.AsyncClient with a "
            "redirect re-validation hook."
        )

        async def drive_hook():
            redirect_resp = _RedirectResponse(metadata_url)
            for hook in hooks:
                await hook(redirect_resp)

        with pytest.raises(ValueError, match=r"Blocked (redirect|unsafe URL)"):
            asyncio.run(drive_hook())
