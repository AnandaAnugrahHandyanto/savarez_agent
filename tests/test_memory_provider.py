"""Tests for the MemoryProvider interface and registry."""

import pytest
from memory_provider import MemoryProvider, MemoryProviderRegistry, inject_provider_context


# ── Test helpers ──

class StubProvider(MemoryProvider):
    """Minimal provider for testing."""

    def __init__(self, name="stub", available=True, session_ctx=None, turn_ctx=None):
        self._name = name
        self._available = available
        self._session_ctx = session_ctx
        self._turn_ctx = turn_ctx
        self.session_started = False
        self.session_ended = False
        self.last_session_id = None
        self.last_label = None
        self.last_end_summary = None
        self.last_end_transcript = None

    @property
    def name(self) -> str:
        return self._name

    def is_available(self) -> bool:
        return self._available

    def on_session_start(self, session_id, label=""):
        self.session_started = True
        self.last_session_id = session_id
        self.last_label = label

    def get_session_context(self):
        return self._session_ctx

    def get_turn_context(self, user_message):
        return self._turn_ctx

    def on_session_end(self, summary="", transcript=None, session_title=None):
        self.session_ended = True
        self.last_end_summary = summary
        self.last_end_transcript = transcript


class FailingProvider(MemoryProvider):
    """Provider that raises on every method call."""

    @property
    def name(self):
        return "failing"

    def is_available(self):
        return True

    def on_session_start(self, session_id, label=""):
        raise RuntimeError("boom on start")

    def get_session_context(self):
        raise RuntimeError("boom on session context")

    def get_turn_context(self, user_message):
        raise RuntimeError("boom on turn context")

    def on_session_end(self, summary="", transcript=None, session_title=None):
        raise RuntimeError("boom on end")


# ── MemoryProvider ABC tests ──

class TestMemoryProviderABC:

    def test_cannot_instantiate_without_name_and_is_available(self):
        with pytest.raises(TypeError):
            MemoryProvider()

    def test_default_methods_return_none_or_pass(self):
        p = StubProvider(session_ctx=None, turn_ctx=None)
        assert p.get_session_context() is None
        assert p.get_turn_context("hello") is None
        # These should not raise
        p.on_session_start("sess-1")
        p.on_session_end()


# ── MemoryProviderRegistry tests ──

class TestRegistryRegister:

    def test_registers_available_provider(self):
        reg = MemoryProviderRegistry()
        p = StubProvider(available=True)
        assert reg.register(p) is True
        assert p in reg.active_providers

    def test_skips_unavailable_provider(self):
        reg = MemoryProviderRegistry()
        p = StubProvider(available=False)
        assert reg.register(p) is False
        assert p not in reg.active_providers

    def test_has_providers_property(self):
        reg = MemoryProviderRegistry()
        assert reg.has_providers is False
        reg.register(StubProvider(available=True))
        assert reg.has_providers is True

    def test_registration_order_preserved(self):
        reg = MemoryProviderRegistry()
        p1 = StubProvider(name="first", available=True)
        p2 = StubProvider(name="second", available=True)
        reg.register(p1)
        reg.register(p2)
        assert [p.name for p in reg.active_providers] == ["first", "second"]

    def test_register_catches_availability_check_exception(self):
        class BrokenAvailability(StubProvider):
            def is_available(self):
                raise RuntimeError("broken")

        reg = MemoryProviderRegistry()
        assert reg.register(BrokenAvailability()) is False


class TestRegistrySessionStart:

    def test_calls_all_providers(self):
        reg = MemoryProviderRegistry()
        p1 = StubProvider(name="a", available=True)
        p2 = StubProvider(name="b", available=True)
        reg.register(p1)
        reg.register(p2)
        reg.on_session_start("sess-123", label="test")
        assert p1.session_started
        assert p1.last_session_id == "sess-123"
        assert p1.last_label == "test"
        assert p2.session_started

    def test_continues_after_provider_failure(self):
        reg = MemoryProviderRegistry()
        reg.register(FailingProvider())
        p2 = StubProvider(name="good", available=True)
        reg.register(p2)
        reg.on_session_start("sess-1")
        assert p2.session_started  # second provider still called


class TestRegistryGetSessionContext:

    def test_concatenates_context_from_multiple_providers(self):
        reg = MemoryProviderRegistry()
        reg.register(StubProvider(name="a", available=True, session_ctx="Goals: X"))
        reg.register(StubProvider(name="b", available=True, session_ctx="Policies: Y"))
        result = reg.get_session_context()
        assert "Goals: X" in result
        assert "Policies: Y" in result

    def test_skips_empty_context(self):
        reg = MemoryProviderRegistry()
        reg.register(StubProvider(name="a", available=True, session_ctx=""))
        reg.register(StubProvider(name="b", available=True, session_ctx="Real context"))
        result = reg.get_session_context()
        assert result == "Real context"

    def test_returns_empty_when_no_providers(self):
        reg = MemoryProviderRegistry()
        assert reg.get_session_context() == ""

    def test_continues_after_provider_failure(self):
        reg = MemoryProviderRegistry()
        reg.register(FailingProvider())
        reg.register(StubProvider(name="good", available=True, session_ctx="OK"))
        assert reg.get_session_context() == "OK"


class TestRegistryGetTurnContext:

    def test_concatenates_turn_context(self):
        reg = MemoryProviderRegistry()
        reg.register(StubProvider(name="a", available=True, turn_ctx="Chunk 1"))
        reg.register(StubProvider(name="b", available=True, turn_ctx="Chunk 2"))
        result = reg.get_turn_context("hello")
        assert "Chunk 1" in result
        assert "Chunk 2" in result

    def test_returns_empty_when_no_context(self):
        reg = MemoryProviderRegistry()
        reg.register(StubProvider(name="a", available=True, turn_ctx=None))
        assert reg.get_turn_context("hello") == ""

    def test_continues_after_provider_failure(self):
        reg = MemoryProviderRegistry()
        reg.register(FailingProvider())
        reg.register(StubProvider(name="good", available=True, turn_ctx="OK"))
        assert reg.get_turn_context("hello") == "OK"


class TestRegistrySessionEnd:

    def test_calls_all_providers(self):
        reg = MemoryProviderRegistry()
        p1 = StubProvider(name="a", available=True)
        p2 = StubProvider(name="b", available=True)
        reg.register(p1)
        reg.register(p2)
        reg.on_session_end(summary="done", transcript=[{"role": "user", "content": "hi"}])
        assert p1.session_ended
        assert p1.last_end_summary == "done"
        assert p2.session_ended

    def test_continues_after_provider_failure(self):
        reg = MemoryProviderRegistry()
        reg.register(FailingProvider())
        p2 = StubProvider(name="good", available=True)
        reg.register(p2)
        reg.on_session_end(summary="test")
        assert p2.session_ended


# ── inject_provider_context tests ──

class TestInjectProviderContext:

    def test_string_content(self):
        result = inject_provider_context("Hello", "Context")
        assert result == "Hello\n\nContext"

    def test_list_content(self):
        content = [{"type": "text", "text": "Hello"}]
        result = inject_provider_context(content, "Context")
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[-1] == {"type": "text", "text": "Context"}

    def test_none_content(self):
        result = inject_provider_context(None, "Context")
        assert result == "Context"

    def test_empty_string_content(self):
        result = inject_provider_context("", "Context")
        assert result == "Context"

    def test_whitespace_only_content(self):
        result = inject_provider_context("   ", "Context")
        assert result == "Context"

    def test_empty_context_returns_original(self):
        assert inject_provider_context("Hello", "") == "Hello"

    def test_none_context_returns_original(self):
        assert inject_provider_context("Hello", None) == "Hello"

    def test_does_not_mutate_original_list(self):
        original = [{"type": "text", "text": "Hello"}]
        inject_provider_context(original, "Context")
        assert len(original) == 1  # original unchanged
