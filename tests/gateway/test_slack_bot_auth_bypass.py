"""Regression guard for Slack bot-sender authorization bypass.

SlackAdapter can accept bot messages when `allow_bots: mentions` and the text
contains the bot mention.  The gateway authz layer must then honor
SLACK_ALLOW_BOTS too; otherwise the adapter admits the event but GatewayRunner
rejects it as an unauthorized bot sender, making main→subordinate mentions look
silent.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from gateway.session import Platform, SessionSource


@pytest.fixture(autouse=True)
def _isolate_slack_env(monkeypatch):
    for var in (
        "SLACK_ALLOW_BOTS",
        "SLACK_ALLOWED_USERS",
        "SLACK_ALLOW_ALL_USERS",
        "GATEWAY_ALLOW_ALL_USERS",
        "GATEWAY_ALLOWED_USERS",
    ):
        monkeypatch.delenv(var, raising=False)


def _make_bare_runner():
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner.pairing_store = SimpleNamespace(is_approved=lambda *_a, **_kw: False)  # type: ignore[assignment]
    return runner


def _make_slack_bot_source(user_id: str = "U_PEER_BOT"):
    return SessionSource(
        platform=Platform.SLACK,
        chat_id="C1",
        chat_type="group",
        user_id=user_id,
        user_name="PeerBot",
        is_bot=True,
    )


def _make_slack_human_source(user_id: str = "U_HUMAN"):
    return SessionSource(
        platform=Platform.SLACK,
        chat_id="C1",
        chat_type="group",
        user_id=user_id,
        user_name="Human",
        is_bot=False,
    )


def test_slack_bot_authorized_when_allow_bots_mentions(monkeypatch):
    runner = _make_bare_runner()
    monkeypatch.setenv("SLACK_ALLOW_BOTS", "mentions")
    monkeypatch.setenv("SLACK_ALLOWED_USERS", "U_HUMAN")

    assert runner._is_user_authorized(_make_slack_bot_source("U_PEER_BOT")) is True


def test_slack_bot_authorized_when_allow_bots_all(monkeypatch):
    runner = _make_bare_runner()
    monkeypatch.setenv("SLACK_ALLOW_BOTS", "all")
    monkeypatch.setenv("SLACK_ALLOWED_USERS", "U_HUMAN")

    assert runner._is_user_authorized(_make_slack_bot_source()) is True


def test_slack_bot_not_authorized_when_allow_bots_none(monkeypatch):
    runner = _make_bare_runner()
    monkeypatch.setenv("SLACK_ALLOW_BOTS", "none")
    monkeypatch.setenv("SLACK_ALLOWED_USERS", "U_HUMAN")

    assert runner._is_user_authorized(_make_slack_bot_source("U_PEER_BOT")) is False


def test_slack_bot_not_authorized_when_allow_bots_unset(monkeypatch):
    runner = _make_bare_runner()
    monkeypatch.setenv("SLACK_ALLOWED_USERS", "U_HUMAN")

    assert runner._is_user_authorized(_make_slack_bot_source("U_PEER_BOT")) is False


def test_slack_human_still_checked_against_allowlist_when_bot_policy_set(monkeypatch):
    """SLACK_ALLOW_BOTS=all must NOT open the gate for humans."""
    runner = _make_bare_runner()
    monkeypatch.setenv("SLACK_ALLOW_BOTS", "all")
    monkeypatch.setenv("SLACK_ALLOWED_USERS", "U_HUMAN")

    assert runner._is_user_authorized(_make_slack_human_source("U_STRANGER")) is False
    assert runner._is_user_authorized(_make_slack_human_source("U_HUMAN")) is True


def test_slack_bot_bypass_does_not_leak_to_other_platforms(monkeypatch):
    """SLACK_ALLOW_BOTS=all must not authorize Telegram bot sources."""
    runner = _make_bare_runner()
    monkeypatch.setenv("SLACK_ALLOW_BOTS", "all")

    telegram_bot = SessionSource(
        platform=Platform.TELEGRAM,
        chat_id="123",
        chat_type="channel",
        user_id="999",
        is_bot=True,
    )
    assert runner._is_user_authorized(telegram_bot) is False
