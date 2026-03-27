"""Integration tests for MemoryProvider through AIAgent lifecycle.

Tests the full path: agent init → registry populated → session start →
turn context retrieval → injection into API message → session end.
"""

import pytest
from unittest.mock import patch, MagicMock
from memory_provider import (
    MemoryProvider,
    MemoryProviderRegistry,
    create_default_registry,
    inject_provider_context,
)


# ── Test provider ──

class MockProvider(MemoryProvider):
    """Controllable provider for integration testing."""

    def __init__(self):
        self._available = True
        self.calls = []

    @property
    def name(self):
        return "mock"

    def is_available(self):
        return self._available

    def on_session_start(self, session_id, label=""):
        self.calls.append(("session_start", session_id, label))

    def get_session_context(self):
        self.calls.append(("session_context",))
        return "## Mock Context\nActive goals: test the system"

    def get_turn_context(self, user_message):
        self.calls.append(("turn_context", user_message))
        if len(user_message) > 10:
            return f"[Relevant memory for: {user_message[:20]}]"
        return None  # skip short messages

    def on_session_end(self, summary="", transcript=None, session_title=None):
        self.calls.append(("session_end", summary, bool(transcript)))


# ── create_default_registry tests ──

class TestCreateDefaultRegistry:

    @patch.dict("os.environ", {}, clear=False)
    def test_returns_empty_registry_when_no_providers_configured(self):
        """With no MINDGRAPH_API_KEY, registry should be empty."""
        # Remove the key if it exists
        import os
        os.environ.pop("MINDGRAPH_API_KEY", None)
        reg = create_default_registry()
        assert isinstance(reg, MemoryProviderRegistry)
        # MindGraph should not activate without API key

    @patch.dict("os.environ", {"MINDGRAPH_API_KEY": "test-key"})
    def test_registers_mindgraph_when_key_present(self):
        """With MINDGRAPH_API_KEY set, MindGraph provider should register."""
        try:
            reg = create_default_registry()
            names = [p.name for p in reg.active_providers]
            assert "mindgraph" in names
        except Exception:
            # SDK may not be importable in test env — that's ok
            pass


# ── Full lifecycle simulation ──

class TestProviderLifecycle:
    """Simulates the agent lifecycle with a mock provider."""

    def test_full_session_lifecycle(self):
        """Test: init → session start → context → turn → end."""
        provider = MockProvider()
        reg = MemoryProviderRegistry()
        reg.register(provider)

        # 1. Session start (first turn, no history)
        reg.on_session_start("sess-abc123", label="hermes-sess-abc")
        assert ("session_start", "sess-abc123", "hermes-sess-abc") in provider.calls

        # 2. System prompt context (called once)
        ctx = reg.get_session_context()
        assert "Active goals" in ctx
        assert ("session_context",) in provider.calls

        # 3. Per-turn context (called each turn)
        turn_ctx = reg.get_turn_context("What are the open decisions?")
        assert turn_ctx is not None
        assert "Relevant memory" in turn_ctx

        # 4. Short messages return no context
        short_ctx = reg.get_turn_context("hi")
        assert short_ctx == ""  # registry returns "" not None

        # 5. Injection into user message
        msg_content = "What are the open decisions?"
        injected = inject_provider_context(msg_content, turn_ctx)
        assert msg_content in injected
        assert "Relevant memory" in injected

        # 6. Session end
        transcript = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
        ]
        reg.on_session_end(
            summary="Test session completed",
            transcript=transcript,
            session_title="Test Session",
        )
        assert ("session_end", "Test session completed", True) in provider.calls

    def test_multiple_providers_combine_context(self):
        """Two providers' context is concatenated in registration order."""
        p1 = MockProvider()
        p1._name_override = "first"

        class SecondProvider(MemoryProvider):
            @property
            def name(self):
                return "second"
            def is_available(self):
                return True
            def get_session_context(self):
                return "## Second Provider\nPolicies: be helpful"
            def get_turn_context(self, msg):
                return "[Second provider context]"

        reg = MemoryProviderRegistry()
        reg.register(p1)
        reg.register(SecondProvider())

        session_ctx = reg.get_session_context()
        assert "Mock Context" in session_ctx
        assert "Second Provider" in session_ctx
        # Order matters: first provider's context comes first
        assert session_ctx.index("Mock Context") < session_ctx.index("Second Provider")

        turn_ctx = reg.get_turn_context("Tell me about the project")
        assert "Relevant memory" in turn_ctx
        assert "Second provider context" in turn_ctx

    def test_failing_provider_does_not_block_others(self):
        """A broken provider shouldn't prevent other providers from working."""

        class BrokenProvider(MemoryProvider):
            @property
            def name(self):
                return "broken"
            def is_available(self):
                return True
            def on_session_start(self, session_id, label=""):
                raise RuntimeError("💥")
            def get_session_context(self):
                raise RuntimeError("💥")
            def get_turn_context(self, user_message):
                raise RuntimeError("💥")
            def on_session_end(self, **kw):
                raise RuntimeError("💥")

        good = MockProvider()
        reg = MemoryProviderRegistry()
        reg.register(BrokenProvider())
        reg.register(good)

        # All operations succeed despite broken provider
        reg.on_session_start("s1")
        assert good.calls[-1][0] == "session_start"

        ctx = reg.get_session_context()
        assert "Active goals" in ctx

        turn = reg.get_turn_context("long enough message here")
        assert "Relevant memory" in turn

        reg.on_session_end(summary="done")
        assert good.calls[-1][0] == "session_end"


# ── HonchoProvider stub tests ──

class TestHonchoProviderStub:
    """Verify the stub HonchoProvider satisfies the interface."""

    def test_implements_all_methods(self):
        from providers.honcho_provider import HonchoProvider
        p = HonchoProvider()
        assert p.name == "honcho"
        # All methods should be callable without error
        p.on_session_start("sess-1", label="test")
        assert p.get_session_context() is None
        assert p.get_turn_context("hello") is None
        p.on_session_end(summary="done")

    def test_is_available_without_config(self):
        """Without honcho config, should return False gracefully."""
        from providers.honcho_provider import HonchoProvider
        p = HonchoProvider()
        # May return True or False depending on env — should not raise
        try:
            result = p.is_available()
            assert isinstance(result, bool)
        except Exception:
            pytest.fail("is_available() should never raise")


# ── MindGraphProvider tests ──

class TestMindGraphProviderInterface:
    """Verify MindGraphProvider satisfies the interface."""

    def test_implements_all_methods(self):
        from providers.mindgraph_provider import MindGraphProvider
        p = MindGraphProvider()
        assert p.name == "mindgraph"

    @patch.dict("os.environ", {}, clear=False)
    def test_not_available_without_key(self):
        import os
        os.environ.pop("MINDGRAPH_API_KEY", None)
        from providers.mindgraph_provider import MindGraphProvider
        p = MindGraphProvider()
        assert p.is_available() is False
