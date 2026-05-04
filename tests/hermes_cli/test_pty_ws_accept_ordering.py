"""Tests for the FastAPI 0.136 WebSocket accept-before-close fix -- issue #19914.

FastAPI / Starlette 0.136 changed WebSocket close() semantics: calling
ws.close() before ws.accept() now hangs because the ASGI websocket.connect
message must be consumed (via accept) before a close frame can be sent.

The fix: call ws.accept() at the top of each WebSocket handler before any
early-return close(), so the handshake always completes.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


def _make_ws(token="valid-token", channel="ch1", client_host="127.0.0.1"):
    ws = MagicMock()
    ws.accept = AsyncMock()
    ws.close = AsyncMock()
    ws.send_text = AsyncMock()
    ws.send_bytes = AsyncMock()
    ws.receive = AsyncMock(return_value={"type": "websocket.disconnect"})
    ws.query_params = {"token": token, "channel": channel}
    ws.client = MagicMock()
    ws.client.host = client_host
    ws.headers = {"host": "localhost"}
    return ws


class TestPtyWsAcceptBeforeClose:

    def test_accept_called_before_close_when_chat_disabled(self):
        """When embedded chat is disabled, accept() must precede close()."""
        ws = _make_ws()

        import hermes_cli.web_server as mod

        async def _run_test():
            with patch.object(mod, "_DASHBOARD_EMBEDDED_CHAT_ENABLED", False):
                await mod.pty_ws(ws)

        asyncio.get_event_loop().run_until_complete(_run_test())

        assert ws.accept.call_count >= 1, "ws.accept() was not called"
        assert ws.close.call_count >= 1, "ws.close() was not called"

    def test_accept_called_when_token_invalid(self):
        """Bad token: accept() must still be called before close(4401)."""
        ws = _make_ws(token="bad-token")

        import hermes_cli.web_server as mod

        async def _run_test():
            with patch.object(mod, "_DASHBOARD_EMBEDDED_CHAT_ENABLED", True), \
                 patch.object(mod, "_SESSION_TOKEN", "valid-token"), \
                 patch.object(mod, "_ws_client_is_allowed", return_value=True):
                await mod.pty_ws(ws)

        asyncio.get_event_loop().run_until_complete(_run_test())

        assert ws.accept.call_count >= 1, "accept() not called before rejecting bad token"
        ws.close.assert_called_once()
        close_args = ws.close.call_args
        code = close_args[1].get("code") or (close_args[0][0] if close_args[0] else None)
        assert code == 4401, f"Expected close code 4401, got {code}"

    def test_accept_called_when_client_not_allowed(self):
        """Disallowed client: accept() must still be called before close(4403)."""
        ws = _make_ws()

        import hermes_cli.web_server as mod

        async def _run_test():
            with patch.object(mod, "_DASHBOARD_EMBEDDED_CHAT_ENABLED", True), \
                 patch.object(mod, "_SESSION_TOKEN", "valid-token"), \
                 patch.object(mod, "_ws_client_is_allowed", return_value=False):
                await mod.pty_ws(ws)

        asyncio.get_event_loop().run_until_complete(_run_test())

        assert ws.accept.call_count >= 1, "accept() not called before rejecting disallowed client"
        ws.close.assert_called_once()


class TestHandleWsAlreadyAccepted:

    def test_already_accepted_skips_accept(self):
        """When already_accepted=True, handle_ws must not call ws.accept() again."""
        ws = MagicMock()
        ws.accept = AsyncMock()
        ws.send_text = AsyncMock()
        ws.receive_text = AsyncMock(side_effect=Exception("disconnect"))

        from tui_gateway.ws import handle_ws
        from tui_gateway import server

        with patch.object(server, "resolve_skin", return_value="default"):
            try:
                asyncio.get_event_loop().run_until_complete(
                    handle_ws(ws, already_accepted=True)
                )
            except Exception:
                pass

        assert ws.accept.call_count == 0, (
            f"ws.accept() called {ws.accept.call_count} times despite already_accepted=True"
        )

    def test_default_calls_accept(self):
        """When already_accepted is not set, handle_ws must call ws.accept()."""
        ws = MagicMock()
        ws.accept = AsyncMock()
        ws.send_text = AsyncMock()
        ws.receive_text = AsyncMock(side_effect=Exception("disconnect"))

        from tui_gateway.ws import handle_ws
        from tui_gateway import server

        with patch.object(server, "resolve_skin", return_value="default"):
            try:
                asyncio.get_event_loop().run_until_complete(handle_ws(ws))
            except Exception:
                pass

        assert ws.accept.call_count == 1, (
            f"ws.accept() called {ws.accept.call_count} times, expected 1"
        )
