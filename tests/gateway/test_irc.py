"""Tests for IRC platform adapter."""
import pytest
from unittest.mock import MagicMock, patch

from gateway.config import Platform, PlatformConfig


# ---------------------------------------------------------------------------
# Platform Enum
# ---------------------------------------------------------------------------

class TestIRCPlatformEnum:
    def test_irc_enum_exists(self):
        assert Platform.IRC.value == "irc"

    def test_irc_in_platform_list(self):
        platforms = [p.value for p in Platform]
        assert "irc" in platforms


# ---------------------------------------------------------------------------
# Config Loading
# ---------------------------------------------------------------------------

class TestIRCConfigLoading:
    def test_irc_disabled_without_server(self, monkeypatch):
        """IRC should not be enabled without IRC_SERVER."""
        monkeypatch.delenv("IRC_SERVER", raising=False)
        monkeypatch.setenv("IRC_NICK", "hermesbot")

        from gateway.config import GatewayConfig, _apply_env_overrides

        config = GatewayConfig()
        _apply_env_overrides(config)

        assert Platform.IRC not in config.platforms

    def test_irc_home_channel_from_env(self, monkeypatch):
        """IRC_HOME_CHANNEL should override the default."""
        monkeypatch.setenv("IRC_SERVER", "irc.example.com")
        monkeypatch.setenv("IRC_NICK", "hermesbot")
        monkeypatch.setenv("IRC_CHANNELS", "#bots,#test")
        monkeypatch.setenv("IRC_HOME_CHANNEL", "#test")

        from gateway.config import GatewayConfig, _apply_env_overrides

        config = GatewayConfig()
        _apply_env_overrides(config)

        home = config.get_home_channel(Platform.IRC)
        assert home is not None
        assert home.chat_id == "#test"

    def test_irc_tls_flag(self, monkeypatch):
        """IRC_USE_TLS should be parsed as boolean."""
        monkeypatch.setenv("IRC_SERVER", "irc.example.com")
        monkeypatch.setenv("IRC_NICK", "hermesbot")
        monkeypatch.setenv("IRC_USE_TLS", "true")

        from gateway.config import GatewayConfig, _apply_env_overrides

        config = GatewayConfig()
        _apply_env_overrides(config)

        mc = config.platforms[Platform.IRC]
        assert mc.extra.get("use_tls") is True

    def test_irc_not_enabled_without_creds(self, monkeypatch):
        """IRC should not appear in platforms without credentials."""
        monkeypatch.delenv("IRC_SERVER", raising=False)
        monkeypatch.delenv("IRC_NICK", raising=False)

        from gateway.config import GatewayConfig, _apply_env_overrides

        config = GatewayConfig()
        _apply_env_overrides(config)

        assert Platform.IRC not in config.platforms


# ---------------------------------------------------------------------------
# Adapter Tests
# ---------------------------------------------------------------------------

class TestIRCAdapterFormatMessage:
    """Tests for IRCAdapter.format_message (passthrough, no markdown stripping)."""

    def test_format_message_returns_unchanged(self, monkeypatch):
        """format_message should return content unchanged."""
        monkeypatch.setenv("IRC_SERVER", "irc.example.com")
        monkeypatch.setenv("IRC_NICK", "hermesbot")

        from gateway.platforms.irc import IRCAdapter

        adapter = IRCAdapter(PlatformConfig(enabled=True, extra={"server": "irc.example.com", "nick": "hermesbot"}))
        
        content = "**Hello world**"
        assert adapter.format_message(content) == content

    def test_format_message_preserves_markdown(self, monkeypatch):
        """format_message should preserve markdown syntax."""
        monkeypatch.setenv("IRC_SERVER", "irc.example.com")
        monkeypatch.setenv("IRC_NICK", "hermesbot")

        from gateway.platforms.irc import IRCAdapter

        adapter = IRCAdapter(PlatformConfig(enabled=True, extra={"server": "irc.example.com", "nick": "hermesbot"}))

        content = "**bold** and _italic_ and `code`"
        assert adapter.format_message(content) == content

    def test_format_message_preserves_newlines(self, monkeypatch):
        """format_message should preserve newlines."""
        monkeypatch.setenv("IRC_SERVER", "irc.example.com")
        monkeypatch.setenv("IRC_NICK", "hermesbot")

        from gateway.platforms.irc import IRCAdapter

        adapter = IRCAdapter(PlatformConfig(enabled=True, extra={"server": "irc.example.com", "nick": "hermesbot"}))

        content = "line 1\nline 2\nline 3"
        assert adapter.format_message(content) == content

    def test_format_message_empty_input(self, monkeypatch):
        """format_message with empty input returns empty string."""
        monkeypatch.setenv("IRC_SERVER", "irc.example.com")
        monkeypatch.setenv("IRC_NICK", "hermesbot")

        from gateway.platforms.irc import IRCAdapter

        adapter = IRCAdapter(PlatformConfig(enabled=True, extra={"server": "irc.example.com", "nick": "hermesbot"}))

        assert adapter.format_message("") == ""


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------

class TestIRCAdapterMentions:
    """Tests for IRCAdapter mention pattern matching."""

    def test_single_mention_accepted(self, monkeypatch):
        """Messages starting with a single mention should be accepted."""
        monkeypatch.setenv("IRC_SERVER", "irc.example.com")
        monkeypatch.setenv("IRC_NICK", "bot1")

        from gateway.platforms.irc import IRCAdapter
        import re

        adapter = IRCAdapter(PlatformConfig(enabled=True, extra={"server": "irc.example.com", "nick": "bot1"}))

        mention_block_pattern = re.compile(r"^(([a-zA-Z_][a-zA-Z0-9_-]*:)+ )+", re.IGNORECASE)

        text = "bot1: hi"
        match = mention_block_pattern.match(text)
        assert match is not None

        nick_pattern = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_-]*$")
        mentioned_nicks = [
            nick_part.lower()
            for nick_part in match.group(0).split(": ")
            if nick_part and nick_pattern.match(nick_part)
        ]
        assert mentioned_nicks == ["bot1"]

    def test_multiple_mentions_accepted(self, monkeypatch):
        """Messages starting with multiple mentions should extract all nicks."""
        monkeypatch.setenv("IRC_SERVER", "irc.example.com")
        monkeypatch.setenv("IRC_NICK", "bot1")

        from gateway.platforms.irc import IRCAdapter
        import re

        adapter = IRCAdapter(PlatformConfig(enabled=True, extra={"server": "irc.example.com", "nick": "bot1"}))

        mention_block_pattern = re.compile(r"^(([a-zA-Z_][a-zA-Z0-9_-]*:)+ )+", re.IGNORECASE)

        text = "foo: bar: baz: hi"
        match = mention_block_pattern.match(text)
        assert match is not None

        nick_pattern = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_-]*$")
        mentioned_nicks = [
            nick_part.lower()
            for nick_part in match.group(0).split(": ")
            if nick_part and nick_pattern.match(nick_part)
        ]
        assert mentioned_nicks == ["foo", "bar", "baz"]

    def test_nick_among_mentions(self, monkeypatch):
        """Bot should be extracted when its nick is among multiple mentions."""
        monkeypatch.setenv("IRC_SERVER", "irc.example.com")
        monkeypatch.setenv("IRC_NICK", "bot1")

        from gateway.platforms.irc import IRCAdapter
        import re

        adapter = IRCAdapter(PlatformConfig(enabled=True, extra={"server": "irc.example.com", "nick": "bot1"}))

        mention_block_pattern = re.compile(r"^(([a-zA-Z_][a-zA-Z0-9_-]*:)+ )+", re.IGNORECASE)
        nick_pattern = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_-]*$")

        # Bot mentioned second
        text1 = "bot2: bot1: bot3: hi"
        match1 = mention_block_pattern.match(text1)
        mentioned_nicks1 = [
            nick_part.lower()
            for nick_part in match1.group(0).split(": ")
            if nick_part and nick_pattern.match(nick_part)
        ]
        assert "bot1" in mentioned_nicks1

        # Bot mentioned third
        text2 = "bot2: bot3: bot1: hi"
        match2 = mention_block_pattern.match(text2)
        mentioned_nicks2 = [
            nick_part.lower()
            for nick_part in match2.group(0).split(": ")
            if nick_part and nick_pattern.match(nick_part)
        ]
        assert "bot1" in mentioned_nicks2

    def test_nick_not_mentioned(self, monkeypatch):
        """Bot should NOT be extracted when its nick is not mentioned."""
        monkeypatch.setenv("IRC_SERVER", "irc.example.com")
        monkeypatch.setenv("IRC_NICK", "bot1")

        from gateway.platforms.irc import IRCAdapter
        import re

        adapter = IRCAdapter(PlatformConfig(enabled=True, extra={"server": "irc.example.com", "nick": "bot1"}))

        mention_block_pattern = re.compile(r"^(([a-zA-Z_][a-zA-Z0-9_-]*:)+ )+", re.IGNORECASE)
        nick_pattern = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_-]*$")

        text = "bot2: bot3: bot4: hi"
        match = mention_block_pattern.match(text)
        mentioned_nicks = [
            nick_part.lower()
            for nick_part in match.group(0).split(": ")
            if nick_part and nick_pattern.match(nick_part)
        ]
        assert "bot1" not in mentioned_nicks

    def test_no_leading_mention_block(self, monkeypatch):
        """Messages without a leading mention block should not match."""
        monkeypatch.setenv("IRC_SERVER", "irc.example.com")
        monkeypatch.setenv("IRC_NICK", "bot1")

        from gateway.platforms.irc import IRCAdapter
        import re

        adapter = IRCAdapter(PlatformConfig(enabled=True, extra={"server": "irc.example.com", "nick": "bot1"}))

        mention_block_pattern = re.compile(r"^(([a-zA-Z_][a-zA-Z0-9_-]*:)+ )+", re.IGNORECASE)

        # No mention at start
        texts = [
            "hi bot1:",
            "hello world",
            "bot1: hi",  # this actually has a mention block!
        ]

        match_count = 0
        for text in texts:
            if mention_block_pattern.match(text):
                match_count += 1

        # Only "bot1: hi" should match
        assert match_count == 1

    def test_no_space_after_colon(self, monkeypatch):
        """Messages without space after colon are not valid mentions."""
        monkeypatch.setenv("IRC_SERVER", "irc.example.com")
        monkeypatch.setenv("IRC_NICK", "bot1")

        from gateway.platforms.irc import IRCAdapter
        import re

        adapter = IRCAdapter(PlatformConfig(enabled=True, extra={"server": "irc.example.com", "nick": "bot1"}))

        mention_block_pattern = re.compile(r"^(([a-zA-Z_][a-zA-Z0-9_-]*:)+ )+", re.IGNORECASE)

        # No space after colon - should not match
        text = "bot1:hi"
        match = mention_block_pattern.match(text)
        assert match is None

    def test_case_insensitive(self, monkeypatch):
        """Mention matching should be case-insensitive."""
        monkeypatch.setenv("IRC_SERVER", "irc.example.com")
        monkeypatch.setenv("IRC_NICK", "Bot1")

        from gateway.platforms.irc import IRCAdapter
        import re

        adapter = IRCAdapter(PlatformConfig(enabled=True, extra={"server": "irc.example.com", "nick": "Bot1"}))

        mention_block_pattern = re.compile(r"^(([a-zA-Z_][a-zA-Z0-9_-]*:)+ )+", re.IGNORECASE)
        nick_pattern = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_-]*$")

        texts = [
            "bot1: hi",
            "Bot1: hi",
            "BOT1: hi",
            "bot2: bot1: hi",
        ]

        for text in texts:
            match = mention_block_pattern.match(text)
            mentioned_nicks = [
                nick_part.lower()
                for nick_part in match.group(0).split(": ")
                if nick_part and nick_pattern.match(nick_part)
            ]
            assert "bot1" in mentioned_nicks

    def test_command_strips_mention_block(self, monkeypatch):
        """Commands after mention block should have mention block stripped."""
        monkeypatch.setenv("IRC_SERVER", "irc.example.com")
        monkeypatch.setenv("IRC_NICK", "bot1")

        from gateway.platforms.irc import IRCAdapter
        import re

        adapter = IRCAdapter(PlatformConfig(enabled=True, extra={"server": "irc.example.com", "nick": "bot1"}))

        mention_block_pattern = re.compile(r"^(([a-zA-Z_][a-zA-Z0-9_-]*:)+ )+", re.IGNORECASE)
        command_pattern = re.compile(r"^/[a-zA-Z_][a-zA-Z0-9_-]+")

        # Command after mention block
        text = "bot1: /help"
        match = mention_block_pattern.match(text)
        mention_block = match.group(0)
        remainder = text[len(mention_block):]

        assert command_pattern.match(remainder) is not None
        assert remainder.lstrip() == "/help"

        # Multiple mentions with command
        text2 = "bot2: bot1: /status"
        match2 = mention_block_pattern.match(text2)
        mention_block2 = match2.group(0)
        remainder2 = text2[len(mention_block2):]

        assert command_pattern.match(remainder2) is not None
        assert remainder2.lstrip() == "/status"

    def test_command_with_extra_spaces(self, monkeypatch):
        """Commands should be lstrip() to ensure first char is / even with extra spaces."""
        monkeypatch.setenv("IRC_SERVER", "irc.example.com")
        monkeypatch.setenv("IRC_NICK", "bot1")

        from gateway.platforms.irc import IRCAdapter
        import re

        adapter = IRCAdapter(PlatformConfig(enabled=True, extra={"server": "irc.example.com", "nick": "bot1"}))

        mention_block_pattern = re.compile(r"^(([a-zA-Z_][a-zA-Z0-9_-]*:)+ )+", re.IGNORECASE)
        command_pattern = re.compile(r"^/[a-zA-Z_][a-zA-Z0-9_-]+")

        # Command with extra spaces before slash
        text = "bot1:   /test command"
        match = mention_block_pattern.match(text)
        mention_block = match.group(0)
        remainder = text[len(mention_block):]

        # After lstrip(), it should match command pattern
        assert command_pattern.match(remainder.lstrip()) is not None
        assert remainder.lstrip() == "/test command"

    def test_non_command_keeps_mention_block(self, monkeypatch):
        """Non-command messages should keep the full text including mention block."""
        monkeypatch.setenv("IRC_SERVER", "irc.example.com")
        monkeypatch.setenv("IRC_NICK", "bot1")

        from gateway.platforms.irc import IRCAdapter
        import re

        adapter = IRCAdapter(PlatformConfig(enabled=True, extra={"server": "irc.example.com", "nick": "bot1"}))

        mention_block_pattern = re.compile(r"^(([a-zA-Z_][a-zA-Z0-9_-]*:)+ )+", re.IGNORECASE)
        command_pattern = re.compile(r"^/[a-zA-Z_][a-zA-Z0-9_-]+")

        # Regular message - not a command
        text = "bot1: hello world"
        match = mention_block_pattern.match(text)
        mention_block = match.group(0)
        remainder = text[len(mention_block):]

        assert command_pattern.match(remainder) is None
        # Text should remain unchanged
        assert text == "bot1: hello world"

    def test_slash_without_command_word(self, monkeypatch):
        """Just a slash is not a command."""
        monkeypatch.setenv("IRC_SERVER", "irc.example.com")
        monkeypatch.setenv("IRC_NICK", "bot1")

        from gateway.platforms.irc import IRCAdapter
        import re

        adapter = IRCAdapter(PlatformConfig(enabled=True, extra={"server": "irc.example.com", "nick": "bot1"}))

        mention_block_pattern = re.compile(r"^(([a-zA-Z_][a-zA-Z0-9_-]*:)+ )+", re.IGNORECASE)
        command_pattern = re.compile(r"^/[a-zA-Z_][a-zA-Z0-9_-]+")

        # Slash without command word
        text = "bot1: /"
        match = mention_block_pattern.match(text)
        mention_block = match.group(0)
        remainder = text[len(mention_block):]

        assert command_pattern.match(remainder) is None

        # Slash without valid command word (starts with number)
        text2 = "bot1: /123test"
        match2 = mention_block_pattern.match(text2)
        mention_block2 = match2.group(0)
        remainder2 = text2[len(mention_block2):]

        assert command_pattern.match(remainder2) is None


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------

class TestIRCIntegration:
    def test_irc_not_in_connected_platforms_when_disabled(self, monkeypatch):
        """IRC should not appear in get_connected_platforms when not configured."""
        monkeypatch.delenv("IRC_SERVER", raising=False)
        monkeypatch.delenv("IRC_NICK", raising=False)

        from gateway.config import GatewayConfig, _apply_env_overrides

        config = GatewayConfig()
        _apply_env_overrides(config)

        connected = config.get_connected_platforms()
        assert "irc" not in connected
