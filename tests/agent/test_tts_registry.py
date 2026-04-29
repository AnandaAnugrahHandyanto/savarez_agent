"""Tests for agent/tts_registry.py — provider registration & active lookup.

Mirrors tests/agent/test_image_gen_registry.py.  The TTS registry has a
deliberately different ``get_active_provider`` fallback (returns None when
``tts.provider`` is unset, so legacy Edge default wins) — that divergence is
covered here.
"""

from __future__ import annotations

import pytest


class _FakeProvider:
    """Minimal TtsProvider-shaped object used by registry tests."""

    def __init__(self, name: str, available: bool = True):
        self._name = name
        self._available = available

    @property
    def name(self) -> str:
        return self._name

    def is_available(self) -> bool:
        return self._available

    def synthesize(self, text, output_path, config):
        return {
            "success": True,
            "file_path": output_path,
            "format": "mp3",
            "native_opus": False,
            "voice_compatible": False,
        }


def _make(name: str, available: bool = True):
    """Build a _FakeProvider and register it as a TtsProvider subclass.

    We inherit at runtime so isinstance(_FakeProvider, TtsProvider) works
    without making _FakeProvider a top-level TtsProvider subclass (which
    would require implementing the abstract methods up-front).
    """
    from agent.tts_provider import TtsProvider

    class _Concrete(TtsProvider):
        @property
        def name(self) -> str:
            return name

        def is_available(self) -> bool:
            return available

        def synthesize(self, text, output_path, config):
            return {
                "success": True,
                "file_path": output_path,
                "format": "mp3",
                "native_opus": False,
                "voice_compatible": False,
            }

    return _Concrete()


@pytest.fixture(autouse=True)
def _reset_registry():
    from agent import tts_registry

    tts_registry._reset_for_tests()
    yield
    tts_registry._reset_for_tests()


class TestRegisterProvider:
    def test_register_and_lookup(self):
        from agent import tts_registry

        provider = _make("fake")
        tts_registry.register_provider(provider)
        assert tts_registry.get_provider("fake") is provider

    def test_rejects_non_provider(self):
        from agent import tts_registry

        with pytest.raises(TypeError):
            tts_registry.register_provider("not a provider")  # type: ignore[arg-type]

    def test_rejects_empty_name(self):
        from agent import tts_registry
        from agent.tts_provider import TtsProvider

        class Empty(TtsProvider):
            @property
            def name(self) -> str:
                return ""

            def synthesize(self, text, output_path, config):
                return {}

        with pytest.raises(ValueError):
            tts_registry.register_provider(Empty())

    def test_reregister_overwrites(self):
        from agent import tts_registry

        a = _make("same")
        b = _make("same")
        tts_registry.register_provider(a)
        tts_registry.register_provider(b)
        assert tts_registry.get_provider("same") is b

    def test_list_is_sorted(self):
        from agent import tts_registry

        tts_registry.register_provider(_make("zeta"))
        tts_registry.register_provider(_make("alpha"))
        names = [p.name for p in tts_registry.list_providers()]
        assert names == ["alpha", "zeta"]


class TestGetActiveProvider:
    def test_unset_returns_none_preserves_legacy(self, tmp_path, monkeypatch):
        """KEY DIVERGENCE from image_gen registry: TTS returns None when
        ``tts.provider`` is unset so that ``text_to_speech`` falls through
        to the legacy Edge default.  image_gen auto-selects the single
        registered provider; we explicitly do NOT.
        """
        from agent import tts_registry

        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        tts_registry.register_provider(_make("solo"))
        assert tts_registry.get_active_provider() is None

    def test_explicit_config_wins(self, tmp_path, monkeypatch):
        import yaml
        from agent import tts_registry

        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        (tmp_path / "config.yaml").write_text(
            yaml.safe_dump({"tts": {"provider": "volcengine"}})
        )
        tts_registry.register_provider(_make("edge"))
        tts_registry.register_provider(_make("volcengine"))
        active = tts_registry.get_active_provider()
        assert active is not None and active.name == "volcengine"

    def test_missing_configured_returns_none(self, tmp_path, monkeypatch):
        """Configured name not registered → None (dispatcher surfaces
        the "plugin not registered" error; registry stays simple)."""
        import yaml
        from agent import tts_registry

        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        (tmp_path / "config.yaml").write_text(
            yaml.safe_dump({"tts": {"provider": "unknown-backend"}})
        )
        tts_registry.register_provider(_make("volcengine"))
        assert tts_registry.get_active_provider() is None

    def test_none_when_empty(self, tmp_path, monkeypatch):
        from agent import tts_registry

        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        assert tts_registry.get_active_provider() is None

    def test_config_read_errors_do_not_crash(self, tmp_path, monkeypatch):
        """Malformed config.yaml must not propagate from get_active_provider."""
        from agent import tts_registry

        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        (tmp_path / "config.yaml").write_text("this is: [not: valid yaml")
        tts_registry.register_provider(_make("volcengine"))
        # Should return None rather than raising
        assert tts_registry.get_active_provider() is None
