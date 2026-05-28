"""Tests for the Discord reminder-buttons sentinel extractor + view.

Covers:

  * :func:`extract` — sentinel parsing, base64 decoding, persistence, and
    cleaned-text output.
  * :class:`ReminderButtonsView` — button custom_ids, done/snooze/tomorrow9
    callbacks, and the message-edit + add_reaction side-effects.
  * :func:`schedule_snooze` — cron job creation via ``cron.jobs.create_job``.
  * :func:`register_persistent_views` — view re-registration on bot startup.

Discord is mocked via the shared :mod:`tests.gateway.conftest` fixtures.
``cron.jobs.create_job`` is patched per-test so we don't write real cron
jobs to ``~/.hermes/cron/jobs.json``.
"""

from __future__ import annotations

import base64
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

# Repo root importable
_repo = str(Path(__file__).resolve().parents[2])
if _repo not in sys.path:
    sys.path.insert(0, _repo)

# Trigger the shared discord mock from tests/gateway/conftest.py before
# importing the production modules.
from plugins.platforms.discord import reminder_buttons as rb  # noqa: E402
from plugins.platforms.discord.adapter import DiscordAdapter  # noqa: E402
from plugins.platforms.discord.reminder_buttons import (  # noqa: E402
    ReminderButtonsView,
    delete_reminder,
    extract,
    list_active_reminder_ids,
    load_reminder,
    register_persistent_views,
    save_reminder,
    schedule_snooze,
    _next_tomorrow_9am,
)
from gateway.config import PlatformConfig  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

OSLO = ZoneInfo("Europe/Oslo")


@pytest.fixture
def hermes_home(tmp_path, monkeypatch):
    """Point HERMES_HOME at a tmp dir so persistence stays test-local."""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    return tmp_path


def _b64(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def _sentinel_block(reminder_id: str, text: str) -> str:
    return (
        f'<<<REMINDER_BUTTONS reminder_id="{reminder_id}" text_b64="{_b64(text)}">>>\n'
        "✅ Done | ⏰ +15min | ⏰ +1h | ⏰ Tomorrow 9am\n"
        "<<</REMINDER_BUTTONS>>>"
    )


def _make_interaction(*, message_content: str = "the reminder body"):
    response = SimpleNamespace(
        edit_message=AsyncMock(),
        send_message=AsyncMock(),
        defer=AsyncMock(),
    )
    message = SimpleNamespace(
        content=message_content,
        add_reaction=AsyncMock(),
    )
    return SimpleNamespace(response=response, message=message)


# ---------------------------------------------------------------------------
# extract()
# ---------------------------------------------------------------------------

class TestExtract:
    def test_no_sentinel_returns_unchanged(self, hermes_home):
        cleaned, view = extract("hello world")
        assert cleaned == "hello world"
        assert view is None

    def test_empty_input(self, hermes_home):
        cleaned, view = extract("")
        assert cleaned == ""
        assert view is None

    def test_strips_sentinel_block(self, hermes_home):
        body = "Time to drink water!"
        text = f"{body}\n\n{_sentinel_block('abc123', body)}"
        cleaned, view = extract(text)
        # Sentinel block removed
        assert "<<<REMINDER_BUTTONS" not in cleaned
        assert "<<</REMINDER_BUTTONS>>>" not in cleaned
        # Body preserved
        assert "Time to drink water!" in cleaned
        assert view is not None

    def test_view_has_four_buttons_with_correct_custom_ids(self, hermes_home):
        text = _sentinel_block("rid42", "stand up")
        _, view = extract(text)
        assert view is not None
        assert len(view.children) == 4
        custom_ids = [b.custom_id for b in view.children]
        assert custom_ids == [
            "reminder:rid42:done",
            "reminder:rid42:snooze15",
            "reminder:rid42:snooze60",
            "reminder:rid42:tomorrow9",
        ]

    def test_persists_reminder_json(self, hermes_home):
        body = "Take a break"
        text = _sentinel_block("ridP1", body)
        origin = {"platform": "discord", "chat_id": "9001", "thread_id": None}
        extract(text, origin=origin, deliver="origin")

        record = load_reminder("ridP1")
        assert record is not None
        assert record["text"] == body
        assert record["origin"] == origin
        assert record["deliver"] == "origin"

    def test_bad_base64_leaves_sentinel_in_place(self, hermes_home):
        text = (
            '<<<REMINDER_BUTTONS reminder_id="ridBad" '
            'text_b64="!!!notbase64!!!">>>\n'
            "x\n"
            "<<</REMINDER_BUTTONS>>>"
        )
        cleaned, view = extract(text)
        # Regex requires base64 chars in text_b64, so the sentinel never
        # matches — text is returned untouched.
        assert cleaned == text
        assert view is None

    def test_invalid_base64_payload_leaves_text_unchanged(self, hermes_home):
        # Construct a sentinel whose text_b64 is regex-valid base64 chars but
        # decodes to bytes that are not valid UTF-8.  This forces the
        # decode-side exception branch.
        bad_payload = "////"  # decodes to bytes 0xff 0xff 0xff
        text = (
            f'<<<REMINDER_BUTTONS reminder_id="ridUE" '
            f'text_b64="{bad_payload}">>>\n'
            "<<</REMINDER_BUTTONS>>>"
        )
        cleaned, view = extract(text)
        assert cleaned == text
        assert view is None

    def test_only_first_sentinel_block_is_consumed(self, hermes_home):
        first = _sentinel_block("rid1", "one")
        second = _sentinel_block("rid2", "two")
        text = f"intro\n{first}\nmid\n{second}"
        cleaned, view = extract(text)
        assert view is not None
        # First sentinel removed, second remains
        assert "intro" in cleaned
        assert "<<<REMINDER_BUTTONS" in cleaned
        assert 'reminder_id="rid2"' in cleaned


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

class TestPersistence:
    def test_save_and_load_round_trip(self, hermes_home):
        save_reminder("ridS", "hello", origin={"platform": "discord", "chat_id": "1"})
        record = load_reminder("ridS")
        assert record["reminder_id"] == "ridS"
        assert record["text"] == "hello"
        assert record["origin"]["chat_id"] == "1"

    def test_load_returns_none_for_missing(self, hermes_home):
        assert load_reminder("does-not-exist") is None

    def test_delete_reminder_removes_file(self, hermes_home):
        save_reminder("ridD", "x")
        assert load_reminder("ridD") is not None
        assert delete_reminder("ridD") is True
        assert load_reminder("ridD") is None
        # Idempotent
        assert delete_reminder("ridD") is False

    def test_list_active_returns_all_ids(self, hermes_home):
        save_reminder("ridA", "a")
        save_reminder("ridB", "b")
        ids = list_active_reminder_ids()
        assert "ridA" in ids
        assert "ridB" in ids

    def test_rejects_invalid_id(self, hermes_home):
        with pytest.raises(ValueError):
            save_reminder("../escape", "x")


# ---------------------------------------------------------------------------
# _next_tomorrow_9am
# ---------------------------------------------------------------------------

class TestNextTomorrow9am:
    def test_returns_today_9am_when_before_9am(self):
        now = datetime(2026, 5, 28, 7, 30, tzinfo=OSLO)
        target = _next_tomorrow_9am(now)
        assert target.year == 2026
        assert target.month == 5
        assert target.day == 28
        assert target.hour == 9
        assert target.minute == 0
        assert target.tzinfo == OSLO

    def test_returns_tomorrow_9am_when_after_9am(self):
        now = datetime(2026, 5, 28, 10, 0, tzinfo=OSLO)
        target = _next_tomorrow_9am(now)
        assert target.day == 29
        assert target.hour == 9

    def test_returns_tomorrow_when_exactly_9am(self):
        # Exact 9am is already "passed" — should target tomorrow.
        now = datetime(2026, 5, 28, 9, 0, tzinfo=OSLO)
        target = _next_tomorrow_9am(now)
        assert target.day == 29

    def test_handles_non_oslo_input_via_conversion(self):
        # UTC 06:00 on a non-DST day == 07:00 Oslo (CET / CEST drift handled
        # by ZoneInfo).  Either way: target must be today's 9am Oslo.
        now = datetime(2026, 1, 15, 6, 0, tzinfo=timezone.utc)
        target = _next_tomorrow_9am(now)
        # Today in Oslo is still 2026-01-15
        assert target.day == 15
        assert target.hour == 9
        assert target.tzinfo == OSLO


# ---------------------------------------------------------------------------
# schedule_snooze
# ---------------------------------------------------------------------------

class TestScheduleSnooze:
    def test_returns_none_when_state_missing(self, hermes_home):
        with patch("cron.jobs.create_job") as cj:
            assert schedule_snooze("missing") is None
            cj.assert_not_called()

    def test_delay_minutes_invokes_create_job_with_minute_schedule(
        self, hermes_home,
    ):
        save_reminder(
            "ridS15", "drink water",
            origin={"platform": "discord", "chat_id": "9001"},
            deliver="origin",
        )
        fake_job = {"id": "jobxyz", "name": "x"}
        with patch("cron.jobs.create_job", return_value=fake_job) as cj:
            job = schedule_snooze("ridS15", delay_minutes=15)
        assert job is fake_job
        cj.assert_called_once()
        kwargs = cj.call_args.kwargs
        assert kwargs["schedule"] == "15m"
        assert kwargs["repeat"] == 1
        assert kwargs["deliver"] == "origin"
        assert kwargs["origin"] == {"platform": "discord", "chat_id": "9001"}
        # Prompt must contain the reminder text + a fresh sentinel block
        assert "drink water" in kwargs["prompt"]
        assert "<<<REMINDER_BUTTONS" in kwargs["prompt"]
        assert "<<</REMINDER_BUTTONS>>>" in kwargs["prompt"]
        # Fresh sentinel: new reminder_id, not the original
        assert 'reminder_id="ridS15"' not in kwargs["prompt"]

    def test_run_at_invokes_create_job_with_iso_schedule(self, hermes_home):
        save_reminder("ridT9", "stand up")
        target = datetime(2026, 5, 29, 9, 0, tzinfo=OSLO)
        with patch("cron.jobs.create_job", return_value={"id": "j"}) as cj:
            schedule_snooze("ridT9", run_at=target)
        kwargs = cj.call_args.kwargs
        # Schedule is the ISO timestamp string
        assert kwargs["schedule"] == target.isoformat()

    def test_persists_new_reminder_for_chained_buttons(self, hermes_home):
        save_reminder(
            "ridChain", "do the thing",
            origin={"platform": "discord", "chat_id": "42"},
            deliver="origin",
        )
        with patch("cron.jobs.create_job", return_value={"id": "j"}):
            schedule_snooze("ridChain", delay_minutes=15)
        # A new reminder JSON must exist with the same text + origin so the
        # next reminder's buttons work too.
        ids = list_active_reminder_ids()
        new_ids = [rid for rid in ids if rid != "ridChain"]
        assert len(new_ids) == 1
        new_record = load_reminder(new_ids[0])
        assert new_record["text"] == "do the thing"
        assert new_record["origin"] == {"platform": "discord", "chat_id": "42"}

    def test_requires_delay_or_run_at(self, hermes_home):
        save_reminder("ridX", "x")
        with patch("cron.jobs.create_job"):
            with pytest.raises(ValueError):
                schedule_snooze("ridX")


# ---------------------------------------------------------------------------
# ReminderButtonsView callbacks
# ---------------------------------------------------------------------------

class TestReminderButtonsView:
    @pytest.mark.asyncio
    async def test_done_edits_message_and_reacts(self, hermes_home):
        save_reminder("ridDone", "x")
        view = ReminderButtonsView("ridDone")
        interaction = _make_interaction(message_content="Drink water")
        await view._on_done(interaction)
        # Buttons disabled
        assert all(c.disabled for c in view.children)
        # edit_message called with new content suffixed
        interaction.response.edit_message.assert_called_once()
        kwargs = interaction.response.edit_message.call_args.kwargs
        assert "✓ done" in kwargs["content"]
        # ✅ reaction added
        interaction.message.add_reaction.assert_called_once_with("✅")
        # Persisted state removed
        assert load_reminder("ridDone") is None

    @pytest.mark.asyncio
    async def test_snooze15_schedules_cron_and_edits(self, hermes_home):
        save_reminder(
            "ridSn15", "remember",
            origin={"platform": "discord", "chat_id": "1"},
        )
        view = ReminderButtonsView("ridSn15")
        interaction = _make_interaction(message_content="Remember!")
        with patch("cron.jobs.create_job", return_value={"id": "j15"}) as cj:
            await view._on_snooze(interaction, delay_minutes=15, label="+15min")
        # Cron job created
        cj.assert_called_once()
        assert cj.call_args.kwargs["schedule"] == "15m"
        # Buttons disabled + message edited
        assert all(c.disabled for c in view.children)
        kwargs = interaction.response.edit_message.call_args.kwargs
        assert "snoozed +15min" in kwargs["content"]

    @pytest.mark.asyncio
    async def test_snooze60_uses_60_minute_schedule(self, hermes_home):
        save_reminder("ridSn60", "remember")
        view = ReminderButtonsView("ridSn60")
        interaction = _make_interaction()
        with patch("cron.jobs.create_job", return_value={"id": "j60"}) as cj:
            await view._on_snooze(interaction, delay_minutes=60, label="+1h")
        assert cj.call_args.kwargs["schedule"] == "60m"

    @pytest.mark.asyncio
    async def test_tomorrow9_schedules_at_oslo_9am(self, hermes_home):
        save_reminder("ridT9", "wake up")
        view = ReminderButtonsView("ridT9")
        interaction = _make_interaction()
        with patch("cron.jobs.create_job", return_value={"id": "jT9"}) as cj:
            await view._on_tomorrow9(interaction)
        schedule = cj.call_args.kwargs["schedule"]
        # ISO timestamp of next 9am Oslo — must parse and be in Oslo tz.
        dt = datetime.fromisoformat(schedule)
        # Confirm hour/min in Oslo time
        dt_oslo = dt.astimezone(OSLO)
        assert dt_oslo.hour == 9
        assert dt_oslo.minute == 0

    @pytest.mark.asyncio
    async def test_snooze_without_persisted_state_warns_user(self, hermes_home):
        # No save_reminder — state is missing
        view = ReminderButtonsView("ridGone")
        interaction = _make_interaction()
        with patch("cron.jobs.create_job") as cj:
            await view._on_snooze(interaction, delay_minutes=15, label="+15min")
        cj.assert_not_called()
        # Buttons still disabled + edit indicates the failure
        assert all(c.disabled for c in view.children)
        kwargs = interaction.response.edit_message.call_args.kwargs
        assert "couldn't snooze" in kwargs["content"]


# ---------------------------------------------------------------------------
# register_persistent_views
# ---------------------------------------------------------------------------

class TestRegisterPersistentViews:
    def test_registers_one_view_per_active_reminder(self, hermes_home):
        save_reminder("r1", "a")
        save_reminder("r2", "b")
        save_reminder("r3", "c")
        bot = MagicMock()
        count = register_persistent_views(bot)
        assert count == 3
        # All three views passed to bot.add_view
        assert bot.add_view.call_count == 3
        registered_ids = [
            call.args[0].reminder_id for call in bot.add_view.call_args_list
        ]
        assert set(registered_ids) == {"r1", "r2", "r3"}

    def test_returns_zero_when_no_reminders(self, hermes_home):
        bot = MagicMock()
        count = register_persistent_views(bot)
        assert count == 0
        bot.add_view.assert_not_called()

    def test_none_bot_returns_zero(self, hermes_home):
        save_reminder("r1", "x")
        assert register_persistent_views(None) == 0


# ---------------------------------------------------------------------------
# Adapter wiring — send() should call extract() and attach the view
# ---------------------------------------------------------------------------

def _make_adapter():
    config = PlatformConfig(enabled=True, token="t", extra={})
    adapter = DiscordAdapter(config)
    adapter._client = MagicMock()
    return adapter


class TestAdapterSendIntegration:
    @pytest.mark.asyncio
    async def test_send_strips_sentinel_and_attaches_view(self, hermes_home):
        adapter = _make_adapter()
        channel = MagicMock()
        sent_msg = MagicMock()
        sent_msg.id = 555
        channel.send = AsyncMock(return_value=sent_msg)
        adapter._client.get_channel = MagicMock(return_value=channel)
        # Treat as non-forum
        adapter._is_forum_parent = MagicMock(return_value=False)

        body = "Drink water"
        content = f"{body}\n\n{_sentinel_block('ridSend', body)}"

        result = await adapter.send(chat_id="9001", content=content)
        assert result.success is True
        # channel.send called with view kwarg + cleaned content
        channel.send.assert_called()
        kwargs = channel.send.call_args.kwargs
        assert "view" in kwargs
        assert isinstance(kwargs["view"], ReminderButtonsView)
        # Sentinel block stripped from outgoing content
        assert "<<<REMINDER_BUTTONS" not in kwargs["content"]
        assert body in kwargs["content"]

    @pytest.mark.asyncio
    async def test_send_without_sentinel_does_not_attach_view(self, hermes_home):
        adapter = _make_adapter()
        channel = MagicMock()
        sent_msg = MagicMock()
        sent_msg.id = 1
        channel.send = AsyncMock(return_value=sent_msg)
        adapter._client.get_channel = MagicMock(return_value=channel)
        adapter._is_forum_parent = MagicMock(return_value=False)

        await adapter.send(chat_id="9001", content="just a normal message")
        kwargs = channel.send.call_args.kwargs
        assert "view" not in kwargs
