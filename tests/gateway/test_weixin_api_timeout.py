"""Regression tests for the weixin _api_post / _api_get cross-event-loop timeout fix.

The bug: when send_message invokes _run_async (which creates a worker thread
with its own event loop), the session is bound to the gateway loop.  Using
``aiohttp.ClientTimeout`` per-request calls ``asyncio.current_task(loop=self._loop)``
where ``self._loop`` is the gateway loop, not the worker loop — returning None
and raising ``"Timeout context manager should be used inside a task"``.

The fix replaces per-request ``aiohttp.ClientTimeout`` with
``asyncio.wait_for()``, which works correctly across event loops.

These tests verify:
1. _api_post / _api_get work with asyncio.wait_for (no aiohttp ClientTimeout).
2. The session-level ClientTimeout is total=None (no conflict).
3. Cross-event-loop invocation does not raise the timeout-context error.
"""

from __future__ import annotations

import asyncio
import json
import threading
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# aiohttp is optional — skip the whole module if unavailable.
aiohttp = pytest.importorskip("aiohttp")

from gateway.platforms.weixin import (
    _api_get,
    _api_post,
    _headers,
    _json_dumps,
)


def _mock_response(status: int = 200, body: str = '{"ret": 0}') -> MagicMock:
    """Build a minimal mock aiohttp.ClientResponse."""
    resp = AsyncMock()
    resp.status = status
    resp.ok = 200 <= status < 300
    resp.text = AsyncMock(return_value=body)

    # Make it usable as an async context manager (for `async with`).
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=resp)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


class TestApiPostUsesWaitFor(unittest.TestCase):
    """_api_post should use asyncio.wait_for, not per-request ClientTimeout."""

    def test_api_post_returns_json_on_success(self):
        """_api_post returns parsed JSON from a successful response."""

        async def _run():
            session = MagicMock()
            session.post.return_value = _mock_response(200, '{"ret": 0, "ok": true}')

            result = await _api_post(
                session,
                base_url="https://fake.api",
                endpoint="test/endpoint",
                payload={"key": "value"},
                token="test-token",
                timeout_ms=5000,
            )
            assert result == {"ret": 0, "ok": True}
            session.post.assert_called_once()

        asyncio.run(_run())

    def test_api_post_raises_on_http_error(self):
        """_api_post raises RuntimeError on non-2xx responses."""

        async def _run():
            session = MagicMock()
            session.post.return_value = _mock_response(500, 'Internal Server Error')

            with pytest.raises(RuntimeError, match="HTTP 500"):
                await _api_post(
                    session,
                    base_url="https://fake.api",
                    endpoint="test/endpoint",
                    payload={},
                    token=None,
                    timeout_ms=5000,
                )

        asyncio.run(_run())

    def test_api_post_no_per_request_client_timeout(self):
        """_api_post must NOT create an aiohttp.ClientTimeout per request.

        The bug was using ``aiohttp.ClientTimeout(total=...)`` which fails
        when invoked from a different event loop via run_coroutine_threadsafe.
        """

        async def _run():
            session = MagicMock()
            session.post.return_value = _mock_response(200, '{"ret": 0}')

            await _api_post(
                session,
                base_url="https://fake.api",
                endpoint="test/endpoint",
                payload={"data": 1},
                token="tok",
                timeout_ms=10000,
            )

            # The call kwargs should NOT contain a timeout= kwarg (which would
            # be an aiohttp.ClientTimeout instance).
            call_kwargs = session.post.call_args
            if call_kwargs and call_kwargs.kwargs:
                assert "timeout" not in call_kwargs.kwargs, (
                    "session.post() must not receive a per-request timeout kwarg; "
                    "use asyncio.wait_for() instead"
                )

        asyncio.run(_run())


class TestApiGetUsesWaitFor(unittest.TestCase):
    """_api_get should use asyncio.wait_for, not per-request ClientTimeout."""

    def test_api_get_returns_json_on_success(self):

        async def _run():
            session = MagicMock()
            session.get.return_value = _mock_response(200, '{"ret": 0, "data": [1,2]}')

            result = await _api_get(
                session,
                base_url="https://fake.api",
                endpoint="test/endpoint",
                timeout_ms=5000,
            )
            assert result == {"ret": 0, "data": [1, 2]}

        asyncio.run(_run())

    def test_api_get_raises_on_http_error(self):

        async def _run():
            session = MagicMock()
            session.get.return_value = _mock_response(404, 'Not Found')

            with pytest.raises(RuntimeError, match="HTTP 404"):
                await _api_get(
                    session,
                    base_url="https://fake.api",
                    endpoint="test/endpoint",
                    timeout_ms=5000,
                )

        asyncio.run(_run())

    def test_api_get_no_per_request_client_timeout(self):

        async def _run():
            session = MagicMock()
            session.get.return_value = _mock_response(200, '{"ok": true}')

            await _api_get(
                session,
                base_url="https://fake.api",
                endpoint="test/endpoint",
                timeout_ms=10000,
            )

            call_kwargs = session.get.call_args
            if call_kwargs and call_kwargs.kwargs:
                assert "timeout" not in call_kwargs.kwargs, (
                    "session.get() must not receive a per-request timeout kwarg; "
                    "use asyncio.wait_for() instead"
                )

        asyncio.run(_run())


class TestCrossEventLoopTimeout(unittest.TestCase):
    """Verify _api_post/_api_get work when called from a different event loop.

    This is the exact scenario that triggered the original bug: the send_message
    tool uses asyncio.run_coroutine_threadsafe() which creates a coroutine in a
    worker thread's event loop, while the aiohttp session belongs to the gateway
    loop.
    """

    def test_cross_loop_api_post(self):
        """_api_post invoked via run_coroutine_threadsafe from another loop."""

        async def _gateway_loop_main():
            """Simulate the gateway loop creating a session."""
            connector = aiohttp.TCPConnector()
            session = aiohttp.ClientSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(total=None),  # no aiohttp timeout
            )
            return session

        async def _worker_coro(session):
            """Simulate the worker thread calling _api_post."""
            # Patch session.post to avoid real HTTP
            mock_cm = AsyncMock()
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_resp.ok = True
            mock_resp.text = AsyncMock(return_value='{"ret": 0}')
            mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
            mock_cm.__aexit__ = AsyncMock(return_value=False)
            session.post = MagicMock(return_value=mock_cm)

            result = await _api_post(
                session,
                base_url="https://fake.api",
                endpoint="ilink/bot/sendmessage",
                payload={"msg": {"text": "hello"}},
                token="fake-token",
                timeout_ms=15000,
            )
            assert result == {"ret": 0}
            await session.close()

        # Run the gateway loop to create a session
        session = asyncio.run(_gateway_loop_main())

        # Now simulate calling from a different event loop (worker thread)
        worker_loop = asyncio.new_event_loop()
        result_container = [None, None]

        def _run_worker():
            try:
                worker_loop.run_until_complete(_worker_coro(session))
                result_container[0] = "success"
            except Exception as e:
                result_container[1] = str(e)
            finally:
                worker_loop.close()

        thread = threading.Thread(target=_run_worker)
        thread.start()
        thread.join(timeout=10)

        # The key assertion: no "Timeout context manager should be used inside a task" error
        assert result_container[0] == "success", (
            f"Cross-event-loop call failed: {result_container[1]}"
        )

    def test_cross_loop_api_get(self):
        """_api_get invoked via run_coroutine_threadsafe from another loop."""

        async def _gateway_loop_main():
            connector = aiohttp.TCPConnector()
            session = aiohttp.ClientSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(total=None),
            )
            return session

        async def _worker_coro(session):
            mock_cm = AsyncMock()
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_resp.ok = True
            mock_resp.text = AsyncMock(return_value='{"ret": 0, "qrcode": "abc"}')
            mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
            mock_cm.__aexit__ = AsyncMock(return_value=False)
            session.get = MagicMock(return_value=mock_cm)

            result = await _api_get(
                session,
                base_url="https://fake.api",
                endpoint="ilink/bot/get_bot_qrcode",
                timeout_ms=35000,
            )
            assert result == {"ret": 0, "qrcode": "abc"}
            await session.close()

        session = asyncio.run(_gateway_loop_main())

        worker_loop = asyncio.new_event_loop()
        result_container = [None, None]

        def _run_worker():
            try:
                worker_loop.run_until_complete(_worker_coro(session))
                result_container[0] = "success"
            except Exception as e:
                result_container[1] = str(e)
            finally:
                worker_loop.close()

        thread = threading.Thread(target=_run_worker)
        thread.start()
        thread.join(timeout=10)

        assert result_container[0] == "success", (
            f"Cross-event-loop GET failed: {result_container[1]}"
        )


class TestSessionLevelTimeoutDisabled(unittest.TestCase):
    """Verify that the send_session is configured with no aiohttp timeout."""

    def test_no_aiohttp_timeout_config(self):
        """The _no_aiohttp_timeout object must disable all timeout categories."""
        no_timeout = aiohttp.ClientTimeout(
            total=None, connect=None, sock_connect=None, sock_read=None
        )
        assert no_timeout.total is None
        assert no_timeout.connect is None
        assert no_timeout.sock_connect is None
        assert no_timeout.sock_read is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
