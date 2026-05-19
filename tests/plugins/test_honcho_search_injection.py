"""Regression tests for Honcho query-scoped search injection."""

from types import SimpleNamespace

from plugins.memory.honcho import HonchoMemoryProvider
from plugins.memory.honcho.session import HonchoSession, HonchoSessionManager


class FakeManager:
    def __init__(self):
        self.search_queries = []

    def get_prefetch_context(self, session_key):
        return {"representation": "old broad representation"}

    def pop_context_result(self, session_key):
        return None

    def search_context(self, session_key, query, max_tokens=800, peer="user"):
        self.search_queries.append((session_key, query, max_tokens, peer))
        return "LAB_TOOL animal = tatu canastra"


class FakeHoncho:
    def __init__(self, messages):
        self.messages = messages
        self.queries = []

    def search(self, query, filters=None, limit=10):
        self.queries.append(query)
        if query == "LAB_TOOL animal":
            return self.messages
        return []


def test_prefetch_injects_query_scoped_honcho_search_results():
    provider = HonchoMemoryProvider()
    manager = FakeManager()
    provider._manager = manager
    provider._session_key = "lab-session"
    provider._recall_mode = "context"
    provider._turn_count = 1
    provider._last_dialectic_turn = 0  # avoid first-turn dialectic thread in this unit test
    provider._dialectic_cadence = 999
    provider._config = SimpleNamespace(context_tokens=None, search_injection_tokens=800)

    result = provider.prefetch("qual é o animal do LAB_TOOL?")

    assert "## Relevant Memory Search Results" in result
    assert "LAB_TOOL animal = tatu canastra" in result
    assert manager.search_queries == [
        ("lab-session", "qual é o animal do LAB_TOOL?", 800, "user")
    ]


def test_search_context_prefers_raw_honcho_search_excerpts_over_peer_context(monkeypatch):
    manager = HonchoSessionManager(honcho=FakeHoncho([
        SimpleNamespace(peer_id="philip_lab", content="LAB_TOOL animal = tatu canastra"),
    ]))
    manager._cache["lab-session"] = HonchoSession(
        key="lab-session",
        user_peer_id="philip_lab",
        assistant_peer_id="honchogatewaylab",
        honcho_session_id="lab-session",
    )

    monkeypatch.setattr(
        manager,
        "_fetch_peer_context",
        lambda *args, **kwargs: {"representation": "old broad representation", "card": []},
    )

    result = manager.search_context("lab-session", "LAB_TOOL animal", max_tokens=50)

    assert "LAB_TOOL animal = tatu canastra" in result
    assert "old broad representation" not in result
