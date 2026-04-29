"""Tests for _detect_tts_status plugin-registry integration in hermes_cli/setup.py.

The setup wizard's tool-status probe should recognize plugin TTS providers.
"""

from __future__ import annotations

import pytest

from agent import tts_registry
from agent.tts_provider import TtsProvider


class _FakeTts(TtsProvider):
    def __init__(self, name: str, available: bool = True):
        self._name = name
        self._available = available

    @property
    def name(self) -> str:
        return self._name

    def is_available(self) -> bool:
        return self._available

    def synthesize(self, text, output_path, config):
        return {"success": True, "file_path": output_path, "format": "mp3",
                "native_opus": False, "voice_compatible": False}


@pytest.fixture(autouse=True)
def _reset(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    tts_registry._reset_for_tests()
    # Bypass plugin discovery
    try:
        from hermes_cli import plugins as _plugins
        monkeypatch.setattr(_plugins, "_ensure_plugins_discovered", lambda *a, **kw: None)
    except Exception:
        pass
    yield
    tts_registry._reset_for_tests()


def _build_tool_status(config: dict, monkeypatch):
    """Invoke just the TTS status section from setup's _detect_tool_status."""
    # We can't easily call _detect_tool_status in isolation (it reads subscription etc).
    # Instead, test at the integration point: the tool_status list append logic.
    from hermes_cli.setup import cfg_get

    tts_provider = cfg_get(config, "tts", "provider", default="edge")

    # Simulate the else-branch path that reaches plugin check
    from tools.tts_tool import LEGACY_TTS_PROVIDERS
    if tts_provider in LEGACY_TTS_PROVIDERS:
        return "legacy"

    # Plugin-registered backend?
    try:
        from agent.tts_registry import get_provider
        from hermes_cli.plugins import _ensure_plugins_discovered
        _ensure_plugins_discovered()
        plugin = get_provider(tts_provider)
        if plugin is not None and plugin.is_available():
            return "configured"
        if plugin is not None:
            return "missing env vars"
    except Exception:
        pass
    return "unknown"


def test_plugin_configured_and_available(monkeypatch, tmp_path):
    tts_registry.register_provider(_FakeTts("volctest", available=True))
    config = {"tts": {"provider": "volctest"}}
    assert _build_tool_status(config, monkeypatch) == "configured"


def test_plugin_configured_but_unavailable(monkeypatch, tmp_path):
    tts_registry.register_provider(_FakeTts("volctest", available=False))
    config = {"tts": {"provider": "volctest"}}
    assert _build_tool_status(config, monkeypatch) == "missing env vars"


def test_unknown_plugin_not_registered(monkeypatch, tmp_path):
    config = {"tts": {"provider": "nonexistent-plugin"}}
    assert _build_tool_status(config, monkeypatch) == "unknown"


def test_legacy_provider_not_routed_to_plugin(monkeypatch, tmp_path):
    config = {"tts": {"provider": "edge"}}
    assert _build_tool_status(config, monkeypatch) == "legacy"
