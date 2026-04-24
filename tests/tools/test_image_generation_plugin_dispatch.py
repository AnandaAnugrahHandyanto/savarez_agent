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
    @property
    def name(self) -> str:
        return "codex"

    def generate(self, prompt, aspect_ratio="landscape", **kwargs):
        return {
            "success": True,
            "image": "/tmp/codex-test.png",
            "model": "gpt-5.2-codex",
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "provider": "codex",
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
        monkeypatch.setattr(registry_module, "get_provider", lambda name: _FakeCodexProvider() if name == "codex" else None)

        dispatched = image_generation_tool._dispatch_to_plugin_provider("draw cat", "square")
        payload = json.loads(dispatched)

        assert payload["success"] is True
        assert payload["provider"] == "codex"
        assert payload["image"] == "/tmp/codex-test.png"
        assert payload["aspect_ratio"] == "square"

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


class _FakeReferenceCapableProvider(ImageGenProvider):
    """Provider that opts in to references — records what the dispatcher forwards."""

    def __init__(self):
        self.last_call: dict = {}

    @property
    def name(self) -> str:
        return "ref-capable"

    @property
    def supports_references(self) -> bool:
        return True

    def generate(self, prompt, aspect_ratio="landscape", **kwargs):
        self.last_call = {
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "references": kwargs.get("references"),
        }
        return {
            "success": True,
            "image": "/tmp/ref.png",
            "model": "ref-model",
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "provider": "ref-capable",
            "references": len(kwargs.get("references") or []),
        }


class TestReferencesDispatch:
    def test_references_forwarded_to_capable_provider(self, monkeypatch, tmp_path):
        from tools import image_generation_tool
        from hermes_cli import plugins as plugins_module
        from agent import image_gen_registry as registry_module

        prov = _FakeReferenceCapableProvider()

        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        monkeypatch.setattr(image_generation_tool, "_read_configured_image_provider", lambda: "ref-capable")
        monkeypatch.setattr(plugins_module, "_ensure_plugins_discovered", lambda force=False: None)
        monkeypatch.setattr(registry_module, "get_provider", lambda name: prov)

        dispatched = image_generation_tool._dispatch_to_plugin_provider(
            "merge these",
            "square",
            references=["/path/a.png", "/path/b.png"],
        )
        payload = json.loads(dispatched)

        assert payload["success"] is True
        assert prov.last_call["references"] == ["/path/a.png", "/path/b.png"]

    def test_references_rejected_for_non_capable_provider(self, monkeypatch, tmp_path):
        from tools import image_generation_tool
        from hermes_cli import plugins as plugins_module
        from agent import image_gen_registry as registry_module

        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        monkeypatch.setattr(image_generation_tool, "_read_configured_image_provider", lambda: "codex")
        monkeypatch.setattr(plugins_module, "_ensure_plugins_discovered", lambda force=False: None)
        monkeypatch.setattr(registry_module, "get_provider", lambda name: _FakeCodexProvider())

        dispatched = image_generation_tool._dispatch_to_plugin_provider(
            "merge these",
            "square",
            references=["/path/a.png"],
        )
        payload = json.loads(dispatched)

        assert payload["success"] is False
        assert payload["error_type"] == "references_unsupported"

    def test_references_rejected_for_fal_fallback(self, monkeypatch, tmp_path):
        # FAL is the in-tree default; the dispatcher short-circuits to None
        # for it, but references must still be rejected so the caller gets
        # an actionable error instead of a silently dropped kwarg.
        from tools import image_generation_tool

        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        monkeypatch.setattr(image_generation_tool, "_read_configured_image_provider", lambda: "fal")

        dispatched = image_generation_tool._dispatch_to_plugin_provider(
            "merge these",
            "square",
            references=["/path/a.png"],
        )
        payload = json.loads(dispatched)

        assert payload["success"] is False
        assert payload["error_type"] == "references_unsupported"

    def test_no_references_still_falls_through_to_fal(self, monkeypatch, tmp_path):
        from tools import image_generation_tool

        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        monkeypatch.setattr(image_generation_tool, "_read_configured_image_provider", lambda: "fal")

        # No references → original fall-through behaviour preserved.
        dispatched = image_generation_tool._dispatch_to_plugin_provider(
            "just a cat", "square"
        )
        assert dispatched is None
