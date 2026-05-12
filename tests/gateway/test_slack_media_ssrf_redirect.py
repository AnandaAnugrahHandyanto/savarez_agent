"""RED test: Slack multi-image upload must re-validate redirects.

``SlackAdapter.send_multiple_images`` downloads each remote image via an
``httpx.AsyncClient`` built with ``follow_redirects=True``. Today that
client is constructed *without* the shared ``_ssrf_redirect_guard``
event hook, so a public-looking initial URL that responds with a 302
to ``http://169.254.169.254/latest/meta-data/`` is silently followed
and the cloud-metadata bytes get attached to the Slack message.

The desired behavior, mirroring ``cache_image_from_url`` /
``SlackAdapter.send_image``, is to either install an ``event_hooks``
redirect guard or otherwise verify the redirect target so the
attempted upload is dropped (``file_uploads`` stays empty) and the
Slack ``files_upload_v2`` API is never called with metadata content.

This test is expected to FAIL today because the production code path
does not register a redirect guard and would proxy IMDS bytes into the
multi-image batch.
"""

from __future__ import annotations

import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Mock the slack-bolt + slack-sdk packages so importing the adapter works
# without the real third-party dependencies installed.
# ---------------------------------------------------------------------------


def _ensure_slack_mock() -> None:
    if "slack_bolt" in sys.modules and hasattr(sys.modules["slack_bolt"], "__file__"):
        return
    slack_bolt = MagicMock()
    slack_bolt.async_app.AsyncApp = MagicMock
    slack_bolt.adapter.socket_mode.async_handler.AsyncSocketModeHandler = MagicMock
    slack_sdk = MagicMock()
    slack_sdk.web.async_client.AsyncWebClient = MagicMock
    for name, mod in [
        ("slack_bolt", slack_bolt),
        ("slack_bolt.async_app", slack_bolt.async_app),
        ("slack_bolt.adapter", slack_bolt.adapter),
        ("slack_bolt.adapter.socket_mode", slack_bolt.adapter.socket_mode),
        (
            "slack_bolt.adapter.socket_mode.async_handler",
            slack_bolt.adapter.socket_mode.async_handler,
        ),
        ("slack_sdk", slack_sdk),
        ("slack_sdk.web", slack_sdk.web),
        ("slack_sdk.web.async_client", slack_sdk.web.async_client),
    ]:
        sys.modules.setdefault(name, mod)
    sys.modules.setdefault("aiohttp", MagicMock())


_ensure_slack_mock()

import gateway.platforms.slack as _slack_mod  # noqa: E402
_slack_mod.SLACK_AVAILABLE = True

from gateway.config import PlatformConfig  # noqa: E402
from gateway.platforms.slack import SlackAdapter  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_slack_adapter() -> SlackAdapter:
    adapter = SlackAdapter(PlatformConfig(enabled=True, token="xoxb-fake"))
    adapter._app = MagicMock()
    adapter._app.client = AsyncMock()
    adapter._bot_user_id = "U_BOT"
    adapter._running = True
    return adapter


def _make_redirect_response(target_url: str) -> MagicMock:
    """Mock an httpx response that *would* be followed as a redirect."""
    resp = MagicMock()
    resp.is_redirect = True
    resp.next_request = MagicMock(url=target_url)
    resp.headers = {"content-type": "text/plain"}
    # If the production code follows the redirect without guarding, it will
    # ultimately treat the metadata payload as image bytes.
    resp.content = b"AKIA-FAKE-IAM-CREDENTIAL-FROM-IMDS"

    def _raise_for_status() -> None:
        return None

    resp.raise_for_status = _raise_for_status
    return resp


def _capture_async_client():
    """Return (mock_client, captured_kwargs, factory)."""
    captured: dict = {}
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    def factory(*args, **kwargs):
        captured.update(kwargs)
        return mock_client

    return mock_client, captured, factory


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


class TestSlackMultiImageSsrfRedirect:
    """``send_multiple_images`` must drop uploads whose downloads redirect
    into a private/internal IP (e.g. cloud metadata)."""

    def test_multi_image_blocks_redirect_to_imds(self, monkeypatch):
        """Public initial URL → 302 → IMDS must NOT result in a
        ``files_upload_v2`` call carrying metadata bytes.

        The guard mechanism mirrors the pattern in
        ``SlackAdapter.send_image`` and ``cache_image_from_url``: the
        ``httpx.AsyncClient`` is constructed with
        ``event_hooks={"response": [_ssrf_redirect_guard]}`` and the
        guard raises ``ValueError`` on a redirect to a private host.
        """
        adapter = _make_slack_adapter()

        # is_safe_url is True only for the *initial* public URL — a private
        # IP / metadata host must report False.
        public_url = "https://public.example.com/cute-cat.png"
        metadata_url = "http://169.254.169.254/latest/meta-data/"

        def fake_safe(url: str) -> bool:
            return url == public_url

        redirect_resp = _make_redirect_response(metadata_url)
        mock_client, captured, factory = _capture_async_client()

        async def fake_get(_url, **_kwargs):
            # If the production code installed the guard, invoking it on a
            # redirect-to-metadata response would raise ValueError before any
            # bytes were attached to the upload payload.
            hooks = (captured.get("event_hooks") or {}).get("response") or []
            for hook in hooks:
                await hook(redirect_resp)
            return redirect_resp

        mock_client.get = AsyncMock(side_effect=fake_get)

        # files_upload_v2 is the API that would carry the unsafe payload —
        # capture every call so we can assert nothing leaked.
        upload_mock = AsyncMock(return_value={"ok": True})
        adapter._app.client.files_upload_v2 = upload_mock
        adapter._get_client = MagicMock(return_value=adapter._app.client)

        async def run():
            with patch("tools.url_safety.is_safe_url", side_effect=fake_safe), \
                 patch("httpx.AsyncClient", side_effect=factory):
                await adapter.send_multiple_images(
                    chat_id="C123",
                    images=[(public_url, "alt text")],
                    metadata=None,
                    human_delay=0.0,
                )

        asyncio.run(run())

        # 1) The httpx.AsyncClient *must* be configured with a redirect
        #    re-validation hook. The slack send_image path uses event_hooks
        #    for exactly this; send_multiple_images currently omits it.
        event_hooks = captured.get("event_hooks") or {}
        response_hooks = event_hooks.get("response") or []
        assert response_hooks, (
            "Slack send_multiple_images must build httpx.AsyncClient with "
            "event_hooks={'response': [_ssrf_redirect_guard]} to prevent "
            "redirect-based SSRF; today the hook is absent."
        )

        # 2) The metadata payload must never be uploaded. If the guard is
        #    installed, the download will raise, the upload list stays
        #    empty, and files_upload_v2 is not called at all.
        if upload_mock.await_count > 0:
            for call in upload_mock.await_args_list:
                file_uploads = call.kwargs.get("file_uploads") or []
                for entry in file_uploads:
                    content = entry.get("content") or b""
                    assert b"IMDS" not in content and b"AKIA" not in content, (
                        "files_upload_v2 was called with metadata bytes from "
                        "169.254.169.254 — redirect was followed without "
                        "SSRF revalidation."
                    )

    def test_multi_image_redirect_guard_message_blocked(self, monkeypatch):
        """The redirect guard error must mention 'Blocked redirect' or
        'Blocked unsafe URL' so log audits / warning paths can match it.

        The slack path swallows download exceptions and continues, but the
        guard's *message* is still observable: tests in test_media_download_retry
        use ``pytest.raises(ValueError, match='Blocked redirect')`` against
        the production hook installed on the AsyncClient.

        Here we directly invoke whatever response hook send_multiple_images
        registered and verify it raises with the expected message — today
        no hook is registered, so the test fails the right way.
        """
        adapter = _make_slack_adapter()
        public_url = "https://public.example.com/img.png"
        metadata_url = "http://169.254.169.254/latest/meta-data/"

        def fake_safe(url: str) -> bool:
            return url == public_url

        redirect_resp = _make_redirect_response(metadata_url)
        mock_client, captured, factory = _capture_async_client()

        # Make .get a no-op so we just observe how AsyncClient was built.
        async def fake_get(_url, **_kwargs):
            return redirect_resp

        mock_client.get = AsyncMock(side_effect=fake_get)

        # Stop before doing any real Slack API call.
        adapter._get_client = MagicMock(return_value=MagicMock(
            files_upload_v2=AsyncMock(return_value={"ok": True})
        ))

        async def run():
            with patch("tools.url_safety.is_safe_url", side_effect=fake_safe), \
                 patch("httpx.AsyncClient", side_effect=factory):
                await adapter.send_multiple_images(
                    chat_id="C123",
                    images=[(public_url, "alt")],
                    metadata=None,
                    human_delay=0.0,
                )

        asyncio.run(run())

        hooks = (captured.get("event_hooks") or {}).get("response") or []
        assert hooks, (
            "send_multiple_images did not install a response event hook on "
            "httpx.AsyncClient — redirect-based SSRF is not prevented."
        )

        async def _drive_hook():
            for hook in hooks:
                await hook(redirect_resp)

        with pytest.raises(ValueError) as exc_info:
            asyncio.run(_drive_hook())

        msg = str(exc_info.value)
        assert ("Blocked redirect" in msg) or ("Blocked unsafe URL" in msg), (
            f"Redirect guard exception must mention 'Blocked redirect' or "
            f"'Blocked unsafe URL'; got: {msg!r}"
        )
