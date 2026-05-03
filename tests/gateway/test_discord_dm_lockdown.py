"""Tests for the Discord DM lockdown gate.

Replicates the inline logic at gateway/platforms/discord.py:584
(the `DISCORD_BLOCK_DMS_FROM_NON_GIANNIS` guard) so we can exercise
it in isolation without standing up a full discord.Client.
"""

import os
from unittest.mock import MagicMock, patch

import pytest


class _DMChannel:
    """Stand-in for discord.DMChannel used purely for isinstance() checks."""


class _GuildChannel:
    """Stand-in for a guild text channel used purely for isinstance() checks."""


def _should_block_dm(message, *, dm_channel_cls=_DMChannel) -> bool:
    """Replica of the lockdown logic embedded in DiscordPlatform.on_message.

    Returns True when the message should be dropped by the DM lockdown.
    """
    if not isinstance(message.channel, dm_channel_cls):
        return False
    block_dms = os.getenv(
        "DISCORD_BLOCK_DMS_FROM_NON_GIANNIS", "false"
    ).lower().strip() in ("1", "true", "yes", "on")
    giannis_id = os.getenv("OPERATOR_DISCORD_ID", "123456789012345678")
    if block_dms and str(message.author.id) != giannis_id:
        return True
    return False


def _make_message(author_id, *, in_dm: bool = True):
    msg = MagicMock()
    msg.author.id = author_id
    msg.channel = _DMChannel() if in_dm else _GuildChannel()
    return msg


class TestDiscordDMLockdown:
    def test_giannis_dm_allowed(self, monkeypatch):
        monkeypatch.setenv("DISCORD_BLOCK_DMS_FROM_NON_GIANNIS", "true")
        monkeypatch.setenv("OPERATOR_DISCORD_ID", "123456789012345678")
        msg = _make_message("123456789012345678")
        assert _should_block_dm(msg) is False

    def test_non_giannis_dm_blocked(self, monkeypatch):
        monkeypatch.setenv("DISCORD_BLOCK_DMS_FROM_NON_GIANNIS", "true")
        monkeypatch.setenv("OPERATOR_DISCORD_ID", "123456789012345678")
        msg = _make_message("234567890123456789")  # example_unauthorized_user
        assert _should_block_dm(msg) is True

    def test_non_giannis_dm_allowed_when_flag_off(self, monkeypatch):
        monkeypatch.setenv("DISCORD_BLOCK_DMS_FROM_NON_GIANNIS", "false")
        monkeypatch.setenv("OPERATOR_DISCORD_ID", "123456789012345678")
        msg = _make_message("234567890123456789")
        assert _should_block_dm(msg) is False

    def test_string_int_id_equivalence(self, monkeypatch):
        """Discord.py exposes author.id as int; the guard coerces to str."""
        monkeypatch.setenv("DISCORD_BLOCK_DMS_FROM_NON_GIANNIS", "true")
        monkeypatch.setenv("OPERATOR_DISCORD_ID", "123456789012345678")
        msg = _make_message(123456789012345678)  # int, not str
        assert _should_block_dm(msg) is False
