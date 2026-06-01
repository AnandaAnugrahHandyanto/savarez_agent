"""Tests for Slack Block Kit approval-button fail-closed auth.

When SLACK_ALLOWED_USERS is not configured, _handle_approval_action must
deny approval-button clicks by default unless GATEWAY_ALLOW_ALL_USERS=true.
Button clicks bypass the normal message auth flow, so an unset allowlist
must not silently authorize every workspace member in the channel.
Mirrors the Telegram _is_callback_user_authorized fix (#24457).
"""

import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Ensure the repo root is importable
# ---------------------------------------------------------------------------
_repo = str(Path(__file__).resolve().parents[2])
if _repo not in sys.path:
    sys.path.insert(0, _repo)


# ---------------------------------------------------------------------------
# Minimal Slack SDK mock so SlackAdapter can be imported
# ---------------------------------------------------------------------------
def _ensure_slack_mock():
    if "slack_bolt" in sys.modules:
        return
    slack_bolt = MagicMock()
    slack_bolt.async_app.AsyncApp = MagicMock
    sys.modules["slack_bolt"] = slack_bolt
    sys.modules["slack_bolt.async_app"] = slack_bolt.async_app
    handler_mod = MagicMock()
    handler_mod.AsyncSocketModeHandler = MagicMock
    sys.modules["slack_bolt.adapter"] = MagicMock()
    sys.modules["slack_bolt.adapter.socket_mode"] = MagicMock()
    sys.modules["slack_bolt.adapter.socket_mode.async_handler"] = handler_mod
    sdk_mod = MagicMock()
    sdk_mod.web = MagicMock()
    sdk_mod.web.async_client = MagicMock()
    sdk_mod.web.async_client.AsyncWebClient = MagicMock
    sys.modules["slack_sdk"] = sdk_mod
    sys.modules["slack_sdk.web"] = sdk_mod.web
    sys.modules["slack_sdk.web.async_client"] = sdk_mod.web.async_client


_ensure_slack_mock()

from gateway.platforms.slack import SlackAdapter  # noqa: E402
from gateway.config import PlatformConfig  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_adapter():
    config = PlatformConfig(enabled=True, token="xoxb-test-token")
    adapter = SlackAdapter(config)
    adapter._app = MagicMock()
    adapter._bot_user_id = "U_BOT"
    # Pre-register the pending approval so the double-click guard (atomic pop)
    # lets the handler proceed past the auth gate when authorized.
    adapter._approval_resolved = {"123.456": False}
    adapter._get_client = MagicMock(return_value=AsyncMock())
    return adapter


def _body(user_id):
    return {
        "user": {"id": user_id, "name": "tester"},
        "message": {"ts": "123.456", "blocks": []},
        "channel": {"id": "C1"},
    }


_ACTION = {"action_id": "hermes_approve_always", "value": "session-xyz"}


def _run_click(adapter, user_id):
    """Invoke _handle_approval_action and report whether the approval was
    resolved (i.e. the click was treated as authorized)."""
    resolve = MagicMock(return_value=1)
    fake_approval = types.ModuleType("tools.approval")
    fake_approval.resolve_gateway_approval = resolve
    with patch.dict(sys.modules, {"tools.approval": fake_approval}):
        import asyncio

        asyncio.run(
            adapter._handle_approval_action(
                ack=AsyncMock(), body=_body(user_id), action=_ACTION
            )
        )
    return resolve.called


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSlackApprovalFailClosed:
    """_handle_approval_action auth must be fail-closed (parity with Telegram #24457)."""

    def test_no_allowlist_no_allow_all_denies(self, monkeypatch):
        monkeypatch.delenv("SLACK_ALLOWED_USERS", raising=False)
        monkeypatch.delenv("GATEWAY_ALLOW_ALL_USERS", raising=False)
        assert _run_click(_make_adapter(), "U_STRANGER") is False

    def test_no_allowlist_allow_all_permits(self, monkeypatch):
        monkeypatch.delenv("SLACK_ALLOWED_USERS", raising=False)
        monkeypatch.setenv("GATEWAY_ALLOW_ALL_USERS", "true")
        assert _run_click(_make_adapter(), "U_ANYONE") is True

    def test_wildcard_allowlist_permits(self, monkeypatch):
        monkeypatch.delenv("GATEWAY_ALLOW_ALL_USERS", raising=False)
        monkeypatch.setenv("SLACK_ALLOWED_USERS", "*")
        assert _run_click(_make_adapter(), "U_ANYONE") is True

    def test_listed_user_permits(self, monkeypatch):
        monkeypatch.delenv("GATEWAY_ALLOW_ALL_USERS", raising=False)
        monkeypatch.setenv("SLACK_ALLOWED_USERS", "U_ALICE,U_BOB")
        assert _run_click(_make_adapter(), "U_ALICE") is True

    def test_unlisted_user_denies(self, monkeypatch):
        monkeypatch.delenv("GATEWAY_ALLOW_ALL_USERS", raising=False)
        monkeypatch.setenv("SLACK_ALLOWED_USERS", "U_ALICE,U_BOB")
        assert _run_click(_make_adapter(), "U_MALLORY") is False
