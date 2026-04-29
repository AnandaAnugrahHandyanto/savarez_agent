"""Tests for plugin TTS providers injecting themselves into the picker.

Covers `_plugin_tts_providers`, `_visible_providers`, and
`_toolset_needs_configuration_prompt` handling of plugin TTS providers.
Mirrors `test_image_gen_picker.py`.
"""

from __future__ import annotations

import pytest

from agent import tts_registry
from agent.tts_provider import TtsProvider


class _FakeTtsProvider(TtsProvider):
    def __init__(self, name: str, available: bool = True, schema=None):
        self._name = name
        self._available = available
        self._schema = schema or {
            "name": name.title(),
            "badge": "test",
            "tag": f"{name} test tag",
            "env_vars": [{"key": f"{name.upper()}_API_KEY", "prompt": f"{name} key"}],
        }

    @property
    def name(self) -> str:
        return self._name

    def is_available(self) -> bool:
        return self._available

    def get_setup_schema(self):
        return dict(self._schema)

    def synthesize(self, text, output_path, config):
        return {"success": True, "file_path": output_path, "format": "mp3",
                "native_opus": False, "voice_compatible": False}


@pytest.fixture(autouse=True)
def _reset_registry():
    tts_registry._reset_for_tests()
    yield
    tts_registry._reset_for_tests()


class TestPluginPickerInjection:
    def test_plugin_providers_returns_registered(self, monkeypatch):
        from hermes_cli import tools_config

        tts_registry.register_provider(_FakeTtsProvider("volctest"))

        rows = tools_config._plugin_tts_providers()
        names = [r["name"] for r in rows]
        plugin_names = [r.get("tts_plugin_name") for r in rows]

        assert "Volctest" in names
        assert "volctest" in plugin_names

    def test_legacy_name_collision_suppressed(self, monkeypatch):
        """A plugin named 'edge' should not appear in the picker —
        it collides with the hardcoded LEGACY_TTS_PROVIDERS entry."""
        from hermes_cli import tools_config

        tts_registry.register_provider(_FakeTtsProvider("edge"))
        tts_registry.register_provider(_FakeTtsProvider("volctest"))

        rows = tools_config._plugin_tts_providers()
        plugin_names = [r.get("tts_plugin_name") for r in rows]
        assert "edge" not in plugin_names
        assert "volctest" in plugin_names

    def test_visible_providers_includes_plugins_for_tts(self, monkeypatch):
        from hermes_cli import tools_config

        tts_registry.register_provider(_FakeTtsProvider("volctest"))

        cat = tools_config.TOOL_CATEGORIES["tts"]
        visible = tools_config._visible_providers(cat, {})
        plugin_names = [p.get("tts_plugin_name") for p in visible if p.get("tts_plugin_name")]
        assert "volctest" in plugin_names

    def test_visible_providers_does_not_inject_into_other_categories(self, monkeypatch):
        from hermes_cli import tools_config

        tts_registry.register_provider(_FakeTtsProvider("volctest"))

        # Browser category must NOT see TTS plugins.
        browser = tools_config.TOOL_CATEGORIES["browser"]
        visible = tools_config._visible_providers(browser, {})
        assert all(p.get("tts_plugin_name") is None for p in visible)


class TestConfigPrompt:
    def test_tts_satisfied_by_plugin_provider(self, monkeypatch, tmp_path):
        """When a plugin provider reports is_available(), the picker should
        not force a setup prompt on the user if tts.provider is already set."""
        from hermes_cli import tools_config

        monkeypatch.setenv("HERMES_HOME", str(tmp_path))

        tts_registry.register_provider(_FakeTtsProvider("avail-tts", available=True))

        # When provider is already set, no prompt needed
        config = {"tts": {"provider": "avail-tts"}}
        assert tools_config._toolset_needs_configuration_prompt("tts", config) is False

    def test_tts_still_prompts_when_no_provider_set(self, monkeypatch, tmp_path):
        from hermes_cli import tools_config

        monkeypatch.setenv("HERMES_HOME", str(tmp_path))

        tts_registry.register_provider(_FakeTtsProvider("unavail-tts", available=False))

        # No provider set → needs prompt
        assert tools_config._toolset_needs_configuration_prompt("tts", {}) is True


class TestConfigWriting:
    def test_picking_tts_plugin_provider_writes_config(self, monkeypatch, tmp_path):
        """When a user picks a plugin-backed TTS provider with no env vars,
        ``_configure_provider`` should write ``tts.provider: <name>``."""
        from hermes_cli import tools_config

        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        tts_registry.register_provider(_FakeTtsProvider("volctest", schema={
            "name": "VolcTest",
            "badge": "free",
            "tag": "",
            "env_vars": [],
        }))

        config: dict = {}
        provider_row = {
            "name": "VolcTest",
            "env_vars": [],
            "tts_plugin_name": "volctest",
        }
        tools_config._configure_provider(provider_row, config)

        assert config["tts"]["provider"] == "volctest"

    def test_is_provider_active_for_tts_plugin(self, monkeypatch):
        from hermes_cli import tools_config

        config = {"tts": {"provider": "volctest"}}
        plugin_row = {
            "name": "VolcTest",
            "tts_plugin_name": "volctest",
        }
        other_row = {
            "name": "Other",
            "tts_plugin_name": "other-tts",
        }

        assert tools_config._is_provider_active(plugin_row, config) is True
        assert tools_config._is_provider_active(other_row, config) is False

    def test_picking_tts_plugin_with_env_vars(self, monkeypatch, tmp_path):
        """Plugin with env_vars: after entering keys, tts.provider is set."""
        from hermes_cli import tools_config

        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        tts_registry.register_provider(_FakeTtsProvider("envplugin", schema={
            "name": "EnvPlugin",
            "badge": "",
            "tag": "",
            "env_vars": [{"key": "ENVPLUGIN_KEY", "prompt": "API key"}],
        }))

        # Simulate key already present
        monkeypatch.setattr(
            tools_config,
            "get_env_value",
            lambda key: "sk-test" if key == "ENVPLUGIN_KEY" else "",
        )

        config: dict = {}
        provider_row = {
            "name": "EnvPlugin",
            "env_vars": [{"key": "ENVPLUGIN_KEY", "prompt": "API key"}],
            "tts_plugin_name": "envplugin",
        }
        tools_config._configure_provider(provider_row, config)

        assert config["tts"]["provider"] == "envplugin"
