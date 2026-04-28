"""Tests for multi-sender visibility in busy acknowledgments and progress.

When a shared-session group has multiple participants, the busy/queue ack
and the tool-progress message must be wired up so that:

1. The ack message is a *reply* to the participant's own message — Telegram
   then draws a connecting line so each participant sees the bot answering
   *their* specific question.

2. The 30-second per-session debounce on busy acks is keyed per-sender, so
   when 玉青 just got an ack and 子家 sends a follow-up 5 seconds later,
   子家 still gets an ack instead of silence.

3. A topic-preview helper extracts a short summary from the user message,
   stripping any leading ``[name] `` shared-session sender prefix so the
   preview shows the real intent, not the marker.
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Stub telegram so gateway.run imports cleanly. (Same approach as
# tests/gateway/test_busy_session_ack.py.)
import sys
import types

_tg = types.ModuleType("telegram")
_tg.constants = types.ModuleType("telegram.constants")
_ct = MagicMock()
_ct.SUPERGROUP = "supergroup"
_ct.GROUP = "group"
_ct.PRIVATE = "private"
_tg.constants.ChatType = _ct
sys.modules.setdefault("telegram", _tg)
sys.modules.setdefault("telegram.constants", _tg.constants)
sys.modules.setdefault("telegram.ext", types.ModuleType("telegram.ext"))

from gateway.platforms.base import MessageEvent, MessageType
from gateway.session import SessionSource


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _shared_group_event(user_id, user_name, text, message_id):
    from gateway.config import Platform
    src = SessionSource(
        platform=Platform.TELEGRAM,
        chat_id="-1003964576906",
        chat_type="group",
        user_id=user_id,
        user_name=user_name,
    )
    return MessageEvent(
        text=text,
        message_type=MessageType.TEXT,
        source=src,
        message_id=message_id,
    )


def _make_runner():
    from gateway.run import GatewayRunner, _AGENT_PENDING_SENTINEL

    runner = object.__new__(GatewayRunner)
    runner._running_agents = {}
    runner._running_agents_ts = {}
    runner._pending_messages = {}
    runner._busy_ack_ts = {}
    runner._draining = False
    runner.adapters = {}
    runner.config = MagicMock()
    runner.config.busy_input_mode = "queue"
    runner.config.group_sessions_per_user = False
    runner.config.thread_sessions_per_user = False
    runner.session_store = None
    runner.hooks = MagicMock()
    runner.hooks.emit = AsyncMock()
    runner.pairing_store = MagicMock()
    runner.pairing_store.is_approved.return_value = True
    runner._is_user_authorized = lambda _source: True
    runner._busy_input_mode = "queue"
    return runner, _AGENT_PENDING_SENTINEL


def _make_adapter():
    from gateway.config import Platform
    adapter = MagicMock()
    adapter._pending_messages = {}
    adapter._send_with_retry = AsyncMock()
    adapter.send = AsyncMock()
    adapter.config = MagicMock()
    adapter.config.extra = {}
    adapter.platform = Platform.TELEGRAM
    return adapter


# ---------------------------------------------------------------------------
# Topic preview helper
# ---------------------------------------------------------------------------


def test_topic_preview_strips_sender_marker_and_truncates():
    """`topic_preview_for_progress` removes a leading [name] marker."""
    from gateway.run import topic_preview_for_progress

    raw = "[玉青] 米粉跟醬包各2，麻煩你幫我記一下今天的午餐熱量"
    out = topic_preview_for_progress(raw, max_chars=30)
    assert not out.startswith("[玉青]")
    # Some prefix of the actual content should be present.
    assert "米粉" in out
    # Truncated to roughly max_chars (allowing for ellipsis).
    assert len(out) <= 33


def test_topic_preview_handles_text_without_marker():
    from gateway.run import topic_preview_for_progress

    out = topic_preview_for_progress("水煮蛋一顆", max_chars=30)
    assert out == "水煮蛋一顆"


def test_topic_preview_handles_empty():
    from gateway.run import topic_preview_for_progress

    assert topic_preview_for_progress("", max_chars=30) == ""
    assert topic_preview_for_progress(None, max_chars=30) == ""


def test_topic_preview_strips_reply_prefix_too():
    """A reply prefix like '[Replying to ...]' followed by the real text
    should be skipped over so the preview reflects the new intent."""
    from gateway.run import topic_preview_for_progress

    raw = '[Replying to message from 玉青 at 13:02: "便當"]\n\n[子家] 看起來怎樣'
    out = topic_preview_for_progress(raw, max_chars=30)
    assert "看起來怎樣" in out
    assert "Replying" not in out
    assert "玉青" not in out  # the [玉青] marker (from the body) is also stripped


# ---------------------------------------------------------------------------
# Per-sender busy-ack debounce
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_busy_ack_per_sender_debounce_lets_second_user_through():
    """玉青 gets an ack, 子家 5s later in the same shared session must also
    get an ack (not silenced by the 30s per-session debounce)."""
    runner, sentinel = _make_runner()
    adapter = _make_adapter()
    from gateway.config import Platform
    runner.adapters[Platform.TELEGRAM] = adapter

    # Pretend an agent is running for this shared-session key.
    session_key = "agent:main:telegram:group:-1003964576906"
    running_agent = MagicMock()
    running_agent.get_activity_summary = MagicMock(
        return_value={"api_call_count": 1, "max_iterations": 90, "current_tool": None}
    )
    runner._running_agents[session_key] = running_agent
    runner._running_agents_ts[session_key] = time.time()

    yuqing = _shared_group_event("1285712441", "玉青", "米粉", message_id="m1")
    zijia = _shared_group_event("8682281996", "子家", "水煮蛋", message_id="m2")

    with patch("gateway.run._load_gateway_config", return_value={}):
        await runner._handle_active_session_busy_message(yuqing, session_key)
        # Now 子家 sends within the 30s window.
        await runner._handle_active_session_busy_message(zijia, session_key)

    # Both senders should have produced an outgoing ack.
    assert adapter._send_with_retry.await_count >= 2, (
        f"Expected at least 2 acks (one per sender), got "
        f"{adapter._send_with_retry.await_count}"
    )


@pytest.mark.asyncio
async def test_busy_ack_same_sender_still_debounced():
    """玉青 sends two messages within 30s — only the first ack should fire."""
    runner, sentinel = _make_runner()
    adapter = _make_adapter()
    from gateway.config import Platform
    runner.adapters[Platform.TELEGRAM] = adapter

    session_key = "agent:main:telegram:group:-1003964576906"
    running_agent = MagicMock()
    running_agent.get_activity_summary = MagicMock(
        return_value={"api_call_count": 1, "max_iterations": 90, "current_tool": None}
    )
    runner._running_agents[session_key] = running_agent
    runner._running_agents_ts[session_key] = time.time()

    first = _shared_group_event("1285712441", "玉青", "米粉", message_id="m1")
    second = _shared_group_event("1285712441", "玉青", "再加蛋", message_id="m2")

    with patch("gateway.run._load_gateway_config", return_value={}):
        await runner._handle_active_session_busy_message(first, session_key)
        await runner._handle_active_session_busy_message(second, session_key)

    # Only the first should have produced an ack.
    assert adapter._send_with_retry.await_count == 1


# ---------------------------------------------------------------------------
# Busy-ack reply_to wiring
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_busy_ack_replies_to_origin_message_id():
    """The ack message must reply to the originating message id so Telegram
    visually links the ack to the correct sender's message."""
    runner, sentinel = _make_runner()
    adapter = _make_adapter()
    from gateway.config import Platform
    runner.adapters[Platform.TELEGRAM] = adapter

    session_key = "agent:main:telegram:group:-1003964576906"
    running_agent = MagicMock()
    running_agent.get_activity_summary = MagicMock(
        return_value={"api_call_count": 1, "max_iterations": 90, "current_tool": None}
    )
    runner._running_agents[session_key] = running_agent
    runner._running_agents_ts[session_key] = time.time()

    evt = _shared_group_event("8682281996", "子家", "幫我查股票", message_id="msg-42")

    with patch("gateway.run._load_gateway_config", return_value={}):
        await runner._handle_active_session_busy_message(evt, session_key)

    assert adapter._send_with_retry.await_count == 1
    call = adapter._send_with_retry.await_args
    # Verify the call carried reply_to pointing at this sender's message.
    sent_kwargs = call.kwargs
    assert sent_kwargs.get("reply_to") == "msg-42"


# ---------------------------------------------------------------------------
# Progress header for shared-session multi-user groups
# ---------------------------------------------------------------------------


def test_build_progress_header_in_shared_session_marks_sender_and_topic():
    """`_build_progress_header(source, message)` returns a one-line topic
    header marking the sender and a short preview, used as the first line of
    the progress message in shared-session groups."""
    from gateway.config import Platform
    from gateway.run import _build_progress_header

    src = SessionSource(
        platform=Platform.TELEGRAM,
        chat_id="-1003964576906",
        chat_type="group",
        user_id="1285712441",
        user_name="玉青",
    )
    out = _build_progress_header(
        src,
        "[玉青] 米粉跟醬包各2",
        group_sessions_per_user=False,
        thread_sessions_per_user=False,
    )
    assert out is not None
    assert "玉青" in out
    assert "米粉" in out
    # It should be a single line — no embedded newline.
    assert "\n" not in out


def test_build_progress_header_dm_returns_none():
    """In a DM (single sender), no header is needed — return None."""
    from gateway.config import Platform
    from gateway.run import _build_progress_header

    src = SessionSource(
        platform=Platform.TELEGRAM,
        chat_id="8682281996",
        chat_type="dm",
        user_id="8682281996",
        user_name="子家",
    )
    assert (
        _build_progress_header(
            src,
            "幫我查股票",
            group_sessions_per_user=False,
            thread_sessions_per_user=False,
        )
        is None
    )


def test_build_progress_header_per_user_group_returns_none():
    """Per-user-isolated groups don't need a sender header either: each
    participant has their own session, so any progress message a user sees is
    necessarily theirs."""
    from gateway.config import Platform
    from gateway.run import _build_progress_header

    src = SessionSource(
        platform=Platform.TELEGRAM,
        chat_id="-1003964576906",
        chat_type="group",
        user_id="1285712441",
        user_name="玉青",
    )
    assert (
        _build_progress_header(
            src,
            "[玉青] 米粉",
            group_sessions_per_user=True,
            thread_sessions_per_user=False,
        )
        is None
    )
