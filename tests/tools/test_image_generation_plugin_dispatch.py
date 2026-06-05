from __future__ import annotations

import json
import pytest

from agent import image_gen_registry
from agent.image_gen_provider import ImageGenProvider


@pytest.fixture(autouse=True)
def _reset_registry():
    image_gen_registry._reset_for_tests()
    yield
    image_gen_registry._reset_for_tests()


class _FakeCodexProvider(ImageGenProvider):
    def __init__(self):
        self.calls = []

    @property
    def name(self) -> str:
        return "codex"

    def generate(self, prompt, aspect_ratio="landscape", **kwargs):
        self.calls.append({"prompt": prompt, "aspect_ratio": aspect_ratio, **kwargs})
        return {
            "success": True,
            "image": "/tmp/codex-test.png",
            "model": kwargs.get("model", "gpt-5.2-codex"),
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "provider": "codex",
            "hints": {k: v for k, v in kwargs.items() if k != "model"},
        }


class TestPluginDispatch:
    def test_dispatch_routes_to_codex_provider(self, monkeypatch, tmp_path):
        from tools import image_generation_tool
        from agent import image_gen_registry as registry_module
        from hermes_cli import plugins as plugins_module

        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        (tmp_path / "config.yaml").write_text("image_gen:\n  provider: codex\n")
        image_gen_registry.register_provider(_FakeCodexProvider())

        monkeypatch.setattr(image_generation_tool, "_read_configured_image_provider", lambda: "codex")
        monkeypatch.setattr(plugins_module, "_ensure_plugins_discovered", lambda: None)
        fake_provider = _FakeCodexProvider()
        monkeypatch.setattr(registry_module, "get_provider", lambda name: fake_provider if name == "codex" else None)

        dispatched = image_generation_tool._dispatch_to_plugin_provider("draw cat", "square")
        payload = json.loads(dispatched)

        assert payload["success"] is True
        assert payload["provider"] == "codex"
        assert payload["image"] == "/tmp/codex-test.png"
        assert payload["aspect_ratio"] == "square"
        assert fake_provider.calls == [{"prompt": "draw cat", "aspect_ratio": "square"}]

    def test_dispatch_prefers_tool_model_over_configured_model_and_forwards_hints(self, monkeypatch, tmp_path):
        from tools import image_generation_tool
        from agent import image_gen_registry as registry_module
        from hermes_cli import plugins as plugins_module

        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        (tmp_path / "config.yaml").write_text("image_gen:\n  provider: codex\n  model: configured-model\n")

        fake_provider = _FakeCodexProvider()
        monkeypatch.setattr(image_generation_tool, "_read_configured_image_provider", lambda: "codex")
        monkeypatch.setattr(image_generation_tool, "_read_configured_image_model", lambda: "configured-model")
        monkeypatch.setattr(plugins_module, "_ensure_plugins_discovered", lambda: None)
        monkeypatch.setattr(registry_module, "get_provider", lambda name: fake_provider if name == "codex" else None)

        dispatched = image_generation_tool._dispatch_to_plugin_provider(
            "draw cat",
            "square",
            model="tool-model",
            intent="poster",
            quality="high",
            style="photorealistic",
            text_heavy=True,
        )
        payload = json.loads(dispatched)

        assert payload["success"] is True
        assert payload["model"] == "tool-model"
        assert fake_provider.calls == [
            {
                "prompt": "draw cat",
                "aspect_ratio": "square",
                "model": "tool-model",
                "intent": "poster",
                "quality": "high",
                "style": "photorealistic",
                "text_heavy": True,
            }
        ]

    def test_handle_image_generate_forwards_optional_routing_args(self, monkeypatch):
        from tools import image_generation_tool

        calls = []

        def fake_dispatch(prompt, aspect_ratio, **kwargs):
            calls.append({"prompt": prompt, "aspect_ratio": aspect_ratio, **kwargs})
            return json.dumps({"success": True, "image": "fake://image"})

        monkeypatch.setattr(image_generation_tool, "_dispatch_to_plugin_provider", fake_dispatch)

        result = image_generation_tool._handle_image_generate({
            "prompt": "draw poster",
            "aspect_ratio": "portrait",
            "model": "nano-banana-pro",
            "intent": "poster",
            "quality": "high",
            "style": "flat vector",
            "text_heavy": True,
        })
        payload = json.loads(result)

        assert payload["success"] is True
        assert calls == [
            {
                "prompt": "draw poster",
                "aspect_ratio": "portrait",
                "model": "nano-banana-pro",
                "intent": "poster",
                "quality": "high",
                "style": "flat vector",
                "text_heavy": True,
            }
        ]

    def test_dispatch_reports_missing_registered_provider(self, monkeypatch, tmp_path):
        from tools import image_generation_tool
        from hermes_cli import plugins as plugins_module

        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        (tmp_path / "config.yaml").write_text("image_gen:\n  provider: missing-codex\n")

        monkeypatch.setattr(image_generation_tool, "_read_configured_image_provider", lambda: "missing-codex")
        monkeypatch.setattr(plugins_module, "_ensure_plugins_discovered", lambda: None)

        dispatched = image_generation_tool._dispatch_to_plugin_provider("draw cat", "landscape")
        payload = json.loads(dispatched)

        assert payload["success"] is False
        assert payload["error_type"] == "provider_not_registered"
        assert "image_gen.provider='missing-codex'" in payload["error"]

    def test_router_dispatch_ignores_stale_top_level_configured_model(self, monkeypatch, tmp_path):
        from tools import image_generation_tool
        from agent import image_gen_registry as registry_module
        from hermes_cli import plugins as plugins_module

        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        (tmp_path / "config.yaml").write_text(
            "image_gen:\n  provider: router\n  model: stale-fal-model\n"
        )

        fake_provider = _FakeCodexProvider()
        monkeypatch.setattr(image_generation_tool, "_read_configured_image_provider", lambda: "router")
        monkeypatch.setattr(image_generation_tool, "_read_configured_image_model", lambda: "stale-fal-model")
        monkeypatch.setattr(plugins_module, "_ensure_plugins_discovered", lambda force=False: None)
        monkeypatch.setattr(registry_module, "get_provider", lambda name: fake_provider if name == "router" else None)

        dispatched = image_generation_tool._dispatch_to_plugin_provider("draw cat", "landscape")
        payload = json.loads(dispatched)

        assert payload["success"] is True
        assert fake_provider.calls == [{"prompt": "draw cat", "aspect_ratio": "landscape"}]

    def test_dispatch_force_refreshes_plugins_when_provider_initially_missing(self, monkeypatch, tmp_path):
        from tools import image_generation_tool
        from hermes_cli import plugins as plugins_module
        from agent import image_gen_registry as registry_module

        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        (tmp_path / "config.yaml").write_text("image_gen:\n  provider: codex\n")

        monkeypatch.setattr(image_generation_tool, "_read_configured_image_provider", lambda: "codex")

        calls = []
        provider_state = {"provider": None}

        def fake_ensure_plugins_discovered(force=False):
            calls.append(force)
            if force:
                provider_state["provider"] = _FakeCodexProvider()

        monkeypatch.setattr(plugins_module, "_ensure_plugins_discovered", fake_ensure_plugins_discovered)
        monkeypatch.setattr(registry_module, "get_provider", lambda name: provider_state["provider"])

        dispatched = image_generation_tool._dispatch_to_plugin_provider("draw hammy", "portrait")
        payload = json.loads(dispatched)

        assert calls == [False, True]
        assert payload["success"] is True
        assert payload["provider"] == "codex"
        assert payload["aspect_ratio"] == "portrait"
