from __future__ import annotations

import json

from agent import image_gen_registry
from agent.image_gen_provider import ImageGenProvider


class _FakeEditProvider(ImageGenProvider):
    @property
    def name(self) -> str:
        return "codex"

    def generate(self, prompt, aspect_ratio="landscape", **kwargs):
        raise AssertionError("generate should not be called by image_edit")

    def supports_edit(self) -> bool:
        return True

    def is_available(self) -> bool:
        return True

    def edit(self, prompt, image, aspect_ratio="landscape", **kwargs):
        return {
            "success": True,
            "image": "/tmp/edit.png",
            "model": "gpt-image-2-medium",
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "provider": "codex",
            "source_image": image,
        }


class _NoEditProvider(ImageGenProvider):
    @property
    def name(self) -> str:
        return "noedit"

    def generate(self, prompt, aspect_ratio="landscape", **kwargs):
        return {}


def setup_function():
    image_gen_registry._reset_for_tests()


def teardown_function():
    image_gen_registry._reset_for_tests()


def test_image_edit_schema_requires_prompt_and_image():
    from tools.image_edit_tool import IMAGE_EDIT_SCHEMA

    assert IMAGE_EDIT_SCHEMA["name"] == "image_edit"
    assert IMAGE_EDIT_SCHEMA["parameters"]["required"] == ["prompt", "image"]
    assert "aspect_ratio" in IMAGE_EDIT_SCHEMA["parameters"]["properties"]


def test_dispatch_routes_to_edit_provider(monkeypatch):
    from tools import image_edit_tool
    from agent import image_gen_registry as registry_module
    from hermes_cli import plugins as plugins_module

    monkeypatch.setattr(image_edit_tool, "_read_configured_image_provider", lambda: "codex")
    monkeypatch.setattr(plugins_module, "_ensure_plugins_discovered", lambda force=False: None)
    monkeypatch.setattr(registry_module, "get_provider", lambda name: _FakeEditProvider() if name == "codex" else None)

    payload = json.loads(image_edit_tool._dispatch_to_plugin_provider("make it blue", "/tmp/source.png", "square"))

    assert payload["success"] is True
    assert payload["provider"] == "codex"
    assert payload["image"] == "/tmp/edit.png"
    assert payload["source_image"] == "/tmp/source.png"
    assert payload["aspect_ratio"] == "square"


def test_dispatch_reports_provider_without_edit(monkeypatch):
    from tools import image_edit_tool
    from agent import image_gen_registry as registry_module
    from hermes_cli import plugins as plugins_module

    monkeypatch.setattr(image_edit_tool, "_read_configured_image_provider", lambda: "noedit")
    monkeypatch.setattr(plugins_module, "_ensure_plugins_discovered", lambda force=False: None)
    monkeypatch.setattr(registry_module, "get_provider", lambda name: _NoEditProvider() if name == "noedit" else None)

    payload = json.loads(image_edit_tool._dispatch_to_plugin_provider("make it blue", "/tmp/source.png", "square"))

    assert payload["success"] is False
    assert payload["error_type"] == "unsupported"


def test_image_gen_toolset_includes_image_edit():
    from toolsets import resolve_toolset

    tools = resolve_toolset("image_gen")
    assert "image_generate" in tools
    assert "image_edit" in tools
