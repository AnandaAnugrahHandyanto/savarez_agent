"""Tests for current-turn external memory recall support."""

from agent.memory_manager import MemoryManager
from agent.memory_provider import MemoryProvider


class RecallNowProvider(MemoryProvider):
    def __init__(self, name="recall", result="", fail=False):
        self._name = name
        self.result = result
        self.fail = fail
        self.calls = []

    @property
    def name(self):
        return self._name

    def is_available(self):
        return True

    def initialize(self, session_id, **kwargs):
        pass

    def get_tool_schemas(self):
        return []

    def recall_now(self, query, *, session_id="", max_tokens=None):
        self.calls.append((query, session_id, max_tokens))
        if self.fail:
            raise RuntimeError("boom")
        return self.result


def test_memory_provider_default_recall_now_is_empty():
    provider = RecallNowProvider(result="ignored")
    # Call through the base implementation explicitly to prove the optional
    # hook defaults to a safe no-op for providers that do not override it.
    assert MemoryProvider.recall_now(provider, "hello") == ""


def test_memory_manager_recall_now_all_merges_provider_results():
    mgr = MemoryManager()
    first = RecallNowProvider("builtin", result="First memory")
    second = RecallNowProvider("external", result="Second memory")
    mgr.add_provider(first)
    mgr.add_provider(second)

    result = mgr.recall_now_all("what did we decide?", session_id="s1", max_tokens=321)

    assert "First memory" in result
    assert "Second memory" in result
    assert first.calls == [("what did we decide?", "s1", 321)]
    assert second.calls == [("what did we decide?", "s1", 321)]


def test_memory_manager_recall_now_all_skips_empty_and_failure():
    mgr = MemoryManager()
    failing = RecallNowProvider("builtin", fail=True)
    empty = RecallNowProvider("external", result="")
    mgr.add_provider(failing)
    mgr.add_provider(empty)

    assert mgr.recall_now_all("query") == ""
