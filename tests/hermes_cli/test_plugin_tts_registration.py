"""Tests for PluginContext.register_tts_provider hook on the plugin loader."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def _reset_registry():
    from agent import tts_registry

    tts_registry._reset_for_tests()
    yield
    tts_registry._reset_for_tests()


def _make_ctx(plugin_name: str = "test-plugin"):
    """Build a minimal PluginContext for unit testing hook methods."""
    from hermes_cli.plugins import PluginContext, PluginManifest

    manifest = PluginManifest(
        name=plugin_name,
        version="0.0.0",
        description="",
        kind="backend",
        source="bundled",
    )
    # PluginContext needs a manager reference; register_tts_provider
    # doesn't touch it, so a MagicMock is sufficient for this hook test.
    mock_manager = MagicMock()
    mock_manager._plugin_tool_names = set()
    return PluginContext(manifest=manifest, manager=mock_manager)


def _make_provider(name: str = "fake"):
    from agent.tts_provider import TtsProvider

    class FakeProvider(TtsProvider):
        @property
        def name(self) -> str:
            return name

        def synthesize(self, text, output_path, config):
            return {
                "success": True,
                "file_path": output_path,
                "format": "mp3",
                "native_opus": False,
                "voice_compatible": False,
            }

    return FakeProvider()


class TestRegisterTtsProvider:
    def test_registers_with_registry(self):
        from agent import tts_registry

        ctx = _make_ctx()
        provider = _make_provider("myplugin")
        ctx.register_tts_provider(provider)

        assert tts_registry.get_provider("myplugin") is provider

    def test_rejects_wrong_abc(self, caplog):
        from agent import tts_registry

        ctx = _make_ctx()

        class NotAProvider:
            name = "imposter"

        ctx.register_tts_provider(NotAProvider())  # type: ignore[arg-type]
        assert tts_registry.get_provider("imposter") is None
        # The plugin loader logs a warning rather than crashing.
        assert any(
            "not inherit from TtsProvider" in rec.message
            for rec in caplog.records
        )

    def test_reregistration_overwrites(self):
        from agent import tts_registry

        ctx = _make_ctx()
        a = _make_provider("dup")
        b = _make_provider("dup")
        ctx.register_tts_provider(a)
        ctx.register_tts_provider(b)
        assert tts_registry.get_provider("dup") is b

    def test_plugin_name_surfaces_in_log(self, caplog):
        import logging

        ctx = _make_ctx("my-voice-plugin")
        provider = _make_provider("fake")
        with caplog.at_level(logging.INFO, logger="hermes_cli.plugins"):
            ctx.register_tts_provider(provider)

        assert any(
            "my-voice-plugin" in rec.message and "tts provider" in rec.message.lower()
            for rec in caplog.records
        )
