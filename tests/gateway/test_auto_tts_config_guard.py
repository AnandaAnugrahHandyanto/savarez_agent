"""Tests for voice.auto_tts config guard in gateway auto-TTS path (#16007).

The gateway adapter previously ignored voice.auto_tts in config.yaml and
always generated TTS on voice messages.  The fix reads the setting once at
adapter init and gates the auto-TTS block on _auto_tts_globally_enabled.
"""

import inspect
from unittest.mock import patch


class TestReadAutoTtsConfig:
    """_read_auto_tts_config() correctly reads voice.auto_tts from read_raw_config."""

    def test_returns_false_when_voice_section_absent(self):
        with patch("hermes_cli.config.read_raw_config", return_value={}):
            from gateway.platforms.base import _read_auto_tts_config
            assert _read_auto_tts_config() is False

    def test_returns_false_when_explicitly_false(self):
        with patch("hermes_cli.config.read_raw_config", return_value={"voice": {"auto_tts": False}}):
            from gateway.platforms.base import _read_auto_tts_config
            assert _read_auto_tts_config() is False

    def test_returns_true_when_explicitly_true(self):
        with patch("hermes_cli.config.read_raw_config", return_value={"voice": {"auto_tts": True}}):
            from gateway.platforms.base import _read_auto_tts_config
            assert _read_auto_tts_config() is True

    def test_returns_false_when_voice_is_non_dict(self):
        with patch("hermes_cli.config.read_raw_config", return_value={"voice": "invalid"}):
            from gateway.platforms.base import _read_auto_tts_config
            assert _read_auto_tts_config() is False

    def test_returns_false_on_exception(self):
        with patch("hermes_cli.config.read_raw_config", side_effect=Exception("io error")):
            from gateway.platforms.base import _read_auto_tts_config
            assert _read_auto_tts_config() is False

    def test_returns_false_for_string_false(self):
        # YAML may parse quoted "false" as a string — must not be treated as truthy
        with patch("hermes_cli.config.read_raw_config", return_value={"voice": {"auto_tts": "false"}}):
            from gateway.platforms.base import _read_auto_tts_config
            assert _read_auto_tts_config() is False

    def test_returns_true_for_string_true(self):
        with patch("hermes_cli.config.read_raw_config", return_value={"voice": {"auto_tts": "true"}}):
            from gateway.platforms.base import _read_auto_tts_config
            assert _read_auto_tts_config() is True


class TestAutoTtsConditionStructure:
    """Source-level checks that the config guard is wired into the adapter."""

    def test_condition_checks_globally_enabled(self):
        """_process_message_background must reference _auto_tts_globally_enabled."""
        from gateway.platforms.base import BasePlatformAdapter
        source = inspect.getsource(BasePlatformAdapter._process_message_background)
        assert "_auto_tts_globally_enabled" in source, (
            "_process_message_background must check _auto_tts_globally_enabled "
            "before entering the auto-TTS block"
        )

    def test_init_populates_globally_enabled(self):
        """BasePlatformAdapter.__init__ must set _auto_tts_globally_enabled via _read_auto_tts_config."""
        from gateway.platforms.base import BasePlatformAdapter
        init_source = inspect.getsource(BasePlatformAdapter.__init__)
        assert "_auto_tts_globally_enabled" in init_source
        assert "_read_auto_tts_config" in init_source
